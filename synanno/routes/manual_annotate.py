import base64
import json
import logging
import re
from io import BytesIO

import numpy as np
from flask import Blueprint, current_app, jsonify, render_template, request
from flask_cors import cross_origin
from PIL import Image

from synanno.backend.processing import process_instance, update_slice_number
from synanno.backend.utils import img_to_png_bytes, png_bytes_to_pil_img

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


@blueprint.route("/get_coordinates", methods=["GET"])
def get_coordinates() -> dict:
    """Get the current coordinates of the Neuroglancer instance."""
    return jsonify({"cz": current_app.cz, "cy": current_app.cy, "cx": current_app.cx})
