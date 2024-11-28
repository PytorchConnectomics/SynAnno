# import global configs
import synanno

# flask util functions
from flask import render_template, flash, request, jsonify, session, flash

# flask ajax requests
from flask_cors import cross_origin

# backend package
import synanno.backend.processing as ip

# load existing json
import json

# setup and configuration of Neuroglancer instances
import synanno.backend.ng_util as ng_util

# access and remove files
import os

# for type hinting
from jinja2 import Template
from werkzeug.datastructures import MultiDict
from typing import Dict

import pandas as pd

import numpy as np

from flask import Blueprint
from flask import current_app as app


# define a Blueprint for opendata routes
blueprint = Blueprint("open_data", __name__)

# global variables
global draw_or_annotate  # defines the downstream task; either draw or annotate - default to annotate
draw_or_annotate = "annotate"


@blueprint.route("/open_data", defaults={"task": "annotate"})
@blueprint.route("/open_data/<string:task>", methods=["GET"], endpoint="open_data_task")
def open_data(task: str) -> Template:
    """Renders the open-data view that lets the user specify the source, target, and json file.

    Args:
        task: Defined through the path chosen by the user |  'draw', 'annotate'

    Return:
        Renders the open-data view
    """

    # defines the downstream task | 'draw', 'annotate'
    global draw_or_annotate
    draw_or_annotate = task

    if os.path.isdir("./synanno/static/Images/Img"):
        flash(
            'Click "Reset Backend" to clear the memory, start a new task, and start up a Neuroglancer instance.'
        )
        return render_template(
            "opendata.html",
            modecurrent="d-none",
            modenext="d-none",
            modereset="inline",
            mode=draw_or_annotate,
            json_name=app.config["JSON"],
            view_style="view",
        )
    return render_template(
        "opendata.html", modenext="disabled", mode=draw_or_annotate, view_style="view"
    )


