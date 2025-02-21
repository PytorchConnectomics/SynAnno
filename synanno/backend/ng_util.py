import logging
from random import randint
from typing import Union

import neuroglancer

# for type hinting
import numpy as np
import numpy.typing as npt
from flask import Flask

# setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def center_annotation(app, coordinate_space):
    """Ng action function that enables the recording and depiction
    of center markers for newly identified FN instances.
    """

    def _center_annotation(s):
        # record the current mouse position
        center = s.mouse_voxel_coordinates

        # prevent crashes if off ng view
        if center is None:
            logging.info("No mouse coordinates available.")
            return

        center_coord = {
            key: int(value) for key, value in zip(coordinate_space.names, center)
        }

        # split the position and convert to int
        app.cz = int(center_coord["z"])
        app.cy = int(center_coord["y"])
        app.cx = int(center_coord["x"])

        logging.info(f"Center Coordinates: {[app.cx, app.cy, app.cz]}")

        # add a yellow dot at the recorded position within the NG
        with app.ng_viewer.txn() as layer:
            layer.layers["marker_dot"].annotations = []  # Clear previous annotations
            pt = neuroglancer.PointAnnotation(
                point=[int(center[0]), int(center[1]), int(center[2])],
                id="center_point",
            )
            layer.layers["marker_dot"].annotations.append(pt)

    return _center_annotation


def get_hovered_neuron_id(app):
    """Retrieve and logging.info the neuron ID at the voxel under the mouse cursor."""

    def _get_hovered_neuron_id(s):
        # get the current mouse voxel coordinates
        voxel_coords = s.mouse_voxel_coordinates

        # prevent crashes if off ng view
        if voxel_coords is None:
            logging.info("No mouse coordinates available.")
            return

        logging.info(f"Mouse Voxel Coordinates: {voxel_coords}")

        # retrieve the selected neuron ID from the segmentation layer
        neuron_info = s.selected_values["neuropil"].value
        logging.info(f"Raw Selected Neuron ID: {neuron_info}")

        neuron_id = None

        # handle different types of neuron_info
        if isinstance(neuron_info, neuroglancer.viewer_config_state.SegmentIdMapEntry):
            neuron_id = neuron_info.key
        elif isinstance(neuron_info, int):
            neuron_id = neuron_info
        elif isinstance(neuron_info, str) and neuron_info.isdigit():
            neuron_id = int(neuron_info)
        else:
            logging.info("No valid neuron ID found at this voxel.")
            return

        # store the neuron ID globally in the app context
        app.selected_neuron_id = neuron_id
        logging.info(f"Selected Neuron ID: {neuron_id}")

        # add a marker at the neuron ID location
        with app.ng_viewer.txn() as layer:
            layer.layers["marker_dot"].annotations = []  # Clear previous annotations
            pt = neuroglancer.PointAnnotation(
                point=[
                    int(voxel_coords[0]),
                    int(voxel_coords[1]),
                    int(voxel_coords[2]),
                ],
                id="neuron_point",
            )
            layer.layers["marker_dot"].annotations.append(pt)

    return _get_hovered_neuron_id


def enable_neuropil_layer(app):
    """Enable the neuropil neuron segmentation layer."""
    with app.ng_viewer.txn() as s:
        s.layers["neuropil"].selectedAlpha = 0.5
        s.layers["neuropil"].notSelectedAlpha = 0.1


def disable_neuropil_layer(app):
    """Disable the neuropil neuron segmentation layer."""
    with app.ng_viewer.txn() as s:
        s.layers["neuropil"].selectedAlpha = 0.0
        s.layers["neuropil"].notSelectedAlpha = 0.0


