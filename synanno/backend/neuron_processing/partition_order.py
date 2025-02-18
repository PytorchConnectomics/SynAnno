import numpy as np
import pandas as pd
from scipy.spatial import KDTree


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
    # Step 1: Compute section positions in one pass
    section_positions = {
        section_idx: [
            tree_traversal.index(node) for node in section if node in tree_traversal
        ]
        for section_idx, section in enumerate(sections)
    }

    # Step 2: Compute mean traversal index for each section
    section_mean_positions = {
        sec: np.mean(pos_list)
        for sec, pos_list in section_positions.items()
        if pos_list
    }

    # Step 3: Sort sections by mean traversal index and return an ordered dict
    sorted_sections = sorted(
        section_mean_positions.keys(), key=lambda sec: section_mean_positions[sec]
    )

    # Step 4: Construct output dictionary with 1-based ranking
    section_order = {rank: sec for rank, sec in enumerate(sorted_sections)}

    return section_order


def assign_section_order_index(
    materialization_pd: pd.DataFrame,
    sections: list[list[int]],
    section_order: dict[int, int],
    neuron_tree: KDTree,
) -> None:
    """
    Assigns a section index and section order index to each row in the materialization DataFrame.

    Args:
        materialization_pd: DataFrame containing synapse information.
        sections: List of lists, where each inner list represents a section of nodes.
        section_order: Dictionary where keys are traversal order (1-based) and values are section indices.
        neuron_tree: KDTree of neuron coordinates.
    """
    for index, synapse in materialization_pd.iterrows():
        # Retrieve the x, y, z coordinates of the synapse
        synapse_coords = np.array([synapse["x"], synapse["y"], synapse["z"]])

        # Cluster the synapse coordinate using the neuron_tree
        _, node_id = neuron_tree.query(synapse_coords)

        # Derive a mapping from neuron node to section index
        section_idx, order_idx = neuron_section_lookup(sections, section_order)[node_id]

        # Update the materialization DataFrame with the section index and order index
        materialization_pd.at[index, "Section_Index"] = section_idx
        materialization_pd.at[index, "Section_Order_Index"] = order_idx


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
    neuron_section_lookup = {}

    # Create node to section mapping
    for i, section in enumerate(sections):
        for node_id in section:
            neuron_section_lookup[node_id] = (i, section_order[i])

    return neuron_section_lookup
