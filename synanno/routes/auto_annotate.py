import logging
import os
from glob import glob

import numpy as np
import torch
from flask import Blueprint, current_app, jsonify, request
from PIL import Image

from synanno.backend.auto_segmentation.config import get_config
from synanno.backend.auto_segmentation.dataset import binarize_tensor, normalize_tensor
from synanno.backend.auto_segmentation.trainer import Trainer
from synanno.backend.auto_segmentation.visualize_instances import visualize_instances
from synanno.backend.processing import apply_transparency

# Define a Blueprint for auto_annotate routes
blueprint = Blueprint("auto_annotate", __name__)

CONFIG = get_config()

logger = logging.getLogger(__name__)


def load_images_and_masks(
    image_folder: str, mask_folder: str, data_id: int
) -> tuple[dict, np.ndarray, np.ndarray]:
    """
    Load images and masks from the specified folders.

    Args:
        image_folder (str): Path to the image folder.
        mask_folder (str): Path to the mask folder.
        data_id (int): ID of the sample.

    Returns:
        tuple[dict, np.ndarray, np.ndarray]: Loaded images and masks as 3D numpy arrays.
    """
    img_sub_folder = os.path.join(image_folder, str(data_id))
    img_paths = glob(img_sub_folder + "/*.png")

    mask_sub_folder = os.path.join(mask_folder, str(data_id))
    curve_masks_path = glob(mask_sub_folder + "/curve_*.png")

    # Sort both images and masks to ensure they are in the same order
    curve_masks_path.sort()
    img_paths.sort()

    map_slice_to_idx = {}
    image_np_list = []

    for i, img_path in enumerate(img_paths):
        img_name = img_path.split("/")[-1]
        slice_number = img_name.split(".")[0]
        map_slice_to_idx[slice_number] = i

        img = Image.open(img_path)
        image_np_list.append(np.array(img))

    img_np_3d = np.stack(image_np_list, axis=0)

    mask_np_3d = np.zeros(
        (
            CONFIG["DATASET_CONFIG"]["resize_depth"],
            CONFIG["DATASET_CONFIG"]["resize_height"],
            CONFIG["DATASET_CONFIG"]["resize_width"],
        )
    )

    for mask_path in curve_masks_path:
        mask_name = mask_path.split("/")[-1]
        slice_number = mask_name.split("_")[4]

        mask = Image.open(mask_path)
        binary_mask = np.array(mask)[:, :, 0] > 0
        mask_np_3d[map_slice_to_idx[slice_number], :, :] = binary_mask

    return map_slice_to_idx, img_np_3d, mask_np_3d


def prepare_sample(img_np_3d: np.ndarray, mask_np_3d: np.ndarray) -> torch.Tensor:
    """
    Prepare the sample tensor from images and masks.

    Args:
        img_np_3d (np.ndarray): 3D numpy array of images.
        mask_np_3d (np.ndarray): 3D numpy array of masks.

    Returns:
        torch.Tensor: Prepared sample tensor.
    """
    # Convert numpy arrays to tensors and add channel dimension
    img_tensor = torch.tensor(img_np_3d, dtype=torch.float32)  # Shape: (D, H, W)
    mask_tensor = torch.tensor(mask_np_3d, dtype=torch.float32)  # Shape: (D, H, W)

    # Add channel dimension
    img_tensor = img_tensor.unsqueeze(0)  # Shape: (1, D, H, W)
    mask_tensor = mask_tensor.unsqueeze(0)  # Shape: (1, D, H, W)

    # Add batch dimension
    img_tensor = img_tensor.unsqueeze(0)  # Shape: (1, 1, D, H, W)
    mask_tensor = mask_tensor.unsqueeze(0)  # Shape: (1, 1, D, H, W)

    img_tensor = torch.nn.functional.interpolate(
        img_tensor,
        size=(
            CONFIG["DATASET_CONFIG"]["resize_depth"],
            CONFIG["DATASET_CONFIG"]["resize_height"],
            CONFIG["DATASET_CONFIG"]["resize_width"],
        ),
        mode="trilinear",
        align_corners=False,
    )
    mask_tensor = torch.nn.functional.interpolate(
        mask_tensor,
        size=(
            CONFIG["DATASET_CONFIG"]["resize_depth"],
            CONFIG["DATASET_CONFIG"]["resize_height"],
            CONFIG["DATASET_CONFIG"]["resize_width"],
        ),
        mode="nearest",
    )

    # Normalize the image channel
    img_tensor = normalize_tensor(img_tensor)
    mask_tensor = binarize_tensor(mask_tensor)

    assert (torch.max(img_tensor) <= 1.0) and (torch.min(img_tensor) >= 0.0)
    assert (torch.max(mask_tensor) <= 1.0) and (torch.min(mask_tensor) >= 0.0)

    # Stack image and mask tensors
    sample = torch.cat([img_tensor, mask_tensor], dim=1)  # Shape: (1, 2, D, H, W)

    assert sample.shape == (
        1,
        2,
        CONFIG["DATASET_CONFIG"]["resize_depth"],
        CONFIG["DATASET_CONFIG"]["resize_height"],
        CONFIG["DATASET_CONFIG"]["resize_width"],
    ), f"The shape is incorrect: {sample.shape}"

    return sample


