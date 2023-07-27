# os and process dependent imports
import os

# flask dependent imports
from flask_session import Session
from flask_cors import CORS
from flask import Flask
import pandas as pd

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

# setting the secret key to a random value to invalidate the old sessions
app.secret_key = os.urandom(32)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

''' DANGER! 
    The following three path variables are used by finish.py for deletion.
    Changing them might lead to unwanted loss of files.
'''
app.config['PACKAGE_NAME'] = 'synanno/'

app.config['UPLOAD_FOLDER'] = 'files/' 

app.config['STATIC_FOLDER'] = 'static/'

'''
    The following two variables are used by opendata.py for loading the data.
'''
app.config['CLOUD_VOLUME_BUCKETS'] = ['gs:', 's3:', 'file:']   

app.config['JSON'] = 'synAnno.json'

app.config['IP'] = '127.0.0.1'
app.config['PORT'] = '5000'

app.config['NG_IP'] = 'localhost'
app.config['NG_PORT'] = '9015'

# document the time needed for loading the image, gt, and json data
global progress_bar_status
progress_bar_status = {"status":"Loading Source File", "percent":0}

# document the time needed for proofreading
global proofread_time
proofread_time = {"start_grid":None,"finish_grid":None,"difference_grid":None, "start_categorize":None,"finish_categorize":None,"difference_categorize":None}

# neuroglancer instance
global ng_viewer  # handle to the neurglancer viewer instance
global ng_version  # versioning number for the neuroglancer instance

ng_version = None # initialize the neuroglancer version number as noon


# view style
global view_style

view_style = 'view'

# grid opacity for the annotation view
global grid_opacity
grid_opacity = 0.5

# coordinate order and resolution
global coordinate_order

coordinate_order = {}

# record the max volume dimensions for the provided image volume
global vol_dim_x
global vol_dim_y
global vol_dim_z

vol_dim_x, vol_dim_y, vol_dim_z = 0,0,0

# handle to the loaded image
global source
source = None

# backlog for the custom bounding boxes of the false negatives
global cus_fp_bbs

cus_fp_bbs = []

# values for the current false negative's custom bounding box of the false negatives
global cz
global cy
global cx

cz1, cz2, cy, cx = 0, 0, 0, 0

# global pandas dataframe for the unified storage and access of the instance meta data
global df_metadata

# Define the column names
columns = ['Page', 'Image_Index', 'GT', 'EM', 'Label', 'Annotated', 'Error_Description',
           'Middle_Slice', 'Original_Bbox', 'cz0', 'cy0', 'cx0', 'crop_size_x',
           'crop_size_y', 'crop_size_z', 'Adjusted_Bbox', 'Padding']

# create an empty DataFrame with these columns
df_metadata = pd.DataFrame(columns=columns)

# global materialization data object
global materialization

materialization =  {}

# load all views - avoid cycle load
from synanno.routes import annotation, finish, opendata, categorize, landingpage, manual_annotate


@app.context_processor
def handle_context() -> dict:
    # injects the os variable in to all templates
    # enabling the use of it in jinja logic
    return dict(os=os)