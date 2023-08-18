# import the package app
from synanno import app

# flask util functions
from flask import render_template, request, jsonify, session

# flask ajax requests
from flask_cors import cross_origin

# open, resize and transform images
from PIL import Image

# handle binary stream from base64 decoder
from io import BytesIO

# base64 decoder to convert canvas
import base64

# regular expression matching
import re

# manage paths and files
import os

# import processing functions
from synanno.backend.processing import calculate_crop_pad, create_dir

# for type hinting
from jinja2 import Template
from typing import Dict

import json

from cloudvolume import Bbox

import numpy as np

import pandas as pd

from synanno.backend.utils import adjust_datatype

import glob


@app.route("/draw")
def draw() -> Template:
    """Reload the updated JSON and render the draw view.
    Careful: The draw view can also be invoked via '/set-data/draw' - see opendata.py

    Return:
        Renders the draw view.
    """

    # retrieve the data from the dataframe for which the user has marked the instance as "Incorrect" or "Unsure"
    data = app.df_metadata[
        app.df_metadata["Label"].isin(["Incorrect", "Unsure"])
    ].to_dict("records")
    return render_template("draw.html", images=data)


@app.route("/save_canvas", methods=["POST"])
def save_canvas() -> Dict[str, object]:
    """Serves an Ajax request from draw.js, downloading, converting, and saving
    the canvas as image.

    Return:
        Passes the instance specific session information as JSON to draw.js
    """

    coordinate_order = list(app.coordinate_order.keys())

    # retrieve the canvas
    image_data = re.sub("^data:image/.+;base64,", "", request.form["imageBase64"])

    # retrieve the instance specifiers
    page = int(request.form["page"])
    index = int(request.form["data_id"])
    viewed_instance_slice = int(request.form["viewed_instance_slice"])
    canvas_type = str(request.form["canvas_type"])

    # convert the canvas to PIL image format
    im = Image.open(BytesIO(base64.b64decode(image_data)))

    # adjust the size of the PIL Image in accordance with the session's path size
    crop_axes = (
        (session["crop_size_y"], session["crop_size_x"])
        if coordinate_order.index("y") < coordinate_order.index("x")
        else (session["crop_size_x"], session["crop_size_y"])
    )
    im = im.resize((crop_axes[0], crop_axes[1]), Image.LANCZOS)

    # create folder where to save the image
    folder_path = os.path.join(
        os.path.join(app.root_path, app.config["STATIC_FOLDER"]), "custom_masks"
    )
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # retrieve the instance specific information for naming the image

    data = app.df_metadata.query("Page == @page & Image_Index == @index").to_dict(
        "records"
    )[0]
    coordinates = "_".join(map(str, data["Adjusted_Bbox"]))
    img_index = str(data["Image_Index"])

    # image name
    img_name = (
        canvas_type
        + "_idx_"
        + img_index
        + "_slice_"
        + str(viewed_instance_slice)
        + "_cor_"
        + coordinates
        + ".png"
    )

    # we only want to save one pre and one post circle per instance
    if canvas_type == "circlePre" or canvas_type == "circlePost":
        # if a file exist with path path= os.path.join(folder_path, canvas_type +'_idx_'+img_index)
        existing_path = glob.glob(
            os.path.join(
                folder_path,
                canvas_type
                + "_idx_"
                + img_index
                + "_slice_*_cor_"
                + coordinates
                + ".png",
            )
        )
        if len(existing_path) > 0:
            # remove the existing file
            os.remove(existing_path[0])

    # save the mask
    im.save(os.path.join(folder_path, img_name))

    # send the instance specific information to draw.js
    data = json.dumps(data)
    final_json = jsonify(data=data)

    return final_json


