import numpy as np
from scipy.stats import norm


def pick_slice_based_on_range(
    volume_shape: tuple[int, int, int], target_range: tuple[int, int]
) -> int:
    """
    Pick a slice from the volume based on a Gaussian centered within the target range.

    Args:
        volume_shape: Shape of the volume as (x, y, z).
        target_range: Range of slices to consider as (start, end).

    Returns:
        The index of the selected slice.
    """
    z_dim = volume_shape[2]
    start, end = target_range

    if not (0 <= start < z_dim and 0 < end <= z_dim and start < end):
        raise ValueError("Target range is out of bounds or invalid.")

    range_center = (start + end) / 2
    sigma = (end - start) / 6  # Approx. 99.7% of values within the range

    probabilities = _generate_probabilities(z_dim, range_center, sigma, start, end)

    return np.random.choice(np.arange(z_dim), p=probabilities)


def _generate_probabilities(
    z_dim: int, range_center: float, sigma: float, start: int, end: int
) -> np.ndarray:
    """Generate probabilities for all slices in the volume."""
    z_indices = np.arange(z_dim)
    probabilities = norm.pdf(z_indices, loc=range_center, scale=sigma)
    probabilities[:start] = 0
    probabilities[end:] = 0
    probabilities /= probabilities.sum()
    return probabilities


def generate_seed_target(
    volume: np.ndarray, slices_to_generate: int, target_range: tuple[int, int]
) -> tuple[np.ndarray, list[int]]:
    """
    Generate the seed channel by masking a set number of slices in the target volume.

    Args:
        volume: The target volume of shape (x, y, z).
        slices_to_generate: Max number of slices to select and mask.
        target_range: Range of slices to consider as (start, end).

    Returns:
        A tuple containing the masked volume and the selected slices.
    """
    actual_slices_to_generate = _determine_slices_to_generate(slices_to_generate)
    selected_slices = _select_slices(
        volume.shape, target_range, actual_slices_to_generate
    )
    masked_volume = _create_masked_volume(volume, selected_slices)

    return masked_volume, selected_slices


def _determine_slices_to_generate(slices_to_generate: int) -> int:
    """Determine how many slices to generate."""
    slice_indices = np.arange(1, slices_to_generate + 1)
    slice_probs = norm.pdf(slice_indices, loc=1, scale=slices_to_generate / 3)
    slice_probs /= slice_probs.sum()
    return np.random.choice(slice_indices, p=slice_probs)


def _select_slices(
    volume_shape: tuple[int, int, int],
    target_range: tuple[int, int],
    slices_to_generate: int,
) -> list[int]:
    """Select the slices to include in the training sample."""
    selected_slices: list[int] = []
    while len(selected_slices) < slices_to_generate:
        selected_slice = pick_slice_based_on_range(volume_shape, target_range)
        if selected_slice not in selected_slices:
            selected_slices.append(selected_slice)
    return selected_slices


def _create_masked_volume(volume: np.ndarray, selected_slices: list[int]) -> np.ndarray:
    """Create a masked volume with all selected slices."""
    masked_volume = np.zeros_like(volume)
    for selected_slice in selected_slices:
        masked_volume[:, :, selected_slice] = volume[:, :, selected_slice]
    return masked_volume
