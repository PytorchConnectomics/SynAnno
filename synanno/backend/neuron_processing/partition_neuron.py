import logging

import navis
import networkx as nx
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def compute_sections(
    pruned_swc_file: str, merge: bool = True
) -> tuple[list[list[int]], navis.TreeNeuron, dict[int, int]]:
    """Compute the sections of the pruned neuron.

    Args:
        pruned_swc_file: The path to the pruned SWC file.
        merge: Whether to merge the segments.

    Returns:
        The merged segments of the neuron, the tree traversal order,
        the pruned neuron, and the node traversal lookup.
    """
    neuron_pruned = navis.read_swc(pruned_swc_file, write_meta=True)
    undirected_graph = convert_to_undirected_graph(neuron_pruned)
    center_node = find_center_node(neuron_pruned, undirected_graph)
    tree_traversal, node_traversal_lookup = generate_tree_traversal(
        undirected_graph, center_node
    )
    segments = partition_segments(
        tree_traversal, undirected_graph, merge, node_traversal_lookup
    )
    validate_segments(segments, undirected_graph)
    return segments, neuron_pruned, node_traversal_lookup


def convert_to_undirected_graph(neuron_pruned: navis.TreeNeuron) -> nx.Graph:
    """Convert the neuron graph to an undirected graph.

    Args:
        neuron_pruned: The pruned neuron.

    Returns:
        The undirected graph.
    """
    nx_graph = navis.neuron2nx(neuron_pruned)
    return nx_graph.to_undirected()


def find_center_node(
    neuron_pruned: navis.TreeNeuron, undirected_graph: nx.Graph
) -> int:
    """Find the center node of the neuron.

    Args:
        neuron_pruned: The pruned neuron.
        undirected_graph: The undirected graph.

    Returns:
        The center node.
    """
    if neuron_pruned.soma is None:
        pagerank = nx.pagerank(undirected_graph)
        return sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[0][0]
    return neuron_pruned.soma.node_id


def generate_tree_traversal(
    undirected_graph: nx.Graph, center_node: int
) -> tuple[list[int], dict[int, int]]:
    """Generate the tree traversal order.

    Args:
        undirected_graph: The undirected graph.
        center_node: The center node.

    Returns:
        The tree traversal order and the node traversal lookup.
    """
    tree_traversal = list(nx.dfs_preorder_nodes(undirected_graph, source=center_node))
    node_traversal_lookup = node_tree_traversal_mapping(tree_traversal)
    return tree_traversal, node_traversal_lookup


def partition_segments(
    tree_traversal: list[int],
    undirected_graph: nx.Graph,
    merge: bool,
    node_traversal_lookup: dict[int, int],
) -> list[list[int]]:
    """Partition the neuron into segments.

    Args:
        tree_traversal: The tree traversal order.
        undirected_graph: The undirected graph.
        merge: Whether to merge the segments.
        node_traversal_lookup: The node traversal lookup.

    Returns:
        The segments.
    """
    branch_points = identify_branch_points(undirected_graph)
    adjacency_list = get_adjacency_list(undirected_graph)
    segments = df_degree_based_partitioning(
        tree_traversal, adjacency_list, branch_points
    )

    validate_segments(segments, undirected_graph)

    logger.info(
        f"{len((segments))} segments with"
        f"a joint length of {sum([len(s) for s in segments])}."
    )
    num_sections = len(branch_points) // 4

    if num_sections > 1 and merge:
        logger.info(
            f"Merging {len(segments)} segments into {num_sections} largest segments..."
        )
        segments = merge_segments_traversal_order(
            segments, node_traversal_lookup, num_sections, adjacency_list
        )
        logger.info(
            f"{len((segments))} merged segments "
            f"with a joint length of {sum([len(s) for s in segments])}."
        )

    return segments


