from scipy.spatial import KDTree
import numpy as np
import logging
import os
import pandas as pd
from navis import TreeNeuron
import json

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)


def load_synapse_point_cloud(
    neuron_id: int, neuron: TreeNeuron, materialization_pd: pd.DataFrame, swc_path: str
) -> np.ndarray:
    """
    Load synapse point cloud, snap points to neuron skeleton, and save the results.

    Args:
        neuron_id (int): ID of the neuron.
        neuron (TreeNeuron): Neuron object containing the skeleton.
        materialization_pd (pd.DataFrame): DataFrame containing synapse information.
        swc_path (str): Path to save the output files.

    Returns:
        np.ndarray: Snapped points and the path to the saved JSON file.
    """
    neuron_coords = get_neuron_coordinates(neuron)
    filtered_df = filter_synapse_data(neuron_id, materialization_pd)
    point_cloud = convert_to_point_cloud(filtered_df)

    if point_cloud is None:
        return

    snapped_points = snap_points_to_neuron(neuron_coords, point_cloud)
    save_point_clouds(neuron_id, point_cloud, snapped_points, swc_path)

    return snapped_points, f"snapped_synapse_point_cloud_{neuron_id}.json"


def get_neuron_coordinates(neuron: TreeNeuron) -> np.ndarray:
    """
    Get the coordinates of the neuron nodes.

    Args:
        neuron (TreeNeuron): Neuron object containing the skeleton.

    Returns:
        np.ndarray: Array of neuron coordinates.
    """
    return neuron.nodes[["x", "y", "z"]].values


def filter_synapse_data(
    neuron_id: int, materialization_pd: pd.DataFrame
) -> pd.DataFrame:
    """
    Filter the synapse data for the given neuron ID.

    Args:
        neuron_id (int): ID of the neuron.
        materialization_pd (pd.DataFrame): DataFrame containing synapse information.

    Returns:
        pd.DataFrame: Filtered DataFrame containing synapse information for the given neuron ID.
    """
    return materialization_pd[
        (materialization_pd["pre_neuron_id"] == neuron_id)
        | (materialization_pd["post_neuron_id"] == neuron_id)
    ]


def convert_to_point_cloud(filtered_df: pd.DataFrame) -> np.ndarray:
    """
    Convert the filtered DataFrame to a point cloud.

    Args:
        filtered_df (pd.DataFrame): Filtered DataFrame containing synapse information.

    Returns:
        np.ndarray: Point cloud array.
    """
    try:
        return np.column_stack(
            (filtered_df["x"] * 8, filtered_df["y"] * 8, filtered_df["z"] * 33)
        )
    except KeyError as e:
        logger.error(
            f"Error: Column '{e}' not found in the DataFrame. Please check the column names."
        )
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        return None


def snap_points_to_neuron(
    neuron_coords: np.ndarray, point_cloud: np.ndarray
) -> np.ndarray:
    """
    Snap the points in the point cloud to the nearest neuron coordinates.

    Args:
        neuron_coords (np.ndarray): Array of neuron coordinates.
        point_cloud (np.ndarray): Array of point cloud coordinates.

    Returns:
        np.ndarray: Array of snapped points.
    """
    neuron_tree = KDTree(neuron_coords)
    _, indices = neuron_tree.query(point_cloud)
    return neuron_coords[indices]


def save_point_clouds(
    neuron_id: int, point_cloud: np.ndarray, snapped_points: np.ndarray, swc_path: str
) -> None:
    """
    Save the point cloud and snapped points to JSON files.

    Args:
        neuron_id (int): ID of the neuron.
        point_cloud (np.ndarray): Array of point cloud coordinates.
        snapped_points (np.ndarray): Array of snapped points.
        swc_path (str): Path to save the output files.
    """
    logger.info(f"Length of point cloud: {len(point_cloud)}")
    logger.info(f"Length of snapped points: {len(snapped_points)}")
    point_cloud_json = json.dumps([int(x) for x in point_cloud.flatten()])
    snapped_points_json = json.dumps([int(x) for x in snapped_points.flatten()])

    point_cloud_json_path = f"synapse_point_cloud_{neuron_id}.json"
    snapped_points_json_path = f"snapped_synapse_point_cloud_{neuron_id}.json"

    with open(os.path.join(swc_path, point_cloud_json_path), "w") as f:
        f.write(point_cloud_json)
    with open(os.path.join(swc_path, snapped_points_json_path), "w") as f:
        f.write(snapped_points_json)
