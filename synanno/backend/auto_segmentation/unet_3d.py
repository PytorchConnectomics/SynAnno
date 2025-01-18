import torch
import torch.nn as nn
from torchsummary import summary
from synanno.backend.auto_segmentation.config import get_config

CONFIG = get_config()


class ConvBlock(nn.Module):
    """Basic convolutional block with two 3D convolutions, batch normalization, and ReLU."""

    def __init__(self, in_channels: int, out_channels: int):
        """
        Initialize the ConvBlock.

        Args:
            in_channels (int): Number of input channels.
            out_channels (int): Number of output channels.
        """
        super(ConvBlock, self).__init__()
        self.conv = nn.Sequential(
            nn.Conv3d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv3d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm3d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the ConvBlock.

        Args:
            x (torch.Tensor): Input tensor.

        Returns:
            torch.Tensor: Output tensor.
        """
        return self.conv(x)


class DownBlock(nn.Module):
    """Downsampling block with strided convolution followed by a ConvBlock."""

    def __init__(self, in_channels: int, out_channels: int):
        """
        Initialize the DownBlock.

        Args:
            in_channels (int): Number of input channels.
            out_channels (int): Number of output channels.
        """
        super(DownBlock, self).__init__()
        self.block = nn.Sequential(
            nn.MaxPool3d(kernel_size=2),
            ConvBlock(in_channels, out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the DownBlock.

        Args:
            x (torch.Tensor): Input tensor.

        Returns:
            torch.Tensor: Output tensor.
        """
        return self.block(x)


class UpBlock(nn.Module):
    """Upsampling block with concatenation and ConvBlock."""

    def __init__(self, in_channels: int, out_channels: int, bilinear: bool = True):
        """
        Initialize the UpBlock.

        Args:
            in_channels (int): Number of input channels.
            out_channels (int): Number of output channels.
            bilinear (bool): Whether to use bilinear upsampling. Defaults to True.
        """
        super(UpBlock, self).__init__()

        # Determine upsampling method
        if bilinear:
            self.up = nn.Upsample(scale_factor=2, mode="trilinear", align_corners=True)
            up_channels = in_channels
        else:
            self.up = nn.ConvTranspose3d(
                in_channels, out_channels, kernel_size=2, stride=2
            )
            up_channels = out_channels

        # After upsampling, concatenate with skip connection and apply ConvBlock
        self.conv = ConvBlock(up_channels + out_channels, out_channels)

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the UpBlock.

        Args:
            x1 (torch.Tensor): Input tensor from the previous layer.
            x2 (torch.Tensor): Input tensor from the skip connection.

        Returns:
            torch.Tensor: Output tensor.
        """
        x1 = self.up(x1)

        # Padding to match dimensions if needed
        diffZ = x2.size(2) - x1.size(2)
        diffY = x2.size(3) - x1.size(3)
        diffX = x2.size(4) - x1.size(4)
        x1 = nn.functional.pad(
            x1,
            [
                diffX // 2,
                diffX - diffX // 2,
                diffY // 2,
                diffY - diffY // 2,
                diffZ // 2,
                diffZ - diffZ // 2,
            ],
        )

        # Concatenate along the channel dimension
        x = torch.cat([x2, x1], dim=1)
        return self.conv(x)


class OutputConv(nn.Module):
    """Final output convolution to map to the desired number of channels."""

    def __init__(self, in_channels: int, out_channels: int):
        """
        Initialize the OutputConv.

        Args:
            in_channels (int): Number of input channels.
            out_channels (int): Number of output channels.
        """
        super(OutputConv, self).__init__()
        self.conv = nn.Conv3d(in_channels, out_channels, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the OutputConv.

        Args:
            x (torch.Tensor): Input tensor.

        Returns:
            torch.Tensor: Output tensor.
        """
        return self.conv(x)


class UNet3D(nn.Module):
    """3D U-Net model with encoder-decoder architecture."""

    def __init__(self):
        """
        Initialize the UNet3D model.
        """
        super(UNet3D, self).__init__()
        in_channels = CONFIG["UNET3D_CONFIG"]["in_channels"]
        out_channels = CONFIG["UNET3D_CONFIG"]["out_channels"]
        bilinear = CONFIG["UNET3D_CONFIG"]["bilinear"]
        features = CONFIG["UNET3D_CONFIG"]["features"]

        self.inc = ConvBlock(in_channels, features[0])
        self.down_blocks = nn.ModuleList(
            [DownBlock(features[i], features[i + 1]) for i in range(len(features) - 1)]
        )
        self.up_blocks = nn.ModuleList(
            [
                UpBlock(features[i + 1], features[i], bilinear)
                for i in reversed(range(len(features) - 1))
            ]
        )
        self.outc = OutputConv(features[0], out_channels)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the UNet3D.

        Args:
            x (torch.Tensor): Input tensor.

        Returns:
            torch.Tensor: Output tensor.
        """
        encoder_outputs = []
        x1 = self.inc(x)
        encoder_outputs.append(x1)

        for down in self.down_blocks:
            x1 = down(x1)
            encoder_outputs.append(x1)

        x1 = encoder_outputs.pop()
        for up in self.up_blocks:
            x1 = up(x1, encoder_outputs.pop())

        return self.outc(x1)


if __name__ == "__main__":
    # Device setup
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Initialize Model
    model = UNet3D().to(device)

    # Test Input
    input_tensor = torch.randn(1, 2, 16, 256, 256).to(
        device
    )  # Batch size 1, 2 channels, depth 16, 256x256 resolution

    # Forward Pass
    output = model(input_tensor)

    assert output.shape == (
        1,
        1,
        16,
        256,
        256,
    ), f"Output shape mismatch - {output.shape}"

    summary(model, input_size=(2, 16, 256, 256))
