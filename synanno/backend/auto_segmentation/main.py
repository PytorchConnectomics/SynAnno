import pandas as pd
from synanno.backend.auto_segmentation.dataset import SynapseDataset, RandomRotation90
from synanno.backend.auto_segmentation.match_source_and_target import (
    retrieve_smallest_volume_dim,
    compute_scale_factor,
)
from synanno.backend.auto_segmentation.retrieve_instances import setup_cloud_volume
from synanno.backend.auto_segmentation.visualize_instances import visualize_instances
from synanno.backend.auto_segmentation.trainer import Trainer
from synanno.backend.auto_segmentation.config import get_config
from cloudvolume import CloudVolume
from typing import Any
import logging
import os
import torchvision.transforms as transforms

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


CONFIG = get_config()


def load_materialization_csv(csv_path: str) -> pd.DataFrame:
    """Load the materialization CSV file into a DataFrame."""
    return pd.read_csv(csv_path)


def setup_cloud_volumes() -> tuple[CloudVolume, CloudVolume]:
    """Set up CloudVolume handles for the source and target volumes."""
    source_cv = setup_cloud_volume(CONFIG["source_bucket_url"], CONFIG["cv_secret"])
    target_cv = setup_cloud_volume(CONFIG["target_bucket_url"], CONFIG["cv_secret"])
    return source_cv, target_cv


def prepare_metadata(source_cv, target_cv) -> dict[str, Any]:
    """Prepare metadata required for processing."""
    vol_dim = retrieve_smallest_volume_dim(source_cv, target_cv)
    scale = compute_scale_factor(
        CONFIG["coord_resolution_target"], CONFIG["coord_resolution_source"]
    )
    return {
        "coordinate_order": CONFIG["coordinate_order"],
        "coord_resolution_source": CONFIG["coord_resolution_source"],
        "coord_resolution_target": CONFIG["coord_resolution_target"],
        "source_cv": source_cv,
        "target_cv": target_cv,
        "scale": scale,
        "vol_dim": vol_dim,
    }


if __name__ == "__main__":
    """Main function to train and validate the model."""
    materialization_df = load_materialization_csv(CONFIG["materialization_csv"])
    source_cv, target_cv = setup_cloud_volumes()
    meta_data = prepare_metadata(source_cv, target_cv)
    trainer = Trainer()

    # Define the transformations
    data_transforms = transforms.Compose(
        [
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            RandomRotation90(),
        ]
    )

    if os.environ["EXECUTION_ENV"] == "slurm":
        logger.info("Loading training dataset...")
        train_dataset = SynapseDataset(
            materialization_df,
            meta_data,
            CONFIG["TRAINING_CONFIG"]["train_range"],
            CONFIG["TRAINING_CONFIG"]["select_nr_train_samples"],
            transform=data_transforms,
        )

        logger.info("Loading validation dataset...")
        val_dataset = SynapseDataset(
            materialization_df,
            meta_data,
            CONFIG["TRAINING_CONFIG"]["val_range"],
            CONFIG["TRAINING_CONFIG"]["select_nr_val_samples"],
            transform=data_transforms,
        )

        logger.info("Running training process...")
        trainer.run_training(train_dataset, val_dataset)

        logger.info("Finished Training.")
    elif os.environ["EXECUTION_ENV"] == "local":
        logger.info("Loading test dataset...")

        test_dataset = SynapseDataset(
            materialization_df, meta_data, CONFIG["TRAINING_CONFIG"]["test_range"]
        )
        logger.info("Running inference...")
        targets, predictions = trainer.run_inference(
            CONFIG["TRAINING_CONFIG"]["checkpoints"], test_dataset
        )

        logger.info("Visual result validation...")
        for tar, pred in zip(targets, predictions):
            for i in range(5, 11):
                visualize_instances(tar[0, 0, :, :, :], pred[0, 0, :, :, :], i, 0)
