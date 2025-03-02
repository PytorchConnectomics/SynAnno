import datetime
import io
import json
import logging
import zipfile

from flask import (
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
    send_file,
    session,
)
from jinja2 import Template

from synanno import initialize_global_variables
from synanno.backend.utils import img_to_png_bytes, png_bytes_to_pil_img

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

blueprint = Blueprint("finish", __name__)


@blueprint.route("/export_annotate")
def export_annotate() -> Template:
    """Renders final view of the annotation process.

    Return:
        Export-annotate view
    """
    return render_template("export_annotate.html", disable_snp="disabled")


@blueprint.route("/export_draw")
def export_draw() -> Template:
    """Renders final view of the draw process.

    Return:
        Export-draw view
    """
    return render_template("export_draw.html", disable_snp="disabled")


@blueprint.route("/download_json", methods=["GET", "HEAD"])
def download_json():
    """Provide JSON data as a direct download from memory.

    Returns:
        - Serves JSON data directly from memory.
        - Returns 200 for HEAD requests if data exists.
        - Renders an error page if no data is available.
    """
    if current_app.n_pages <= 0 or current_app.df_metadata.empty:
        flash("No file - session data is empty.", "error")
        return render_template("export_annotate.html", disable_snp=" ")

    final_data = {
        "Proofread Time": current_app.proofread_time,
        "Metadata": current_app.df_metadata.to_dict("records"),
    }

    json_bytes = convert_json_to_bytes(final_data)

    if request.method == "HEAD":
        return "", 200

    return send_file(
        json_bytes,
        mimetype="application/json",
        as_attachment=True,
        download_name="synanno.json",
    )


def convert_json_to_bytes(data: dict) -> io.BytesIO:
    """Convert JSON data to bytes."""
    json_str = json.dumps(data, indent=4, default=json_serial)
    json_bytes = io.BytesIO(json_str.encode("utf-8"))
    json_bytes.seek(0)
    return json_bytes


@blueprint.route("/download_all_masks", methods=["GET"])
def download_all_masks():
    """Creates a ZIP file in memory with all custom masks and serves it for download."""
    zip_buffer = create_zip_with_masks()

    if zip_buffer.tell() == 0:
        flash(
            "No masks available for download. " "Did you draw custom masks?",
            "error",
        )
        return render_template("export_draw.html", disable_snp=" ")

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name="custom_masks.zip",
    )


def create_zip_with_masks() -> io.BytesIO:
    """Create a ZIP file in memory with all masks."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for img_index, mask_data in current_app.target_image_data.items():
            meta_data = get_metadata_for_image_index(img_index)
            coordinates = "_".join(map(str, meta_data["Adjusted_Bbox"]))

            for canvas_type in ["circlePre", "circlePost", "curve"]:
                if canvas_type in mask_data:
                    for slice_id, image_bytes in mask_data[canvas_type].items():
                        img = png_bytes_to_pil_img(image_bytes)
                        img_io = img_to_png_bytes(img)
                        filename = f"{canvas_type}_idx_{img_index}_slice_{slice_id}"
                        f"_cor_{coordinates}.png"
                        zip_file.writestr(filename, img_io)
    return zip_buffer


def get_metadata_for_image_index(img_index: str) -> dict:
    """Retrieve metadata for a given image index."""
    int(img_index)
    return current_app.df_metadata.query("Image_Index == @img_index_int").to_dict(
        "records"
    )[0]


@blueprint.route("/reset")
def reset() -> Template:
    """Resets all processes by clearing the session content, resetting the process bar,
    resetting the timer, deleting the JSON, the images, the SWCs, masks, and zip folder.

    Return:
        Renders the landing-page view.
    """
    session.clear()
    initialize_global_variables(current_app)
    return render_template("landingpage.html")


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime.timedelta)):
        return str(obj)
    if isinstance(obj, (datetime.datetime)):
        return obj.isoformat()
    raise TypeError("Type %s not serializable" % type(obj))
