import base64
import io
import json
import logging
import re
from io import BytesIO

import numpy as np
import pandas as pd
from cloudvolume import Bbox
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_cors import cross_origin
from PIL import Image

from synanno.backend.processing import (
    calculate_crop_pad,
    process_instance,
    update_slice_number,
)
from synanno.backend.utils import (
    adjust_datatype,
    img_to_png_bytes,
    png_bytes_to_pil_img,
)

blueprint = Blueprint("manual_annotate", __name__)
logger = logging.getLogger(__name__)


@blueprint.route("/draw")
def draw() -> str:
    """Reload the updated JSON and render the draw view.
    Careful: The draw view can also be invoked via '/set-data/draw' - see opendata.py

    Returns:
        Renders the draw view.
    """
    data = current_app.df_metadata[
        current_app.df_metadata["Label"].isin(["Incorrect", "Unsure"])
    ].to_dict("records")
    return render_template("draw.html", images=data)


def get_instance_data(page: int, index: int) -> dict:
    """Retrieve instance specific data from metadata."""
    return current_app.df_metadata.query(
        "Page == @page & Image_Index == @index"
    ).to_dict("records")[0]


def decode_image(image_base64: str) -> Image:
    """Decode base64 image data."""
    image_data = re.sub("^data:image/.+;base64,", "", image_base64)
    return Image.open(BytesIO(base64.b64decode(image_data)))


def resize_image(image: Image, crop_axes: tuple) -> Image:
    """Resize image to the specified crop axes."""
    return image.resize((crop_axes[0], crop_axes[1]), Image.LANCZOS)


def save_image_data(
    img_index: str,
    canvas_type: str,
    image_byte: bytes,
    viewed_instance_slice: int,
) -> None:
    """Save image data to the current app's target image data."""
    if canvas_type == "circlePre" or canvas_type == "circlePost":
        current_app.target_image_data[img_index][canvas_type] = {
            str(viewed_instance_slice): image_byte
        }
    elif canvas_type == "curve":
        if canvas_type not in current_app.target_image_data[img_index]:
            current_app.target_image_data[img_index][canvas_type] = {}
        current_app.target_image_data[img_index][canvas_type][
            str(viewed_instance_slice)
        ] = image_byte


@blueprint.route("/save_canvas", methods=["POST"])
def save_canvas() -> dict:
    """Serves an Ajax request from draw.js, downloading, converting, and saving
    the canvas as image.

    Returns:
        Passes the instance specific session information as JSON to draw.js
    """
    coordinate_order = list(current_app.coordinate_order.keys())
    image = decode_image(request.form["imageBase64"])
    page = int(request.form["page"])
    index = int(request.form["data_id"])
    viewed_instance_slice = int(request.form["viewed_instance_slice"])
    canvas_type = str(request.form["canvas_type"])

    crop_axes = (
        (current_app.crop_size_y, current_app.crop_size_x)
        if coordinate_order.index("y") < coordinate_order.index("x")
        else (current_app.crop_size_x, current_app.crop_size_y)
    )
    image = resize_image(image, crop_axes)
    image_byte = img_to_png_bytes(image)

    data = get_instance_data(page, index)
    img_index = str(data["Image_Index"])

    save_image_data(img_index, canvas_type, image_byte, viewed_instance_slice)

    data = json.dumps(data)
    final_json = jsonify(data=data)

    return final_json


@blueprint.route("/load_missing_slices", methods=["POST"])
def load_missing_slices() -> dict:
    """The auto segmentation view needs a set number of slices per instance (depth).
    Coming from the Annotation view the user might use a different number of slices
    - most likely a single slice. To enable the user to go through the individual
    slices, redraw the mask and auto generate the mask we thus need to download the
    remaining slices.

    Returns:
        JSON response indicating success.
    """
    data = current_app.df_metadata.query(
        "Label == 'Incorrect' or Label == 'Unsure'"
    ).to_dict("records")

    update_slice_number(data)

    data = current_app.df_metadata.query(
        "Label == 'Incorrect' or Label == 'Unsure'"
    ).to_dict("records")

    for instance in data:
        process_instance(instance)

    return jsonify({"result": "success"})


