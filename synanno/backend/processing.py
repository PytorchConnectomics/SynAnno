import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

import numpy as np
import pandas as pd
from cloudvolume import Bbox, CloudVolume
from flask import Flask, current_app
from PIL import Image
from scipy.ndimage import center_of_mass
from skimage.measure import label as label_cc
from skimage.transform import resize

from .utils import adjust_image_range, draw_cylinder, img_to_png_bytes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_with_app_context(app: Flask, func: Callable, *args, **kwargs):
    """Helper function to run a task within the app context."""
    with app.app_context():  # Ensure app context is available
        return func(*args, **kwargs)


def process_syn(gt: np.ndarray) -> np.ndarray:
    """Process the ground truth segmentation.

    Args:
        gt (np.ndarray): the ground truth segmentation.
        small_thres (int): the threshold for removing small objects.

    Returns:
        seg (np.ndarray): the processed segmentation.
    """

    # convert the semantic segmentation to instance-level segmentation
    # assign each synapse a unique index
    seg = label_cc(gt).astype(int)
    # identify the centers largest connected component and mask out the rest
    unique, _ = np.unique(seg, return_counts=True)
    if len(unique) > 1:
        center_blob_value = get_center_blob_value_vectorized(seg, np.unique(seg)[1:])
        seg *= seg == center_blob_value
    else:
        logger.warning("No synapse segmentation mask found in the volume.")
    return seg


def get_center_blob_value_vectorized(
    labeled_array: np.ndarray,
    blob_values: np.ndarray,
    center_threshold: float = 0.25,
) -> int:
    """Get the value of the non-zero blob closest to the center of the labeled array.

    Args:
        labeled_array: 3D array with individual blobs represented by different integers
        blob_values: Array of unique blob values in the labeled_array
        center_threshold : Threshold for the center blob

    Returns:
        Value of the center blob or -1 if no blob is within 40% of the center.
    """
    # Calculate the center of the entire array
    array_center = np.array(labeled_array.shape) / 2.0

    # Create a 4D array where the first dimension is equal to the number of blobs
    # and the last three dimensions are equal to the dimensions of the original array
    blob_masks = np.equal.outer(blob_values, labeled_array)

    # Compute the center of mass for each blob
    blob_centers = np.array([center_of_mass(mask) for mask in blob_masks])

    # Calculate the distance from each blob center to the array center
    distances = np.linalg.norm(blob_centers - array_center, axis=1)

    # Find the index of the blob with the minimum distance
    center_blob_index = np.argmin(distances)

    # Check if the center blob is within 40% of the array center
    if np.all(
        np.abs(blob_centers[center_blob_index][:2] - array_center[:2])
        <= center_threshold * array_center[:2]
    ):
        # Return the value of the blob with the minimum distance
        return blob_values[center_blob_index]
    else:
        # Return 0 if no blob is within center_threshold% of the center
        logger.warning(f"No blob is within {center_threshold} percent of the center.")
        return -1


def calculate_crop_pad(
    bbox_3d: list, volume_shape: tuple, pad_z: bool = False
) -> tuple[list, list]:
    """Calculate the crop/pad parameters for the given bounding box and volume shape.

    Args:
        bbox_3d (list): the bounding box of the 3D volume.
        volume_shape (tuple): the shape of the 3D volume.
        pad_z (bool): whether to pad the z dimension.

    Returns:
        bbox (list): the bounding box of the 3D volume.
        pad (tuple): the padding parameters.

    """
    c11o, c12o, c21o, c22o, c31o, c32o = bbox_3d  # region to crop
    c11m, c12m, c21m, c22m, c31m, c32m = (
        0,
        volume_shape[0],
        0,
        volume_shape[1],
        0,
        volume_shape[2],
    )
    c11, c21, c31 = max(c11o, c11m), max(c21o, c21m), max(c31o, c31m)
    c12, c22, c32 = min(c12o, c12m), min(c22o, c22m), min(c32o, c32m)

    assert c11 < c12 and c21 < c22 and c31 < c32, "Invalid bounding box."

    pad = [
        [c11 - c11o, c12o - c12],
        [c21 - c21o, c22o - c22],
        [c31 - c31o, c32o - c32],
    ]

    if not pad_z:
        pad[list(current_app.coordinate_order.keys()).index("z")] = [0, 0]

    return [c11, c12, c21, c22, c31, c32], pad


