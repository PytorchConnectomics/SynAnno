import logging

from flask import Blueprint, send_from_directory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

blueprint = Blueprint("file_access", __name__)


@blueprint.route("/static/<path:filename>")
def static_files(filename):
    logger.info(f"Serving static file: {filename}")
    return send_from_directory("static", filename)
