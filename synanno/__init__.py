from flask import Flask
from flask_session import Session
from flask_cors import CORS
import pandas as pd
import os
from threading import Lock


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

    # global lock for cloud volume download operations
    app.cloud_volume_download_lock = Lock()

    return app


def configure_app(app):
    """Configure the Flask app with required settings."""
    # Enable CORS
    CORS(app)
    app.config["DEBUG_APP"] = bool(os.getenv("DEBUG_APP", "True") == "True")
    app.config["CORS_HEADERS"] = "Content-Type"

    # Secret key and session settings
    app.secret_key = os.getenv("SECRET_KEY", os.urandom(32))
    app.config["SESSION_PERMANENT"] = bool(os.getenv("DEBUG_APP", "False") == "True")
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = "/tmp/flask_session"

    # Initialize session
    Session(app)

    # Application-specific configurations
    app.config.update(
        PACKAGE_NAME="synanno/",
        STATIC_FOLDER="static/",
        UPLOAD_FOLDER="files/",
        CLOUD_VOLUME_BUCKETS=["gs:", "s3:", "file:"],
        JSON="synAnno.json",
        IP=os.getenv("APP_IP", "0.0.0.0"),
        PORT=int(os.getenv("APP_PORT", 80)),
        NG_IP="localhost",
        NG_PORT="9015",
    )

    # Initialize global variables
    initialize_global_variables(app)


def initialize_global_variables(app):
    """Set up the global variables for the app."""
    app.progress_bar_status = {"status": "Loading Source File", "percent": 0}
    app.proofread_time = {
        "start_grid": None,
        "finish_grid": None,
        "difference_grid": None,
        "start_categorize": None,
        "finish_categorize": None,
        "difference_categorize": None,
    }
    app.ng_viewer = None
    app.ng_version = None
    app.view_style = "view"
    app.grid_opacity = 0.5
    app.coordinate_order = {}
    app.vol_dim = (0, 0, 0)
    app.vol_dim_scaled = (0, 0, 0)
    app.source = None
    app.cz1, app.cz2, app.cz, app.cy, app.cx = 0, 0, 0, 0, 0
    app.columns = [
        "Page",
        "Image_Index",
        "GT",
        "EM",
        "Label",
        "Annotated",
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

    app.df_metadata = pd.DataFrame(columns=app.columns)
    app.materialization = {}

    app.pre_id_color_main = (0, 255, 0)
    app.pre_id_color_sub = (200, 255, 200)
    app.post_id_color_main = (0, 0, 255)
    app.post_id_color_sub = (200, 200, 255)


def register_routes(app):
    """Register routes to avoid circular imports and ensure proper Blueprint registration."""
    from synanno.routes.annotation import blueprint as annotation_blueprint
    from synanno.routes.finish import blueprint as finish_blueprint
    from synanno.routes.opendata import blueprint as opendata_blueprint
    from synanno.routes.categorize import blueprint as categorize_blueprint
    from synanno.routes.landingpage import blueprint as landingpage_blueprint
    from synanno.routes.manual_annotate import blueprint as manual_annotate_blueprint
    from synanno.routes.auto_annotate import blueprint as auto_annotate_blueprint

    # Register the Blueprints with the app object.
    app.register_blueprint(annotation_blueprint)
    app.register_blueprint(finish_blueprint)
    app.register_blueprint(opendata_blueprint)
    app.register_blueprint(categorize_blueprint)
    app.register_blueprint(landingpage_blueprint)
    app.register_blueprint(manual_annotate_blueprint)
    app.register_blueprint(auto_annotate_blueprint)


def setup_context_processors(app):
    """Set up context processors for the app."""

    @app.context_processor
    def handle_context():
        return dict(os=os)
