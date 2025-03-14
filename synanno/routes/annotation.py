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

# define a Blueprint for annotation routes
blueprint = Blueprint("annotation", __name__)


@blueprint.route("/retrive_first_page_of_section/<int:section_index>")
def retrieve_first_page_of_section(section_index):
    print(current_app.page_section_mapping)
    print(section_index)
    for page, (sec_idx, _) in current_app.page_section_mapping.items():
        if sec_idx == section_index:
            return jsonify({"page": page})
    return jsonify({"error": "Section not found"}), 404


@blueprint.route("/annotation/<int:page>", endpoint="annotation_page")
@blueprint.route("/annotation")
def annotation(page: int = 1) -> Template:
    """Start the proofreading timer and load the annotation view.

    Args:
        page: The current data page that is depicted in the grid view

    Return:
        The annotation view
    """

    # remove the synapse and image slices for the previous and next page
    free_page()

    # start the timer for the annotation process
    if current_app.proofread_time["start_grid"] is None:
        current_app.proofread_time["start_grid"] = datetime.datetime.now()

    print(current_app.df_metadata)

    return render_template(
        "annotation.html",
        page=page,
        n_pages=current_app.n_pages,
        neuron_id=current_app.selected_neuron_id,
        grid_opacity=current_app.grid_opacity,
        neuronReady=current_app.neuron_ready,
        neuronSections=current_app.sections,
        synapsePointCloud=current_app.snapped_point_cloud,
        activeNeuronSection=(
            current_app.page_section_mapping[page][0]
            if page in current_app.page_section_mapping
            else 0
        ),
        activeSynapseIDs=current_app.synapse_data.query("page == @page").index.tolist(),
    )


@blueprint.route("/loading_bar_image_tiles", methods=["GET"])
@cross_origin()
def loading_bar_image_tiles() -> Template:
    return render_template("loading_bar_image_tiles.html")


@blueprint.route("/update_image_tiles/<int:page>", endpoint="update_image_tiles_page")
@blueprint.route("/update_image_tiles", methods=["POST"])
@cross_origin()
def update_images(page: int = 1) -> Template:
    # Fetch updated image data
    # load the data for the current page
    retrieve_instance_metadata(page=page)

    # retrieve the data for the current page
    data = (
        current_app.df_metadata.query("Page == @page")
        .sort_values(by=["Image_Index"])
        .to_dict("records")
    )

    # retrieve image index for the first page

    fn_page = (
        current_app.page_section_mapping[page][1]
        if page in current_app.page_section_mapping
        else False
    )

    return render_template(
        "annotation_image_tiles.html",
        images=data,
        page=page,
        neuron_id=current_app.selected_neuron_id,
        grid_opacity=current_app.grid_opacity,
        neuronReady=current_app.neuron_ready,
        fn_page="true" if fn_page else "false",
        activeNeuronSection=(
            current_app.page_section_mapping[page][0]
            if page in current_app.page_section_mapping
            else 0
        ),
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
