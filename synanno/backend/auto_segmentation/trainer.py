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


class Trainer:
    def __init__(self):
        pass

    def load_model(self, model_path: Optional[str]) -> UNet3D:
        """
        Load the UNet3D model from the specified path.

        Args:
            model_path (Optional[str]): Path to the model file.

        Returns:
            UNet3D: Loaded UNet3D model.
        """
        model = UNet3D()
        if model_path is not None:
            model.load_state_dict(torch.load(model_path))
        return model

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
        model = self.load_model(TRAINING_CONFIG["model_path"])

        criterion = WeightedBCEWithLogitsLoss(
            pos_weight=torch.tensor(TRAINING_CONFIG["pos_weight"]).to(device)
        )
        optimizer = torch.optim.Adam(
            model.parameters(), lr=TRAINING_CONFIG["learning_rate"]
        )

        num_epochs = TRAINING_CONFIG["num_epochs"]
        best_val_loss = float("inf")

        for epoch in range(num_epochs):
            print(f"Epoch {epoch + 1}/{num_epochs}")

            train_loss = self.train(model, train_loader, criterion, optimizer, device)
            val_loss = self.validate(model, val_loader, criterion, device)

            print(f"Train Loss: {train_loss:.4f} | Validation Loss: {val_loss:.4f}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss

                train_loss_decimal = str(train_loss).split(".")[1]
                val_loss_decimal = str(val_loss).split(".")[1]
                model_name = (
                    f"best_unet3d_tl_{train_loss_decimal}_vl_{val_loss_decimal}.pth"
                )

                torch.save(model.state_dict(), model_name)
                print(
                    f"New best model {model_name} saved with validation loss: {val_loss:.4f}"
                )

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
            if isinstance(dataset[0], torch.Tensor):
                dataset = [(sample, None) for sample in dataset]
            test_loader = dataset

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

        for inputs, targets in tqdm(dataloader, desc="Training", leave=False):
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
            for inputs, targets in tqdm(dataloader, desc="Validation", leave=False):
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)
                running_loss += loss.item()

        return running_loss / len(dataloader)
