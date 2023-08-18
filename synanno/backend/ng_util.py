import neuroglancer
from random import randint

# import the package app
from synanno import app

# for type hinting
import numpy as np

import numpy.typing as npt


from typing import Union


def setup_ng(source: Union[npt.NDArray, str], target: Union[npt.NDArray, str]) -> None:
    """Setup function for the Neuroglancer (ng) that enables the recording and depiction
    of center markers for newly identified FN instances.

    Args:
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
    coordinate_space = neuroglancer.CoordinateSpace(
        names=[
            list(app.coordinate_order.keys())[0],
            list(app.coordinate_order.keys())[1],
            list(app.coordinate_order.keys())[2],
        ],
        units=["nm", "nm", "nm"],
        scales=np.array([int(res[0]) for res in app.coordinate_order.values()]).astype(
            int
        ),
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

        # additional layer that lets the user mark the center of FPs
        s.layers.append(
            name="center_dot",
            layer=neuroglancer.LocalAnnotationLayer(
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
            ),
        )

        # init the view position
        s.position = [0, 0, 0]

    def center_annotation(s):
        """Ng action function that enables the recording and depiction
        of center markers for newly identified FN instances.
        """

        # record the current mouse position
        center = s.mouse_voxel_coordinates

        center_coord = {
            key: int(value)
            for key, value in zip(list(app.coordinate_order.keys()), center)
        }

        # split the position and convert to int
        app.cz = int(center_coord["z"])
        app.cy = int(center_coord["y"])
        app.cx = int(center_coord["x"])

        # add a yellow dot at the recorded position with in the NG
        with app.ng_viewer.txn() as l:
            pt = neuroglancer.PointAnnotation(
                point=[int(center[0]), int(center[1]), int(center[2])], id=f"point{1}"
            )
            l.layers["center_dot"].annotations.append(pt)

    # add the function as action
    app.ng_viewer.actions.add("center", center_annotation)
    with app.ng_viewer.config_state.txn() as s:
        # set the trigger for the action to the key 'c'
        s.input_event_bindings.viewer["keyc"] = "center"

    print(
        f"Starting a Neuroglancer instance at {app.ng_viewer}, centered at x,y,x {0,0,0}"
    )
