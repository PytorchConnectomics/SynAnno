import networkx as nx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def df_degree_based_partitioning(
    tree_traversal: list[int],
    undirected_graph: nx.Graph,
) -> list[list[int]]:
    """
    Splits the neuron skeleton into `num_sections` connected segments by identifying meaningful branch points,
    ensuring each section remains connected while approximating equal size. A new segment starts only at
    branch points or when the segment size exceeds `min_segment_size`.

    Args:
        tree_traversal: A list of node indices representing the traversal order of the neuron skeleton.
        undirected_graph: The neuron skeleton graph as an undirected NetworkX graph.
        num_sections: The number of final sections to retain.
        min_segment_size: Minimum allowed segment size; if None, it is set dynamically.

    Returns:
        A list of `num_sections` largest connected segments.
    """
    # Identify branch points (nodes with degree >= 3)
    branch_points = {node for node, degree in undirected_graph.degree() if degree >= 3}

    # Walk along the tree traversal and create segments
    segments = []
    current_segment = []
    last_node = None

    for node in tree_traversal:
        is_junction = node in branch_points

        # Add first node to the first section
        if last_node is None:
            current_segment.append(node)
        # Start a new section at a branch point if the segment is large enough
        elif is_junction:
            if current_segment not in segments:
                segments.append(current_segment)
            current_segment = [node]
        # Add node if directly connected to the last node
        elif undirected_graph.has_edge(last_node, node):
            current_segment.append(node)
        # Add node if it is directly connected to any node in the segment
        elif any(
            undirected_graph.has_edge(prev_node, node) for prev_node in current_segment
        ):
            current_segment.append(node)
        # If not directly connected, find the smallest parent segment to merge into
        else:
            parent_segment = None
            smallest_parent_segment_size = float("inf")

            for segment in segments:
                if any(
                    undirected_graph.has_edge(seg_node, node) for seg_node in segment
                ):
                    if len(segment) < smallest_parent_segment_size:
                        smallest_parent_segment_size = len(segment)
                        parent_segment = segment

            # If no parent segment found, raise an error
            if parent_segment is None:
                raise ValueError(
                    f"No parent segment found for node {node}. Ensure the neuron skeleton is fully connected."
                )

            # Move to the parent segment and append the node
            if current_segment not in segments:
                segments.append(current_segment)
            current_segment = parent_segment
            current_segment.append(node)

        last_node = node

    # Append the last segment if it's not already added
    if current_segment not in segments:
        segments.append(current_segment)

    # Ensure each segment is fully connected
    for i, segment in enumerate(segments):
        subgraph = undirected_graph.subgraph(segment)
        if not nx.is_connected(subgraph):
            raise ValueError(f"Segment {i} is not fully connected.")

    return segments


def merge_segments_traversal_order(
    segments: list[list[int]],
    tree_traversal: list[int],
    undirected_graph: nx.Graph,
    num_sections: int,
) -> list[list[int]]:
    """
    Iteratively merges the smallest segment with the smallest directly connected segment in the depth-first
    traversal until only `num_sections` segments remain.

    Args:
        segments: List of neuron skeleton segments (each a list of node indices).
        tree_traversal: A list of node indices representing the depth-first traversal order.
        undirected_graph: The neuron skeleton graph as an undirected NetworkX graph.
        num_sections: The number of final sections to retain.

    Returns:
        List of `num_sections` connected segments.
    """
    node_position_lookup: dict[int, int] = {
        node: i for i, node in enumerate(tree_traversal)
    }

    while len(segments) > num_sections:
        # Step 1: Sort segments by size (ascending, smallest first)
        segments.sort(key=len)

        # Step 2: Pick the smallest segment and remove it from the list
        smallest_segment = segments.pop(0)

        # Step 3: Find all segments that share a direct connection with the current smallest segment
        connected_segments = id_adjacent_sections_size_asce(
            smallest_segment, segments, undirected_graph
        )

        merged = extend_section(
            smallest_segment, connected_segments, segments, node_position_lookup
        )

        if not merged:
            # TODO: Handle the case where the smallest segment cannot be merged
            logger.error("The sections do not cover all nodes")

    return segments


def id_adjacent_sections_size_asce(
    smallest_segment: list[int], segments: list[list[int]], undirected_graph: nx.Graph
) -> list[tuple[int, list[int]]]:
    """
    Identify all segments that share a direct connection with the current smallest segment.
    Return those connected segments ordered by size ascending.

    Args:
        smallest_segment: List of node indices representing the smallest segment.
        segments: List of neuron skeleton segments (each a list of node indices).
        undirected_graph: The neuron skeleton graph as an undirected NetworkX graph.

    Returns:
        List of connected segments sorted by size.
    """
    # Find all directly connected segments
    connected_segments: dict[int, list[int]] = {
        i: segment
        for i, segment in enumerate(segments)
        if any(
            undirected_graph.has_edge(small_node, large_node)
            for small_node in smallest_segment
            for large_node in segment
        )
    }

    # Sort connected segments by size (ascending)
    return sorted(connected_segments.items(), key=lambda item: len(item[1]))


def extend_section(
    smallest_segment: list[int],
    connected_segments: list[tuple[int, list[int]]],
    segments: list[list[int]],
    node_position_lookup: list[int, int],
) -> bool:
    """
    Merge the smallest segment with the best candidate section.

    Check if the first or last node of a connected_segments candidate comes
    immediately before or after the first or last node in the current
    smallest segment in the tree traversal, starting with the smallest
    connected_segments.

    If none of the connected_segments is a direct neighbor in the traversal,
    add the smallest_segment to the smallest_connected_segment.

    Args:
        smallest_segment: List of node indices representing the smallest segment.
        connected_segments: List of connected segments.
        segments: List of neuron skeleton segments (each a list of node indices).
        node_position_lookup: Dictionary mapping node indices to their position in the tree traversal.

    Returns:
        True if a merge was made, False otherwise.
    """
    first_node, last_node = smallest_segment[0], smallest_segment[-1]

    for j, connected_seg in connected_segments:
        segment_first, segment_last = connected_seg[0], connected_seg[-1]

        # Extend smallest_segment with segment
        if node_position_lookup[last_node] == node_position_lookup[segment_first] - 1:
            smallest_segment.extend(connected_seg)
            segments[j] = smallest_segment
            return True

        # Extend segment with smallest_segment
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
