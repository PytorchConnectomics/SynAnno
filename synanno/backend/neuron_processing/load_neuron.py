import io
import logging
import tempfile

import navis
from cloudvolume import CloudVolume

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_neuron_skeleton(c3_bucket: str, neuron_id: int) -> navis.TreeNeuron:
    """Fetch, process, prune neuron from CloudVolume without writing to permanent disk.

    Args:
        c3_bucket: The c3 bucket to load the neuron from.
        neuron_id: The ID of the neuron to load.

    Returns:
        The pruned and reindexed neuron as a navis.TreeNeuron.
    """
    cv = CloudVolume(c3_bucket, mip=0, cache=False, use_https=True)
    skeleton = fetch_skeleton(cv, neuron_id)
    swc_string = skeleton.to_swc()
    neuron = read_neuron_from_swc_string(swc_string)
    neuron = heal_neuron(neuron)
    neuron_pruned = prune_neuron(neuron)
    neuron_reindexed = reindex_neuron(neuron_pruned)
    return neuron_reindexed


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
    if not skeletons or len(skeletons[0].vertices) == 0:
        raise ValueError(f"Neuron {neuron_id} is empty or not found in {cv.cloudpath}.")
    return skeletons[0]


def read_neuron_from_swc_string(swc_string: str) -> navis.TreeNeuron:
    """Read a neuron from an SWC string.

    Args:
        swc_string: The SWC string.

    Returns:
        The neuron as a navis.TreeNeuron.
    """
    with tempfile.NamedTemporaryFile(suffix=".swc", delete=True) as temp_swc:
        temp_swc.write(swc_string.encode("utf-8"))
        temp_swc.flush()
        neuron = navis.read_swc(temp_swc.name)
    return neuron


def heal_neuron(neuron: navis.TreeNeuron) -> navis.TreeNeuron:
    """Heal the neuron skeleton.

    Args:
        neuron: The neuron skeleton.

    Returns:
        The healed neuron skeleton.
    """
    if not isinstance(neuron, navis.TreeNeuron):
        raise TypeError(f"Neuron type is {type(neuron)} and not a navis.TreeNeuron")
    neuron.units = "nm"
    navis.heal_skeleton(neuron, inplace=True)
    if "parent_id" not in neuron.nodes:
        logger.info("Adding parent-child relationships...")
        neuron.reconnect(method="spatial")
    return neuron


def prune_neuron(neuron: navis.TreeNeuron) -> navis.TreeNeuron:
    """Prune the neuron.

    Args:
        neuron: The neuron skeleton.

    Returns:
        The pruned neuron.
    """
    neuron_pruned = navis.prune_twigs(
        neuron, size="4096 nm", inplace=False, recursive=True
    )
    if neuron_pruned.n_nodes == 0:
        raise ValueError("Pruning removed all nodes! Check pruning logic.")
    return neuron_pruned


def reindex_neuron(neuron: navis.TreeNeuron) -> navis.TreeNeuron:
    """Reindex the neuron by saving and reloading it.

    Args:
        neuron: The neuron skeleton.

    Returns:
        The reindexed neuron.
    """
    with tempfile.NamedTemporaryFile(suffix=".swc", delete=True) as temp_swc:
        neuron.to_swc(temp_swc.name, write_meta=True)
        neuron_reindexed = navis.read_swc(temp_swc.name)
    return neuron_reindexed


def neuron_to_bytes(neuron: navis.TreeNeuron) -> bytes:
    """Convert a neuron object to an SWC file and return its contents as bytes.

    Args:
        neuron: The navis.TreeNeuron object.

    Returns:
        SWC data as bytes.
    """
    with tempfile.NamedTemporaryFile(suffix=".swc", delete=True) as temp_swc:
        navis.write_swc(neuron, temp_swc.name)
        with open(temp_swc.name, "r", encoding="utf-8") as f:
            swc_data = f.read()
    return io.BytesIO(swc_data.encode("utf-8"))