def save_auto_masks(
    data_id: int,
    mask_folder: str,
    map_slice_to_idx: dict,
    prediction: torch.Tensor,
    non_zero: bool = True,
):
    """
    Save the prediction to the mask folder as individual mask images.

    This function sets up the path to save the masks, validates the path exists,
    and iterates over the slices to save the masks.

    Args:
        data_id (int): ID of the sample.
        mask_folder (str): Path to the mask folder.
        map_slice_to_idx (dict): Mapping from slice number to index.
        prediction (torch.Tensor): The mask prediction for the given sample.
        non_zero (bool): Only save the image slice if max value is large enough
    """
    mask_sub_folder = os.path.join(mask_folder, str(data_id))
    map_idx_to_slice = {v: k for k, v in map_slice_to_idx.items()}

    if not os.path.exists(mask_sub_folder):
        os.makedirs(mask_sub_folder)

    for i in range(prediction[0].shape[2]):
        img_array = (prediction[0][0, 0, i, :, :].cpu().numpy() * 255).astype(np.uint8)

        if not non_zero or np.max(img_array) > 1e-4:
            image = apply_transparency(img_array, color=(0, 255, 255))
            image.save(
                os.path.join(
                    mask_sub_folder,
                    "auto_curve_idx_"
                    + str(data_id)
                    + "_slice_"
                    + str(map_idx_to_slice[i].split("/")[-1])
                    + ".png",
                )
            )


@blueprint.route("/auto_annotate", methods=["POST"])
def auto_annotate() -> dict[str, object]:
    """
    Serves an Ajax request from draw.js, downloading, converting, and saving
    the canvas as image.

    Returns:
        dict[str, object]: Instance specific session information as JSON.
    """
    data_id = int(request.form["data_id"])

    static_folder = os.path.join(
        current_app.root_path, current_app.config["STATIC_FOLDER"]
    )
    image_folder = os.path.join(static_folder, "Images/Img/")
    mask_folder = os.path.join(static_folder, "Images/Mask/")

    map_slice_to_idx, img_np_3d, mask_np_3d = load_images_and_masks(
        image_folder, mask_folder, data_id
    )
    sample = prepare_sample(img_np_3d, mask_np_3d)

    # Run inference
    trainer = Trainer()
    prediction, _ = trainer.run_inference(
        CONFIG["TRAINING_CONFIG"]["checkpoints"], [sample]
    )

    # Save the auto masks
    save_auto_masks(data_id, mask_folder, map_slice_to_idx, prediction)

    return jsonify({"result": "success"})


if __name__ == "__main__":
    static_folder = "/Users/lando/Code/SynAnno/synanno/static/"
    image_folder = os.path.join(static_folder, "Images/Img/")
    mask_folder = os.path.join(static_folder, "Images/Mask/")
    data_id = 2

    map_slice_to_idx, img_np_3d, mask_np_3d = load_images_and_masks(
        image_folder, mask_folder, data_id
    )
    sample = prepare_sample(img_np_3d, mask_np_3d)

    trainer = Trainer()

    prediction, _ = trainer.run_inference(
        CONFIG["TRAINING_CONFIG"]["checkpoints"], [sample]
    )

    save_auto_masks(data_id, mask_folder, map_slice_to_idx, prediction)

    for i in range(prediction[0].shape[2]):
        visualize_instances(sample[0, 0, :, :, :], prediction[0][0, 0, :, :, :], i, 0)
