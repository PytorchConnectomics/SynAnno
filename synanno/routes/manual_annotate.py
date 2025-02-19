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

from flask import Blueprint
from flask import current_app

from synanno.backend.processing import process_instance, update_slice_number

# define a Blueprint for manual_annotate routes
blueprint = Blueprint("manual_annotate", __name__)


@blueprint.route("/draw")
def draw() -> Template:
    """Reload the updated JSON and render the draw view.
    Careful: The draw view can also be invoked via '/set-data/draw' - see opendata.py

    Return:
        Renders the draw view.
    """

    # retrieve the data from the dataframe for which the user has marked the instance as "Incorrect" or "Unsure"
    data = current_app.df_metadata[
        current_app.df_metadata["Label"].isin(["Incorrect", "Unsure"])
    ].to_dict("records")
    return render_template("draw.html", images=data)


@blueprint.route("/save_canvas", methods=["POST"])
def save_canvas() -> Dict[str, object]:
    """Serves an Ajax request from draw.js, downloading, converting, and saving
    the canvas as image.

    Return:
        Passes the instance specific session information as JSON to draw.js
    """

    coordinate_order = list(current_app.coordinate_order.keys())

    # retrieve the canvas
    image_data = re.sub("^data:image/.+;base64,", "", request.form["imageBase64"])

    # retrieve the instance specifiers
    page = int(request.form["page"])  # required for pd query
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

    # create the base folder where to save all custom mask objects
    static_folder = os.path.join(
        current_app.root_path, current_app.config["STATIC_FOLDER"]
    )
    mask_folder = os.path.join(static_folder, "Images/Mask")

    if not os.path.exists(mask_folder):
        os.makedirs(mask_folder)

    # create the instance specific sub folder
    instance_folder_path = os.path.join(mask_folder, str(index))

    if not os.path.exists(instance_folder_path):
        os.makedirs(instance_folder_path)

    # retrieve the instance specific information for naming the image

    data = current_app.df_metadata.query(
        "Page == @page & Image_Index == @index"
    ).to_dict("records")[0]
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
                instance_folder_path,
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
    im.save(os.path.join(instance_folder_path, img_name))

    # send the instance specific information to draw.js
    data = json.dumps(data)
    final_json = jsonify(data=data)

    return final_json


@blueprint.route("/load_missing_slices", methods=["POST"])
def load_missing_slices() -> Dict[str, str]:
    """The auto segmentation view needs a set number of slices per instance (depth). Coming from the
    Annotation view the user might use a different number of slices - most likely a single slice.
    To enable the user to go through the individual slices, redraw the mask and auto generate the mask we thus
    need to download the remaining slices.
    """

    # Retrieve the current meta data from current_app.df_metadata
    # Identify the instance with a label incorrect or unsure
    data = current_app.df_metadata.query(
        "Label == 'Incorrect' or Label == 'Unsure'"
    ).to_dict("records")

    static_folder = os.path.join(
        os.path.join(current_app.root_path, current_app.config["STATIC_FOLDER"]),
    )
    image_folder = os.path.join(static_folder, "Images")

    syn_dir, img_dir = os.path.join(image_folder, "Syn"), os.path.join(
        image_folder, "Img"
    )

    # update the slice number of the instances
    update_slice_number(data)

    # retrieve the updated data
    data = current_app.df_metadata.query(
        "Label == 'Incorrect' or Label == 'Unsure'"
    ).to_dict("records")

    # load the remaining slices
    for instance in data:
        process_instance(
            instance,
            os.path.join(img_dir, str(instance["Image_Index"])),
            os.path.join(syn_dir, str(instance["Image_Index"])),
        )

    return jsonify({"result": "success"})


