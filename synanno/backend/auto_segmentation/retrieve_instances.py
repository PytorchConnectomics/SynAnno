import numpy as np
import pandas as pd
from cloudvolume import CloudVolume
from skimage.transform import resize
from cloudvolume import Bbox
from synanno.backend.processing import calculate_crop_pad, process_syn
from typing import Any


def setup_cloud_volume(bucket_url: str, cv_secret: str) -> CloudVolume:
    """
    Set up a CloudVolume instance.

    Args:
        bucket_url (str): URL of the bucket.
        cv_secret (str): Path to the CloudVolume secret.

    Returns:
        CloudVolume: Configured CloudVolume instance.
    """
    return CloudVolume(
        bucket_url,
        secrets=cv_secret,
        fill_missing=True,
        parallel=True,
        progress=False,
        use_https=True,
    )


def retrieve_instance_metadata(
    idx: int,
    materialization_df: pd.DataFrame,
    coordinate_order: list[str],
    crop_size_x: int,
    crop_size_y: int,
    crop_size_z: int,
    vol_dim: tuple[int, int, int],
) -> dict[str, Any]:
    """
    Retrieve metadata for a specific instance.

    Args:
        idx (int): Index of the instance.
        materialization_df (pd.DataFrame): DataFrame containing materialization data.
        coordinate_order (list[str]): Order of coordinates.
        crop_size_x (int): Crop size in x dimension.
        crop_size_y (int): Crop size in y dimension.
        crop_size_z (int): Crop size in z dimension.
        vol_dim (tuple[int, int, int]): Volume dimensions.

    Returns:
        dict[str, Any]: Metadata dictionary for the instance.
    """
    materialization_selection = materialization_df.query("index == @idx").iloc[0]
    materialization_selection = materialization_selection[
        [
            "pre_pt_x",
            "pre_pt_y",
            "pre_pt_z",
            "post_pt_x",
            "post_pt_y",
            "post_pt_z",
            "x",
            "y",
            "z",
        ]
    ]

    item = {
        "Image_Index": int(idx),
        "X_Index": coordinate_order.index("x"),
        "Y_Index": coordinate_order.index("y"),
        "Z_Index": coordinate_order.index("z"),
        "cz0": int(materialization_selection["z"]),
        "cy0": int(materialization_selection["y"]),
        "cx0": int(materialization_selection["x"]),
        "pre_pt_x": int(materialization_selection["pre_pt_x"]),
        "pre_pt_y": int(materialization_selection["pre_pt_y"]),
        "pre_pt_z": int(materialization_selection["pre_pt_z"]),
        "post_pt_x": int(materialization_selection["post_pt_x"]),
        "post_pt_y": int(materialization_selection["post_pt_y"]),
        "post_pt_z": int(materialization_selection["post_pt_z"]),
        "crop_size_x": crop_size_x,
        "crop_size_y": crop_size_y,
        "crop_size_z": crop_size_z,
    }

    z1, z2 = item["cz0"] - crop_size_z // 2, item["cz0"] + crop_size_z // 2
    y1, y2 = item["cy0"] - crop_size_y // 2, item["cy0"] + crop_size_y // 2
    x1, x2 = item["cx0"] - crop_size_x // 2, item["cx0"] + crop_size_x // 2

    bbox_org = list(map(int, [z1, z2, y1, y2, x1, x2]))

    item["Original_Bbox"] = [
        bbox_org[coordinate_order.index(coord) * 2 + i]
        for coord in ["z", "y", "x"]
        for i in range(2)
    ]

    crop_bbox, img_padding = calculate_crop_pad(
        item["Original_Bbox"], vol_dim, coordinate_order
    )

    item["Adjusted_Bbox"], item["Padding"] = crop_bbox, img_padding

    return item


def retrieve_instance_from_cv(
    item: dict[str, Any], meta_data: dict[str, Any]
) -> dict[str, np.ndarray]:
    """
    Process the synapse and EM images for a single instance, returning numpy arrays.

    Args:
        item (dict[str, Any]): Metadata dictionary for the instance.
        meta_data (dict[str, Any]): Metadata dictionary for the volume.

    Returns:
        dict[str, np.ndarray]: Dictionary containing the source image and ground truth target.
    """
    crop_bbox, img_padding = item["Adjusted_Bbox"], item["Padding"]
    coord_order = meta_data["coordinate_order"]
    coord_resolution_source = meta_data["coord_resolution_source"]
    coord_resolution_target = meta_data["coord_resolution_target"]
    source_cv = meta_data["source_cv"]
    target_cv = meta_data["target_cv"]
    scale = meta_data["scale"]

    crop_box_dict = {
        coord_order[0] + "1": crop_bbox[0],
        coord_order[0] + "2": crop_bbox[1],
        coord_order[1] + "1": crop_bbox[2],
        coord_order[1] + "2": crop_bbox[3],
        coord_order[2] + "1": crop_bbox[4],
        coord_order[2] + "2": crop_bbox[5],
    }

    bound_target = Bbox(
        [crop_box_dict[coord_order[i] + "1"] for i in range(3)],
        [crop_box_dict[coord_order[i] + "2"] for i in range(3)],
    )

    bound_source = Bbox(
        (bound_target.minpt * list(scale.values())).astype(int),
        (bound_target.maxpt * list(scale.values())).astype(int),
    )

    cropped_img = source_cv.download(
        bound_source, coord_resolution=coord_resolution_source, mip=0, parallel=True
    )
    cropped_gt = target_cv.download(
        bound_target, coord_resolution=coord_resolution_target, mip=0, parallel=True
    )

    cropped_img = cropped_img.squeeze(axis=3)
    cropped_gt = cropped_gt.squeeze(axis=3)

    if sum(cropped_img.shape) > sum(cropped_gt.shape):  # Up-sampling
        cropped_gt = resize(
            cropped_gt,
            cropped_img.shape,
            mode="constant",
            preserve_range=True,
            anti_aliasing=False,
        )
        cropped_gt = (cropped_gt > 0.5).astype(int)  # Convert to binary mask
    elif sum(cropped_img.shape) < sum(cropped_gt.shape):  # Down-sampling
        cropped_gt = resize(
            cropped_gt,
            cropped_img.shape,
            mode="constant",
            preserve_range=True,
            anti_aliasing=True,
        )
        cropped_gt = (cropped_gt > 0.5).astype(int)  # Convert to binary mask

    cropped_seg = process_syn(cropped_gt)

    cropped_img_pad = np.pad(
        cropped_img, img_padding, mode="constant", constant_values=148
    )
    cropped_seg_pad = np.pad(
        cropped_seg, img_padding, mode="constant", constant_values=0
    )

    assert (
        cropped_img_pad.shape == cropped_seg_pad.shape
    ), "The shape of the source and target images do not match."

    return {"source_image": cropped_img_pad, "target": cropped_seg_pad}