@blueprint.route("/upload", methods=["GET", "POST"])
def upload_file() -> Template:
    """Upload the source, target, and json file specified by the user.
    Rerender the open-data view, enabling the user to start the annotation or draw process.

    Return:
        Renders the open-data view, with additional buttons enabled
    """

    # defines the downstream task, set by the open-data view | 'draw', 'annotate'
    global draw_or_annotate

    # set the number of cards in one page
    # this variable is, e.g., used by the preprocess script and the set_data function
    session["per_page"] = 18

    # init the number of pages to 0
    session["n_pages"] = 0

    # retrieve the view_style mode from the form, either view or neuron
    app.view_style = request.form.get("view_style")

    # Check if files folder exists, if not create it
    if not os.path.exists(
        os.path.join(
            ".", os.path.join(app.config["PACKAGE_NAME"], app.config["UPLOAD_FOLDER"])
        )
    ):
        os.mkdir(
            os.path.join(
                ".",
                os.path.join(app.config["PACKAGE_NAME"], app.config["UPLOAD_FOLDER"]),
            )
        )

    # remove the old json file should it exist
    if os.path.isfile(
        os.path.join(
            os.path.join(app.config["PACKAGE_NAME"], app.config["UPLOAD_FOLDER"]),
            app.config["JSON"],
        )
    ):
        os.remove(
            os.path.join(
                os.path.join(app.config["PACKAGE_NAME"], app.config["UPLOAD_FOLDER"]),
                app.config["JSON"],
            )
        )

    # retrieve the coordinate order and resolution from the form and save them in a dict, used by the NG instance and the processing functions
    app.coordinate_order = {
        c: (
            request.form.get("res-source-" + str(i + 1)),
            request.form.get("res-target-" + str(i + 1)),
        )
        for i, c in enumerate(list(request.form.get("coordinates")))
    }

    coordinate_order = list(app.coordinate_order.keys())

    # retrieve the crop size from the form and save it to the session
    session["crop_size_x"] = int(
        request.form.get("crop_size_c" + str(coordinate_order.index("x")))
    )
    session["crop_size_y"] = int(
        request.form.get("crop_size_c" + str(coordinate_order.index("y")))
    )
    session["crop_size_z"] = int(
        request.form.get("crop_size_c" + str(coordinate_order.index("z")))
    )

    if (
        session["crop_size_x"] == 0
        or session["crop_size_y"] == 0
        or session["crop_size_z"] == 0
    ):
        flash(
            "The crop sizes have to be larger then zero, the current setting will result in a crash of the backend!",
            "error",
        )
        raise ValueError(
            "A crop size was set to 0, this will result in a crash of the backend!"
        )

    # retrieve the handle to the json should one have been provided
    file_json = request.files["file_json"]

    # if a json was provided write its data to the metadata dataframe
    if file_json.filename:
        # retrieve the columns from app.df_metadata
        expected_columns = set(app.df_metadata.columns)

        app.df_metadata = pd.read_json(file_json, orient="records")

        # retrieve the columns from app.df_metadata
        actual_columns = set(app.df_metadata.columns)

        # Check if the expected columns match the actual ones
        if expected_columns == actual_columns:
            print("All columns are present.")
            # sort the dataframe by page and image_index
            app.df_metadata.sort_values(["Page", "Image_Index"], inplace=True)
        else:
            missing_columns = expected_columns - actual_columns
            extra_columns = actual_columns - expected_columns
            print(f"Missing columns: {missing_columns}")
            print(f"Extra columns: {extra_columns}")
            raise ValueError("The provided JSON does not match the expected format!")

    # Convert coordinate resolution values to integers
    app.coord_resolution_source = np.array(
        [int(res[0]) for res in app.coordinate_order.values()]
    ).astype(int)
    app.coord_resolution_target = np.array(
        [int(res[1]) for res in app.coordinate_order.values()]
    ).astype(int)

    # calculate the scale factor for the source and target cloud volume
    app.scale = {
        c: v
        for c, v in zip(
            coordinate_order,
            np.where(
                app.coord_resolution_target / app.coord_resolution_source > 0,
                app.coord_resolution_target / app.coord_resolution_source,
                1,
            ),
        )
    }

    # retrieve the urls for the source and target cloud volume buckets
    source_url = request.form.get("source_url")
    target_url = request.form.get("target_url")

    # check if the provided urls are valid based on the cloud provider prefix
    if any(
        bucket in source_url for bucket in app.config["CLOUD_VOLUME_BUCKETS"]
    ) and any(bucket in target_url for bucket in app.config["CLOUD_VOLUME_BUCKETS"]):
        # retrieve the bucket secret if the user provided one
        if bucket_secret := request.files.get("secrets_file"):
            bucket_secret = json.loads(bucket_secret.read())

        # TODO: The URL should be a url currently it is set to text, if providing a false path no error handling is in place
        # retrieve the materialization url
        materialization_url = request.form.get("materialization_url")

        # if the user chose the view view_style mode load the bbox specific subvolume and then process the data like in the local case
        if app.view_style == "view":
            subvolume = {}
            for coord in coordinate_order:
                subvolume[coord + "1"] = (
                    int(request.form.get(coord + "1"))
                    if request.form.get(coord + "1")
                    else 0
                )
                subvolume[coord + "2"] = (
                    int(request.form.get(coord + "2"))
                    if request.form.get(coord + "2")
                    else -1
                )

            ip.neuron_centric_3d_data_processing(
                source_url,
                target_url,
                materialization_url,
                subvolume=subvolume,
                bucket_secret_json=bucket_secret
                if bucket_secret
                else "~/.cloudvolume/secrets",
                mode=draw_or_annotate,
                view_style=app.view_style,
            )
        # if the user chose the neuron view_style mode, retrieve a list of all the synapses of the provided neuron ids and then process the data on synapse level
        elif app.view_style == "neuron":
            # if the user chose the neuron view_style mode retrieve the neuron ids
            preid = (
                int(request.form.get("preid")) if request.form.get("preid") else None
            )
            postid = (
                int(request.form.get("postid")) if request.form.get("postid") else None
            )

            ip.neuron_centric_3d_data_processing(
                source_url,
                target_url,
                materialization_url,
                preid,
                postid,
                bucket_secret_json=bucket_secret
                if bucket_secret
                else "~/.cloudvolume/secrets",
                mode=draw_or_annotate,
                view_style=app.view_style,
            )

    else:
        flash(
            "Please provide at least the paths to valid source and target cloud volume buckets!",
            "error",
        )
        return render_template(
            "opendata.html", modenext="disabled", mode=draw_or_annotate
        )

    # if the NG version number is None setup a new NG viewer
    if app.ng_version is None:
        ng_util.setup_ng(
            source="precomputed://" + source_url, target="precomputed://" + target_url
        )

    flash("Data ready!")
    return render_template(
        "opendata.html",
        modecurrent="disabled",
        modeform="formFileDisabled",
        view_style=app.view_style,
        mode=draw_or_annotate,
    )