def syn2rgb(label: np.ndarray) -> np.ndarray:
    """Convert the binary mask of the synapse to RGB format.

    Args:
        label (np.ndarray): the binary mask of the synapse.

    Returns:
        out (np.ndarray): the RGB mask of the synapse.
    """
    tmp = [None] * 3
    tmp[0] = tmp[2] = label > 0
    tmp[1] = np.zeros_like(label)
    out = adjust_image_range(np.stack(tmp, -1))  # shape is (*, 3))
    return out


def free_page() -> None:
    """Remove the current and next page segmentation/images from the dict."""

    # retrieve the image index for all instances that are not labeled as "Correct"
    with current_app.df_metadata_lock:
        key_list = current_app.df_metadata.query('Label == "Correct"')[
            "Image_Index"
        ].values.tolist()

    for key in key_list:
        if str(key) in current_app.source_image_data:
            del current_app.source_image_data[str(key)]
        if str(key) in current_app.target_image_data:
            del current_app.target_image_data[str(key)]


def retrieve_materialization_data(df: pd.DataFrame) -> dict:
    """Retrieve the for the view style relevant columns from the materialization data.

    Args:
        df (pd.DataFrame): the material

    Returns:
        The selected materialization data as a dictionary.
    """
    if current_app.view_style == "volume":
        df = current_app.synapse_data
        df = df[
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
                "page",
            ]
        ]
    elif current_app.view_style == "neuron":
        df = df[
            [
                "materialization_index",
                "section_index",
                "tree_traversal_index",
                "pre_pt_x",
                "pre_pt_y",
                "pre_pt_z",
                "post_pt_x",
                "post_pt_y",
                "post_pt_z",
                "x",
                "y",
                "z",
                "page",
            ]
        ]
    return df.to_dict("index")