def validate_segments(segments: list[list[int]], undirected_graph: nx.Graph) -> None:
    """
    Ensure each segment is fully connected.

    Args:
        segments (list[list[int]]): List of connected segments.
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.

    Raises:
        ValueError: If any segment is not fully connected.
    """
    for i, segment in enumerate(segments):
        subgraph = undirected_graph.subgraph(segment)
        if not nx.is_connected(subgraph):
            raise ValueError(f"Segment {i} is not fully connected.")


def df_degree_based_partitioning(
    tree_traversal: list[int],
    adjacent_nodes: nx.Graph,
    branch_points: set[int],
) -> list[list[int]]:
    """
    Splits the neuron skeleton into connected segments by identifying meaningful
    branch points, ensuring each section remains connected while approximating
    equal size.

    Args:
        tree_traversal: List of node indices representing the traversal order of
            the neuron skeleton.
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.
        branch_points (set[int]): Set of branch point node indices.


    Returns:
        A list of connected segments.
    """
    segments = []
    current_segment = []
    last_node = None

    for node in tree_traversal:
        is_junction = node in branch_points

        if last_node is None:
            current_segment.append(node)
        elif is_junction:
            if current_segment not in segments:
                segments.append(current_segment)
            current_segment = [node]
        elif last_node in adjacent_nodes[node]:
            current_segment.append(node)
        elif any(prev_node in adjacent_nodes[node] for prev_node in current_segment):
            current_segment.append(node)
        else:
            parent_segment = _find_parent_segment(node, segments, adjacent_nodes)
            if current_segment not in segments:
                segments.append(current_segment)
            current_segment = parent_segment
            current_segment.append(node)

        last_node = node

    if current_segment not in segments:
        segments.append(current_segment)

    return segments


def identify_branch_points(undirected_graph: nx.Graph) -> set[int]:
    """
    Identify branch points (nodes with degree >= 3).

    Args:
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.

    Returns:
        set[int]: A set of branch point node indices.
    """
    return {node for node, degree in undirected_graph.degree() if degree >= 3}


def get_adjacency_list(undirected_graph: nx.Graph) -> dict[int, set[int]]:
    """Precompute adjacency list for faster edge lookups.

    Args:
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.

    Returns:
        A dictionary mapping node indices to their neighbors.
    """
    return {node: set(neighbors) for node, neighbors in undirected_graph.adjacency()}


def _find_parent_segment(
    node: int, segments: list[list[int]], adjacency_list: dict[int, set[int]]
) -> list[int]:
    """
    Find the smallest parent segment to merge into.

    Args:
        node (int): Node index to find the parent segment for.
        segments (list[list[int]]): List of existing segments.
        adjacency_list (dict[int, set[int]]): Precomputed adjacency node list

    Returns:
        list[int]: The parent segment to merge into.

    Raises:
        ValueError: If no parent segment is found for the node.
    """
    parent_segment = None
    smallest_parent_segment_size = float("inf")

    for segment in segments:
        if any(neighbor in segment for neighbor in adjacency_list[node]):
            if len(segment) < smallest_parent_segment_size:
                smallest_parent_segment_size = len(segment)
                parent_segment = segment

    if parent_segment is None:
        raise ValueError(
            f"No parent segment found for node {node}. Ensure the neuron skeleton "
            "is fully connected."
        )

    return parent_segment


def merge_segments_traversal_order(
    segments: list[list[int]],
    node_traversal_lookup: dict[int, int],
    num_sections: int,
    adjacency_list: dict[int, set[int]],
) -> list[list[int]]:
    """
    Iteratively merges the smallest segment with the smallest directly connected
    segment in the depth-first traversal until only `num_sections` segments remain.

    Args:
        segments (list[list[int]]): List of neuron skeleton segments (each a list
            of node indices).
        node_traversal_lookup (dict[int, int]): Dictionary mapping node indices to
            their position in the tree traversal.
        num_sections (int): The number of final sections to retain.
        adjacency_list (dict[int, set[int]]): Precomputed adjacency node list.

    Returns:
        list[list[int]]: List of `num_sections` connected segments.
    """

    while len(segments) > num_sections:
        segments.sort(key=len)
        smallest_segment = segments.pop(0)
        connected_segments = _id_adjacent_sections_size_asce(
            smallest_segment, segments, adjacency_list
        )
        merged = _extend_section(
            smallest_segment,
            connected_segments,
            segments,
            node_traversal_lookup,
        )

        if not merged:
            logger.error("The sections do not cover all nodes")

    return segments


