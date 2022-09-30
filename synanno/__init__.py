# os and process dependent imports
import os
from time import process_time

# flask dependent imports
from flask_session import Session
from flask_cors import CORS
from flask import Flask


app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

# setting the secret key to a random value to invalidate the old sessions
app.secret_key = os.urandom(32)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

app.config['PACKAGE_NAME'] = 'synanno/'

app.config['UPLOAD_FOLDER'] = 'files/' # carful with changing this as it is used for deletion

app.config['UPLOAD_EXTENSIONS'] = ['.json', '.h5']

app.config['STATIC_FOLDER'] = 'static/'

app.config['JSON'] = 'synAnno.json'

app.config['IP'] = '127.0.0.1'
app.config['PORT'] = '5000'

app.config['NG_IP'] = 'localhost'
app.config['NG_PORT'] = '9015'

# document the time needed for loading the image, gt, and json data
global progress_bar_status
progress_bar_status = {"status":"Loading Source File", "percent":0}

# handle to the loaded image and gt data
global im
global seg

im = None
seg = None

# document the time needed for proofreading
global proofread_time
proofread_time = {"start_grid":None,"finish_grid":None,"difference_grid":None, "start_categorize":None,"finish_categorize":None,"difference_categorize":None}

# volume dimensions
global vol_dim_x
global vol_dim_y
global vol_dim_z

vol_dim_x = 0
vol_dim_y = 0
vol_dim_z = 0

# neuroglancer instance
global ng_viewer  # handle to the neurglancer viewer instance
global ng_version  # versioning number for the neuroglancer instance
ng_version = None # initialize the neuroglancer version number as noon

# backlog for the custom fp bounding boxes
global cus_fp_bbs

cus_fp_bbs = []

# values for the current custom fp bounding box
global cz
global cy
global cx

cz1 = 0
cz2 = 0
cy = 0
cx = 0

# indicate whether the json was changed
global new_json
new_json = False

from synanno.routes import annotation, finish, opendata, categorize, landingpage, manual_annotate


@app.context_processor
def handle_context():
    return dict(os=os)