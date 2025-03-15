from typing import Any

import numpy as np
from cloudvolume import Bbox
from skimage.transform import resize

from synanno.backend.processing import process_syn


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
        bound_source,
        coord_resolution=coord_resolution_source,
        mip=0,
        parallel=True,
    )
    cropped_gt = target_cv.download(
        bound_target,
        coord_resolution=coord_resolution_target,
        mip=0,
        parallel=True,
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

    return {"source_image": cropped_img_pad, "gt_target": cropped_seg_pad}
