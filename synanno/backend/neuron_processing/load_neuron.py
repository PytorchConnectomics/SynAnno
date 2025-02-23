import logging
import os

import navis
import networkx as nx
from cloudvolume import CloudVolume

from synanno.backend.neuron_processing.partition_neuron import (
    df_degree_based_partitioning,
    merge_segments_traversal_order,
    node_tree_traversal_mapping,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_neuron_skeleton(
    c3_bucket: str, neuron_id: int, swc_path: str, overwrite: bool = False
) -> str:
    """Load the skeleton of a neuron from the c3 bucket and save it as an SWC file.

    Args:
        c3_bucket: The c3 bucket to load the neuron from.
        neuron_id: The id of the neuron to load.
        swc_path: The path to save the SWC file.
        overwrite: Whether to overwrite the existing SWC file.

    Returns:
        The path to the saved SWC file.
    """
    os.makedirs(swc_path, exist_ok=True)
    cv = CloudVolume(c3_bucket, mip=0, cache=False, use_https=True)
    skeleton = fetch_skeleton(cv, neuron_id)
    swc_file = save_skeleton(skeleton, swc_path, neuron_id, overwrite)
    return swc_file


def fetch_skeleton(cv: CloudVolume, neuron_id: int) -> navis.TreeNeuron:
    """Fetch the neuron skeleton from the CloudVolume.

    Args:
        cv: The CloudVolume object.
        neuron_id: The id of the neuron to fetch.

    Returns:
        The neuron skeleton.
    """
    try:
        skeletons = cv.skeleton.get([neuron_id])
    except ValueError as e:
        raise ValueError(
            f"Neuron {neuron_id} not found in c3 bucket {cv.cloudpath}"
        ) from e
    return skeletons[0]


def save_skeleton(
    skeleton: navis.TreeNeuron, swc_path: str, neuron_id: int, overwrite: bool
) -> str:
    """Save the neuron skeleton to an SWC file.

    Args:
        skeleton: The neuron skeleton.
        swc_path: The path to save the SWC file.
        neuron_id: The id of the neuron.
        overwrite: Whether to overwrite the existing SWC file.

    Returns:
        The path to the saved SWC file.
    """
    swc_file = os.path.join(swc_path, f"{neuron_id}.swc")
    if overwrite and os.path.exists(swc_file):
        os.remove(swc_file)
    with open(swc_file, "w") as f:
        f.write(skeleton.to_swc())
        logger.info(f"Skeleton saved as SWC: {swc_file}")
    return swc_file


def navis_neuron(swc_file: str) -> tuple[navis.TreeNeuron, str]:
    """Load the skeleton, prune it, and save the pruned neuron as navis TreeNeuron.

    Args:
        swc_file: The path to the SWC file.

    Returns:
        The pruned and healed neuron and the path to the SWC file.
    """
    neuron = load_and_heal_neuron(swc_file)
    pruned_swc_file = prune_and_save_neuron(neuron, swc_file)
    return pruned_swc_file


def load_and_heal_neuron(swc_file: str) -> navis.TreeNeuron:
    """Load and heal the neuron skeleton.

    Args:
        swc_file: The path to the SWC file.

    Returns:
        The healed neuron skeleton.
    """
    neuron = navis.read_swc(swc_file)
    if not isinstance(neuron, navis.TreeNeuron):
        raise TypeError(f"Neuron type is {type(neuron)} and not a navis.TreeNeuron")
    neuron.units = "nm"
    navis.heal_skeleton(neuron, inplace=True)
    if "parent_id" not in neuron.nodes:
        logger.info("Adding parent-child relationships...")
        neuron.reconnect(method="spatial")
    return neuron


def prune_and_save_neuron(neuron: navis.TreeNeuron, swc_file: str) -> str:
    """Prune the neuron and save it to an SWC file.

    Args:
        neuron: The neuron skeleton.
        swc_file: The path to the SWC file.

    Returns:
        The path to the pruned SWC file.
    """
    neuron_pruned = navis.prune_twigs(
        neuron, size="4096 nm", inplace=False, recursive=True
    )
    pruned_swc_file = swc_file.replace(".swc", "_pruned.swc")
    neuron_pruned.to_swc(pruned_swc_file, write_meta=True)
    return pruned_swc_file


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
    segments = df_degree_based_partitioning(tree_traversal, undirected_graph)
    logger.info(
        f"{len((segments))} segments with"
        f"a joint length of {sum([len(s) for s in segments])}."
    )
    num_sections = (
        len({node for node, degree in undirected_graph.degree() if degree >= 3}) // 4
    )
    if num_sections > 1 and merge:
        logger.info(
            f"Merging {len(segments)} segments into {num_sections} largest segments..."
        )
        segments = merge_segments_traversal_order(
            segments, node_traversal_lookup, undirected_graph, num_sections
        )
        logger.info(
            f"{len((segments))} merged segments "
            f"with a joint length of {sum([len(s) for s in segments])}."
        )
    return segments


def validate_segments(segments: list[list[int]], undirected_graph: nx.Graph) -> None:
    """Validate that all segments are connected.

    Args:
        segments: The segments.
        undirected_graph: The undirected graph.
    """
    for i, segment in enumerate(segments):
        assert nx.is_connected(
            undirected_graph.subgraph(segment)
        ), f"The section {i} is not connected with in it self."
