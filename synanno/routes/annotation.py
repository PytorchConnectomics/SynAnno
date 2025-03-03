# import global configs
# track the annotation time
import datetime

# ajax json response
import json

# retrieve list of all files with in a directory
from typing import Dict

# flask util functions
from flask import Blueprint, current_app, jsonify, render_template, request

# flask ajax requests
from flask_cors import cross_origin

# for type hinting
from jinja2 import Template

from synanno.backend.processing import free_page, retrieve_instance_metadata

# io operations


# define a Blueprint for annotation routes
blueprint = Blueprint("annotation", __name__)


@blueprint.route("/annotation/<int:page>", endpoint="annotation_page")
@blueprint.route("/annotation")
def annotation(page: int = 0) -> Template:
    """Start the proofreading timer and load the annotation view.

    Args:
        page: The current data page that is depicted in the grid view

    Return:
        The annotation view
    """

    # remove the synapse and image slices for the previous and next page
    free_page()

    # load the data for the current page
    retrieve_instance_metadata(page=page)

    # start the timer for the annotation process
    if current_app.proofread_time["start_grid"] is None:
        current_app.proofread_time["start_grid"] = datetime.datetime.now()

    # retrieve the data for the current page
    data = (
        current_app.df_metadata.query("Page == @page")
        .sort_values(by=["Image_Index"])
        .to_dict("records")
    )

    return render_template(
        "annotation.html",
        images=data,
        page=page,
        n_pages=current_app.n_pages,
        grid_opacity=current_app.grid_opacity,
        neuron_id=current_app.selected_neuron_id,
        neuronReady=current_app.neuron_ready,
        neuronSection=current_app.sections,
        synapsePointCloud=current_app.snapped_point_cloud,
    )


@blueprint.route("/set_grid_opacity", methods=["POST"])
@cross_origin()
def set_grid_opacity() -> tuple[str, int, Dict[str, str]]:
    """Serves and Ajax request from annotation.js updating the grid's opacity value

    Return:
        Passes a success confirmation to the frontend
    """
    # retrieve the current opacity value, only keep first decimal
    current_app.grid_opacity = int(float(request.form["grid_opacity"]) * 10) / 10
    # returning a JSON formatted response to trigger the ajax success logic
    return (
        json.dumps({"success": True}),
        200,
        {"ContentType": "application/json"},
    )


@blueprint.route("/update-card", methods=["POST"])
@cross_origin()
def update_card() -> Dict[str, object]:
    """Updates the label of an instance - switch between Correct, Incorrect to Unsure

    Return:
        Passes the updated label to the frontend
    """

    # retrieve the passed frontend information
    page = int(request.form["page"])
    index = int(request.form["data_id"])
    label = request.form["label"]

    # update the session data with the new label
    if label == "Incorrect":
        current_app.df_metadata.loc[
            (current_app.df_metadata["Page"] == page)
            & (current_app.df_metadata["Image_Index"] == index),
            "Label",
        ] = "Unsure"
    elif label == "Unsure":
        current_app.df_metadata.loc[
            (current_app.df_metadata["Page"] == page)
            & (current_app.df_metadata["Image_Index"] == index),
            "Label",
        ] = "Correct"
    elif label == "Correct":
        current_app.df_metadata.loc[
            (current_app.df_metadata["Page"] == page)
            & (current_app.df_metadata["Image_Index"] == index),
            "Label",
        ] = "Incorrect"

    return jsonify({"result": "success", "label": label})
