import neuroglancer
from random import randint

# for type hinting
import numpy as np

import numpy.typing as npt


from typing import Union
from flask import Flask


def setup_ng(
    app: Flask, source: Union[npt.NDArray, str], target: Union[npt.NDArray, str]
) -> None:
    """Setup function for the Neuroglancer (ng) that enables the recording and depiction
    of center markers for newly identified FN instances.

    Args:
        app: a handle to the application context
        source_img: The image volume depicted by the ng
        target_seg: The target volume depicted by the ng
    """

    # generate a version number
    app.ng_version = str(randint(0, 32e2))

    # setup a Tornado web server and create viewer instance
    neuroglancer.set_server_bind_address(
        bind_address=app.config["NG_IP"], bind_port=app.config["NG_PORT"]
    )
    app.ng_viewer = neuroglancer.Viewer(token=app.ng_version)

    # specify the NG coordinate space
    default_coordinate_order = {"x": (4, 4), "y": (4, 4), "z": (40, 40)}
    coordinate_order = getattr(app, "coordinate_order", default_coordinate_order)

    # parse the coordinate space into neuroglancer
    coordinate_space = neuroglancer.CoordinateSpace(
        names=list(coordinate_order.keys()),
        units=["nm", "nm", "nm"],
        scales=np.array([int(res[0]) for res in coordinate_order.values()]).astype(int),
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
        ):  # Assuming it's a string URL for the precomputed source
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
        ):  # Assuming it's a string URL for the precomputed target
            s.layers["annotation"] = neuroglancer.SegmentationLayer(source=target)
        else:
            raise ValueError("Unknown annotation type")

        s.selected_layer.layer = "image"
        s.selected_layer.visible = True
        s.show_slices = True

        # c3 segmentation layer for neuron-centric synapse selection
        s.layers["c3_neuron_segmentation"] = neuroglancer.SegmentationLayer(
            source="precomputed://gs://h01-release/data/20210601/c3",
            # disabled by default but enabled in neuon-centric mode
            selectedAlpha=0.0,
            notSelectedAlpha=0.0,
            # optional niceties
            hoverHighlight=True,
            hideSegmentZero=True,
        )

        # init the view position
        s.position = [711044, 315210, 2587]

        def get_hovered_neuron_id(s):
            """Retrieve and print the neuron ID at the voxel under the mouse cursor."""
            # Get the current mouse voxel coordinates
            voxel_coords = s.mouse_voxel_coordinates
            print(f"Mouse Voxel Coordinates: {voxel_coords}")

            # Retrieve the selected neuron ID from the segmentation layer
            neuron_info = s.selected_values["c3_neuron_segmentation"].value
            print(f"Raw Selected Neuron ID: {neuron_info}")

            neuron_id = None

            # Handle different types of neuron_info
            if isinstance(
                neuron_info, neuroglancer.viewer_config_state.SegmentIdMapEntry
            ):
                neuron_id = neuron_info.key
            elif isinstance(neuron_info, int):
                neuron_id = neuron_info
            elif isinstance(neuron_info, str) and neuron_info.isdigit():
                neuron_id = int(neuron_info)
            else:
                print("No valid neuron ID found at this voxel.")
                return

            # Store the neuron ID globally in the app context
            app.selected_neuron_id = neuron_id
            print(f"Selected Neuron ID: {neuron_id}")

            # if voxel_coords is None:
            #     print("Mouse is not hovering over any voxel.")
            #     return

            # print(type(s))

            # # Access the segmentation layer
            # segmentation_layer = s.viewer_state.layers["c3_neuron_segmentation"]

            # if segmentation_layer is None:
            #     print("Segmentation layer 'c3_neuron_segmentation' not found.")
            #     return

            # # Query the segment (neuron ID) at the current voxel
            # neuron_id = segmentation_layer.segment_at_voxel(voxel_coords)

            # if neuron_id:
            #     print(f"Neuron ID at {voxel_coords}: {neuron_id}")
            # else:
            #     print("No neuron found at this voxel.")

        # Bind the action to a key, e.g., 'n'
        app.ng_viewer.actions.add("get_neuron_id", get_hovered_neuron_id)

        with app.ng_viewer.config_state.txn() as s:
            s.input_event_bindings.viewer["keyn"] = "get_neuron_id"

        def enable_c3_layer():
            """Enable the c3 neuron segmentation layer."""
            with app.ng_viewer.txn() as s:
                s.layers["c3_neuron_segmentation"].selectedAlpha = 0.5
                s.layers["c3_neuron_segmentation"].notSelectedAlpha = 0.1

        def disable_c3_layer():
            """Disable the c3 neuron segmentation layer."""
            with app.ng_viewer.txn() as s:
                s.layers["c3_neuron_segmentation"].selectedAlpha = 0.0
                s.layers["c3_neuron_segmentation"].notSelectedAlpha = 0.0

    print(
        f"Starting a Neuroglancer instance at {app.ng_viewer}, centered at x,y,x {0,0,0}"
    )
