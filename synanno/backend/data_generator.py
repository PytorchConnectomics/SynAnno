import numpy as np
import os
import pandas as pd
import json
from cloudvolume import CloudVolume
from cloudvolume.lib import Bbox
from typing import Tuple, List, Dict, Set
import matplotlib.pyplot as plt
from skimage.transform import resize
from synanno.backend.processing import process_syn
from google.cloud import storage

# defaults to running on GCP
LOCAL_EXECUTION = False


def upload_to_bucket(blob_name, data, bucket_name="synanno"):
    """Uploads numpy array data to the bucket."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Use BytesIO as an in-memory binary stream
    with io.BytesIO() as data_stream:
        np.save(data_stream, data)
        data_stream.seek(0)
        blob.upload_from_file(data_stream, content_type="application/octet-stream")


def download_from_bucket(blob_name, bucket_name="synanno"):
    """Downloads numpy array data from the bucket."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Download as bytes and convert to numpy array
    np_data_bytes = blob.download_as_bytes()
    data_stream = io.BytesIO(np_data_bytes)
    data_stream.seek(0)
    data = np.load(data_stream, allow_pickle=True)
    return data


def select_random_instances(n, table_name):
    """
    Select n random instances from the materialization table. The materialization table
    references the pre- and post-synaptic coordinates of the synapse with in the target volume.

    Args:
        n (int): Number of instances to select.
        table_name (str): Name of the table to read instances from.

    Returns:
        list: List of instance keys.
        dict: Materialization dictionary.
    """
    try:
        df = pd.read_csv(table_name)
    except Exception as e:
        raise IOError(f"Error reading table {table_name}: {e}")

    df_sampled = df.sample(n).reset_index()
    df_sampled = df_sampled[
        [
            "index",
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

    bbox_dict = df_sampled.to_dict("index")

    return list(bbox_dict.keys()), bbox_dict


def connect_to_cloudvolumes(source_url, target_url, bucket_secret_json_path):
    """
    Connect to the source and target CloudVolumes.

    Args:
        source_url (str): URL of the source CloudVolume.
        target_url (str): URL of the target CloudVolume.
        bucket_secret_json_path (str): Path to the bucket secret JSON file.

    Returns:
        tuple: Tuple of CloudVolume objects.
    """
    try:
        with open(bucket_secret_json_path, "r") as f:
            bucket_secret_json = json.load(f)

        source_cv = CloudVolume(
            source_url, secrets=bucket_secret_json, fill_missing=True, parallel=True
        )
        target_cv = CloudVolume(
            target_url, secrets=bucket_secret_json, fill_missing=True, parallel=True
        )

    except Exception as e:
        raise ConnectionError(f"Error connecting to CloudVolumes: {e}")

    return source_cv, target_cv


def cloudvolume_metadata(
    source_cv,
    target_cv,
    coordinate_order,
    coord_resolution_source,
    coord_resolution_target,
):
    """
    Calculate metadata for the source and target CloudVolumes.

    Args:
        source_cv (CloudVolume): Source CloudVolume object.
        target_cv (CloudVolume): Target CloudVolume object.
        coordinate_order (list): Order of coordinates (e.g., ['x', 'y', 'z']).
        coord_resolution_source (list): Coordinate resolution of source.
        coord_resolution_target (list): Coordinate resolution of target.

    Returns:
        Tuple: Volume dimensions and scaled volume dimensions.
    """

    # calculate the scale factor between the source and target volumes
    # since the materialization table is in the target volume coordinate system
    # we need to scale the bounding boxes of the source volume to match the target volume
    scale = {
        c: v
        for c, v in zip(
            coordinate_order,
            np.where(
                (
                    np.array(coord_resolution_target).astype(int)
                    / np.array(coord_resolution_source).astype(int)
                )
                > 0,
                np.array(coord_resolution_target).astype(int)
                / np.array(coord_resolution_source).astype(int),
                1,
            ),
        )
    }

    # set the volumes sizes to the smaller of the two volumes
    # we use the smaller volume size to avoid out of bounds errors
    if list(source_cv.volume_size) == list(target_cv.volume_size):
        vol_dim = tuple([s - 1 for s in source_cv.volume_size])
    else:
        print(
            f"The dimensions of the source ({source_cv.volume_size}) and target ({target_cv.volume_size}) volumes do not match. We use the smaller size of the two volumes."
        )

        if np.prod(source_cv.volume_size) < np.prod(target_cv.volume_size):
            vol_dim = tuple([s - 1 for s in source_cv.volume_size])
        else:
            vol_dim = tuple([s - 1 for s in target_cv.volume_size])

    vol_dim_scaled = tuple(int(a * b) for a, b in zip(vol_dim, scale.values()))

    return vol_dim, vol_dim_scaled, scale


def download_subvolumes(
    instance_keys,
    source_cv,
    target_cv,
    local_dir,
    materialization,
    coordinate_order,
    crop_sizes,
    volume_dimensions,
    scale,
    pad_z=False,
):
    """
    Download the source and target subvolumes for the selected instances.

    Args:
        instance_keys (list): List of instance keys.
        source_cv (CloudVolume): CloudVolume object of the source.
        target_cv (CloudVolume): CloudVolume object of the target.
        local_dir (str): Local directory to store the subvolumes.
        materialization (dict): Dictionary containing the instance data.
    """
    if LOCAL_EXECUTION:
        source_dir = os.path.join(local_dir, "source")
        gt_dir = os.path.join(local_dir, "gt")

        # create dirs if they do not exist
        if not os.path.exists(source_dir):
            os.makedirs(source_dir, exist_ok=True)
        if not os.path.exists(gt_dir):
            os.makedirs(gt_dir, exist_ok=True)

    for key in instance_keys:
        instance_data = materialization[key]
        bbox, padding = get_bbox_from_instance_data(
            instance_data,
            coordinate_order,
            crop_sizes,
            volume_dimensions,
        )
        gt_subvol = target_cv.download(bbox, mip=0)

        # scale the bounding box to the resolution of the source cloud volume
        bbox = Bbox(
            (bbox.minpt * list(scale.values())).astype(int),
            (bbox.maxpt * list(scale.values())).astype(int),
        )
        source_subvol = source_cv.download(bbox, mip=0)

        gt_subvol = gt_subvol.squeeze(axis=3)
        source_subvol = source_subvol.squeeze(axis=3)

        # adjust the scale of the label volume
        if sum(source_subvol.shape) > sum(gt_subvol.shape):  # up-sampling
            gt_subvol = resize(
                gt_subvol,
                source_subvol.shape,
                mode="constant",
                preserve_range=True,
                anti_aliasing=False,
            )
            gt_subvol = (gt_subvol > 0.5).astype(int)  # convert to binary mask
        elif sum(source_subvol.shape) < sum(gt_subvol.shape):  # down-sampling
            gt_subvol = resize(
                gt_subvol,
                source_subvol.shape,
                mode="constant",
                preserve_range=True,
                anti_aliasing=True,
            )
        gt_subvol = (gt_subvol > 0.5).astype(int)  # convert to binary mask

        gt_subvol = process_syn(gt_subvol)

        # pad the images and synapse segmentation to fit the crop size (sz)
        source_subvol_pad = np.pad(
            source_subvol, padding, mode="constant", constant_values=148
        )
        gt_subvol_pad = np.pad(gt_subvol, padding, mode="constant", constant_values=0)

        if LOCAL_EXECUTION:
            source_blob_name = f"source/source_{materialization[key]['index']}.npy"
            target_blob_name = f"gt/target_{materialization[key]['index']}.npy"

            upload_to_bucket(source_blob_name, source_subvol_pad)
            upload_to_bucket(target_blob_name, gt_subvol_pad)
        else:
            np.save(
                os.path.join(source_dir, f"source_{materialization[key]['index']}.npy"),
                source_subvol_pad,
            )
            np.save(
                os.path.join(gt_dir, f"target_{materialization[key]['index']}.npy"),
                gt_subvol_pad,
            )


def generate_training_data(
    instance_keys, materialization, local_dir, coordinate_order, crop_size_z=128
):
    """
    Generate training data from the downloaded subvolumes.

    Args:
        instance_keys (list): List of instance keys.
        local_dir (str): Local directory to store the subvolumes.
    """
    if not LOCAL_EXECUTION:
        gt_dir = os.path.join(local_dir, "gt")
        target_dir = os.path.join(local_dir, "target")

        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

    for key in instance_keys:
        if LOCAL_EXECUTION:
            gt_subvol = download_from_bucket(
                f"gt/target_{materialization[key]['index']}.npy"
            )
        else:
            gt_subvol_path = os.path.join(
                gt_dir, f"target_{materialization[key]['index']}.npy"
            )
            gt_subvol = np.load(gt_subvol_path)

        seed_layers = get_seed_layers(crop_size_z)
        augmented_subvol = augment_target_volume(
            gt_subvol, seed_layers, coordinate_order
        )
        if LOCAL_EXECUTION:
            augmented_blob_name = (
                f"target/augmented_target_{materialization[key]['index']}.npy"
            )
            upload_to_bucket(augmented_blob_name, augmented_subvol)
        else:
            np.save(
                os.path.join(
                    target_dir, f"augmented_target_{materialization[key]['index']}.npy"
                ),
                augmented_subvol,
            )


def get_bbox_from_instance_data(
    instance_data: Dict[str, int],
    coordinate_order: List[str],
    crop_sizes: Dict[str, int],
    volume_dimensions: Dict[str, int],
    pad_z: bool = False,
) -> Tuple[Bbox, Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]:
    """
    Construct a Bbox object from instance center data, considering padding and volume bounds.

    Args:
        instance_data (Dict[str, int]): Dictionary containing the center coordinates for an instance.
        coordinate_order (List[str]): The order of the coordinates (e.g., ['x', 'y', 'z']).
        crop_sizes (Dict[str, int]): Dictionary containing the sizes to crop from the center in each dimension.
        volume_dimensions (Dict[str, int]): Dictionary containing the max dimensions of the volume.
        pad_z (bool): Whether to pad the z dimension if out of bounds.

    Returns:
        Tuple[Bbox, Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]: A CloudVolume Bbox object defining the volume to download and the padding parameters.
    """
    bbox_3d = [0] * 6
    for i, coord in enumerate(coordinate_order):
        center = instance_data[coord]
        size = crop_sizes[f"crop_size_{coord}"]
        half_size = size // 2
        min_edge = max(center - half_size, 0)
        max_edge = min(center + half_size, volume_dimensions[coord] - 1)
        bbox_3d[i * 2] = min_edge
        bbox_3d[i * 2 + 1] = max_edge

    adjusted_bbox, pad = calculate_crop_pad(
        bbox_3d, list(volume_dimensions.values()), pad_z
    )

    bbox_min = [adjusted_bbox[i] for i in range(0, len(adjusted_bbox), 2)]
    bbox_max = [adjusted_bbox[i] for i in range(1, len(adjusted_bbox), 2)]

    if coordinate_order != ["x", "y", "z"]:
        bbox_min = [
            bbox_min[coordinate_order.index(coord)] for coord in ["x", "y", "z"]
        ]
        bbox_max = [
            bbox_max[coordinate_order.index(coord)] for coord in ["x", "y", "z"]
        ]

    return Bbox(bbox_min, bbox_max), pad


def apply_padding_to_segmentation(
    cropped_seg: np.ndarray, padding: List[Tuple[int, int]], pad_value: int = 0
) -> np.ndarray:
    """
    Apply padding to a segmented volume.

    Args:
        cropped_seg (np.ndarray): The segmented volume to pad.
        padding (List[Tuple[int, int]]): The padding to apply along each axis.
        pad_value (int, optional): The value to use for padding. Defaults to 0.

    Returns:
        np.ndarray: The padded segmented volume.
    """
    if any(pad > 0 for axis in padding for pad in axis):
        cropped_seg_pad = np.pad(
            cropped_seg, padding, mode="constant", constant_values=pad_value
        )
    else:
        cropped_seg_pad = cropped_seg

    return cropped_seg_pad


def get_seed_layers(z_crop_size: int) -> Set[int]:
    """
    Sample at most n-1 numbers from 0 to n-1, where n is the crop size for the z axis.
    The sampling is more likely to choose the center number and less likely to choose numbers closer to 0 or n-1.

    Args:
        z_crop_size (int): The crop size for the z axis.

    Returns:
        Set[int]: A set of selected seed layers.
    """
    seed_layers = set()
    # Generate a single random number from an exponential distribution
    random_number = np.random.exponential(scale=z_crop_size, size=1)

    number_of_seed_layers = min(int(random_number[0]), z_crop_size - 1)

    for _ in range(number_of_seed_layers):
        layer = int(np.random.normal(z_crop_size // 2, z_crop_size / 4))
        layer = max(0, min(layer, z_crop_size - 1))
        if layer not in seed_layers:
            seed_layers.add(layer)

    return seed_layers


def augment_target_volume(
    gt_subvol: np.ndarray, seed_layers: Set[int], coordinate_order: List[str]
) -> np.ndarray:
    """
    Augment the target volume based on the seed layers.

    Args:
        gt_subvol (np.ndarray): The ground truth subvolume.
        seed_layers (Set[int]): A set of seed layer indices.

    Returns:
        np.ndarray: The augmented subvolume.
    """
    augmented_subvol = np.zeros_like(gt_subvol)
    index_z = coordinate_order.index("z")

    for seed_layer in seed_layers:
        if index_z == 0:
            augmented_subvol[seed_layer, :, :] = gt_subvol[seed_layer, :, :]
        elif index_z == 1:
            augmented_subvol[:, seed_layer, :] = gt_subvol[:, seed_layer, :]
        elif index_z == 2:
            augmented_subvol[:, :, seed_layer] = gt_subvol[:, :, seed_layer]
    return augmented_subvol


def calculate_crop_pad(
    bbox_3d: List[int], volume_shape: List[int], pad_z: bool = False
) -> Tuple[List[int], Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]:
    """
    Calculate the crop and pad parameters for the given bounding box and volume shape.

    Args:
        bbox_3d (List[int]): the bounding box of the 3D volume.
        volume_shape (List[int]): the shape of the 3D volume.
        pad_z (bool): whether to pad the z dimension.

    Returns:
        Tuple[List[int], Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]: the adjusted bounding box and the padding parameters.
    """
    c11, c12, c21, c22, c31, c32 = bbox_3d
    volume_max = [volume_shape[i] - 1 for i in range(3)]

    bbox = [
        max(c11, 0),
        min(c12, volume_max[0]),
        max(c21, 0),
        min(c22, volume_max[1]),
        max(c31, 0),
        min(c32, volume_max[2]),
    ]

    pad = [[bbox[i] - bbox_3d[i], bbox_3d[i + 1] - bbox[i + 1]] for i in range(0, 6, 2)]

    if not pad_z:
        pad[2] = [0, 0]

    return bbox, pad


def visualize_data(file):
    # Load the data from the .npy file
    data = np.load(file)
    data = ((data - np.min(data)) / (np.max(data) - np.min(data))) * 255
    print(data.shape)
    print(np.max(data), np.min(data))

    # Check the dimension of the data
    if data.ndim == 1:
        # For 1D data, you can plot it directly
        plt.plot(data)
    elif data.ndim == 2:
        # For 2D data, you can use imshow for visualization
        plt.imshow(data, cmap="gray")  # or any other colormap
    elif data.ndim > 2:
        # For multi-dimensional data, you might want to visualize specific slices
        slice_to_visualize = data[:, :, 0]  # example for 3D data
        plt.imshow(slice_to_visualize, cmap="gray")

    # Show the plot
    plt.show()
