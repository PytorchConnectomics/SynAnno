import logging
import os
import threading
from collections import defaultdict
from threading import Lock

import pandas as pd
from flask import Flask
from flask_cors import CORS
from flask_session import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    """Factory function to create and configure the Flask app."""

    app = Flask(__name__)

    # Configure Flask app
    configure_app(app)

    # Register routes with app context properly handled
    with app.app_context():
        register_routes(app)

    # Set up context processor
    setup_context_processors(app)

    # attach a lock for the data frame access to the app instance
    app.df_metadata_lock = Lock()

    return app


def configure_app(app):
    """Configure the Flask app with required settings."""
    # Enable CORS
    CORS(app)
    app.config["DEBUG_APP"] = bool(os.getenv("DEBUG_APP", "True") == "True")
    app.config["CORS_HEADERS"] = "Content-Type"

    # Secret key and session settings
    app.config["SESSION_PERMANENT"] = bool(os.getenv("DEBUG_APP", "False") == "True")
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = "/tmp/flask_session"

    # Initialize session
    Session(app)

    # Application-specific configurations
    app.config.update(
        CLOUD_VOLUME_BUCKETS=["gs:", "s3:", "file:"],
        IP=os.getenv("APP_IP", "0.0.0.0"),
        PORT=int(os.getenv("APP_PORT", 80)),
        NG_IP=os.getenv("PUBLIC_DNS_SYNANNO", "0.0.0.0"),
        NG_PORT=os.getenv("NG_PORT", "9015"),
    )

    # Initialize global variables
    initialize_global_variables(app)


def initialize_global_variables(app):
    """Set up the global variables for the app."""
    app.proofread_time = {
        "start_grid": None,
        "finish_grid": None,
        "difference_grid": None,
        "start_categorize": None,
        "finish_categorize": None,
        "difference_categorize": None,
    }
    app.draw_or_annotate = "annotate"
    app.ng_viewer = None
    app.ng_version = None
    app.selected_neuron_id = None
    app.grid_opacity = 0.5
    # default coordinate order to pass in if processing route not undergone
    # TODO: set scales before the neuron button gets pressed and remove need for default
    app.coordinate_order = {"x": (4, 8), "y": (4, 8), "z": (33, 33)}
    app.vol_dim = (0, 0, 0)
    app.vol_dim_scaled = (0, 0, 0)
    app.source = None
    app.cz1, app.cz2, app.cz, app.cy, app.cx = 0, 0, 0, 0, 0
    app.n_pages = 0
    app.tiles_per_page = 24  # Number of images per page
    # Neuron skeleton info/data
    app.sections = None
    app.neuron_ready = None
    # The auto segmentation view needs a set number of slices per instance (depth)
    # see process_instances.py::load_missing_slices for more details
    app.crop_size_z_draw = 16
    app.crop_size_z = 6
    app.crop_size_x = 256
    app.crop_size_y = 256
    app.columns = [
        "Page",
        "Image_Index",
        "materialization_index",
        "section_index",
        "tree_traversal_index",
        "Label",
        "Annotated",
        "neuron_id",
        "Error_Description",
        "Y_Index",
        "X_Index",
        "Z_Index",
        "Middle_Slice",
        "Original_Bbox",
        "cz0",
        "cy0",
        "cx0",
        "pre_pt_z",
        "pre_pt_x",
        "pre_pt_y",
        "post_pt_y",
        "post_pt_z",
        "post_pt_x",
        "crop_size_x",
        "crop_size_y",
        "crop_size_z",
        "Adjusted_Bbox",
        "Padding",
    ]

    dtypes = {
        "Page": int,  # Example: 1
        "Image_Index": int,  # Example: 0
        "materialization_index": int,  # Example: 0
        "section_index": int,  # Example: 0
        "tree_traversal_index": int,  # Example
        "Label": str,  # Example: 'Images/Img/1'
        "Annotated": str,  # Example: 'incorrect'
        "neuron_id": int,  # Example: 1
        "Error_Description": str,  # Example: 'No'
        "Y_Index": int,  # Example: None (can be float if numeric)
        "X_Index": int,  # Example: 1
        "Z_Index": int,  # Example: 0
        "Middle_Slice": int,  # Example: 2
        "Original_Bbox": object,  # Example: [290204, 290460, 114415, 114671, 256, 257]
        "cz0": int,  # Example: 290204
        "cy0": int,  # Example: 290460
        "cx0": int,  # Example: 114415
        "pre_pt_z": int,  # Example: 114671
        "pre_pt_x": int,  # Example: 256
        "pre_pt_y": int,  # Example: 257
        "post_pt_y": int,  # Example: 114543
        "post_pt_z": int,  # Example: 290332
        "post_pt_x": int,  # Example: 256
        "crop_size_x": int,  # Example: 290329
        "crop_size_y": int,  # Example: 114538
        "crop_size_z": int,  # Example: 114546
        "Adjusted_Bbox": object,  # Example: [290204, 290460, 114415, 114671, 256, 257]
        "Padding": object,  # Example: [[0, 0], [0, 0], [0, 0]]
    }

    app.df_metadata = pd.DataFrame(columns=app.columns).astype(dtypes)

    app.synapse_data = {}

    # holds a dict of tuples with the page number and the section index
    app.page_section_mapping = {}

    app.source_image_data = defaultdict(dict)
    app.target_image_data = defaultdict(dict)

    app.snapped_point_cloud = None

    app.pre_id_color_main = (0, 255, 0)
    app.pre_id_color_sub = (200, 255, 200)
    app.post_id_color_main = (0, 0, 255)
    app.post_id_color_sub = (200, 200, 255)

    app.retrieve_instance_metadata_lock = threading.Lock()


def register_routes(app):
    """Register routes to avoid circular imports."""
    from synanno.routes.annotation import blueprint as annotation_blueprint
    from synanno.routes.auto_annotate import blueprint as auto_annotate_blueprint
    from synanno.routes.categorize import blueprint as categorize_blueprint
    from synanno.routes.false_negatives import blueprint as fn_blueprint
    from synanno.routes.file_access import blueprint as file_access_blueprint
    from synanno.routes.finish import blueprint as finish_blueprint
    from synanno.routes.landingpage import blueprint as landingpage_blueprint
    from synanno.routes.manual_annotate import blueprint as manual_annotate_blueprint
    from synanno.routes.opendata import blueprint as opendata_blueprint

    # Register the Blueprints with the app object.
    app.register_blueprint(file_access_blueprint)
    app.register_blueprint(annotation_blueprint)
    app.register_blueprint(finish_blueprint)
    app.register_blueprint(opendata_blueprint)
    app.register_blueprint(categorize_blueprint)
    app.register_blueprint(landingpage_blueprint)
    app.register_blueprint(manual_annotate_blueprint)
    app.register_blueprint(auto_annotate_blueprint)
    app.register_blueprint(fn_blueprint)


def setup_context_processors(app):
    """Set up context processors for the app."""

    @app.context_processor
    def handle_context():
        return dict(os=os)  # noqa: C408
