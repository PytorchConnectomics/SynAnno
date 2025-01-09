# flask util functions
from flask import render_template, session, send_file, flash

# for type hinting
from jinja2 import Template

# enable multiple return types
from typing import Union

# manage paths and files
import os

# to zip folder
import shutil

import json

import datetime

import time

from flask import Blueprint
from flask import current_app

# define a Blueprint for finish routes
blueprint = Blueprint("finish", __name__)


@blueprint.route("/export_annotate")
def export_annotate() -> Template:
    """Renders final view of the annotation process that lets the user download the JSON.

    Return:
        Export-annotate view
    """

    # disable the 'Start New Process' button as long as the user did not download the masks or JSON
    # the user can always interrupt a process using the home button, but we want to prevent data loss
    return render_template("export_annotate.html", disable_snp="disabled")


@blueprint.route("/export_draw")
def export_draw() -> Template:
    """Renders final view of the draw process that lets the user download the custom masks.

    Return:
        Export-draw view
    """

    # disable the 'Start New Process' button as long as the user did not download the masks or JSON
    # the user can always interrupt a process using the home button, but we want to prevent data loss
    return render_template("export_draw.html", disable_snp="disabled")


@blueprint.route("/export_data/<string:data_type>", methods=["GET"])
def export_data(data_type) -> Union[Template, current_app.response_class]:
    """Download the JSON or the custom masks.

    Args:
        data_type: Specifies the data type for download | json, or masks

    Return:
        Either sends the JSON or the masks to the users download folder
        or rerenders the export view if there is now file that could be downloaded
    """

    with open(
        os.path.join(
            current_app.root_path,
            os.path.join(current_app.config["UPLOAD_FOLDER"]),
            current_app.config["JSON"],
        ),
        "w",
    ) as f:
        # TODO: What to do with the timing data?
        # write the metadata to a json file
        final_file = dict()
        final_file["Proofread Time"] = current_app.proofread_time

        json.dump(
            current_app.df_metadata.to_dict("records"), f, indent=4, default=json_serial
        )

        # provide sufficient time for the json update dependent on the length df_metadata
        time.sleep(0.1 * len(current_app.df_metadata))

    if data_type == "json":
        # exporting the final json
        if session.get("n_pages"):
            return send_file(
                os.path.join(
                    os.path.join(
                        current_app.root_path, current_app.config["UPLOAD_FOLDER"]
                    ),
                    current_app.config["JSON"],
                ),
                as_attachment=True,
                download_name=current_app.config["JSON"],
            )
        else:
            flash("Now file - session data is empty.", "error")
            # rerender export-draw and enable the 'Start New Process' button
            return render_template("export_annotate.html", disable_snp=" ")
    elif data_type == "mask":
        total_folder_path = os.path.join(
            os.path.join(current_app.root_path, current_app.config["STATIC_FOLDER"]),
            "custom_masks",
        )
        if os.path.exists(total_folder_path):
            # create zip of folder
            shutil.make_archive(total_folder_path, "zip", total_folder_path)
            return send_file(
                os.path.join(
                    os.path.join(
                        current_app.root_path, current_app.config["STATIC_FOLDER"]
                    ),
                    "custom_masks.zip",
                ),
                as_attachment=True,
            )
        else:
            flash(
                "The folder containing custom masks is empty. Did you draw custom masks?",
                "error",
            )
            # rerender export-draw and enable the 'Start New Process' button
            return render_template("export_draw.html", disable_snp=" ")


@blueprint.route("/reset")
def reset() -> Template:
    """Resets all process by pooping all the session content, resting the process bar, resting the timer,
    deleting deleting the JSON, the images, masks and zip folder.

    Return:
        Renders the landing-page view.
    """

    # reset progress bar
    current_app.progress_bar_status = {"status": "Loading Source File", "percent": 0}

    # reset time
    current_app.proofread_time = dict.fromkeys(current_app.proofread_time, None)

    # pop all the session content.
    for key in list(session.keys()):
        session.pop(key)

    # delete json file.
    if os.path.isfile(
        os.path.join(
            os.path.join(current_app.root_path, current_app.config["UPLOAD_FOLDER"]),
            current_app.config["JSON"],
        )
    ):
        os.remove(
            os.path.join(
                os.path.join(
                    current_app.root_path, current_app.config["UPLOAD_FOLDER"]
                ),
                current_app.config["JSON"],
            )
        )

    # delete static images
    static_folder = os.path.join(
        current_app.root_path, current_app.config["STATIC_FOLDER"]
    )
    image_folder = os.path.join(static_folder, "Images")

    if os.path.exists(os.path.join(image_folder, "Img")):
        try:
            shutil.rmtree(os.path.join(image_folder, "Img"))
        except Exception as e:
            print("Failed to delete %s. Reason: %s" % (image_folder, e))

    if os.path.exists(os.path.join(image_folder, "Syn")):
        try:
            shutil.rmtree(os.path.join(image_folder, "Syn"))
        except Exception as e:
            print("Failed to delete %s. Reason: %s" % (image_folder, e))

    # delete masks zip file.
    if os.path.isfile(os.path.join(static_folder, "custom_masks.zip")):
        os.remove(os.path.join(static_folder, "custom_masks.zip"))

    # delete custom masks
    mask_folder = os.path.join(static_folder, "custom_masks")
    if os.path.exists(mask_folder):
        try:
            shutil.rmtree(mask_folder)
        except Exception as e:
            print("Failed to delete %s. Reason: %s" % (mask_folder, e))

    # set the metadataframe back to null
    current_app.df_metadata.drop(current_app.df_metadata.index, inplace=True)

    return render_template("landingpage.html")


# handle non json serializable data
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, (datetime.timedelta)):
        return str(obj)
    if isinstance(obj, (datetime.datetime)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))