def retrieve_instance_metadata(page: int = 1, mode: str = "annotate"):
    """Visualize the synapse and EM images in 2D slices for each instance.

        Cropping the bounding box of the instance. Processing each instance
        individually, retrieving them from the cloud volume and saving them
        to the local disk.

    Args:
        page (int): the current page number for which to compute the data.
    """

    # retrieve the order of the coordinates (xyz, xzy, yxz, yzx, zxy, zyx)

    with current_app.df_metadata_lock:
        page_empty = current_app.df_metadata.query("Page == @page").empty

    if page_empty and not (
        mode == "draw" and current_app.df_metadata.query('Label != "Correct"').empty
    ):

        # retrieve the data for the current page
        page_metadata = current_app.synapse_data.query("page == @page")

        page_metadata = retrieve_materialization_data(page_metadata)

        coordinate_order = list(current_app.coordinate_order.keys())

        crop_size_x = (
            current_app.crop_size_z
            if mode == "annotate"
            else current_app.crop_size_z_draw
        )

        instance_list = []
        for idx in page_metadata.keys():

            item = {
                "Page": int(page),
                "Image_Index": int(idx),
                "materialization_index": (
                    page_metadata[idx]["materialization_index"]
                    if "materialization_index" in page_metadata[idx]
                    else -1
                ),
                "section_index": (
                    page_metadata[idx]["section_index"]
                    if "section_index" in page_metadata[idx]
                    else -1
                ),
                "tree_traversal_index": (
                    page_metadata[idx]["tree_traversal_index"]
                    if "tree_traversal_index" in page_metadata[idx]
                    else -1
                ),
                "Label": "Correct",
                "Annotated": "No",
                "neuron_id": (
                    current_app.selected_neuron_id
                    if current_app.selected_neuron_id is not None
                    else "No Neuron Selected..."
                ),
                "Error_Description": "None",
                "X_Index": coordinate_order.index("x"),
                "Y_Index": coordinate_order.index("y"),
                "Z_Index": coordinate_order.index("z"),
                "Middle_Slice": int(page_metadata[idx]["z"]),
                "cz0": int(page_metadata[idx]["z"]),
                "cy0": int(page_metadata[idx]["y"]),
                "cx0": int(page_metadata[idx]["x"]),
                "pre_pt_x": int(page_metadata[idx]["pre_pt_x"]),
                "pre_pt_y": int(page_metadata[idx]["pre_pt_y"]),
                "pre_pt_z": int(page_metadata[idx]["pre_pt_z"]),
                "post_pt_x": int(page_metadata[idx]["post_pt_x"]),
                "post_pt_y": int(page_metadata[idx]["post_pt_y"]),
                "post_pt_z": int(page_metadata[idx]["post_pt_z"]),
                "crop_size_x": current_app.crop_size_x,
                "crop_size_y": current_app.crop_size_y,
                # The auto segmentation view needs a set number of slices per instance
                # (depth) see process_instances.py::load_missing_slices for more details
                "crop_size_z": crop_size_x,
            }

            # Calculate bounding boxes
            bbox_org = [
                item["cz0"] - crop_size_x // 2,
                item["cz0"]
                + max(1, (crop_size_x + 1) // 2),  # incase the depth was set to one.
                item["cy0"] - current_app.crop_size_y // 2,
                item["cy0"] + (current_app.crop_size_y + 1) // 2,
                item["cx0"] - current_app.crop_size_x // 2,
                item["cx0"] + (current_app.crop_size_x + 1) // 2,
            ]

            item["Original_Bbox"] = [
                bbox_org[coordinate_order.index(coord) * 2 + i]
                for coord in ["z", "y", "x"]
                for i in range(2)
            ]

            item["Adjusted_Bbox"], item["Padding"] = calculate_crop_pad(
                item["Original_Bbox"], current_app.vol_dim
            )

            instance_list.append(item)

        # Append to shared DataFrame
        df_list = pd.DataFrame(instance_list)
        with current_app.df_metadata_lock:
            current_app.df_metadata = pd.concat(
                [current_app.df_metadata, df_list], ignore_index=True
            )

    # retrieve the page's metadata from the dataframe
    with current_app.df_metadata_lock:
        if mode == "annotate":
            page_metadata = current_app.df_metadata.query("Page == @page")
        elif mode == "draw":
            page_metadata = current_app.df_metadata.query('Label != "Correct"')

    # sort the metadata by the image index
    page_metadata = page_metadata.sort_values(by="Image_Index").to_dict(
        "records"
    )  # convert dataframe to list of dicts

    with ThreadPoolExecutor(max_workers=8) as executor:  # adjust max_workers as needed
        futures = [
            executor.submit(
                run_with_app_context,
                current_app._get_current_object(),
                process_instance,
                item,
            )
            for item in page_metadata
        ]

        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                logger.error("Error processing instance: %s", exc)
                logger.info("Retrying...")
                try:
                    future.result(timeout=15)
                except Exception as exc_retry:
                    logger.error("Retry failed: %s", exc_retry)
                    traceback.print_exc()

    logger.info("Completed processing for page %d.", page)


def update_slice_number(data: dict) -> None:
    """Update the slice number of the bounding box for the given instances.

    Args:
        data (dict): the dictionary containing the metadata of the instances.
    """
    # Adjust the bounding box
    with current_app.df_metadata_lock:
        coord_order = list(current_app.coordinate_order.keys())

        for instance in data:
            # retrieve the CloudVolume's coordinate order: xyz, xzy, yxz, yzx, zxy, zyx

            instance["crop_size_z"] = current_app.crop_size_z_draw
            og_bb = instance["Original_Bbox"]

            z1 = og_bb[coord_order.index("z") * 2]
            z2 = og_bb[coord_order.index("z") * 2 + 1]

            nr_slices = z2 - z1

            missing_nr_slices = current_app.crop_size_z_draw - nr_slices

            if missing_nr_slices < 0:
                logger.warning("We already have more slices than the model can handle.")
                break

            og_bb[coord_order.index("z") * 2] = z1 - missing_nr_slices // 2
            og_bb[coord_order.index("z") * 2 + 1] = z2 + (missing_nr_slices + 1) // 2

            assert (
                og_bb[coord_order.index("z") * 2 + 1]
                - og_bb[coord_order.index("z") * 2]
                == current_app.crop_size_z_draw
            )

            (
                instance["Adjusted_Bbox"],
                instance["Padding"],
            ) = calculate_crop_pad(
                instance["Original_Bbox"], current_app.vol_dim, pad_z=True
            )

            # Update the fields Adjusted_Bbox, Padding, crop_size_z, and Original_Bbox
            condition = (current_app.df_metadata["Page"] == instance["Page"]) & (
                current_app.df_metadata["Image_Index"] == instance["Image_Index"]
            )

            row_index = current_app.df_metadata.loc[condition].index[0]

            current_app.df_metadata.at[row_index, "Adjusted_Bbox"] = instance[
                "Adjusted_Bbox"
            ]
            current_app.df_metadata.at[row_index, "Padding"] = instance["Padding"]
            current_app.df_metadata.at[row_index, "crop_size_z"] = instance[
                "crop_size_z"
            ]
            current_app.df_metadata.at[row_index, "Original_Bbox"] = instance[
                "Original_Bbox"
            ]


def adjust_synapse_points(
    item: dict, crop_box_dict: dict, img_padding: list, coord_order: list
) -> tuple[int, int, int, int, int, int]:
    """Adjust the pre and post synapse points to the cropped out section.

    Args:
        item: Dictionary containing the metadata of the current instance.
        crop_box_dict: Dictionary containing the bounding box coordinates.
        img_padding: List containing the padding values.
        coord_order: List containing the coordinate order.

    Returns:
        tuple containing the adjusted pre and post synapse points.
    """
    pre_pt_x = (
        item["pre_pt_x"] - crop_box_dict["x1"] + img_padding[coord_order.index("x")][0]
    )
    pre_pt_y = (
        item["pre_pt_y"] - crop_box_dict["y1"] + img_padding[coord_order.index("y")][0]
    )
    pre_pt_z = (
        item["pre_pt_z"] - crop_box_dict["z1"] + img_padding[coord_order.index("z")][0]
    )

    post_pt_x = (
        item["post_pt_x"] - crop_box_dict["x1"] + img_padding[coord_order.index("x")][0]
    )
    post_pt_y = (
        item["post_pt_y"] - crop_box_dict["y1"] + img_padding[coord_order.index("y")][0]
    )
    post_pt_z = (
        item["post_pt_z"] - crop_box_dict["z1"] + img_padding[coord_order.index("z")][0]
    )

    return pre_pt_x, pre_pt_y, pre_pt_z, post_pt_x, post_pt_y, post_pt_z


def scale_synapse_points(
    pre_pt_x: int,
    pre_pt_y: int,
    pre_pt_z: int,
    post_pt_x: int,
    post_pt_y: int,
    post_pt_z: int,
) -> tuple[int, int, int, int, int, int]:
    """Scale the pre/post synapse points to the resolution of the source cloud volume.

    Args:
        pre_pt_x: X coordinate of the pre synapse point.
        pre_pt_y: Y coordinate of the pre synapse point.
        pre_pt_z: Z coordinate of the pre synapse point.
        post_pt_x: X coordinate of the post synapse point.
        post_pt_y: Y coordinate of the post synapse point.
        post_pt_z: Z coordinate of the post synapse point.

    Returns:
        tuple containing the scaled pre and post synapse points.
    """
    pre_pt_x = int(pre_pt_x * current_app.scale["x"])
    pre_pt_y = int(pre_pt_y * current_app.scale["y"])
    pre_pt_z = int(pre_pt_z * current_app.scale["z"])

    post_pt_x = int(post_pt_x * current_app.scale["x"])
    post_pt_y = int(post_pt_y * current_app.scale["y"])
    post_pt_z = int(post_pt_z * current_app.scale["z"])

    return pre_pt_x, pre_pt_y, pre_pt_z, post_pt_x, post_pt_y, post_pt_z


def save_slices_in_memory(
    cropped_img_pad: np.ndarray,
    vis_label: np.ndarray,
    item: dict,
    coord_order: list,
) -> None:
    """Convert images to bytes and save them in Flask's shared memory buffer.

    Args:
        cropped_img_pad: Padded cropped image (numpy array).
        vis_label: Visual label of the synapse segmentation (numpy array).
        item: Dictionary containing metadata of the current instance.
        coord_order: List containing the coordinate order.
    """
    slice_axis = coord_order.index("z")

    for s in range(cropped_img_pad.shape[slice_axis]):

        image_index = str(item["Image_Index"])
        img_z_index = str(item["Adjusted_Bbox"][slice_axis * 2] + s)

        # Process EM image
        slicing_img = [s if idx == slice_axis else slice(None) for idx in range(3)]
        current_app.source_image_data[image_index][img_z_index] = img_to_png_bytes(
            adjust_image_range(cropped_img_pad[tuple(slicing_img)])
        )

        # Process Synapse Segmentation image
        if item["Error_Description"] != "False Negative":
            slicing_seg = [s if idx == slice_axis else slice(None) for idx in range(4)]
            current_app.target_image_data[image_index][img_z_index] = img_to_png_bytes(
                apply_transparency(vis_label[tuple(slicing_seg)])
            )


def process_instance(item: dict) -> None:
    """Process the synapse and EM images for a single instance.

    Args:
        item: Dictionary containing the metadata of the current instance.
    """
    crop_bbox = item["Adjusted_Bbox"]
    img_padding = item["Padding"]

    coord_order = list(current_app.coordinate_order.keys())

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
        (bound_target.minpt * list(current_app.scale.values())).astype(int),
        (bound_target.maxpt * list(current_app.scale.values())).astype(int),
    )

    cropped_img = current_app.source_cv.download(
        bound_source,
        coord_resolution=current_app.coord_resolution_source,
        mip=0,
        parallel=True,
    )
    cropped_gt = current_app.target_cv.download(
        bound_target,
        coord_resolution=current_app.coord_resolution_target,
        mip=0,
        parallel=True,
    )

    cropped_img = cropped_img.squeeze(axis=3)
    cropped_gt = cropped_gt.squeeze(axis=3)

    if sum(cropped_img.shape) > sum(cropped_gt.shape):
        cropped_gt = resize(
            cropped_gt,
            cropped_img.shape,
            mode="constant",
            preserve_range=True,
            anti_aliasing=False,
        )
        cropped_gt = (cropped_gt > 0.5).astype(int)
    elif sum(cropped_img.shape) < sum(cropped_gt.shape):
        cropped_gt = resize(
            cropped_gt,
            cropped_img.shape,
            mode="constant",
            preserve_range=True,
            anti_aliasing=True,
        )
        cropped_gt = (cropped_gt > 0.5).astype(int)

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

    vis_label = None
    if item["Error_Description"] != "False Negative":
        (
            pre_pt_x,
            pre_pt_y,
            pre_pt_z,
            post_pt_x,
            post_pt_y,
            post_pt_z,
        ) = adjust_synapse_points(item, crop_box_dict, img_padding, coord_order)

        (
            pre_pt_x,
            pre_pt_y,
            pre_pt_z,
            post_pt_x,
            post_pt_y,
            post_pt_z,
        ) = scale_synapse_points(
            pre_pt_x, pre_pt_y, pre_pt_z, post_pt_x, post_pt_y, post_pt_z
        )

        vis_label = syn2rgb(cropped_seg_pad)

        vis_label = draw_cylinder(
            vis_label,
            pre_pt_x,
            pre_pt_y,
            pre_pt_z,
            radius=10,
            color_main=current_app.pre_id_color_main,
            color_sub=current_app.pre_id_color_sub,
            layout=coord_order,
        )
        vis_label = draw_cylinder(
            vis_label,
            post_pt_x,
            post_pt_y,
            post_pt_z,
            radius=10,
            color_main=current_app.post_id_color_main,
            color_sub=current_app.post_id_color_sub,
            layout=coord_order,
        )

    save_slices_in_memory(
        cropped_img_pad,
        vis_label,
        item,
        coord_order,
    )


