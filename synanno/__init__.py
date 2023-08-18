import os
from flask_session import Session
from flask_cors import CORS
from flask import Flask
import pandas as pd

app = Flask(__name__)


def configure_app():
    CORS(app)
    app.config["CORS_HEADERS"] = "Content-Type"

    app.secret_key = os.urandom(32)
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = "/tmp/flask_session"

    Session(app)

    app.config["PACKAGE_NAME"] = "synanno/"
    app.config["UPLOAD_FOLDER"] = "files/"
    app.config["STATIC_FOLDER"] = "static/"
    app.config["CLOUD_VOLUME_BUCKETS"] = ["gs:", "s3:", "file:"]
    app.config["JSON"] = "synAnno.json"
    app.config["IP"] = "127.0.0.1"
    app.config["PORT"] = "5000"
    app.config["NG_IP"] = "localhost"
    app.config["NG_PORT"] = "9015"

    # initialize global variables
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

    return app


# Load all views - avoid cycle load
from synanno.routes import (
    annotation,
    finish,
    opendata,
    categorize,
    landingpage,
    manual_annotate,
)


@app.context_processor
def handle_context() -> dict:
    return dict(os=os)
