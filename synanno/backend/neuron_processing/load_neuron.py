import os
from cloudvolume import CloudVolume
import logging
import navis
import networkx as nx
from synanno.backend.neuron_processing.partition_neuron import (
    df_degree_based_partitioning,
    merge_segments_traversal_order,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_neuron_skeleton(
    c3_bucket: str, neuron_id: int, swc_path: str, overwrite: bool = False
):
    """
    Load the skeleton of a neuron from the c3 bucket and save it as an SWC file.

    Args:
        c3_bucket: The c3 bucket to load the neuron from.
        neuron_id: The id of the neuron to load.
        swc_path: The path to save the SWC file.
        overwrite: Whether to overwrite the existing SWC file.

    Returns:
        The path to the saved SWC file.
    """
    # Create SWC folder if it does not exist
    os.makedirs(swc_path, exist_ok=True)

    cv = CloudVolume(c3_bucket, mip=0, cache=False, use_https=True)
    skeletons = cv.skeleton.get([neuron_id])

    if not skeletons:
        raise ValueError(f"Neuron {neuron_id} not found in c3 bucket {c3_bucket}")

    skeleton = skeletons[0]

    # Delete the old SWC file if overwrite is True
    swc_file = os.path.join(swc_path, f"{neuron_id}.swc")
    if overwrite and os.path.exists(swc_file):
        os.remove(swc_file)

    # Save the neuron skeleton to SWC
    with open(swc_file, "w") as f:
        f.write(skeleton.to_swc())
        logger.info(f"Skeleton saved as SWC: {swc_file}")

    return swc_file


def navis_neuron(swc_file: str):
    """
    Load the neuron skeleton into a navis.TreeNeuron object, prune it, and save the pruned neuron.

    Args:
        swc_file: The path to the SWC file.

    Returns:
        The path to the saved pruned SWC file.
    """
    # Load the skeleton into a navis.TreeNeuron object
    neuron = navis.read_swc(swc_file)

    if not isinstance(neuron, navis.TreeNeuron):
        raise TypeError(f"Neuron type is {type(neuron)} and not a navis.TreeNeuron")

    neuron.units = "nm"

    # Heal the neuron skeleton
    navis.heal_skeleton(neuron, inplace=True)

    # Add parent-child relationships if missing
    if "parent_id" not in neuron.nodes:
        logger.info("Adding parent-child relationships...")
        neuron.reconnect(method="spatial")

    # Prune the neuron
    logger.info(f"Nodes before pruning: {neuron.n_nodes}")
    neuron_pruned = navis.prune_twigs(
        neuron, size="8192 nm", inplace=False, recursive=True
    )
    logger.info(f"Nodes after pruning: {neuron_pruned.n_nodes}")

    # Save the pruned neuron to SWC
    pruned_swc_file = swc_file.replace(".swc", "_pruned.swc")
    neuron_pruned.to_swc(pruned_swc_file, write_meta=True)

    return pruned_swc_file


def compute_sections(pruned_swc_file: str):
    """
    Compute the sections of the pruned neuron.

    Args:
        pruned_swc_file: The path to the pruned SWC file.

    Returns:
        The merged segments of the neuron.
    """
    # Reload the pruned neuron
    neuron_pruned = navis.read_swc(pruned_swc_file, write_meta=True)
    # Convert the graph to networkx
    nx_graph = navis.neuron2nx(neuron_pruned)

    # Sanity check
    logger.info(
        "Nodes - # "
        + str(len(nx_graph.nodes.keys()))
        + ":"
        + str(list(nx_graph.nodes.keys())[:100])
    )
    logger.info(
        "Edges - # "
        + str(len(nx_graph.edges.keys()))
        + ":"
        + str(list(nx_graph.edges.keys())[:100])
    )

    # Convert the digraph to an undirected graph
    undirected_graph = nx_graph.to_undirected()

    # Compute the center node
    if neuron_pruned.soma is None:
        pagerank = nx.pagerank(undirected_graph)
        center_node = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[0][0]
    else:
        center_node = neuron_pruned.soma.node_id

    logger.info(f"Center node: {center_node}")

    # Generate nodes in a depth-first-search pre-ordering starting at source
    tree_traversal = list(nx.dfs_preorder_nodes(undirected_graph, source=center_node))
    logger.info(f"Tree length: {len(tree_traversal)}")
    logger.info(f"Tree traversal: {tree_traversal}")

    segments = df_degree_based_partitioning(tree_traversal, undirected_graph)
    logger.info(
        f"{len((segments))} segments with a joint length of {sum([len(s) for s in segments])}."
    )

    num_sections = (
        len({node for node, degree in undirected_graph.degree() if degree >= 3}) // 4
    )

    if num_sections > 1:
        logger.info(
            f"Merging {len(segments)} segments into {num_sections} largest segments..."
        )
        segments = merge_segments_traversal_order(
            segments, tree_traversal, undirected_graph, num_sections
        )
        logger.info(
            f"{len((segments))} merged segments with a joint length of {sum([len(s) for s in segments])}."
        )

    return segments