def apply_transparency(image: np.ndarray, color: Optional[tuple] = None) -> Image:
    """Reduce the opacity of all black pixels to zero in an RGBA image.

    Args:
        image (np.ndarray): The input image.

    Returns:
        The image with transparency applied to black pixels.
    """
    image = np.array(Image.fromarray(image).convert("RGBA"))

    # the coloring function is so far only used for the auto segmentation results
    # if color is not None:
    #    image = np.copy(image)

    r, g, b, a = np.rollaxis(image, axis=-1)  # split into 4 n x m arrays
    r_m = r != 0  # binary mask for red channel, True for all non black values
    g_m = g != 0  # binary mask for green channel, True for all non black values
    b_m = b != 0  # binary mask for blue channel, True for all non black values

    # apply color
    if color is not None:
        r[r_m] = color[0]
        g[g_m] = color[1]
        b[b_m] = color[2]

    # combine the three binary masks by multiplying them (1*1=1, 1*0=0, 0*1=0, 0*0=0)
    # multiply the combined binary mask with the alpha channel
    a = a * ((r_m == 1) | (g_m == 1) | (b_m == 1))

    return Image.fromarray(np.dstack([r, g, b, a]), "RGBA")


def load_cloud_volumes(
    source_url: str,
    target_url: str,
    neuropil_url: str,
    bucket_secret_json: str,
) -> None:
    """
    Load the cloud volumes for source, target, and optionally neuropil.

    Args:
        source_url: URL to the source cloud volume (EM).
        target_url: URL to the target cloud volume (synapse).
        neuropil_url: URL to the neuropil cloud volume (neuron segmentation).
        bucket_secret_json: Path to the JSON file with bucket secrets.
    """
    current_app.source_cv = CloudVolume(
        source_url,
        secrets=bucket_secret_json,
        fill_missing=True,
        parallel=True,
        progress=False,
        use_https=True,
    )
    current_app.target_cv = CloudVolume(
        target_url,
        secrets=bucket_secret_json,
        fill_missing=True,
        parallel=True,
        progress=False,
        use_https=True,
    )
    if neuropil_url:
        current_app.neuropil_cv = CloudVolume(
            neuropil_url,
            secrets=bucket_secret_json,
            fill_missing=True,
            parallel=True,
            progress=False,
            use_https=True,
        )


