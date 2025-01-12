import torch
from torch.utils.data import DataLoader
from typing import Optional, Union
from synanno.backend.auto_segmentation.unet_3d import UNet3D
from tqdm import tqdm
from synanno.backend.auto_segmentation.dataset import SynapseDataset
from synanno.backend.auto_segmentation.weighted_bce_with_logits_loss import (
    WeightedBCEWithLogitsLoss,
)
from synanno.backend.auto_segmentation.config import TRAINING_CONFIG
import os
import glob
import sys

import logging

logger = logging.getLogger(__name__)


class Trainer:
    def __init__(self):
        self.checkpoint_dir = TRAINING_CONFIG["checkpoints"]

        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)

    def load_model(self, model_path: Optional[str] = None) -> UNet3D:
        """
        Load the UNet3D model from the specified path or the best model based on the smallest validation loss if no path is provided.

        Args:
            model_path (Optional[str]): Path to the model file.

        Returns:
            UNet3D: Loaded UNet3D model.
        """
        model = UNet3D()

        logger.info("Checking for checkpoint...")
        if model_path is None:
            model_files = sorted(
                glob.glob(os.path.join(self.checkpoint_dir, "best_unet3d_tl_*.pth")),
                key=lambda x: float(x.split("_vl_")[1].split(".pth")[0]),
            )

            if model_files:
                model_path = model_files[
                    0
                ]  # Load the model with the smallest validation loss
                logger.info(
                    f"Loading best model based on validation loss: {model_path}"
                )

        if model_path and os.path.isfile(model_path):
            model.load_state_dict(torch.load(model_path))

        return model

    def save_best_model(
        self, model: torch.nn.Module, train_loss: float, val_loss: float
    ) -> None:
        """
        Saves the best model based on the training and validation loss. The model is saved with a filename
        that includes the decimal parts of the training and validation losses. If there are more than 3 models
        in the target directory, the oldest model is removed.

        Args:
            model (torch.nn.Module): The model to be saved.
            train_loss (float): The training loss of the model.
            val_loss (float): The validation loss of the model.
        """
        train_loss_decimal = f"{train_loss:.4f}".split(".")[1]
        val_loss_decimal = f"{val_loss:.4f}".split(".")[1]

        model_name = f"best_unet3d_tl_{train_loss_decimal}_vl_{val_loss_decimal}.pth"

        model_path = os.path.join(self.checkpoint_dir, model_name)

        # Remove the worst performing model if there are more than 3 models in the directory
        model_files = sorted(
            glob.glob(os.path.join(self.checkpoint_dir, "best_unet3d_tl_*.pth")),
            key=lambda x: float(x.split("_vl_")[1].split(".pth")[0]),
        )

        if len(model_files) >= 3:
            logger.info(f"Removing oldest model: {model_files[-1]}")
            os.remove(model_files[-1])

        # Save new model
        torch.save(model.state_dict(), model_path)
        logger.info(
            f"New best model {model_name} saved with validation loss: {val_loss:.4f}"
        )

    def run_training(
        self, train_dataset: SynapseDataset, val_dataset: SynapseDataset
    ) -> None:
        """Run the training process for the UNet3D model.

        Args:
            train_dataset (SynapseDataset): Training dataset.
            val_dataset (SynapseDataset): Validation dataset.
        """
        train_loader = DataLoader(
            train_dataset,
            batch_size=TRAINING_CONFIG["batch_size"],
            shuffle=True,
            num_workers=TRAINING_CONFIG["num_workers"],
        )
        val_loader = DataLoader(
            val_dataset,
            batch_size=TRAINING_CONFIG["batch_size"],
            shuffle=False,
            num_workers=TRAINING_CONFIG["num_workers"],
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = self.load_model()

        criterion = WeightedBCEWithLogitsLoss(
            pos_weight=torch.tensor(TRAINING_CONFIG["pos_weight"]).to(device)
        )
        optimizer = torch.optim.Adam(
            model.parameters(), lr=TRAINING_CONFIG["learning_rate"]
        )

        # Update the learning rate every nth epoch by gamma
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=TRAINING_CONFIG["scheduler_step_size"],
            gamma=TRAINING_CONFIG["schedular_gamma"],
        )

        num_epochs = TRAINING_CONFIG["num_epochs"]
        best_val_loss = float("inf")

        # Trigger early stop if not improvement for #patience epochs
        patience = TRAINING_CONFIG.get("patience", 5)
        patience_counter = 0

        for epoch in range(num_epochs):
            logger.info(f"Epoch {epoch + 1}/{num_epochs}")

            logger.info("Training pass...")
            train_loss = self.train(model, train_loader, criterion, optimizer, device)

            logger.info("validation pass...")
            val_loss = self.validate(model, val_loader, criterion, device)

            logger.info(
                f"Train Loss: {train_loss:.4f} | Validation Loss: {val_loss:.4f}"
            )

            if val_loss < best_val_loss:
                self.save_best_model(model, train_loss, val_loss)
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= patience:
                logger.info(
                    "Early stopping triggered due to no improvement in validation loss."
                )
                break

            scheduler.step()

    def run_inference(
        self, model_path: str, dataset: Union[SynapseDataset, list[torch.Tensor]]
    ) -> tuple[list[Optional[torch.Tensor]], list[torch.Tensor]]:
        """Run inference using the UNet3D model.

        Args:
            model_path (str): Path to the model file.
            dataset (Union[SynapseDataset, list[torch.Tensor]]): The dataset to run inference on.

        Returns:
            tuple[list[Optional[torch.Tensor]], list[torch.Tensor]]: Lists of target and prediction tensors.
        """
        model = self.load_model(model_path)

        if isinstance(dataset, SynapseDataset):
            test_loader = DataLoader(
                dataset,
                batch_size=TRAINING_CONFIG["batch_size"],
                shuffle=False,
                num_workers=TRAINING_CONFIG["num_workers"],
            )
        else:
            # add a dummy target entry, if the provided list does not contain tuples of (input, target) pairs
            if len(dataset) > 0 and isinstance(dataset[0], torch.Tensor):
                dataset = [(sample, None) for sample in dataset]
            test_loader = dataset

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()

        targets = []
        predictions = []

        with torch.no_grad():
            for inputs, target in tqdm(
                test_loader,
                desc="Inference",
                leave=False,
                disable=not sys.stdout.isatty(),
            ):
                inputs = inputs.to(device)
                outputs = model(inputs)
                outputs = torch.sigmoid(outputs)
                binary_mask = (outputs > 0.5).float()
                targets.append(target)
                predictions.append(binary_mask)

        return targets, predictions

    def train(
        self,
        model: UNet3D,
        dataloader: DataLoader,
        criterion: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        device: torch.device,
    ) -> float:
        """
        Train the model for one epoch.

        Args:
            model (UNet3D): The model to train.
            dataloader (DataLoader): DataLoader for the training data.
            criterion (torch.nn.Module): Loss function.
            optimizer (torch.optim.Optimizer): Optimizer.
            device (torch.device): Device to run the training on.

        Returns:
            float: Average training loss.
        """
        model.train()
        running_loss = 0.0

        for inputs, targets in tqdm(
            dataloader, desc="Training", leave=False, disable=not sys.stdout.isatty()
        ):
            inputs, targets = inputs.to(device), targets.to(device)

            # log the inputs and target shape
            logger.info(f"Input shape: {inputs.shape}")
            logger.info(f"Input targets: {targets.shape}")

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()

        return running_loss / len(dataloader)

    def validate(
        self,
        model: UNet3D,
        dataloader: DataLoader,
        criterion: torch.nn.Module,
        device: torch.device,
    ) -> float:
        """
        Validate the model.

        Args:
            model (UNet3D): The model to validate.
            dataloader (DataLoader): DataLoader for the validation data.
            criterion (torch.nn.Module): Loss function.
            device (torch.device): Device to run the validation on.

        Returns:
            float: Average validation loss.
        """
        model.eval()
        running_loss = 0.0
        with torch.no_grad():
            for inputs, targets in tqdm(
                dataloader,
                desc="Validation",
                leave=False,
                disable=not sys.stdout.isatty(),
            ):
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                running_loss += loss.item()

        return running_loss / len(dataloader)
