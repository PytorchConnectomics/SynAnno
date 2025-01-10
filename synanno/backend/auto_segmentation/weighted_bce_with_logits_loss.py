import torch
from typing import Optional


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