def determine_volume_dimensions() -> tuple:
    """
    Determine the dimensions of the volume based on the source and target cloud volumes.

    Returns:
        tuple representing the volume dimensions.
    """
    if list(current_app.source_cv.volume_size) == list(
        current_app.target_cv.volume_size
    ):
        return tuple([s - 1 for s in current_app.source_cv.volume_size])
    else:
        logger.warning(
            f"The dimensions of the source ({current_app.source_cv.volume_size}) "
            f" and target ({current_app.target_cv.volume_size}) volumes do not match. "
            " Using the smaller size of the two volumes."
        )
        if np.prod(current_app.source_cv.volume_size) < np.prod(
            current_app.target_cv.volume_size
        ):
            return tuple([s - 1 for s in current_app.source_cv.volume_size])
        else:
            return tuple([s - 1 for s in current_app.target_cv.volume_size])


def calculate_number_of_pages(n_images: int) -> int:
    """
    Calculate the number of pages needed for the given number of images.

    Args:
        n_images: Total number of images.
        per_page: Number of images per page.

    Returns:
        Number of pages.
    """
    number_pages = n_images // current_app.per_page
    if n_images % current_app.per_page != 0:
        number_pages += 1

    current_app.synapse_data["page"] = -1  # Initialize pages to -1

    # assign pages to synapses
    for i, start_idx in enumerate(range(0, n_images, current_app.per_page), start=1):
        current_app.synapse_data.loc[
            current_app.synapse_data.iloc[
                start_idx : start_idx + current_app.per_page  # noqa: E203
            ].index,
            "page",
        ] = i

    return number_pages


