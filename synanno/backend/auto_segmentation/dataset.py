from torch.utils.data import Dataset
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3
import traceback
from tqdm import tqdm
from synanno.backend.auto_segmentation.retrieve_instances import (
    retrieve_instance_from_cv,
    retrieve_instance_metadata,
    setup_cloud_volume,
)
from synanno.backend.auto_segmentation.model_source_data import generate_seed_target
import torch
from synanno.backend.auto_segmentation.config import CONFIG, DATASET_CONFIG
from typing import Any


def normalize_tensor(tensor: torch.Tensor, max_value: int = 255.0) -> torch.Tensor:
    """
    Normalize a tensor to [0, 1].

    Args:
        tensor (torch.Tensor): Target tensor.

    Returns:
        torch.Tensor: Normalized target tensor.
    """
    return tensor / max_value


def binarize_tensor(tensor: torch.Tensor) -> torch.Tensor:
    """
    Binarize a tensor.

    Args:
        tensor (torch.Tensor): Target tensor.

    Returns:
        torch.Tensor: Binarized target tensor.
    """
    return (tensor > 0.5).float()


class SynapseDataset(Dataset):
    """Dataset for synapse images and targets."""

    def __init__(
        self,
        materialization_df: pd.DataFrame,
        meta_data: dict[str, Any],
        synapse_id_range: tuple[int, int],
        transform: Any = None,
        target_transform: Any = None,
    ):
        """
        Initialize the SynapseDataset.

        Args:
            materialization_df (pd.DataFrame): DataFrame containing materialization data.
            meta_data (dict[str, Any]): Metadata dictionary.
            synapse_id_range (tuple[int, int]): Range of synapse IDs to include in the dataset.
            transform (Any, optional): Transform to apply to the source data. Defaults to None.
            target_transform (Any, optional): Transform to apply to the target data. Defaults to None.
        """
        self.materialization_df = materialization_df
        self.meta_data = meta_data
        self.synapse_id_range = synapse_id_range
        self.transform = transform
        self.target_transform = target_transform
        self.num_pools = DATASET_CONFIG["num_pools"]
        self.maxsize = DATASET_CONFIG["maxsize"]
        self.max_workers = DATASET_CONFIG["max_workers"]
        self.timeout = DATASET_CONFIG["timeout"]
        self.resize_depth = DATASET_CONFIG["resize_depth"]
        self.resize_height = DATASET_CONFIG["resize_height"]
        self.resize_width = DATASET_CONFIG["resize_width"]
        self.crop_size_x = DATASET_CONFIG["crop_size_x"]
        self.crop_size_y = DATASET_CONFIG["crop_size_y"]
        self.crop_size_z = DATASET_CONFIG["crop_size_z"]
        self.slices_to_generate = DATASET_CONFIG["slices_to_generate"]
        self.target_range = DATASET_CONFIG["target_range"]
        self.dataset = self._generate_dataset()

    def _generate_dataset(self) -> list[dict[str, Any]]:
        """
        Generate the dataset by retrieving instances and processing them.

        Returns:
            list[dict[str, Any]]: list of dictionaries containing dataset instances.
        """
        instance_list = []
        for idx in tqdm(
            range(self.synapse_id_range[0], self.synapse_id_range[1]),
            desc="Metadata Retrieval",
        ):
            instance = retrieve_instance_metadata(
                idx,
                self.materialization_df,
                CONFIG["coordinate_order"],
                self.crop_size_x,
                self.crop_size_y,
                self.crop_size_z,
                self.meta_data["vol_dim"],
            )
            instance_list.append(instance)

        instance_meta_data_df = pd.DataFrame(instance_list)
        instance_meta_data_list_of_dics = instance_meta_data_df.sort_values(
            by="Image_Index"
        ).to_dict("records")

        dataset = []
        urllib3.PoolManager(
            num_pools=self.num_pools,
            maxsize=self.maxsize,
        )

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                executor.submit(retrieve_instance_from_cv, item, self.meta_data)
                for item in instance_meta_data_list_of_dics
            ]
            for future in tqdm(
                as_completed(futures), total=len(futures), desc="Data Retrieval"
            ):
                try:
                    dataset.append(future.result())
                except Exception as exc:
                    print(f"An exception occurred: {exc}")
                    print("Retry to process the instance.")
                    try:
                        dataset.append(future.result(timeout=self.timeout))
                    except Exception as exc:
                        print(f"The exception persists: {exc}")
                        traceback.print_exc()

        for sample in tqdm(dataset, desc="Seed/Target Generation"):
            seed_volume, selected_seed_slices = generate_seed_target(
                sample["target"], self.slices_to_generate, self.target_range
            )
            sample["source_seed_target"] = seed_volume
            sample["source"] = np.stack([sample["source_image"], seed_volume], axis=-1)
            sample["selected_slices"] = selected_seed_slices

        return dataset

    def __len__(self) -> int:
        """
        Get the length of the dataset.

        Returns:
            int: Length of the dataset.
        """
        return len(self.dataset)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Retrieve a source and target sample from the dataset.

        Note:
            The source volume has 2 channels: Input shape: (batch_size, 2, depth, height, width)
            - Channel 0 (raw image): Normalized image data.
            - Channel 1 (seed masks): Contains partial segmentation masks for some slices, with zeros elsewhere.

            The target has a single-channel volume: (batch_size, 1, depth, height, width)
            - Channel 0 (mask): This represents the predicted segmentation mask for the entire volume.

        Args:
            idx (int): Index of the item to retrieve.

        Returns:
            tuple[torch.Tensor, torch.Tensor]: Source and target tensors.
        """
        # Get the source and target for the current index
        sample = self.dataset[idx]
        source = sample["source"]  # Shape: (x, y, z, 2)
        target = sample["target"]  # Shape: (x, y, z)

        # Convert to tensors
        source = torch.tensor(source, dtype=torch.float32).permute(
            3, 2, 0, 1
        )  # Shape: (2, D, H, W)
        target = torch.tensor(target, dtype=torch.float32).permute(
            2, 0, 1
        )  # Shape: (D, H, W)

        image_channel = source[0]  # Shape: (D, H, W)
        mask_channel = source[1]  # Shape: (D, H, W)

        # Add a channel dimension
        image_channel = image_channel.unsqueeze(0)  # Shape: (1, D, H, W)
        mask_channel = mask_channel.unsqueeze(0)  # Shape: (1, D, H, W)
        target = target.unsqueeze(0)  # Shape: (1, D, H, W)

        # Add a batch dimension
        image_channel = image_channel.unsqueeze(0)  # Shape: (1, 1, D, H, W)
        mask_channel = mask_channel.unsqueeze(0)  # Shape: (1, 1, D, H, W)
        target = target.unsqueeze(0)  # Shape: (1, 1, D, H, W)

        assert (
            image_channel.shape == mask_channel.shape == target.shape
        ), "The shapes of the source and target do not match."

        # Resize channels
        image_channel = torch.nn.functional.interpolate(
            image_channel,
            size=(
                self.resize_depth,
                self.resize_height,
                self.resize_width,
            ),
            mode="trilinear",
            align_corners=False,
        )
        mask_channel = torch.nn.functional.interpolate(
            mask_channel,
            size=(
                self.resize_depth,
                self.resize_height,
                self.resize_width,
            ),
            mode="nearest",
        )
        target = torch.nn.functional.interpolate(
            target,
            size=(
                self.resize_depth,
                self.resize_height,
                self.resize_width,
            ),
            mode="nearest",
        )

        # Collapse the batch dimension
        image_channel = image_channel.squeeze(0)  # Shape: (1, D, H, W)
        mask_channel = mask_channel.squeeze(0)  # Shape: (1, D, H, W)
        target = target.squeeze(0)  # Shape: (1, D, H, W)

        assert (
            image_channel.shape == mask_channel.shape == target.shape
        ), "The shapes of the source and target do not match."

        # Merge channels
        source = torch.cat([image_channel, mask_channel], dim=0)  # Shape: (2, D, H, W)

        # Normalize the image channel
        source[0] = normalize_tensor(source[0])

        # Binarize the segmentation channel and target
        source[1] = binarize_tensor(source[1])
        target = binarize_tensor(target)

        return source, target


if __name__ == "__main__":
    from synanno.backend.auto_segmentation.visualize_instances import (
        visualize_instances,
    )
    from synanno.backend.auto_segmentation.match_source_and_target import (
        retrieve_smallest_volume_dim,
        compute_scale_factor,
    )

    # Load the materialization csv
    materialization_df = pd.read_csv(
        "/Users/lando/Code/SynAnno/h01/synapse-export_000000000000.csv"
    )

    # Set up CV handles to the source and target volume
    source_cv = setup_cloud_volume(CONFIG["source_bucket_url"], CONFIG["cv_secret"])
    target_cv = setup_cloud_volume(CONFIG["target_bucket_url"], CONFIG["cv_secret"])

    vol_dim = retrieve_smallest_volume_dim(source_cv, target_cv)
    scale = compute_scale_factor(
        CONFIG["coord_resolution_target"], CONFIG["coord_resolution_source"]
    )

    meta_data = {
        "coordinate_order": CONFIG["coordinate_order"],
        "coord_resolution_source": CONFIG["coord_resolution_source"],
        "coord_resolution_target": CONFIG["coord_resolution_target"],
        "source_cv": source_cv,
        "target_cv": target_cv,
        "scale": scale,
        "vol_dim": vol_dim,
    }

    train_dataset = SynapseDataset(materialization_df, meta_data, (0, 2))

    # Retrieve a training sample
    sample = train_dataset[0]

    # Validate the shape
    assert sample[0].shape == (
        2,
        16,
        256,
        256,
    ), f"Sample input shape: {sample[0].shape}"
    assert sample[1].shape == (
        1,
        16,
        256,
        256,
    ), f"Sample target shape: {sample[1].shape}"

    # Validate the value ranges
    assert (
        torch.min(sample[0][0, :, :, :]) == 0.0
    ), f"Min value image channel: {torch.min(sample[0][0,:,:,:])}"
    assert (
        torch.max(sample[0][0, :, :, :]) == 1.0
    ), f"Max value image channel: {torch.max(sample[0][0,:,:,:])}"
    assert (
        len(torch.unique(sample[0][0, :, :, :])) > 1
    ), f"Number of unique values in the image channel: {torch.unique(sample[0][0,:,:,:])}"

    assert (
        torch.min(sample[0][1, :, :, :]) == 0.0
    ), f"Min value seed channel: {torch.min(sample[0][1,:,:,:])}"
    assert (
        torch.max(sample[0][1, :, :, :]) == 1.0
    ), f"Max value seed channel: {torch.max(sample[0][1,:,:,:])}"
    assert (
        len(torch.unique(sample[0][1, :, :, :])) == 2
    ), f"Number of unique values in the seed channel: {torch.unique(sample[0][1,:,:,:])}"
    assert (
        torch.sum(sample[0][1, :, :, :] > 0) > 0
    ), f"Number of non-zero values in the seed channel: {torch.sum(sample[0][1,:,:,:] > 0)}"

    assert (
        torch.min(sample[1][0, :, :, :]) == 0.0
    ), f"Min value target: {torch.min(sample[1][0,:,:,:])}"
    assert (
        torch.max(sample[1][0, :, :, :]) == 1.0
    ), f"Max value target: {torch.max(sample[1][0,:,:,:])}"
    assert (
        len(torch.unique(sample[1][0, :, :, :])) == 2
    ), f"Number of unique values in the target: {torch.unique(sample[1][0,:,:,:])}"
    assert (
        torch.sum(sample[1][0, :, :, :] > 0) > 0
    ), f"Number of non-zero values in the target sample: {torch.sum(sample[1][0,:,:,:] > 0)}"

    assert torch.sum(sample[0][1, :, :, :] > 0) < torch.sum(
        sample[1][0, :, :, :] > 0
    ), "The target should have more non-zero values than the seed channel."

    # Visualize the first non-zero seed segmentation slice
    visualize_instances(
        sample[0][0, :, :, :],
        (sample[0][1, :, :, :].numpy() * 255).astype(np.uint8),
        train_dataset.dataset[0]["selected_slices"][0],
        0,
    )
    visualize_instances(
        (sample[0][1, :, :, :].numpy() * 255).astype(np.uint8),
        (sample[1][0, :, :, :].numpy() * 255).astype(np.uint8),
        train_dataset.dataset[0]["selected_slices"][0],
        0,
    )