@blueprint.route("/set-data/<string:task>", methods=["GET"], endpoint="set_data_task")
@blueprint.route("/set-data")
def set_data(task: str = "annotate") -> Template:
    """Used by the annotation and the draw view to set up the session.
    Annotation view: Setup the session, calculate the grid view, render the annotation view
    Draw view: Reload the updated JSON, render the draw view

    Args:
        task: Identifies and links the downstream process: annotate | draw
        json_path: Path to the json file containing the label information

    Return:
        Renders either the annotation or the draw view dependent on the user action
    """

    if task == "draw":
        # retrieve the the data from the metadata dataframe as a list of dicts
        data = app.df_metadata.query('Label != "Correct"').sort_values(by="Image_Index")
        data = data.to_dict("records")
        return render_template("draw.html", images=data)
    # setup the session
    else:
        page = 0
        data = (
            app.df_metadata.query("Page == @page")
            .sort_values(by="Image_Index")
            .to_dict("records")
        )

        return render_template(
            "annotation.html",
            images=data,
            page=page,
            n_pages=session.get("n_pages"),
            grid_opacity=app.grid_opacity,
        )


@blueprint.route("/get_instance", methods=["POST"])
@cross_origin()
def get_instance() -> Dict[str, object]:
    """Serves one of two Ajax calls from annotation.js, passing instance specific information

    Return:
        The instance specific data
    """

    coordinate_order = list(app.coordinate_order.keys())

    # retrieve the page and instance index
    mode = str(request.form["mode"])
    load = str(request.form["load"])
    page = int(request.form["page"])
    index = int(request.form["data_id"])

    custom_mask_path_curve = None
    custom_mask_path_pre = None
    custom_mask_path_post = None

    # when first opening a instance modal view
    if load == "full":
        # calculating the number of slices
        slices_len = len(
            os.listdir(
                "./synanno"
                + app.df_metadata.loc[
                    (app.df_metadata["Page"] == page)
                    & (app.df_metadata["Image_Index"] == index),
                    "EM",
                ].item()
                + "/"
            )
        )
        # retrieve the middle slice
        middle_slice = int(
            app.df_metadata.loc[
                (app.df_metadata["Page"] == page)
                & (app.df_metadata["Image_Index"] == index),
                "Middle_Slice",
            ].item()
        )

        # retrieve the instance specific data
        data = app.df_metadata.query("Page == @page & Image_Index == @index").to_dict(
            "records"
        )[0]

        # retrieve the first slice of the instance
        range_min = data["Adjusted_Bbox"][coordinate_order.index("z") * 2]

        if mode == "draw":
            base_mask_path = str(request.form["base_mask_path"])
            if base_mask_path:
                coordinates = "_".join(list(map(str, data["Adjusted_Bbox"])))
                path_curve = os.path.join(
                    base_mask_path,
                    "curve_idx_"
                    + str(data["Image_Index"])
                    + "_slice_"
                    + str(data["Middle_Slice"])
                    + "_cor_"
                    + coordinates
                    + ".png",
                )
                path_circle_pre = os.path.join(
                    base_mask_path,
                    "circlePre_idx_"
                    + str(data["Image_Index"])
                    + "_slice_"
                    + str(data["Middle_Slice"])
                    + "_cor_"
                    + coordinates
                    + ".png",
                )
                path_circle_post = os.path.join(
                    base_mask_path,
                    "circlePost_idx_"
                    + str(data["Image_Index"])
                    + "_slice_"
                    + str(data["Middle_Slice"])
                    + "_cor_"
                    + coordinates
                    + ".png",
                )
                if os.path.exists("./synanno" + path_curve):
                    custom_mask_path_curve = path_curve
                if os.path.exists("./synanno" + path_circle_pre):
                    custom_mask_path_pre = path_circle_pre
                if os.path.exists("./synanno" + path_circle_post):
                    custom_mask_path_post = path_circle_post

        data = json.dumps(data)

        final_json = jsonify(
            data=data,
            slices_len=slices_len,
            halflen=middle_slice,
            range_min=range_min,
            host=app.config["IP"],
            port=app.config["PORT"],
            custom_mask_path_curve=custom_mask_path_curve,
            custom_mask_path_pre=custom_mask_path_pre,
            custom_mask_path_post=custom_mask_path_post,
        )

    # when changing the depicted slice with in the modal view
    elif load == "single":
        data = app.df_metadata.query("Page == @page & Image_Index == @index").to_dict(
            "records"
        )[0]

        if mode == "draw":
            base_mask_path = str(request.form["base_mask_path"])
            viewed_instance_slice = request.form["viewed_instance_slice"]

            if base_mask_path:
                # check if file exists
                if viewed_instance_slice:
                    coordinates = "_".join(list(map(str, data["Adjusted_Bbox"])))
                    path_curve = os.path.join(
                        base_mask_path,
                        "curve_idx_"
                        + str(data["Image_Index"])
                        + "_slice_"
                        + str(viewed_instance_slice)
                        + "_cor_"
                        + coordinates
                        + ".png",
                    )
                    path_circle_pre = os.path.join(
                        base_mask_path,
                        "circlePre_idx_"
                        + str(data["Image_Index"])
                        + "_slice_"
                        + str(viewed_instance_slice)
                        + "_cor_"
                        + coordinates
                        + ".png",
                    )
                    path_circle_post = os.path.join(
                        base_mask_path,
                        "circlePost_idx_"
                        + str(data["Image_Index"])
                        + "_slice_"
                        + str(viewed_instance_slice)
                        + "_cor_"
                        + coordinates
                        + ".png",
                    )
                    if os.path.exists("./synanno" + path_curve):
                        custom_mask_path_curve = path_curve
                    if os.path.exists("./synanno" + path_circle_pre):
                        custom_mask_path_pre = path_circle_pre
                    if os.path.exists("./synanno" + path_circle_post):
                        custom_mask_path_post = path_circle_post

        data = json.dumps(data)

        final_json = jsonify(
            data=data,
            custom_mask_path_curve=custom_mask_path_curve,
            custom_mask_path_pre=custom_mask_path_pre,
            custom_mask_path_post=custom_mask_path_post,
        )

    return final_json