def setup_ng(
    app: Flask,
    source: Union[npt.NDArray, str],
    target: Union[npt.NDArray, str],
    neuropil: Union[npt.NDArray, str],
) -> None:
    """Setup function for the Neuroglancer (ng) that enables the recording and depiction
    of center markers for newly identified FN instances.

    Args:
        app: a handle to the application context
        source: The image volume depicted by the ng
        target: The target volume depicted by the ng
        neuropil: Neuropil segmentation volume when undergoing view-centric analysis
    """

    # generate a version number
    app.ng_version = str(randint(0, 3200))

    # setup a Tornado web server and create viewer instance
    neuroglancer.set_server_bind_address(
        bind_address=app.config["NG_IP"], bind_port=app.config["NG_PORT"]
    )
    app.ng_viewer = neuroglancer.Viewer(token=app.ng_version)

    # default coordinate order to pass in if processing route not undergone
    # TODO: set scales before the neuron button gets pressed and remove need for default
    default_coordinate_order = {"x": (4, 4), "y": (4, 4), "z": (33, 33)}

    # specify the NG coordinate space
    if hasattr(app, "coordinate_order") and app.coordinate_order:
        coordinate_order = app.coordinate_order
    else:
        coordinate_order = default_coordinate_order

    # parse the coordinate space into neuroglancer
    coordinate_space = neuroglancer.CoordinateSpace(
        names=list(coordinate_order.keys()),
        units=["nm", "nm", "nm"],
        scales=np.array([int(res[0]) for res in coordinate_order.values()], dtype=int),
    )

    # config viewer: Add image layer, add segmentation mask layer, define position
    with app.ng_viewer.txn() as s:
        if isinstance(source, np.ndarray):
            source = neuroglancer.LocalVolume(
                data=source,
                dimensions=coordinate_space,
                volume_type="image",
                voxel_offset=[0, 0, 0],
            )
            s.layers["image"] = neuroglancer.ImageLayer(source=source)
        elif isinstance(
            source, str
        ):  # Assuming the string is a URL for the precomputed source
            s.layers["image"] = neuroglancer.ImageLayer(source=source)
        else:
            raise ValueError("Unknown source type")

        if isinstance(target, np.ndarray):
            target = neuroglancer.LocalVolume(
                data=target,
                dimensions=coordinate_space,
                volume_type="segmentation",
                voxel_offset=[0, 0, 0],
            )
            s.layers["annotation"] = neuroglancer.SegmentationLayer(source=target)
        elif isinstance(
            target, str
        ):  # Assuming it's a string URL for the precomputed neuropil
            s.layers["annotation"] = neuroglancer.SegmentationLayer(source=target)
        else:
            raise ValueError("Unknown annotation type")

        s.selected_layer.layer = "image"
        s.selected_layer.visible = True
        s.show_slices = True

        if isinstance(neuropil, np.ndarray):
            neuropil = neuroglancer.LocalVolume(
                data=neuropil,
                dimensions=coordinate_space,
                volume_type="segmentation",
                voxel_offset=[0, 0, 0],
            )
            s.layers["neuropil"] = neuroglancer.SegmentationLayer(
                source=neuropil,
                # disabled by default but enabled in neuon-centric mode
                selectedAlpha=0.0,
                notSelectedAlpha=0.0,
                # optional niceties
                hoverHighlight=True,
                hideSegmentZero=True,
            )
        elif isinstance(
            neuropil, str
        ):  # Assuming it's a string URL for the precomputed target
            s.layers["neuropil"] = neuroglancer.SegmentationLayer(
                source=neuropil,
                selectedAlpha=0.0,
                notSelectedAlpha=0.0,
                hoverHighlight=True,
                hideSegmentZero=True,
            )

        # choose a random row, skipping the first row
        random_row = app.synapse_data.iloc[1:].sample(n=1).iloc[0]

        # extract xyz coordinates and set them as the starting position
        new_position = [
            int(
                random_row["x"] * 2
            ),  # Multiplying by 2 to adjust for coordinate scaling
            int(
                random_row["y"] * 2
            ),  # Multiplying by 2 to adjust for coordinate scaling
            int(random_row["z"]),
        ]
        s.position = new_position

        # additional layer that lets the user mark the center of FPs
        s.layers["marker"] = neuroglancer.LocalAnnotationLayer(
            dimensions=coordinate_space,
            annotations=[],
        )

    # add the center dot as action
    app.ng_viewer.actions.add("center", center_annotation(app, coordinate_space))
    with app.ng_viewer.config_state.txn() as s:
        # set the trigger for the action to the key 'c'
        s.input_event_bindings.viewer["keyc"] = "center"

    # bind the action to a key, e.g., 'n'
    app.ng_viewer.actions.add("get_neuron_id", get_hovered_neuron_id(app))

    with app.ng_viewer.config_state.txn() as s:
        s.input_event_bindings.viewer["keyn"] = "get_neuron_id"

    logging.info(
        f"Starting a Neuroglancer instance at "
        f"{app.ng_viewer}, centered at x,y,z {0,0,0}."
    )
