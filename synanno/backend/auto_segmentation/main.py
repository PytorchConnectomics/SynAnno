import pandas as pd
import torch
from torch.utils.data import DataLoader
from synanno.backend.auto_segmentation.dataset import SynapseDataset
from synanno.backend.auto_segmentation.config import CONFIG
from synanno.backend.auto_segmentation.match_source_and_target import (
    retrieve_smallest_volume_dim,
    compute_scale_factor,
)
from synanno.backend.auto_segmentation.retrieve_instances import setup_cloud_volume
from synanno.backend.auto_segmentation.visualize_instances import visualize_instances
from synanno.backend.auto_segmentation.trainer import (
    load_model,
    train,
    validate,
    WeightedBCEWithLogitsLoss,
)
from tqdm import tqdm
from cloudvolume import CloudVolume
import datetime
from typing import Any


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


def run_training() -> None:
    """Main function to train and validate the model."""
    materialization_df = load_materialization_csv(
        "/Users/lando/Code/SynAnno/h01/synapse-export_000000000000.csv"
    )
    source_cv, target_cv = setup_cloud_volumes()
    meta_data = prepare_metadata(source_cv, target_cv)

    print("Loading training dataset...")
    train_dataset = SynapseDataset(materialization_df, meta_data, (0, 2))

    print("Loading validation dataset...")
    val_dataset = SynapseDataset(materialization_df, meta_data, (2, 4))

    train_loader = DataLoader(train_dataset, batch_size=1, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=1, shuffle=False, num_workers=4)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model("best_unet3d.pth")

    criterion = WeightedBCEWithLogitsLoss(pos_weight=torch.tensor(4.0).to(device))
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

    num_epochs = 20
    best_val_loss = float("inf")

    for epoch in range(num_epochs):
        print(f"Epoch {epoch + 1}/{num_epochs}")

        train_loss = train(model, train_loader, criterion, optimizer, device)
        val_loss = validate(model, val_loader, criterion, device)

        print(f"Train Loss: {train_loss:.4f} | Validation Loss: {val_loss:.4f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            # add a date to the saved model path
            torch.save(
                model.state_dict(),
                f"best_unet3d_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pth",
            )
            print(f"New best model saved with validation loss: {val_loss:.4f}")


def run_inference() -> None:
    """Run inference using the UNet3D model."""
    model = load_model("best_unet3d.pth")
    materialization_df = load_materialization_csv(
        "/Users/lando/Code/SynAnno/h01/synapse-export_000000000000.csv"
    )
    source_cv, target_cv = setup_cloud_volumes()
    meta_data = prepare_metadata(source_cv, target_cv)

    test_dataset = SynapseDataset(materialization_df, meta_data, (0, 4))
    test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False, num_workers=4)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()

    targets = []
    predictions = []

    with torch.no_grad():
        for inputs, target in tqdm(test_loader, desc="Inference", leave=False):
            inputs = inputs.to(device)
            outputs = model(inputs)

            outputs = torch.sigmoid(outputs)
            binary_mask = (outputs > 0.5).float()

            targets.append(target)
            predictions.append(binary_mask)

    for tar, pred in zip(targets, predictions):
        visualize_instances(tar[0, 0, :, :, :], pred[0, 0, :, :, :], 5, 0)
        visualize_instances(tar[0, 0, :, :, :], pred[0, 0, :, :, :], 6, 0)
        visualize_instances(tar[0, 0, :, :, :], pred[0, 0, :, :, :], 7, 0)
        visualize_instances(tar[0, 0, :, :, :], pred[0, 0, :, :, :], 8, 0)
        visualize_instances(tar[0, 0, :, :, :], pred[0, 0, :, :, :], 9, 0)
        visualize_instances(tar[0, 0, :, :, :], pred[0, 0, :, :, :], 10, 0)


if __name__ == "__main__":
    # run_training()
    run_inference()
