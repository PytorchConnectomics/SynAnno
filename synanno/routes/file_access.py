import io
import logging

from flask import Blueprint, Response, current_app, request, send_file
from flask_cors import cross_origin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

blueprint = Blueprint("file_access", __name__)


@blueprint.route("/get_swc", methods=["GET"])
def get_swc():
    """Serve the SWC file stored in memory."""
    if not hasattr(current_app, "neuron_skeleton"):
        return "SWC file not available", 404  # Handle missing data

    # Read SWC from in-memory bytes and send as response
    swc_data = current_app.neuron_skeleton.getvalue().decode("utf-8")
    return Response(swc_data, mimetype="text/plain")


@blueprint.route("/source_and_target_exist/<image_index>/<slice_id>", methods=["GET"])
@cross_origin()
def source_and_target_exist(image_index, slice_id):
    """Valide that both source and target images are available."""
    image_index = str(image_index)
    slice_id = str(slice_id)
    if (
        image_index in current_app.source_image_data
        and slice_id in current_app.source_image_data[image_index]
    ) and (
        image_index in current_app.target_image_data
        and slice_id in current_app.target_image_data[image_index]
    ):
        return "Image found", 200
    return "Image not found", 204


@blueprint.route("/get_source_image/<image_index>/<slice_id>", methods=["GET", "HEAD"])
@cross_origin()
def get_source_image(image_index, slice_id):
    """Serves EM images from memory."""
    image_index = str(image_index)
    slice_id = str(slice_id)
    if (
        image_index in current_app.source_image_data
        and slice_id in current_app.source_image_data[image_index]
    ):
        if request.method == "HEAD":
            return "", 200  # Respond with an empty body for HEAD request
        return send_file(
            io.BytesIO(current_app.source_image_data[image_index][slice_id]),
            mimetype="image/png",
        )
    if request.method == "HEAD":
        return "", 204  # Return 204 No Content instead of 404 Not Found
    return "Image not found", 404


@blueprint.route("/get_target_image/<image_index>/<slice_id>", methods=["GET", "HEAD"])
@cross_origin()
def get_target_image(image_index, slice_id):
    """Serves synapse segmentation images from memory."""
    image_index = str(image_index)
    slice_id = str(slice_id)
    if (
        image_index in current_app.target_image_data
        and slice_id in current_app.target_image_data[image_index]
    ):
        if request.method == "HEAD":
            return "", 200  # Respond with an empty body for HEAD request
        return send_file(
            io.BytesIO(current_app.target_image_data[image_index][slice_id]),
            mimetype="image/png",
        )
    if request.method == "HEAD":
        return "", 204  # Return 204 No Content instead of 404 Not Found
    return "Image not found", 404


@cross_origin()
@blueprint.route("/get_curve_image/<image_index>/<slice_id>", methods=["GET", "HEAD"])
def get_curve_image(image_index, slice_id):
    """Serves curve images from memory."""
    image_index = str(image_index)
    slice_id = str(slice_id)
    if (
        image_index in current_app.target_image_data
        and "curve" in current_app.target_image_data[image_index]
        and slice_id in current_app.target_image_data[image_index]["curve"]
    ):
        if request.method == "HEAD":
            return "", 200  # Respond with an empty body for HEAD request
        return send_file(
            io.BytesIO(current_app.target_image_data[image_index]["curve"][slice_id]),
            mimetype="image/png",
        )
    if request.method == "HEAD":
        return "", 204  # Return 204 No Content instead of 404 Not Found
    return "Image not found", 404


@cross_origin()
@blueprint.route(
    "/get_auto_curve_image/<image_index>/<slice_id>", methods=["GET", "HEAD"]
)
def get_auto_curve_image(image_index, slice_id):
    """Serves auto curve images from memory."""
    image_index = str(image_index)
    slice_id = str(slice_id)
    if (
        image_index in current_app.target_image_data
        and "auto_curve" in current_app.target_image_data[image_index]
        and slice_id in current_app.target_image_data[image_index]["auto_curve"]
    ):
        if request.method == "HEAD":
            return "", 200  # Respond with an empty body for HEAD request
        return send_file(
            io.BytesIO(
                current_app.target_image_data[image_index]["auto_curve"][slice_id]
            ),
            mimetype="image/png",
        )
    if request.method == "HEAD":
        return "", 204  # Return 204 No Content instead of 404 Not Found
    return "Image not found", 404


@cross_origin()
@blueprint.route(
    "/get_circle_pre_image/<image_index>/<slice_id>", methods=["GET", "HEAD"]
)
def get_circle_pre_image(image_index, slice_id):
    """Serves circle pre images from memory."""
    image_index = str(image_index)
    slice_id = str(slice_id)
    if (
        image_index in current_app.target_image_data
        and "circlePre" in current_app.target_image_data[image_index]
        and slice_id in current_app.target_image_data[image_index]["circlePre"]
    ):
        if request.method == "HEAD":
            return "", 200  # Respond with an empty body for HEAD request
        return send_file(
            io.BytesIO(
                current_app.target_image_data[image_index]["circlePre"][slice_id]
            ),
            mimetype="image/png",
        )
    if request.method == "HEAD":
        return "", 204  # Return 204 No Content instead of 404 Not Found
    return "Image not found", 404


@cross_origin()
@blueprint.route(
    "/get_circle_post_image/<image_index>/<slice_id>", methods=["GET", "HEAD"]
)
def get_circle_post_image(image_index, slice_id):
    """Serves circle post images from memory."""
    image_index = str(image_index)
    slice_id = str(slice_id)
    if (
        image_index in current_app.target_image_data
        and "circlePost" in current_app.target_image_data.get(image_index, {})
        and slice_id in current_app.target_image_data[image_index]["circlePost"]
    ):
        if request.method == "HEAD":
            return "", 200  # Respond with an empty body for HEAD request
        return send_file(
            io.BytesIO(
                current_app.target_image_data[image_index]["circlePost"][slice_id]
            ),
            mimetype="image/png",
        )
    if request.method == "HEAD":
        return "", 204  # Return 204 No Content instead of 404 Not Found
    return "Image not found", 404