@blueprint.route("/ng_bbox_fn", methods=["POST"])
@cross_origin()
def ng_bbox_fn() -> Dict[str, object]:
    """Serves an Ajax request by draw_module.js, passing the coordinates of the center point of a newly marked FN to the front end,
    enabling the front end to depict the values and the user to manual update/correct them.

    Return:
        The x and y coordinates of the center of the newly added instance as well as the upper and the
        lower z bound of the instance as JSON to draw_module.js
    """

    coordinate_order = list(current_app.coordinate_order.keys())

    # expand the bb in in z direction
    # we expand the front and the back z value dependent on their proximity to the boarders

    expand_z = current_app.crop_size_z_draw // 2

    cz1 = int(current_app.cz) - expand_z if int(current_app.cz) - expand_z > 0 else 0
    cz2 = (
        int(current_app.cz) + expand_z
        if int(current_app.cz) + expand_z
        < current_app.vol_dim_scaled[coordinate_order.index("z")]
        else current_app.vol_dim_scaled[coordinate_order.index("z")]
    )

    # server the coordinates to the front end
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
def ng_bbox_fn_save() -> Dict[str, object]:
    """Serves an Ajax request by draw_module.js, that passes the manual updated/corrected bb coordinates
    to this backend function. Additionally, the function creates a new item instance and
    updates the metadata dataframe.

    Return:
        The x and y coordinates of the center of the newly added instance as well as the upper and the
        lower z bound of the instance as JSON to draw_module.js
    """

    coordinate_order = list(current_app.coordinate_order.keys())

    # retrieve manual correction of coordinates
    cz1 = int(request.form["z1"])
    cz2 = int(request.form["z2"])
    current_app.cz = int(cz1 + ((cz2 - cz1) // 2))
    current_app.cy = int(request.form["my"])
    current_app.cx = int(request.form["mx"])

    ## add the new instance to the the json und update the session data

    # create new item
    item = dict()

    # index starts at one, adding item, therefore, incrementing by one

    # calculate the number of pages needed for the instance count in the JSON
    if not (len(current_app.df_metadata) % session.get("per_page") == 0):
        item["Page"] = len(current_app.df_metadata) // session.get("per_page") + 1
    else:
        item["Page"] = len(current_app.df_metadata) // session.get("per_page")

    # divide the number of instance by the number of instances per page to get the index of the current page

    ### Note that all dimensions are saved in then scale of the target (segmentation) volume. ###

    item["Image_Index"] = len(current_app.df_metadata) + 1
    item["materialization_index"] = -1
    item["section_index"] = -1
    item["section_order_index"] = -1

    # crop out and save the relevant gt and im
    idx_dir = create_dir(
        os.path.join(current_app.root_path, current_app.config["STATIC_FOLDER"]),
        "Images",
    )
    img_folder = create_dir(idx_dir, "Img")
    img_all = create_dir(img_folder, str(item["Image_Index"]))

    item["GT"] = "None"  # do not save the GT as we do not have masks for the FNs
    item["EM"] = "/".join(img_all.strip(".\\").split("/")[-3:])

    item["Label"] = "Incorrect"
    item["Annotated"] = "No"
    item["neuron_id"] = -1
    item["Error_Description"] = "False Negatives"
    item["X_Index"] = coordinate_order.index("x")
    item["Y_Index"] = coordinate_order.index("y")
    item["Z_Index"] = coordinate_order.index("z")

    item["Middle_Slice"] = int(current_app.cz)

    # scale the coordinates to the original target size
    item["cz0"] = int(int(current_app.cz) / current_app.scale["z"])
    item["cy0"] = int(int(current_app.cy) / current_app.scale["y"])
    item["cx0"] = int(int(current_app.cx) / current_app.scale["x"])

    # define the bbox
    expand_x = session["crop_size_x"] // 2
    expand_y = session["crop_size_y"] // 2

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

    # we update the pre and post coordinates with None as we do not have them initially for FNs
    item["pre_pt_z"] = None
    item["pre_pt_y"] = None
    item["pre_pt_x"] = None
    item["post_pt_z"] = None
    item["post_pt_y"] = None
    item["post_pt_x"] = None

    item["crop_size_x"] = session["crop_size_x"]
    item["crop_size_y"] = session["crop_size_y"]
    item["crop_size_z"] = current_app.crop_size_z_draw

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
        int(bbox[0] / current_app.scale[coordinate_order[0]]),
        int(bbox[1] / current_app.scale[coordinate_order[0]]),
        int(bbox[2] / current_app.scale[coordinate_order[1]]),
        int(bbox[3] / current_app.scale[coordinate_order[1]]),
        int(bbox[4] / current_app.scale[coordinate_order[2]]),
        int(bbox[5] / current_app.scale[coordinate_order[2]]),
    ]

    crop_bbox, img_padding = calculate_crop_pad(bbox, current_app.vol_dim_scaled)
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
    cord_order = list(current_app.coordinate_order.keys())

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
    coord_resolution = [int(res[0]) for res in current_app.coordinate_order.values()]

    # Retrieve the source and target images from the cloud volume
    cropped_img = current_app.source_cv.download(
        bound, coord_resolution=coord_resolution, mip=0
    )

    # remove the singleton dimension, take care as the z dimension might be singleton
    cropped_img = cropped_img.squeeze(axis=3)

    # pad the images and synapse segmentation to fit the crop size (sz)
    cropped_img = np.pad(cropped_img, img_padding, mode="constant", constant_values=148)

    # scale the coordinates to the original target size
    item["Adjusted_Bbox"] = item["Original_Bbox"] = [
        int(crop_bbox[0] / current_app.scale[coordinate_order[0]]),
        int(crop_bbox[1] / current_app.scale[coordinate_order[0]]),
        int(crop_bbox[2] / current_app.scale[coordinate_order[1]]),
        int(crop_bbox[3] / current_app.scale[coordinate_order[1]]),
        int(crop_bbox[4] / current_app.scale[coordinate_order[2]]),
        int(crop_bbox[5] / current_app.scale[coordinate_order[2]]),
    ]

    # scale the padding to the original target size
    item["Padding"] = [
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
        current_app.df_metadata.columns
    ), f"Difference: {set(item.keys()).symmetric_difference(set(current_app.df_metadata.columns))}"

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


@blueprint.route("/save_pre_post_coordinates", methods=["POST"])
@cross_origin()
def save_pre_post_coordinates() -> None:
    # retrieve the data from the request
    # the x and y value from the java script refers to the classical x=horizontal and y=vertical axis
    # however, this does not necessarily correspond to the x and y axis order of the image

    coordinate_order = list(current_app.coordinate_order.keys())

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
    x = int(x / current_app.scale["x"])
    y = int(y / current_app.scale["y"])
    z = int(z / current_app.scale["z"])

    x = (
        x
        + current_app.df_metadata.loc[
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
    y = (
        y
        + current_app.df_metadata.loc[
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
    z = (
        z
        - current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "Padding",
        ].values[0][z_index][0]
    )

    # if id=='pre' update 'pre_pt_x', 'pre_pt_y', 'post_pt_y' of the instance specific information in the dataframe
    if id == "pre":
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "pre_pt_x",
        ] = x
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "pre_pt_y",
        ] = y
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "pre_pt_z",
        ] = z

        # get the segmentation folder
        seg_folder = current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "GT",
        ].values[0]

        # get the instance middle slice
        middle_slice = current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "Middle_Slice",
        ].values[0]

        # set the color of the pre coordinate instance in the middle slice of the segmentation to (128, 128, 128, 0.5)
        # we only have to check the middle slice since it is the only slice of the original masks,
        # that ever gets depicted in the draw view
        # if the instance is not a false negative and the middle slice mask exists
        if os.path.exists(
            os.path.join(
                current_app.root_path,
                seg_folder.lstrip("/"),
                str(middle_slice) + ".png",
            )
        ):
            # load the slice of the segmentation
            seg_slice = Image.open(
                os.path.join(
                    current_app.root_path,
                    seg_folder.lstrip("/"),
                    str(middle_slice) + ".png",
                )
            )

            # set any pixels with value current_app.pre_id_color_main to pre_id_color_sub
            seg_slice = np.array(seg_slice)

            # Create a boolean mask where the RGB values of seg_slice match current_app.pre_id_color_main and sub
            mask_main = np.all(
                seg_slice[:, :, :3] == current_app.pre_id_color_main, axis=-1
            )
            mask_sub = np.all(
                seg_slice[:, :, :3] == current_app.pre_id_color_sub, axis=-1
            )

            mask = mask_main | mask_sub

            # Where the mask is True, set the RGB values to current_app.pre_id_color_sub
            seg_slice[mask] = (128, 128, 128, 0.5)

            # save the updated segmentation
            Image.fromarray(seg_slice).save(
                os.path.join(
                    current_app.root_path,
                    seg_folder.lstrip("/"),
                    str(middle_slice) + ".png",
                )
            )

    elif id == "post":
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "post_pt_x",
        ] = x
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "post_pt_y",
        ] = y
        current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "post_pt_z",
        ] = z

        # get the segmentation folder
        seg_folder = current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "GT",
        ].values[0]

        # get the instance middle slice
        middle_slice = current_app.df_metadata.loc[
            (current_app.df_metadata["Image_Index"] == data_id)
            & (current_app.df_metadata["Page"] == page),
            "Middle_Slice",
        ].values[0]

        # set the color of the pre instance in the middle slice of the segmentation to gray
        # we only have to check the middle slice since it is the only slice of the original masks,
        # that ever gets depicted in the draw view
        # if the instance is not a false negative and the middle slice mask exists
        if os.path.exists(
            os.path.join(
                current_app.root_path,
                seg_folder.lstrip("/"),
                str(middle_slice) + ".png",
            )
        ):
            # load the slice of the segmentation
            seg_slice = Image.open(
                os.path.join(
                    current_app.root_path,
                    seg_folder.lstrip("/"),
                    str(middle_slice) + ".png",
                )
            )

            # set any pixels with value current_app.post_id_color_main to post_id_color_sub
            seg_slice = np.array(seg_slice)

            # Create a boolean mask where the RGB values of seg_slice match current_app.post_id_color_main
            mask_main = np.all(
                seg_slice[:, :, :3] == current_app.post_id_color_main, axis=-1
            )
            mask_sub = np.all(
                seg_slice[:, :, :3] == current_app.post_id_color_sub, axis=-1
            )

            mask = mask_main | mask_sub

            # Where the mask is True, set the RGB values to current_app.post_id_color_sub
            seg_slice[mask] = (128, 128, 128, 0.5)

            # save the updated segmentation
            Image.fromarray(seg_slice).save(
                os.path.join(
                    current_app.root_path,
                    seg_folder.lstrip("/"),
                    str(middle_slice) + ".png",
                )
            )
    else:
        raise ValueError("id must be pre or post")

    return json.dumps({"success": True}), 200, {"ContentType": "application/json"}


@blueprint.route("/get_coordinates", methods=["GET"])
def get_coordinates():
    """Get the current coordinates of the Neuroglancer instance."""
    return jsonify({"cz": current_app.cz, "cy": current_app.cy, "cx": current_app.cx})