def calculate_number_of_pages_for_neuron_section_based_loading():
    """
    Calculate the number of pages needed for neuron section-based loading.

    This function:
    - Groups synapses by `section_index`.
    - Assigns page numbers within each section based on `current_app.per_page`.
    - Adds an extra empty page per section.

    Returns:
        int: The total number of pages required.
    """

    number_of_pages = 0

    current_app.synapse_data["page"] = -1  # Initialize pages to -1

    # Group synapses by section_index
    grouped = current_app.synapse_data.groupby("section_index")

    # Iterate through sections

    for sec_index in range(len(current_app.sections)):
        if sec_index in grouped.groups:
            synapse_group = grouped.get_group(sec_index)  # Store group once
            total_synapses = len(synapse_group)

            # Assign pages to synapses within the section
            for i, start_idx in enumerate(
                range(0, total_synapses, current_app.per_page), start=1
            ):
                current_app.synapse_data.loc[
                    synapse_group.iloc[
                        start_idx : start_idx + current_app.per_page  # noqa: E203
                    ].index,
                    "page",
                ] = (
                    number_of_pages + i
                )

                current_app.page_section_mapping[number_of_pages + i] = (
                    sec_index,
                    False,
                )

            # Increment by the number of pages needed
            number_of_pages += int(np.ceil(total_synapses / current_app.per_page))

        # Add one empty page for the section
        number_of_pages += 1

        current_app.page_section_mapping[number_of_pages] = (sec_index, True)

    return int(number_of_pages)  # Ensure integer output
