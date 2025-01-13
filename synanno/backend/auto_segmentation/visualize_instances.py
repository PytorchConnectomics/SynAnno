import numpy as np
import matplotlib.pyplot as plt


def visualize_instances(
    cropped_img_pad: np.ndarray,
    cropped_seg_pad: np.ndarray,
    slice_idx: int,
    axis: int = 0,
) -> None:
    """
    Visualize a single slice of the processed EM image and segmentation.

    Args:
        cropped_img_pad (np.ndarray): The padded EM image tensor.
        cropped_seg_pad (np.ndarray): The padded segmentation tensor.
        slice_idx (int): Index of the slice to visualize.
        axis (int): Axis along which to slice (0=x, 1=y, 2=z). Defaults to 0.
    """
    if axis == 0:
        img_slice = cropped_img_pad[slice_idx, :, :]
        seg_slice = cropped_seg_pad[slice_idx, :, :]
    elif axis == 1:
        img_slice = cropped_img_pad[:, slice_idx, :]
        seg_slice = cropped_seg_pad[:, slice_idx, :]
    elif axis == 2:
        img_slice = cropped_img_pad[:, :, slice_idx]
        seg_slice = cropped_seg_pad[:, :, slice_idx]
    else:
        raise ValueError("Axis must be 0, 1, or 2.")

    # Create the plot
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))

    # EM Image Slice
    axes[0].imshow(img_slice, cmap="gray")
    axes[0].set_title("Volume Slice")
    axes[0].axis("off")

    # Segmentation Slice
    axes[1].imshow(seg_slice, cmap="gray")
    axes[1].set_title("Volume Slice")
    axes[1].axis("off")

    plt.tight_layout()
    plt.show()