@blueprint.route("/progress", methods=["POST"])
@cross_origin()
def progress() -> Dict[str, object]:
    """Serves an Ajax request from progressbar.js passing information about the loading
    process to the frontend.

    Return:
        Passes progress status, in percentage, to the frontend as json.
    """
    return jsonify(
        {
            "status": app.progress_bar_status["status"],
            "progress": app.progress_bar_status["percent"],
        }
    )


@blueprint.route("/neuro", methods=["POST"])
@cross_origin()
def neuro() -> Dict[str, object]:
    """Serves an Ajax request from annotation.js or draw_module.js, shifting the view focus with
    in the running NG instance and passing the link for the instance to the frontend.

    Return:
        Passes the link to the NG instance as json.
    """

    coordinate_order = list(app.coordinate_order.keys())

    # unpack the coordinates for the new focus point of the view
    mode = str(request.form["mode"])
    center = {}
    if mode == "annotate":
        center["z"] = int(int(request.form["cz0"]) * app.scale["z"])
        center["y"] = int(int(request.form["cy0"]) * app.scale["y"])
        center["x"] = int(int(request.form["cx0"]) * app.scale["x"])
    elif mode == "draw":
        center["z"] = int(
            (app.vol_dim[coordinate_order.index("z")] // 2) * app.scale["z"]
        )
        center["y"] = int(
            (app.vol_dim[coordinate_order.index("y")] // 2) * app.scale["y"]
        )
        center["x"] = int(
            (app.vol_dim[coordinate_order.index("x")] // 2) * app.scale["x"]
        )

    if app.ng_version is not None:
        # update the view focus of the running NG instance
        with app.ng_viewer.txn() as s:
            s.position = [
                center[coordinate_order[0]],
                center[coordinate_order[1]],
                center[coordinate_order[2]],
            ]

    else:
        raise Exception("No NG instance running")

    print(
        f"Neuroglancer instance running at {app.ng_viewer}, centered at {coordinate_order[0]},{coordinate_order[1]},{coordinate_order[2]}: {center[coordinate_order[0]], center[coordinate_order[1]], center[coordinate_order[2]]}"
    )

    final_json = jsonify(
        {
            "ng_link": "http://"
            + app.config["IP"]
            + ":9015/v/"
            + str(app.ng_version)
            + "/"
        }
    )

    return final_json


def save_file(
    file: MultiDict,
    filename: str,
    path: str = None,
) -> str:
    """Saves the provided file at the specified location.

    Args:
        file: The file to be saved
        filename: The name of the file
        path: Path where to save the file

    Return:
        None if the provided file does not match one of the required extensions,
        else the full path where the file got saved.
    """

    # defines the downstream task, set by the open-data view | 'draw', 'annotate'
    global draw_or_annotate

    path = (
        os.path.join(app.config["PACKAGE_NAME"], app.config["UPLOAD_FOLDER"])
        if not path
        else path
    )

    file_ext = os.path.splitext(filename)[1]
    if file_ext not in app.config["UPLOAD_EXTENSIONS"]:
        flash("Incorrect file format! Load again.", "error")
        render_template("opendata.html", modenext="disabled", mode=draw_or_annotate)
        return None
    else:
        file.save(os.path.join(path, filename))
        return os.path.join(path, filename)