def _id_adjacent_sections_size_asce(
    smallest_segment: list[int],
    segments: list[list[int]],
    adjacency_list: dict[int, set[int]],
) -> list[tuple[int, list[int]]]:
    """
    Identify all segments that share a direct connection with the current smallest
    segment.

    Args:
        smallest_segment (list[int]): List of node indices representing the smallest
            segment.
        segments (list[list[int]]): List of neuron skeleton segments (each a list
            of node indices).
        adjacency_list (dict[int, set[int]]): Precomputed adjacency node list.

    Returns:
        list[tuple[int, list[int]]]: List of connected segments sorted by size.
    """
    connected_segments: dict[int, list[int]] = {
        i: segment
        for i, segment in enumerate(segments)
        if any(
            large_node in adjacency_list[small_node]
            for small_node in smallest_segment
            for large_node in segment
        )
    }
    return sorted(connected_segments.items(), key=lambda item: len(item[1]))


def _extend_section(
    smallest_segment: list[int],
    connected_segments: list[tuple[int, list[int]]],
    segments: list[list[int]],
    node_position_lookup: dict[int, int],
) -> bool:
    """
    Merge the smallest segment with the best candidate section.

    Args:
        smallest_segment (list[int]): List of node indices representing the smallest
            segment.
        connected_segments (list[tuple[int, list[int]]]): List of connected segments.
        segments (list[list[int]]): List of neuron skeleton segments (each a list
            of node indices).
        node_position_lookup (dict[int, int]): Dictionary mapping node indices to
            their position in the tree traversal.

    Returns:
        bool: True if a merge was made, False otherwise.
    """
    first_node, last_node = smallest_segment[0], smallest_segment[-1]

    for j, connected_seg in connected_segments:
        segment_first, segment_last = connected_seg[0], connected_seg[-1]

        if node_position_lookup[last_node] == node_position_lookup[segment_first] - 1:
            smallest_segment.extend(connected_seg)
            segments[j] = smallest_segment
            return True
        elif node_position_lookup[segment_last] == node_position_lookup[first_node] - 1:
            connected_seg.extend(smallest_segment)
            segments[j] = connected_seg
            return True

    if connected_segments:
        smallest_connected_idx, smallest_connected_segment = connected_segments[0]
        smallest_connected_segment.extend(smallest_segment)
        segments[smallest_connected_idx] = smallest_connected_segment
        return True

    return False


def node_tree_traversal_mapping(tree_traversal: list[int]) -> dict[int, int]:
    """
    Create a mapping of node indices to their position in the tree traversal.

    Returns:
        dict[int, int]: Dictionary mapping node indices to their position in the
            tree traversal.
    """
    return {node: i for i, node in enumerate(tree_traversal)}


def sort_sections_by_traversal_order(
    sections: list[list[int]], node_traversal_lookup: dict[int, int]
) -> list[list[int]]:
    """
    Sort sections based on the tree traversal order.

    Args:
        sections: List of neuron skeleton sections (each a list of node indices).
        node_traversal_lookup: Dictionary mapping node indices to their position
            in the tree traversal.

    Returns:
        List of sorted sections.
    """
    traversal_positions = np.array(
        [
            np.mean([node_traversal_lookup[node] for node in section])
            for section in sections
        ]
    )
    return [section for _, section in sorted(zip(traversal_positions, sections))]
