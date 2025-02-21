from typing import Any

import numpy as np
import pandas as pd
from cloudvolume import Bbox, CloudVolume
from skimage.transform import resize

from synanno.backend.processing import calculate_crop_pad, process_syn


def setup_cloud_volume(bucket_url: str, cv_secret: str) -> CloudVolume:
    """
    Set up a CloudVolume instance.

    Args:
        bucket_url: URL of the bucket.
        cv_secret: Path to the CloudVolume secret.

    Returns:
        Configured CloudVolume instance.
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
        idx: Index of the instance.
        materialization_df: DataFrame containing materialization data.
        coordinate_order: Order of coordinates.
        crop_size_x: Crop size in x dimension.
        crop_size_y: Crop size in y dimension.
        crop_size_z: Crop size in z dimension.
        vol_dim: Volume dimensions.

    Returns:
        Metadata dictionary for the instance.
    """
    materialization_selection = _select_materialization_data(materialization_df, idx)
    item = _create_metadata_item(
        idx,
        materialization_selection,
        coordinate_order,
        crop_size_x,
        crop_size_y,
        crop_size_z,
    )
    item["Original_Bbox"] = _calculate_original_bbox(item, coordinate_order)
    item["Adjusted_Bbox"], item["Padding"] = calculate_crop_pad(
        item["Original_Bbox"], vol_dim
    )
    return item


def _select_materialization_data(
    materialization_df: pd.DataFrame, idx: int
) -> pd.Series:
    """Select materialization data for a specific instance."""
    return materialization_df.query("index == @idx").iloc[0][
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


def _create_metadata_item(
    idx: int,
    materialization_selection: pd.Series,
    coordinate_order: list[str],
    crop_size_x: int,
    crop_size_y: int,
    crop_size_z: int,
) -> dict[str, Any]:
    """Create a metadata dictionary for a specific instance."""
    return {
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


def _calculate_original_bbox(
    item: dict[str, Any], coordinate_order: list[str]
) -> list[int]:
    """Calculate the original bounding box for a specific instance."""
    z1, z2 = (
        item["cz0"] - item["crop_size_z"] // 2,
        item["cz0"] + item["crop_size_z"] // 2,
    )
    y1, y2 = (
        item["cy0"] - item["crop_size_y"] // 2,
        item["cy0"] + item["crop_size_y"] // 2,
    )
    x1, x2 = (
        item["cx0"] - item["crop_size_x"] // 2,
        item["cx0"] + item["crop_size_x"] // 2,
    )
    bbox_org = list(map(int, [z1, z2, y1, y2, x1, x2]))
    return [
        bbox_org[coordinate_order.index(coord) * 2 + i]
        for coord in ["z", "y", "x"]
        for i in range(2)
    ]


def retrieve_instance_from_cv(
    item: dict[str, Any], meta_data: dict[str, Any]
) -> dict[str, np.ndarray]:
    """
    Process the synapse and EM images for a single instance, returning numpy arrays.

    Args:
        item: Metadata dictionary for the instance.
        meta_data: Metadata dictionary for the volume.

    Returns:
        Dictionary containing the source image and ground truth target.
    """
    crop_bbox, img_padding = item["Adjusted_Bbox"], item["Padding"]
    coord_order = meta_data["coordinate_order"]
    scale = meta_data["scale"]

    bound_target = _create_bounding_box(crop_bbox, coord_order)
    bound_source = _scale_bounding_box(bound_target, scale)

    cropped_img = _download_volume(
        meta_data["source_cv"], bound_source, meta_data["coord_resolution_source"]
    )
    cropped_gt = _download_volume(
        meta_data["target_cv"], bound_target, meta_data["coord_resolution_target"]
    )

    cropped_img, cropped_gt = _resize_volumes(cropped_img, cropped_gt)
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


def _create_bounding_box(crop_bbox: list[int], coord_order: list[str]) -> Bbox:
    """Create a bounding box for the target volume."""
    crop_box_dict = {
        coord_order[0] + "1": crop_bbox[0],
        coord_order[0] + "2": crop_bbox[1],
        coord_order[1] + "1": crop_bbox[2],
        coord_order[1] + "2": crop_bbox[3],
        coord_order[2] + "1": crop_bbox[4],
        coord_order[2] + "2": crop_bbox[5],
    }
    return Bbox(
        [crop_box_dict[coord_order[i] + "1"] for i in range(3)],
        [crop_box_dict[coord_order[i] + "2"] for i in range(3)],
    )


def _scale_bounding_box(bound_target: Bbox, scale: dict[str, float]) -> Bbox:
    """Scale the bounding box for the source volume."""
    return Bbox(
        (bound_target.minpt * list(scale.values())).astype(int),
        (bound_target.maxpt * list(scale.values())).astype(int),
    )


def _download_volume(
    cv: CloudVolume, bbox: Bbox, coord_resolution: np.ndarray
) -> np.ndarray:
    """Download a volume from CloudVolume."""
    return cv.download(
        bbox,
        coord_resolution=coord_resolution,
        mip=0,
        parallel=True,
    ).squeeze(axis=3)


def _resize_volumes(
    cropped_img: np.ndarray, cropped_gt: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Resize the volumes to match their shapes."""
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
    return cropped_img, cropped_gt
