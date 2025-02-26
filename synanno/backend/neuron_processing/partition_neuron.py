import logging

import networkx as nx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def df_degree_based_partitioning(
    tree_traversal: list[int],
    undirected_graph: nx.Graph,
) -> list[list[int]]:
    """
    Splits the neuron skeleton into connected segments by identifying meaningful
    branch points, ensuring each section remains connected while approximating
    equal size.

    Args:
        tree_traversal: List of node indices representing the traversal order of
            the neuron skeleton.
        undirected_graph: The neuron skeleton graph as an undirected NetworkX graph.

    Returns:
        list[list[int]]: A list of connected segments.
    """
    branch_points = _identify_branch_points(undirected_graph)
    segments = _create_segments(tree_traversal, undirected_graph, branch_points)
    _validate_segments(segments, undirected_graph)
    return segments


def _identify_branch_points(undirected_graph: nx.Graph) -> set[int]:
    """
    Identify branch points (nodes with degree >= 3).

    Args:
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.

    Returns:
        set[int]: A set of branch point node indices.
    """
    return {node for node, degree in undirected_graph.degree() if degree >= 3}


def _create_segments(
    tree_traversal: list[int], undirected_graph: nx.Graph, branch_points: set[int]
) -> list[list[int]]:
    """
    Walk along the tree traversal and create segments.

    Args:
        tree_traversal (list[int]): List of node indices representing the traversal
            order of the neuron skeleton.
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.
        branch_points (set[int]): Set of branch point node indices.

    Returns:
        list[list[int]]: A list of connected segments.
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
        elif undirected_graph.has_edge(last_node, node):
            current_segment.append(node)
        elif any(
            undirected_graph.has_edge(prev_node, node) for prev_node in current_segment
        ):
            current_segment.append(node)
        else:
            parent_segment = _find_parent_segment(node, segments, undirected_graph)
            if current_segment not in segments:
                segments.append(current_segment)
            current_segment = parent_segment
            current_segment.append(node)

        last_node = node

    if current_segment not in segments:
        segments.append(current_segment)

    return segments


def _find_parent_segment(
    node: int, segments: list[list[int]], undirected_graph: nx.Graph
) -> list[int]:
    """
    Find the smallest parent segment to merge into.

    Args:
        node (int): Node index to find the parent segment for.
        segments (list[list[int]]): List of existing segments.
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.

    Returns:
        list[int]: The parent segment to merge into.

    Raises:
        ValueError: If no parent segment is found for the node.
    """
    parent_segment = None
    smallest_parent_segment_size = float("inf")

    for segment in segments:
        if any(undirected_graph.has_edge(seg_node, node) for seg_node in segment):
            if len(segment) < smallest_parent_segment_size:
                smallest_parent_segment_size = len(segment)
                parent_segment = segment

    if parent_segment is None:
        raise ValueError(
            f"No parent segment found for node {node}. Ensure the neuron skeleton "
            "is fully connected."
        )

    return parent_segment


def _validate_segments(segments: list[list[int]], undirected_graph: nx.Graph) -> None:
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


def merge_segments_traversal_order(
    segments: list[list[int]],
    node_traversal_lookup: dict[int, int],
    undirected_graph: nx.Graph,
    num_sections: int,
) -> list[list[int]]:
    """
    Iteratively merges the smallest segment with the smallest directly connected
    segment in the depth-first traversal until only `num_sections` segments remain.

    Args:
        segments (list[list[int]]): List of neuron skeleton segments (each a list
            of node indices).
        node_traversal_lookup (dict[int, int]): Dictionary mapping node indices to
            their position in the tree traversal.
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.
        num_sections (int): The number of final sections to retain.

    Returns:
        list[list[int]]: List of `num_sections` connected segments.
    """

    while len(segments) > num_sections:
        segments.sort(key=len)
        smallest_segment = segments.pop(0)
        connected_segments = _id_adjacent_sections_size_asce(
            smallest_segment, segments, undirected_graph
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
    undirected_graph: nx.Graph,
) -> list[tuple[int, list[int]]]:
    """
    Identify all segments that share a direct connection with the current smallest
    segment.

    Args:
        smallest_segment (list[int]): List of node indices representing the smallest
            segment.
        segments (list[list[int]]): List of neuron skeleton segments (each a list
            of node indices).
        undirected_graph (nx.Graph): The neuron skeleton graph as an undirected
            NetworkX graph.

    Returns:
        list[tuple[int, list[int]]]: List of connected segments sorted by size.
    """
    connected_segments: dict[int, list[int]] = {
        i: segment
        for i, segment in enumerate(segments)
        if any(
            undirected_graph.has_edge(small_node, large_node)
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

    def section_mean_traversal_index(section: list[int]) -> float:
        indices = [node_traversal_lookup[node] for node in section]
        return sum(indices) / len(indices)

    sorted_sections = sorted(sections, key=section_mean_traversal_index)
    return sorted_sections
