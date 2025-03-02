import logging

import numpy as np
import torch
from flask import Blueprint, current_app, jsonify, request

from synanno.backend.auto_segmentation.config import get_config
from synanno.backend.auto_segmentation.dataset import binarize_tensor, normalize_tensor
from synanno.backend.auto_segmentation.trainer import Trainer
from synanno.backend.processing import apply_transparency
from synanno.backend.utils import img_to_png_bytes, png_bytes_to_pil_img

blueprint = Blueprint("auto_annotate", __name__)
CONFIG = get_config()
logger = logging.getLogger(__name__)


def load_images_and_masks(data_id: int) -> tuple:
    """Load images and masks from the specified folders.

    Args:
        data_id: ID of the sample.

    Returns:
        Loaded images and masks as 3D numpy arrays.
    """
    source_images_dict = dict(
        sorted(current_app.source_image_data[str(data_id)].items(), key=lambda k: k[0])
    )
    target_images_dict = dict(
        sorted(
            current_app.target_image_data[str(data_id)]["curve"].items(),
            key=lambda k: k[0],
        )
    )

    map_slice_to_idx = {}
    image_np_list = []

    for i, (key_source, byte_image_source) in enumerate(source_images_dict.items()):
        map_slice_to_idx[key_source] = i
        img = png_bytes_to_pil_img(byte_image_source)
        image_np_list.append(np.array(img))

    img_np_3d = np.stack(image_np_list, axis=0)
    mask_np_3d = np.zeros(
        (
            CONFIG["DATASET_CONFIG"]["resize_depth"],
            CONFIG["DATASET_CONFIG"]["resize_height"],
            CONFIG["DATASET_CONFIG"]["resize_width"],
        )
    )

    for key_target, byte_image_target in target_images_dict.items():
        mask = png_bytes_to_pil_img(byte_image_target)
        binary_mask = np.array(mask)[:, :, 0] > 0
        mask_np_3d[map_slice_to_idx[key_target], :, :] = binary_mask

    return map_slice_to_idx, img_np_3d, mask_np_3d


def prepare_sample(img_np_3d: np.ndarray, mask_np_3d: np.ndarray) -> torch.Tensor:
    """Prepare the sample tensor from images and masks.

    Args:
        img_np_3d: 3D numpy array of images.
        mask_np_3d: 3D numpy array of masks.

    Returns:
        Prepared sample tensor.
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

    img_tensor = normalize_tensor(img_tensor)
    mask_tensor = binarize_tensor(mask_tensor)

    sample = torch.cat([img_tensor, mask_tensor], dim=1)

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
    map_slice_to_idx: dict,
    prediction: torch.Tensor,
    non_zero: bool = True,
) -> None:
    """Save the prediction to the mask folder as individual mask images.

    Args:
        data_id: ID of the sample.
        map_slice_to_idx: Mapping from slice number to index.
        prediction: The mask prediction for the given sample.
        non_zero: Only save the image slice if max value is large enough.
    """
    canvas_type = "auto_curve"
    map_idx_to_slice = {v: k for k, v in map_slice_to_idx.items()}

    if canvas_type not in current_app.target_image_data[str(data_id)]:
        current_app.target_image_data[str(data_id)][canvas_type] = {}

    for i in range(prediction[0].shape[2]):
        img_array = (prediction[0][0, 0, i, :, :].cpu().numpy() * 255).astype(np.uint8)

        if not non_zero or np.max(img_array) > 1e-4:
            image = apply_transparency(img_array, color=(0, 255, 255))
            image_byte = img_to_png_bytes(image)
            current_app.target_image_data[str(data_id)][canvas_type][
                str(map_idx_to_slice[i])
            ] = image_byte


@blueprint.route("/auto_annotate", methods=["POST"])
def auto_annotate() -> dict:
    """Serves an Ajax request from draw.js, downloading, converting, and saving
    the canvas as image.

    Returns:
        Instance specific session information as JSON.
    """
    data_id = int(request.form["data_id"])

    map_slice_to_idx, img_np_3d, mask_np_3d = load_images_and_masks(data_id)
    sample = prepare_sample(img_np_3d, mask_np_3d)

    trainer = Trainer()
    prediction, _ = trainer.run_inference(
        CONFIG["TRAINING_CONFIG"]["checkpoints"], [sample]
    )

    save_auto_masks(data_id, map_slice_to_idx, prediction)

    return jsonify({"result": "success"})
