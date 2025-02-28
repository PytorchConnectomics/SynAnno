import logging
import os

import navis
from cloudvolume import CloudVolume

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
