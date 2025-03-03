import datetime
import json

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_cors import cross_origin

# Define a Blueprint for categorize routes
blueprint = Blueprint("categorize", __name__)


@blueprint.route("/categorize")
def categorize():
    """Render the categorize view.

    Returns:
        Categorization view that enables the user to specify the fault
        of instance masks marked as "Incorrect" or "Unsure".
    """
    stop_annotation_timer()
    start_categorization_timer()

    output_dict = current_app.df_metadata[
        current_app.df_metadata["Label"].isin(["Incorrect", "Unsure"])
    ].to_dict("records")

    return render_template("categorize.html", images=output_dict)


def stop_annotation_timer():
    """Stop the annotation timer."""
    if current_app.proofread_time["finish_grid"] is None:
        if current_app.proofread_time["start_grid"] is None:
            current_app.proofread_time["difference_grid"] = (
                "Non linear execution of the grid process - time invalid"
            )
        else:
            current_app.proofread_time["finish_grid"] = datetime.datetime.now()
            current_app.proofread_time["difference_grid"] = (
                current_app.proofread_time["finish_grid"]
                - current_app.proofread_time["start_grid"]
            )


def start_categorization_timer():
    """Start the categorization timer."""
    if current_app.proofread_time["start_categorize"] is None:
        current_app.proofread_time["start_categorize"] = datetime.datetime.now()


@blueprint.route("/pass_flags", methods=["GET", "POST"])
@cross_origin()
def pass_flags():
    """Serves an Ajax request from categorize.js, retrieving the new error tags from the
    frontend and updating metadata data frame.

    Returns:
        Confirms the successful update to the frontend
    """
    flags = request.get_json()["flags"]
    delete_fps = bool(request.get_json()["delete_fps"])

    update_flags(flags, delete_fps)
    stop_categorization_timer()

    return (
        json.dumps({"success": True}),
        200,
        {"ContentType": "application/json"},
    )


def update_flags(flags, delete_fps):
    """Update the flags in the metadata DataFrame.

    Args:
        flags: List of flags to update.
        delete_fps: Boolean indicating if false positives should be deleted.
    """
    for flag in flags:
        page_nr, img_nr, f = dict(flag).values()
        if f == "falsePositive" and delete_fps:
            current_app.df_metadata.drop(
                current_app.df_metadata[
                    (current_app.df_metadata["Page"] == int(page_nr))
                    & (current_app.df_metadata["Image_Index"] == int(img_nr))
                ].index,
                inplace=True,
            )
        else:
            current_app.df_metadata.loc[
                (current_app.df_metadata["Page"] == int(page_nr))
                & (current_app.df_metadata["Image_Index"] == int(img_nr)),
                "Error_Description",
            ] = f


def stop_categorization_timer():
    """Stop the categorization timer."""
    if current_app.proofread_time["finish_categorize"] is None:
        current_app.proofread_time["finish_categorize"] = datetime.datetime.now()
        current_app.proofread_time["difference_categorize"] = (
            current_app.proofread_time["finish_categorize"]
            - current_app.proofread_time["start_categorize"]
        )


@blueprint.route("/custom_flag", methods=["GET", "POST"])
@cross_origin()
def custom_flag():
    """Serves Ajax request, retrieving the custom error message."""
    page = request.get_json()["page"]
    img_id = request.get_json()["img_id"]
    error_flag = current_app.df_metadata.loc[
        (current_app.df_metadata["Page"] == int(page))
        & (current_app.df_metadata["Image_Index"] == int(img_id)),
        ["Error_Description"],
    ].to_dict(orient="records")[0]["Error_Description"]
    data = json.dumps(error_flag)
    return jsonify(message=data)
