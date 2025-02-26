import json
import logging
import os

import numpy as np
import pandas as pd
from navis import TreeNeuron
from scipy.spatial import KDTree

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)


def get_neuron_coordinates(neuron: TreeNeuron) -> np.ndarray:
    """
    Get the coordinates of the neuron nodes.

    Args:
        neuron: Neuron object containing the skeleton.

    Returns:
        Array of neuron coordinates.
    """
    return neuron.nodes[["x", "y", "z"]].values


def filter_synapse_data(
    neuron_id: int, materialization_pd: pd.DataFrame
) -> pd.DataFrame:
    """
    Filter the synapse data for the given neuron ID.

    Args:
        neuron_id: ID of the neuron.
        materialization_pd: DataFrame containing synapse information.

    Returns:
        Filtered DataFrame containing synapse info for the given neuron ID.
    """
    return materialization_pd[
        (materialization_pd["pre_neuron_id"] == neuron_id)
        | (materialization_pd["post_neuron_id"] == neuron_id)
    ]


def convert_to_point_cloud(filtered_df: pd.DataFrame) -> np.ndarray:
    """
    Convert the filtered DataFrame to a point cloud.

    Args:
        filtered_df: Filtered DataFrame containing synapse information.

    Returns:
        Point cloud array.
    """
    try:
        return np.column_stack(
            (filtered_df["x"] * 8, filtered_df["y"] * 8, filtered_df["z"] * 33)
        )
    except KeyError as e:
        logger.error(
            f"Error: Column '{e}' not found in the DataFrame. "
            "Please check the column names."
        )
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None


def create_neuron_tree(neuron_coords: np.ndarray) -> KDTree:
    """
    Create a KDTree from the neuron coordinates.

    Args:
        neuron_coords: Array of neuron coordinates.

    Returns:
        KDTree object for the neuron coordinates.
    """
    return KDTree(neuron_coords)


def snap_points_to_neuron(point_cloud: np.ndarray, neuron_tree: KDTree) -> np.ndarray:
    """
    Snap the points in the point cloud to the nearest neuron coordinates.

    Args:
        point_cloud: Array of point cloud coordinates.
        neuron_tree: KDTree object for the neuron coordinates.

    Returns:
        The indices of the nearest neuron coordinates for each point in the point cloud.
    """
    _, indices = neuron_tree.query(point_cloud)
    assert len(indices) == len(
        point_cloud
    ), f"Length mismatch: {len(indices)} != {len(point_cloud)}"
    return indices


def save_point_clouds(
    neuron_id: int, point_cloud: np.ndarray, snapped_points: np.ndarray, swc_path: str
) -> None:
    """
    Save the point cloud and snapped points to JSON files.

    Args:
        neuron_id: ID of the neuron.
        point_cloud: Array of point cloud coordinates.
        snapped_points: Array of snapped points.
        swc_path: Path to save the output files.

    Returns:
        Tuple of the file names for the saved JSON files.
    """
    logger.info(f"Length of point cloud: {len(point_cloud)}")
    logger.info(f"Length of snapped points: {len(snapped_points)}")
    point_cloud_json = json.dumps([int(x) for x in point_cloud.flatten()])
    snapped_points_json = json.dumps([int(x) for x in snapped_points.flatten()])

    point_cloud_json_file_name = f"synapse_point_cloud_{neuron_id}.json"
    snapped_points_json_file_name = f"snapped_synapse_point_cloud_{neuron_id}.json"

    with open(os.path.join(swc_path, point_cloud_json_file_name), "w") as f:
        f.write(point_cloud_json)
    with open(os.path.join(swc_path, snapped_points_json_file_name), "w") as f:
        f.write(snapped_points_json)

    return point_cloud_json_file_name, snapped_points_json_file_name


def neuron_section_lookup(
    sections: list[list[int]], node_tree_traversal_mapping: dict[int, int]
) -> dict[int, tuple[int, int]]:
    """
    Match each neuron with a section, section order, and tree traversal order index.

    Args:
        sections: List of lists, where each inner list represents a section of nodes.
        node_tree_traversal_mapping: Dict mapping nodes IDs to their
            tree traversal order index.

    Returns:
        Dict where keys are neuron node IDs and values are tuples
        of section index and section order index.
    """
    # Build the lookup table
    lookup = {}
    for section_index, section in enumerate(sections):
        for node_id in section:
            lookup[node_id] = (
                section_index,
                node_tree_traversal_mapping.get(node_id, -1),
            )  # -1 if missing

    return lookup