@blueprint.route("/ng_bbox_fn", methods=["POST"])
@cross_origin()
def ng_bbox_fn() -> dict:
    """Serves an Ajax request by draw_module.js, passing the coordinates of the center
    point of a newly marked FN to the front end, enabling the front end to depict the
    values and the user to manual update/correct them.

    Returns:
        The x and y coordinates of the center of the newly added instance as well as
        the upper and the lower z bound of the instance as JSON to draw_module.js
    """
    coordinate_order = list(current_app.coordinate_order.keys())
    expand_z = current_app.crop_size_z_draw // 2

    cz1 = int(current_app.cz) - expand_z if int(current_app.cz) - expand_z > 0 else 0
    cz2 = (
        int(current_app.cz) + expand_z
        if int(current_app.cz) + expand_z
        < current_app.vol_dim_scaled[coordinate_order.index("z")]
        else current_app.vol_dim_scaled[coordinate_order.index("z")]
    )

    return jsonify(
        {
            "z1": str(cz1),
            "z2": str(cz2),
            "my": str(current_app.cy),
            "mx": str(current_app.cx),
        }
    )


@blueprint.route("/ng_bbox_fn_save", methods=["POST"])
@cross_origin()
def ng_bbox_fn_save() -> dict:
    """Serves an Ajax request by draw_module.js, that passes the manual updated/
    corrected bb coordinates to this backend function. Additionally, the
    function creates a new item instance and updates the metadata dataframe.

    Returns:
        The x and y coordinates of the center of the newly added instance as well as
        the upper and the lower z bound of the instance as JSON to draw_module.js
    """
    coordinate_order = list(current_app.coordinate_order.keys())
    cz1, cz2, current_app.cz, current_app.cy, current_app.cx = (
        get_corrected_coordinates(request)
    )

    item = create_new_item()

    bbox = define_bbox(cz1, cz2, coordinate_order)
    item["Original_Bbox"] = scale_bbox(bbox, coordinate_order)

    crop_bbox, img_padding = calculate_crop_pad(bbox, current_app.vol_dim_scaled)
    crop_box_dict = map_bbox_to_dict(crop_bbox, coordinate_order)

    bound = create_bbox_bound(crop_box_dict, coordinate_order)
    cropped_img = download_cropped_image(bound, coordinate_order)

    cropped_img = np.pad(cropped_img, img_padding, mode="constant", constant_values=148)
    item["Adjusted_Bbox"] = scale_bbox(crop_bbox, coordinate_order)
    item["Padding"] = scale_padding(img_padding, coordinate_order)

    save_volume_slices(cropped_img, item, coordinate_order)

    df_item = pd.DataFrame([item])
    current_app.df_metadata = pd.concat(
        [current_app.df_metadata, df_item], ignore_index=True
    )

    return jsonify(
        {
            "z1": str(int(cz1)),
            "z2": str(int(cz2)),
            "my": str(int(current_app.cy)),
            "mx": str(int(current_app.cx)),
        }
    )


