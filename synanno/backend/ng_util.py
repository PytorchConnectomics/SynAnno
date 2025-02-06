import neuroglancer
from random import randint

# for type hinting
import numpy as np

import numpy.typing as npt


from typing import Union
from flask import Flask


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
    app.ng_version = str(randint(0, 32e2))

    # setup a Tornado web server and create viewer instance
    neuroglancer.set_server_bind_address(
        bind_address=app.config["NG_IP"], bind_port=app.config["NG_PORT"]
    )
    app.ng_viewer = neuroglancer.Viewer(token=app.ng_version)

    # default coordinate order to pass in if processing route not undergone
    default_coordinate_order = {"x": (4, 4), "y": (4, 4), "z": (40, 40)}

    # specify the NG coordinate space
    if hasattr(app, "coordinate_order") and app.coordinate_order:
        coordinate_order = app.coordinate_order
    else:
        coordinate_order = default_coordinate_order

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
        ):  # assuming it's a string URL for the precomputed source
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

        # TODO: use dimensions from processing.py to determine good starting coordinates
        # init the view position (arbitrary default in H01 range; change later)
        s.position = [711044, 315210, 2587]

        # additional layer that lets the user mark the center of FPs
        s.layers["center_dot"] = neuroglancer.LocalAnnotationLayer(
            dimensions=coordinate_space,
            annotation_properties=[
                neuroglancer.AnnotationPropertySpec(
                    id="color",
                    type="rgb",
                    default="red",
                ),
                neuroglancer.AnnotationPropertySpec(
                    id="size",
                    type="float32",
                    default=10,
                ),
                neuroglancer.AnnotationPropertySpec(
                    id="p_int8",
                    type="int8",
                    default=10,
                ),
                neuroglancer.AnnotationPropertySpec(
                    id="p_uint8",
                    type="uint8",
                    default=10,
                ),
            ],
            annotations=[],
        )

        def center_annotation(s):
            """Ng action function that enables the recording and depiction
            of center markers for newly identified FN instances.
            """

            # record the current mouse position
            center = s.mouse_voxel_coordinates

            # prevent crashes if off ng view
            if center is None:
                print("No mouse coordinates available.")
                return

            center_coord = {
                key: int(value) for key, value in zip(coordinate_space.names, center)
            }

            # split the position and convert to int
            app.cz = int(center_coord["z"])
            app.cy = int(center_coord["y"])
            app.cx = int(center_coord["x"])

            # add a yellow dot at the recorded position within the NG
            with app.ng_viewer.txn() as l:
                pt = neuroglancer.PointAnnotation(
                    point=[int(center[0]), int(center[1]), int(center[2])],
                    id=f"point{1}",
                )
                l.layers["center_dot"].annotations.append(pt)

        # add the center dot as action
        app.ng_viewer.actions.add("center", center_annotation)
        with app.ng_viewer.config_state.txn() as s:
            # set the trigger for the action to the key 'c'
            s.input_event_bindings.viewer["keyc"] = "center"

        def get_hovered_neuron_id(s):
            """Retrieve and print the neuron ID at the voxel under the mouse cursor."""
            # get the current mouse voxel coordinates
            voxel_coords = s.mouse_voxel_coordinates

            # prevent crashes if off ng view
            if voxel_coords is None:
                print("No mouse coordinates available.")
                return

            print(f"Mouse Voxel Coordinates: {voxel_coords}")

            # retrieve the selected neuron ID from the segmentation layer
            neuron_info = s.selected_values["neuropil"].value
            print(f"Raw Selected Neuron ID: {neuron_info}")

            neuron_id = None

            # handle different types of neuron_info
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

            # store the neuron ID globally in the app context
            app.selected_neuron_id = neuron_id
            print(f"Selected Neuron ID: {neuron_id}")

        # bind the action to a key, e.g., 'n'
        app.ng_viewer.actions.add("get_neuron_id", get_hovered_neuron_id)

        with app.ng_viewer.config_state.txn() as s:
            s.input_event_bindings.viewer["keyn"] = "get_neuron_id"

        def enable_neuropil_layer():
            """Enable the neuropil neuron segmentation layer."""
            with app.ng_viewer.txn() as s:
                s.layers["neuropil"].selectedAlpha = 0.5
                s.layers["neuropil"].notSelectedAlpha = 0.1

        def disable_neuropil_layer():
            """Disable the neuropil neuron segmentation layer."""
            with app.ng_viewer.txn() as s:
                s.layers["neuropil"].selectedAlpha = 0.0
                s.layers["neuropil"].notSelectedAlpha = 0.0

    print(
        f"Starting a Neuroglancer instance at {app.ng_viewer}, centered at x,y,x {0,0,0}"
    )
