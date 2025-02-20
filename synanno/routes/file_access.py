from flask import Blueprint, send_from_directory

blueprint = Blueprint("file_access", __name__)


@blueprint.route("/static/<path:filename>")
def static_files(filename):
    print(f"Serving static file: {filename}")
    return send_from_directory("static", filename)