def get_corrected_coordinates(request) -> tuple:
    """Retrieve and correct coordinates from the request."""
    cz1 = int(request.form["z1"])
    cz2 = int(request.form["z2"])
    current_app.cz = int(cz1 + ((cz2 - cz1) // 2))
    current_app.cy = int(request.form["my"])
    current_app.cx = int(request.form["mx"])
    return cz1, cz2, current_app.cz, current_app.cy, current_app.cx


def create_new_item() -> dict:
    """Create a new item instance for the metadata dataframe."""
    item = {}
    if not (len(current_app.df_metadata) % current_app.per_page == 0):
        item["Page"] = len(current_app.df_metadata) // current_app.per_page + 1
    else:
        item["Page"] = len(current_app.df_metadata) // current_app.per_page

    coordinate_order = list(current_app.coordinate_order.keys())

    item["Image_Index"] = len(current_app.df_metadata)
    item["materialization_index"] = -1
    item["section_index"] = -1
    item["tree_traversal_index"] = -1
    item["Label"] = "Incorrect"
    item["Annotated"] = "No"
    item["neuron_id"] = -1
    item["Error_Description"] = "False Negatives"
    item["Y_Index"] = coordinate_order.index("y")
    item["Z_Index"] = coordinate_order.index("z")
    item["X_Index"] = coordinate_order.index("x")
    item["Middle_Slice"] = int(current_app.cz)
    item["crop_size_x"] = current_app.crop_size_x
    item["crop_size_y"] = current_app.crop_size_y
    item["crop_size_z"] = current_app.crop_size_z_draw
    item["pre_pt_z"] = None
    item["pre_pt_y"] = None
    item["pre_pt_x"] = None
    item["post_pt_z"] = None
    item["post_pt_y"] = None
    item["post_pt_x"] = None
    item["cz0"] = int(int(current_app.cz) / current_app.scale["z"])
    item["cy0"] = int(int(current_app.cy) / current_app.scale["y"])
    item["cx0"] = int(int(current_app.cx) / current_app.scale["x"])
    return item


def define_bbox(cz1: int, cz2: int, coordinate_order: list) -> list:
    """Define the bounding box for the new item."""
    expand_x = current_app.crop_size_x // 2
    expand_y = current_app.crop_size_y // 2

    bb_x1 = int(current_app.cx) - expand_x if int(current_app.cx) - expand_x > 0 else 0
    bb_x2 = (
        int(current_app.cx) + expand_x
        if int(current_app.cx) + expand_x
        < current_app.vol_dim_scaled[coordinate_order.index("x")]
        else current_app.vol_dim_scaled[coordinate_order.index("x")]
    )

    bb_y1 = int(current_app.cy) - expand_y if int(current_app.cy) - expand_y > 0 else 0
    bb_y2 = (
        int(current_app.cy) + expand_y
        if int(current_app.cy) + expand_y
        < current_app.vol_dim_scaled[coordinate_order.index("y")]
        else current_app.vol_dim_scaled[coordinate_order.index("y")]
    )

    bbox = [0] * 6
    bbox[coordinate_order.index("z") * 2] = int(cz1)
    bbox[coordinate_order.index("z") * 2 + 1] = int(cz2)
    bbox[coordinate_order.index("y") * 2] = int(bb_y1)
    bbox[coordinate_order.index("y") * 2 + 1] = int(bb_y2)
    bbox[coordinate_order.index("x") * 2] = int(bb_x1)
    bbox[coordinate_order.index("x") * 2 + 1] = int(bb_x2)
    return bbox


def scale_bbox(bbox: list, coordinate_order: list) -> list:
    """Scale the bounding box coordinates to the original target size."""
    return [
        int(bbox[0] / current_app.scale[coordinate_order[0]]),
        int(bbox[1] / current_app.scale[coordinate_order[0]]),
        int(bbox[2] / current_app.scale[coordinate_order[1]]),
        int(bbox[3] / current_app.scale[coordinate_order[1]]),
        int(bbox[4] / current_app.scale[coordinate_order[2]]),
        int(bbox[5] / current_app.scale[coordinate_order[2]]),
    ]


def map_bbox_to_dict(crop_bbox: list, coordinate_order: list) -> dict:
    """Map the bounding box coordinates to a dictionary."""
    return {
        coordinate_order[0] + "1": crop_bbox[0],
        coordinate_order[0] + "2": crop_bbox[1],
        coordinate_order[1] + "1": crop_bbox[2],
        coordinate_order[1] + "2": crop_bbox[3],
        coordinate_order[2] + "1": crop_bbox[4],
        coordinate_order[2] + "2": crop_bbox[5],
    }


def create_bbox_bound(crop_box_dict: dict, coordinate_order: list) -> Bbox:
    """Create a bounding box for the current synapse based on the coordinate order."""
    return Bbox(
        [
            crop_box_dict[coordinate_order[0] + "1"],
            crop_box_dict[coordinate_order[1] + "1"],
            crop_box_dict[coordinate_order[2] + "1"],
        ],
        [
            crop_box_dict[coordinate_order[0] + "2"],
            crop_box_dict[coordinate_order[1] + "2"],
            crop_box_dict[coordinate_order[2] + "2"],
        ],
    )


def download_cropped_image(bound: Bbox, coordinate_order: list) -> np.ndarray:
    """Download the cropped image from the cloud volume."""
    coord_resolution = [int(res[0]) for res in current_app.coordinate_order.values()]
    cropped_img = current_app.source_cv.download(
        bound, coord_resolution=coord_resolution, mip=0
    )
    return cropped_img.squeeze(axis=3)


def scale_padding(img_padding: list, coordinate_order: list) -> list:
    """Scale the padding to the original target size."""
    return [
        [
            int(img_padding[0][0] / current_app.scale[coordinate_order[0]]),
            int(img_padding[0][1] / current_app.scale[coordinate_order[0]]),
        ],
        [
            int(img_padding[1][0] / current_app.scale[coordinate_order[1]]),
            int(img_padding[1][1] / current_app.scale[coordinate_order[1]]),
        ],
        [
            int(img_padding[2][0] / current_app.scale[coordinate_order[2]]),
            int(img_padding[2][1] / current_app.scale[coordinate_order[2]]),
        ],
    ]


def save_volume_slices(
    cropped_img: np.ndarray, item: dict, coordinate_order: list
) -> None:
    """Save the volume slices to the current app's source image data."""
    slice_axis = coordinate_order.index("z")
    for s in range(cropped_img.shape[slice_axis]):
        image_index = str(item["Image_Index"])
        img_z_index = str(item["Adjusted_Bbox"][slice_axis * 2] + s)

        slicing_img = [s if idx == slice_axis else slice(None) for idx in range(3)]
        img_c = Image.fromarray(adjust_datatype(cropped_img[tuple(slicing_img)])[0])
        img_io = io.BytesIO()
        img_c.save(img_io, format="PNG")
        img_io.seek(0)
        current_app.source_image_data[image_index][img_z_index] = img_io.getvalue()


def get_coordinate_order() -> list:
    """Retrieve the coordinate order from the current app."""
    return list(current_app.coordinate_order.keys())


def scale_coordinates(x: int, y: int, z: int) -> tuple:
    """Scale the coordinates to the original target size."""
    x = int(x / current_app.scale["x"])
    y = int(y / current_app.scale["y"])
    z = int(z / current_app.scale["z"])
    return x, y, z


def update_metadata(data_id: int, page: int, x: int, y: int, z: int, id: str) -> None:
    """Update the metadata with the new coordinates."""
    if id == "pre":
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            ["pre_pt_x", "pre_pt_y", "pre_pt_z"],
        ] = [x, y, z]
    elif id == "post":
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            ["post_pt_x", "post_pt_y", "post_pt_z"],
        ] = [x, y, z]
    else:
        raise ValueError("id must be pre or post")


