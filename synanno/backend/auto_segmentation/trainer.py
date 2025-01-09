import torch
from torch.utils.data import DataLoader
from typing import Optional
from synanno.backend.auto_segmentation.unet_3d import UNet3D
from tqdm import tqdm


def load_model(model_path: Optional[str]) -> UNet3D:
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


def train(
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


class WeightedBCEWithLogitsLoss(torch.nn.Module):
    """
    Weighted Binary Cross Entropy with Logits Loss.

    Args:
        pos_weight (float, optional): Weight for positive examples.
    """

    def __init__(self, pos_weight: Optional[float] = None):
        super(WeightedBCEWithLogitsLoss, self).__init__()
        self.loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    def forward(self, outputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for the loss function.

        Args:
            outputs (torch.Tensor): Model outputs.
            targets (torch.Tensor): Ground truth targets.

        Returns:
            torch.Tensor: Computed loss.
        """
        return self.loss_fn(outputs, targets)