@app.route("/ng_bbox_fn", methods=["POST"])
@cross_origin()
def ng_bbox_fn() -> Dict[str, object]:
    """Serves an Ajax request by draw_module.js, passing the coordinates of the center point of a newly marked FN to the front end,
    enabling the front end to depict the values and the user to manual update/correct them.

    Return:
        The x and y coordinates of the center of the newly added instance as well as the upper and the
        lower z bound of the instance as JSON to draw_module.js
    """

    coordinate_order = list(app.coordinate_order.keys())

    # expand the bb in in z direction
    # we expand the front and the back z value dependent on their proximity to the boarders

    expand_z = session["crop_size_z"] // 2

    cz1 = int(app.cz) - expand_z if int(app.cz) - expand_z > 0 else 0
    cz2 = (
        int(app.cz) + expand_z
        if int(app.cz) + expand_z < app.vol_dim_scaled[coordinate_order.index("z")]
        else app.vol_dim_scaled[coordinate_order.index("z")]
    )

    # server the coordinates to the front end
    return jsonify(
        {
            "z1": str(cz1),
            "z2": str(cz2),
            "my": str(app.cy),
            "mx": str(app.cx),
        }
    )


@app.route("/ng_bbox_fn_save", methods=["POST"])
@cross_origin()
def ng_bbox_fn_save() -> Dict[str, object]:
    """Serves an Ajax request by draw_module.js, that passes the manual updated/corrected bb coordinates
    to this backend function. Additionally, the function creates a new item instance and
    updates the metadata dataframe.

    Return:
        The x and y coordinates of the center of the newly added instance as well as the upper and the
        lower z bound of the instance as JSON to draw_module.js
    """

    coordinate_order = list(app.coordinate_order.keys())

    # retrieve manual correction of coordinates
    cz1 = int(request.form["z1"])
    cz2 = int(request.form["z2"])
    app.cz = int(cz1 + ((cz2 - cz1) // 2))
    app.cy = int(request.form["my"])
    app.cx = int(request.form["mx"])

    ## add the new instance to the the json und update the session data

    # create new item
    item = dict()

    # index starts at one, adding item, therefore, incrementing by one

    # calculate the number of pages needed for the instance count in the JSON
    if not (len(app.df_metadata) % session.get("per_page") == 0):
        item["Page"] = len(app.df_metadata) // session.get("per_page") + 1
    else:
        item["Page"] = len(app.df_metadata) // session.get("per_page")

    # divide the number of instance by the number of instances per page to get the index of the current page

    ### Note that all dimensions are saved in then scale of the target (segmentation) volume. ###

    item["Image_Index"] = len(app.df_metadata) + 1

    # crop out and save the relevant gt and im
    idx_dir = create_dir("./synanno/static/", "Images")
    img_folder = create_dir(idx_dir, "Img")
    img_all = create_dir(img_folder, str(item["Image_Index"]))

    item["GT"] = "None"  # do not save the GT as we do not have masks for the FNs
    item["EM"] = "/" + "/".join(img_all.strip(".\\").split("/")[2:])

    item["Label"] = "Incorrect"
    item["Annotated"] = "No"
    item["Error_Description"] = "False Negatives"
    item["X_Index"] = coordinate_order.index("x")
    item["Y_Index"] = coordinate_order.index("y")
    item["Z_Index"] = coordinate_order.index("z")

    item["Middle_Slice"] = int(app.cz)

    # scale the coordinates to the original target size
    item["cz0"] = int(int(app.cz) / app.scale["z"])
    item["cy0"] = int(int(app.cy) / app.scale["y"])
    item["cx0"] = int(int(app.cx) / app.scale["x"])

    # define the bbox
    expand_x = session["crop_size_x"] // 2
    expand_y = session["crop_size_y"] // 2

    bb_x1 = int(app.cx) - expand_x if int(app.cx) - expand_x > 0 else 0
    bb_x2 = (
        int(app.cx) + expand_x
        if int(app.cx) + expand_x < app.vol_dim_scaled[coordinate_order.index("x")]
        else app.vol_dim_scaled[coordinate_order.index("x")]
    )

    bb_y1 = int(app.cy) - expand_y if int(app.cy) - expand_y > 0 else 0
    bb_y2 = (
        int(app.cy) + expand_y
        if int(app.cy) + expand_y < app.vol_dim_scaled[coordinate_order.index("y")]
        else app.vol_dim_scaled[coordinate_order.index("y")]
    )

    # we update the pre and post coordinates with None as we do not have them initially for FNs
    item["pre_pt_z"] = None
    item["pre_pt_y"] = None
    item["pre_pt_x"] = None
    item["post_pt_z"] = None
    item["post_pt_y"] = None
    item["post_pt_x"] = None

    item["crop_size_x"] = session["crop_size_x"]
    item["crop_size_y"] = session["crop_size_y"]
    item["crop_size_z"] = session["crop_size_z"]

    # save the original bounding box using the provided coordinate order
    bbox = [None] * 6
    bbox[coordinate_order.index("z") * 2] = int(cz1)
    bbox[coordinate_order.index("z") * 2 + 1] = int(cz2)
    bbox[coordinate_order.index("y") * 2] = int(bb_y1)
    bbox[coordinate_order.index("y") * 2 + 1] = int(bb_y2)
    bbox[coordinate_order.index("x") * 2] = int(bb_x1)
    bbox[coordinate_order.index("x") * 2 + 1] = int(bb_x2)

    # scale the coordinates to the original target size
    item["Original_Bbox"] = [
        int(bbox[0] / app.scale[coordinate_order[0]]),
        int(bbox[1] / app.scale[coordinate_order[0]]),
        int(bbox[2] / app.scale[coordinate_order[1]]),
        int(bbox[3] / app.scale[coordinate_order[1]]),
        int(bbox[4] / app.scale[coordinate_order[2]]),
        int(bbox[5] / app.scale[coordinate_order[2]]),
    ]

    crop_bbox, img_padding = calculate_crop_pad(bbox, app.vol_dim_scaled)
    # map the bounding box coordinates to a dictionary
    crop_box_dict = {
        coordinate_order[0] + "1": crop_bbox[0],
        coordinate_order[0] + "2": crop_bbox[1],
        coordinate_order[1] + "1": crop_bbox[2],
        coordinate_order[1] + "2": crop_bbox[3],
        coordinate_order[2] + "1": crop_bbox[4],
        coordinate_order[2] + "2": crop_bbox[5],
    }

    # retrieve the order of the coordinates (xyz, xzy, yxz, yzx, zxy, zyx)
    cord_order = list(app.coordinate_order.keys())

    # create the bounding box for the current synapse based on the order of the coordinates
    bound = Bbox(
        [
            crop_box_dict[cord_order[0] + "1"],
            crop_box_dict[cord_order[1] + "1"],
            crop_box_dict[cord_order[2] + "1"],
        ],
        [
            crop_box_dict[cord_order[0] + "2"],
            crop_box_dict[cord_order[1] + "2"],
            crop_box_dict[cord_order[2] + "2"],
        ],
    )

    # Convert coordinate resolution values to integers
    # Each coordinate resolution is a tuple where the first value is the resolution of the source image
    # and the second value is the resolution of the target image
    coord_resolution = [int(res[0]) for res in app.coordinate_order.values()]

    # Retrieve the source and target images from the cloud volume
    cropped_img = app.source_cv.download(
        bound, coord_resolution=coord_resolution, mip=0
    )

    # save the cropped image
    Image.fromarray(adjust_datatype(cropped_img.squeeze(axis=3)[:, :, 0])[0]).save(
        os.path.join(img_all, "X.png"), "PNG"
    )

    # remove the singleton dimension, take care as the z dimension might be singleton
    cropped_img = cropped_img.squeeze(axis=3)

    # pad the images and synapse segmentation to fit the crop size (sz)
    cropped_img = np.pad(cropped_img, img_padding, mode="constant", constant_values=148)

    # scale the coordinates to the original target size
    item["Adjusted_Bbox"] = item["Original_Bbox"] = [
        int(crop_bbox[0] / app.scale[coordinate_order[0]]),
        int(crop_bbox[1] / app.scale[coordinate_order[0]]),
        int(crop_bbox[2] / app.scale[coordinate_order[1]]),
        int(crop_bbox[3] / app.scale[coordinate_order[1]]),
        int(crop_bbox[4] / app.scale[coordinate_order[2]]),
        int(crop_bbox[5] / app.scale[coordinate_order[2]]),
    ]

    # scale the padding to the original target size
    item["Padding"] = [
        [
            int(img_padding[0][0] / app.scale[coordinate_order[0]]),
            int(img_padding[0][1] / app.scale[coordinate_order[0]]),
        ],
        [
            int(img_padding[1][0] / app.scale[coordinate_order[1]]),
            int(img_padding[1][1] / app.scale[coordinate_order[1]]),
        ],
        [
            int(img_padding[2][0] / app.scale[coordinate_order[2]]),
            int(img_padding[2][1] / app.scale[coordinate_order[2]]),
        ],
    ]

    # Determine the slice axis index based on the first entry in coord_order
    slice_axis = coordinate_order.index("z")

    # save volume slices
    for s in range(cropped_img.shape[slice_axis]):
        img_name = str(item["Adjusted_Bbox"][slice_axis * 2] + s) + ".png"

        # image
        slicing_img = [s if idx == slice_axis else slice(None) for idx in range(3)]
        img_c = Image.fromarray(adjust_datatype(cropped_img[tuple(slicing_img)])[0])
        img_c.save(os.path.join(img_all, img_name), "PNG")

    assert set(item.keys()) == set(
        app.df_metadata.columns
    ), f"Difference: {set(item.keys()).symmetric_difference(set(app.df_metadata.columns))}"

    df_item = pd.DataFrame([item])
    app.df_metadata = pd.concat([app.df_metadata, df_item], ignore_index=True)

    return jsonify(
        {
            "z1": str(int(cz1)),
            "z2": str(int(cz2)),
            "my": str(int(app.cy)),
            "mx": str(int(app.cx)),
        }
    )


@app.route("/save_pre_post_coordinates", methods=["POST"])
@cross_origin()
def save_pre_post_coordinates() -> None:
    # retrieve the data from the request
    # the x and y value from the java script refers to the classical x=horizontal and y=vertical axis
    # however, this does not necessarily correspond to the x and y axis order of the image

    coordinate_order = list(app.coordinate_order.keys())

    x_index = coordinate_order.index("x")
    y_index = coordinate_order.index("y")
    z_index = coordinate_order.index("z")

    x = int(round(float(request.form["x"])))
    y = int(round(float(request.form["y"])))
    z = int(round(float(request.form["z"])))
    data_id = int(request.form["data_id"])
    page = int(request.form["page"])
    id = str(request.form["id"])

    # scaling the coordinates to the original target size
    x = int(x / app.scale["x"])
    y = int(y / app.scale["y"])
    z = int(z / app.scale["z"])

    x = (
        x
        + app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "Adjusted_Bbox",
        ].values[0][x_index * 2]
        - app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "Padding",
        ].values[0][x_index][0]
    )
    y = (
        y
        + app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "Adjusted_Bbox",
        ].values[0][y_index * 2]
        - app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "Padding",
        ].values[0][y_index][0]
    )
    z = (
        z
        - app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "Padding",
        ].values[0][z_index][0]
    )

    # if id=='pre' update 'pre_pt_x', 'pre_pt_y', 'post_pt_y' of the instance specific information in the dataframe
    if id == "pre":
        app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "pre_pt_x",
        ] = x
        app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "pre_pt_y",
        ] = y
        app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "pre_pt_z",
        ] = z
    elif id == "post":
        app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "post_pt_x",
        ] = x
        app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "post_pt_y",
        ] = y
        app.df_metadata.loc[
            (app.df_metadata["Image_Index"] == data_id)
            & (app.df_metadata["Page"] == page),
            "post_pt_z",
        ] = z
    else:
        raise ValueError("id must be pre or post")

    # return success
    return json.dumps({"success": True}), 200, {"ContentType": "application/json"}
