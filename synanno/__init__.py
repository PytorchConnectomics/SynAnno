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

global progress_bar_status
progress_bar_status = {"status":"Loading Source File", "percent":0}

# document the time needed for proofreading
global proofread_time
proofread_time = {"start_grid":None,"finish_grid":None,"difference_grid":None, "start_categorize":None,"finish_categorize":None,"difference_categorize":None}

# neuroglancer instance
global ng_viewer  # handle to the neurglancer viewer instance
global ng_version  # versioning number for the neuroglancer instance
ng_version = None # initialize the neuroglancer version number as noon

# values for the custom fp bounding box
global bottom_left # xy value of the bottom left corner of a fp bounding box
global top_right # xy value of the top right corner of a fp bounding box

bottom_left = 0
top_right = 0

from synanno.routes import annotation, finish, opendata, categorize, landingpage, manual_annotate


@app.context_processor
def handle_context():
    return dict(os=os)