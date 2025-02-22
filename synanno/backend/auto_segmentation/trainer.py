import glob
import logging
import os
import sys
from typing import Optional, Union

import torch
from torch.utils.data import DataLoader
from tqdm import tqdm

from synanno.backend.auto_segmentation.config import get_config
from synanno.backend.auto_segmentation.dataset import SynapseDataset
from synanno.backend.auto_segmentation.unet_3d import UNet3D
from synanno.backend.auto_segmentation.weighted_bce_with_logits_loss import (
    WeightedBCEWithLogitsLoss,
)

logger = logging.getLogger(__name__)


CONFIG = get_config()


class Trainer:
    def __init__(self) -> None:
        self.checkpoint_dir = CONFIG["TRAINING_CONFIG"]["checkpoints"]
        self._ensure_checkpoint_dir()

    def _ensure_checkpoint_dir(self) -> None:
        """Ensure the checkpoint directory exists."""
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)

    def load_model(self, model_path: Optional[str] = None) -> UNet3D:
        """
        Load the UNet3D model from the specified path or the best model based on
        the smallest validation loss if no path is provided.

        Args:
            model_path: Path to the model file.

        Returns:
            Loaded UNet3D model.
        """
        model = UNet3D()
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)

        logger.info("Checking for checkpoint...")
        if model_path is not None:
            model_path = self._get_best_model_path(model_path)
            if os.path.isfile(model_path):
                logger.info(f"Loading model: {model_path}")
                model.load_state_dict(torch.load(model_path, map_location=device))

        return model

    def _get_best_model_path(self, model_path: str) -> str:
        """Get the best model path based on the smallest validation loss."""
        if os.path.isdir(model_path):
            model_files = sorted(
                glob.glob(os.path.join(self.checkpoint_dir, "best_unet3d_tl_*.pth")),
                key=lambda x: float(x.split("_vl_")[1].split(".pth")[0]),
            )
            if model_files:
                model_path = model_files[0]
                logger.info(
                    f"Loading best model based on validation loss: {model_path}"
                )
        return model_path

    def save_best_model(
        self, model: torch.nn.Module, train_loss: float, val_loss: float
    ) -> None:
        """
        Saves the best model based on the training and validation loss. The model
        is saved with a filename that includes the decimal parts of the training
        and validation losses. If there are more than 3 models in the target
        directory, the oldest model is removed.

        Args:
            model: The model to be saved.
            train_loss: The training loss of the model.
            val_loss: The validation loss of the model.
        """
        model_name = self._generate_model_name(train_loss, val_loss)
        model_path = os.path.join(self.checkpoint_dir, model_name)

        self._remove_oldest_model_if_needed()
        torch.save(model.state_dict(), model_path)
        logger.info(
            f"New best model {model_name} saved with validation loss: {val_loss:.4f}"
        )

    def _generate_model_name(self, train_loss: float, val_loss: float) -> str:
        """Generate the model name based on training and validation loss."""
        train_loss_decimal = f"{train_loss:.4f}".split(".")[1]
        val_loss_decimal = f"{val_loss:.4f}".split(".")[1]
        return f"best_unet3d_tl_{train_loss_decimal}_vl_{val_loss_decimal}.pth"

    def _remove_oldest_model_if_needed(self) -> None:
        """Remove the oldest model if there are more than 3 models in the directory."""
        model_files = sorted(
            glob.glob(os.path.join(self.checkpoint_dir, "best_unet3d_tl_*.pth")),
            key=lambda x: float(x.split("_vl_")[1].split(".pth")[0]),
        )
        if len(model_files) >= 3:
            logger.info(f"Removing oldest model: {model_files[-1]}")
            os.remove(model_files[-1])

    def run_training(
        self, train_dataset: SynapseDataset, val_dataset: SynapseDataset
    ) -> None:
        """
        Run the training process for the UNet3D model.

        Args:
            train_dataset: Training dataset.
            val_dataset: Validation dataset.
        """
        train_loader = self._create_dataloader(train_dataset, shuffle=True)
        val_loader = self._create_dataloader(val_dataset, shuffle=False)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = self.load_model(self.checkpoint_dir)

        criterion = WeightedBCEWithLogitsLoss(
            pos_weight=torch.tensor(CONFIG["TRAINING_CONFIG"]["pos_weight"]).to(device)
        )
        optimizer = torch.optim.Adam(
            model.parameters(), lr=CONFIG["TRAINING_CONFIG"]["learning_rate"]
        )
        scheduler = self._create_scheduler(optimizer)

        num_epochs = CONFIG["TRAINING_CONFIG"]["num_epochs"]
        best_val_loss = float("inf")
        patience = CONFIG["TRAINING_CONFIG"].get("patience", 5)
        patience_counter = 0

        for epoch in range(num_epochs):
            logger.info(f"Epoch {epoch + 1}/{num_epochs}")
            logger.info(f"Current Learning Rate: {optimizer.param_groups[0]['lr']}")

            logger.info("Training pass...")
            train_loss = self.train(model, train_loader, criterion, optimizer, device)

            logger.info("Validation pass...")
            val_loss = self.validate(model, val_loader, criterion, device)
            scheduler.step(val_loss)

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

    def _create_dataloader(self, dataset: SynapseDataset, shuffle: bool) -> DataLoader:
        """Create a DataLoader for the given dataset."""
        return DataLoader(
            dataset,
            batch_size=CONFIG["TRAINING_CONFIG"]["batch_size"],
            shuffle=shuffle,
            num_workers=CONFIG["TRAINING_CONFIG"]["num_workers"],
        )

    def _create_scheduler(
        self, optimizer: torch.optim.Optimizer
    ) -> torch.optim.lr_scheduler.ReduceLROnPlateau:
        """Create a learning rate scheduler."""
        return torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=CONFIG["TRAINING_CONFIG"]["scheduler_gamma"],
            patience=CONFIG["TRAINING_CONFIG"]["scheduler_patience"],
            threshold=CONFIG["TRAINING_CONFIG"].get("scheduler_threshold", 1e-4),
            verbose=True,
        )

    def run_inference(
        self,
        model_path: str,
        dataset: Union[SynapseDataset, list[torch.Tensor]],
    ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """Run inference using the UNet3D model.

        Args:
            model_path: Path to the model file.
            dataset: The dataset to run inference on.

        Returns:
            Lists of target and prediction tensors.
        """
        model = self.load_model(model_path)

        if isinstance(dataset, SynapseDataset):
            test_loader = self._create_dataloader(dataset, shuffle=False)
        else:
            test_loader = self._prepare_test_loader(dataset)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()

        predictions, targets = self._run_inference_loop(model, test_loader, device)

        return predictions, targets

    def _prepare_test_loader(
        self, dataset: list[torch.Tensor]
    ) -> list[tuple[torch.Tensor, Optional[torch.Tensor]]]:
        """Prepare the test loader for inference."""
        if len(dataset) > 0 and isinstance(dataset[0], torch.Tensor):
            dataset = [(sample, None) for sample in dataset]
        return dataset

    def _run_inference_loop(
        self,
        model: UNet3D,
        test_loader: Union[DataLoader, list[tuple[torch.Tensor, torch.Tensor]]],
        device: torch.device,
    ) -> tuple[list[torch.Tensor], list[torch.Tensor]]:
        """Run the inference loop."""
        predictions: list[torch.Tensor] = []
        targets: list[torch.Tensor] = []

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

                predictions.append(binary_mask)
                targets.append(target)

        return predictions, targets

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
            model: The model to train.
            dataloader: DataLoader for the training data.
            criterion: Loss function.
            optimizer: Optimizer.
            device: Device to run the training on.

        Returns:
            Average training loss.
        """
        model.train()
        running_loss = 0.0

        for inputs, targets in tqdm(
            dataloader,
            desc="Training",
            leave=False,
            disable=not sys.stdout.isatty(),
        ):
            inputs, targets = inputs.to(device), targets.to(device)

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
            model: The model to validate.
            dataloader: DataLoader for the validation data.
            criterion: Loss function.
            device: Device to run the validation on.

        Returns:
            Average validation loss.
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
