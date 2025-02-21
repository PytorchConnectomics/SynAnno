import numpy as np
from scipy.stats import norm


def pick_slice_based_on_range(
    volume_shape: tuple[int, int, int], target_range: tuple[int, int]
) -> int:
    """
    Pick a slice from the volume based on a Gaussian distribution centered within the target range.

    Args:
        volume_shape (tuple[int, int, int]): Shape of the volume as (x, y, z).
        target_range (tuple[int, int]): Range of slices to consider as (start, end).

    Returns:
        int: The index of the selected slice.
    """
    z_dim = volume_shape[2]
    start, end = target_range

    if not (0 <= start < z_dim and 0 < end <= z_dim and start < end):
        raise ValueError("Target range is out of bounds or invalid.")

    range_center = (start + end) / 2
    sigma = (end - start) / 6  # Approx. 99.7% of values within the range

    # Generate probabilities for all slices in the volume
    z_indices = np.arange(z_dim)
    probabilities = norm.pdf(z_indices, loc=range_center, scale=sigma)

    # Restrict probabilities to the target range
    probabilities[:start] = 0
    probabilities[end:] = 0

    # Normalize probabilities
    probabilities /= probabilities.sum()

    # Pick a slice based on the probabilities
    return np.random.choice(z_indices, p=probabilities)


def generate_seed_target(
    volume: np.ndarray, slices_to_generate: int, target_range: tuple[int, int]
) -> tuple[np.ndarray, list[int]]:
    """
    Generate the seed channel by masking a set number of slices in the target volume.

    Args:
        volume (np.ndarray): The target volume of shape (x, y, z).
        slices_to_generate (int): Maximum number of slices to select and mask (0 to slices_to_generate).
        target_range (tuple[int, int]): Range of slices to consider as (start, end).

    Returns:
        tuple[np.ndarray, list[int]]: A tuple containing the masked volume and the selected slices.
    """

    # Create probabilities for the number of slices to generate
    slice_indices = np.arange(0, slices_to_generate + 1)
    slice_probs = norm.pdf(slice_indices, loc=1, scale=slices_to_generate / 3)
    slice_probs /= slice_probs.sum()

    # Determine how many slices to generate
    actual_slices_to_generate = np.random.choice(slice_indices, p=slice_probs)

    # Select the slices to include in the training sample
    selected_slices = []
    while len(selected_slices) < actual_slices_to_generate:
        selected_slice = pick_slice_based_on_range(volume.shape, target_range)
        if selected_slice not in selected_slices:
            selected_slices.append(selected_slice)

    # Create a masked volume with all selected slices
    masked_volume = np.zeros_like(volume)
    for selected_slice in selected_slices:
        masked_volume[:, :, selected_slice] = volume[:, :, selected_slice]

    return masked_volume, selected_slices