def update_segmentation_color(data_id: str, middle_slice: int, color: tuple) -> None:
    """Update the color of the segmentation in the middle slice."""
    if (
        data_id in current_app.target_image_data
        and middle_slice in current_app.target_image_data[str(data_id)]
    ):
        seg_slice = current_app.target_image_data[str(data_id)][str(middle_slice)]
        seg_slice_numpy = np.array(png_bytes_to_pil_img(seg_slice))

        mask_main = np.all(
            seg_slice_numpy[:, :, :3] == current_app.pre_id_color_main, axis=-1
        )
        mask_sub = np.all(
            seg_slice_numpy[:, :, :3] == current_app.pre_id_color_sub, axis=-1
        )
        mask = mask_main | mask_sub
        seg_slice_numpy[mask] = color

        current_app.target_image_data[str(data_id)][str(middle_slice)] = (
            img_to_png_bytes(seg_slice_numpy)
        )


@blueprint.route("/save_pre_post_coordinates", methods=["POST"])
@cross_origin()
def save_pre_post_coordinates() -> tuple:
    """Save the pre or post coordinates."""
    coordinate_order = get_coordinate_order()
    x_index, y_index, z_index = (
        coordinate_order.index("x"),
        coordinate_order.index("y"),
        coordinate_order.index("z"),
    )
    x, y, z = (
        int(round(float(request.form["x"]))),
        int(round(float(request.form["y"]))),
        int(round(float(request.form["z"]))),
    )
    data_id, page, id = (
        int(request.form["data_id"]),
        int(request.form["page"]),
        str(request.form["id"]),
    )
    x, y, z = scale_coordinates(x, y, z)
    x += (
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "Adjusted_Bbox",
        ].values[0][x_index * 2]
        - current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "Padding",
        ].values[0][x_index][0]
    )

    y += (
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "Adjusted_Bbox",
        ].values[0][y_index * 2]
        - current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "Padding",
        ].values[0][y_index][0]
    )
    z -= current_app.df_metadata.loc[
        (current_app.df_metadata["Image_Index"] == data_id)
        & (current_app.df_metadata["Page"] == page),
        "Padding",
    ].values[0][z_index][0]

    update_metadata(data_id, page, x, y, z, id)

    middle_slice = current_app.df_metadata.loc[
        (current_app.df_metadata["Image_Index"] == data_id)
        & (current_app.df_metadata["Page"] == page),
        "Middle_Slice",
    ].values[0]

    update_segmentation_color(data_id, middle_slice, (128, 128, 128, 0.5))
    return json.dumps({"success": True}), 200, {"ContentType": "application/json"}


@blueprint.route("/get_coordinates", methods=["GET"])
def get_coordinates() -> dict:
    """Get the current coordinates of the Neuroglancer instance."""
    return jsonify({"cz": current_app.cz, "cy": current_app.cy, "cx": current_app.cx})
