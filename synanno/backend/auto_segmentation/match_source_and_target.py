import numpy as np
from cloudvolume import CloudVolume
import logging

# Retrieve logger
logger = logging.getLogger(__name__)


def retrieve_smallest_volume_dim(
    source_cv: CloudVolume, target_cv: CloudVolume
) -> tuple:
    """
    Retrieve the smallest volume dimension from the source and target volumes.

    Args:
        source_cv (CloudVolume): The source cloud volume.
        target_cv (CloudVolume): The target cloud volume.

    Returns:
        tuple: The smallest volume dimension.
    """
    source_size = source_cv.volume_size
    target_size = target_cv.volume_size

    if list(source_size) == list(target_size):
        vol_dim = tuple([s - 1 for s in source_size])
    else:
        logger.info(
            f"The dimensions of the source ({source_size}) and target ({target_size}) volumes do not match. Using the smaller size of the two volumes."
        )
        vol_dim = tuple([s - 1 for s in min(source_size, target_size, key=np.prod)])

    return vol_dim


def compute_scale_factor(
    coord_resolution_target: np.ndarray, coord_resolution_source: np.ndarray
) -> dict:
    """
    Compute the scale factor for the source and target cloud volume.

    Args:
        coord_resolution_target (np.ndarray): The target coordinate resolution.
        coord_resolution_source (np.ndarray): The source coordinate resolution.

    Returns:
        dict: The scale factor for the source and target cloud volume.
    """
    scale = {
        c: v
        for c, v in zip(
            ["x", "y", "z"],
            np.where(
                coord_resolution_target / coord_resolution_source > 0,
                coord_resolution_target / coord_resolution_source,
                1,
            ),
        )
    }
    return scale
