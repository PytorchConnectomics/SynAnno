import numpy as np
import pandas as pd
from scipy.spatial import KDTree


def compute_section_positions(
    tree_traversal: list[int], sections: list[list[int]]
) -> dict[int, list[int]]:
    """
    Assigns each node in a section its position in the tree traversal order.

    Args:
        tree_traversal: List of nodes in tree traversal order.
        sections: List of lists, where each inner list represents a section of nodes.

    Returns:
        Dictionary where keys are section indices and values are lists of positions in the tree traversal order.
    """
    return {
        section_idx: [tree_traversal.index(node) for node in section]
        for section_idx, section in enumerate(sections)
    }


def compute_mean_positions(section_positions: dict[int, list[int]]) -> dict[int, float]:
    """
    Computes the mean traversal index for each section.

    Args:
        section_positions: Dictionary where keys are section indices and values are lists of positions in the tree traversal order.

    Returns:
        Dictionary where keys are section indices and values are mean traversal indices.
    """
    return {sec: np.mean(pos_list) for sec, pos_list in section_positions.items()}


def sort_sections_by_mean_position(
    section_mean_positions: dict[int, float]
) -> list[int]:
    """
    Sorts sections by their mean traversal index.

    Args:
        section_mean_positions: Dictionary where keys are section indices and values are mean traversal indices.

    Returns:
        List of section indices sorted by mean traversal index.
    """
    return sorted(
        section_mean_positions.keys(), key=lambda sec: section_mean_positions[sec]
    )


def compute_section_order(
    tree_traversal: list[int], sections: list[list[int]]
) -> dict[int, int]:
    """
    Computes the order in which sections should be traversed based on
    the mean position of their nodes in the tree traversal order.

    Args:
        tree_traversal: List of nodes in tree traversal order.
        sections: List of lists, where each inner list represents a section of nodes.

    Returns:
        Dictionary where keys are traversal order (1-based) and values are section indices.
    """
    section_positions = compute_section_positions(tree_traversal, sections)
    section_mean_positions = compute_mean_positions(section_positions)
    sorted_sections = sort_sections_by_mean_position(section_mean_positions)
    section_order = {sec: rank for rank, sec in enumerate(sorted_sections)}

    # again sort by section
    section_order = dict(sorted(section_order.items()))

    return section_order


def assign_section_order_index(
    materialization_pd: pd.DataFrame,
    neuron_section_lookup: dict[int, tuple[int, int]],
    neuron_tree: KDTree,
) -> None:
    """
    Assigns a section index and section order index to each row in the materialization DataFrame.

    Args:
        materialization_pd: DataFrame containing synapse information.
        neuron_section_lookup: Dictionary where keys are neuron node IDs and values are tuples of section index and section order index.
        neuron_tree: KDTree of neuron coordinates.
    """
    for index, synapse in materialization_pd.iterrows():
        synapse_coords = np.array(
            (synapse["x"] * 8, synapse["y"] * 8, synapse["z"] * 33)
        )
        _, node_id = neuron_tree.query(synapse_coords)
        section_idx, order_idx = neuron_section_lookup[node_id]
        materialization_pd.at[index, "section_index"] = int(section_idx)
        materialization_pd.at[index, "section_order_index"] = int(order_idx)

    # Convert to Python int for later JSON serialization
    materialization_pd["section_index"] = materialization_pd["section_index"].astype(
        int
    )
    materialization_pd["section_order_index"] = materialization_pd[
        "section_order_index"
    ].astype(int)


def neuron_section_lookup(
    sections: list[list[int]], section_order: dict[int, int]
) -> dict[int, tuple[int, int]]:
    """
    Match each neuron with a section index and section order index.

    Args:
        sections: List of lists, where each inner list represents a section of nodes.
        section_order: Dictionary where keys are traversal order (1-based) and values are section indices.

    Returns:
        Dictionary where keys are neuron node IDs and values are tuples of section index and section order index.
    """
    lookup = {}
    for section_index, section in enumerate(sections):
        for node_id in section:
            section_order_index = section_order[section_index]
            lookup[node_id] = (section_index, section_order_index)

    return lookup
