# flask 
from flask import render_template, flash, request, jsonify
from flask_cors import cross_origin

# os and process dependent imports
import os
import os.path
from werkzeug.utils import secure_filename

# backend package
import synanno.backend.processing as ip

# import the package app 
from synanno import app

# json dependent imports
import json

# neuroglancer dependent imports
import neuroglancer
import random

# global variables
global source_img  # path to the images
global target_seg  # path to the segmentation masks
global ng_viewer  # handle to the neurglancer viewer instance
global neuro_version  # versioning number for the neuroglancer instance

# initialize the neuroglancer version number as noon
neuro_version = None

@app.route('/')
def open_data():
    return render_template('opendata.html', modenext='disabled')


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    global source_img
    global target_seg
    global neuro_version
    global ng_viewer

    # Check if files folder exists, if not create it
    if not os.path.exists(os.path.join('.', os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']))):
        os.mkdir(os.path.join('.', os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER'])))

    # retrive the file paths from the coresponding html fields
    file_original = request.files['file_original']
    file_gt = request.files['file_gt']
    file_json = request.files['file_json']

    # update the patch size if provided
    if request.form.get('patchsize'):
        patch_size = int(request.form.get('patchsize'))
    else:
        patch_size = 142  # default patch size

    # check if the path to the required files (source and target) are not None
    if file_original.filename and file_gt.filename:

        # retrive the names of the provided files
        original_name = save_file(file_original, file_original.filename)
        gt_name = save_file(file_gt, file_gt.filename)

        # if the source and target path are valid
        if original_name and gt_name:

            # remove existing json file
            if os.path.isfile(os.path.join('.', 'synAnno.json')):
                os.remove(os.path.join('.', 'synAnno.json'))

            # if a json got provided save it locally
            if file_json.filename:
                filename_json = save_file(file_json, 'synAnno.json', '.')

            # else compute the bounding box information and write them to a json
            else:
                filename_json, source_img, target_seg = ip.load_3d_files(
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']), file_original.filename),
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']), file_gt.filename),
                    patch_size)

            # if the NG version number is None setup a new NG viewer
            if neuro_version is None:
                # generate a version number
                neuro_version = str(random.randint(0, 32e+2))

                # setup a Tornado web server and create viewer instance
                neuroglancer.set_server_bind_address(
                    bind_address=app.config['NG_IP'], bind_port=app.config['NG_PORT'])
                ng_viewer = neuroglancer.Viewer(token=neuro_version)

                # specify the NG coordinate space
                res = neuroglancer.CoordinateSpace(
                    names=['z', 'y', 'x'],
                    units=['nm', 'nm', 'nm'],
                    scales=[30, 8, 8])

                # config viewer: Add image layer, add segmentation mask layer, define position
                with ng_viewer.txn() as s:
                    s.layers.append(name='im', layer=neuroglancer.LocalVolume(
                        source_img, dimensions=res, volume_type='image', voxel_offset=[0, 0, 0]))
                    s.layers.append(name='gt', layer=neuroglancer.LocalVolume(
                        target_seg, dimensions=res, volume_type='segmentation', voxel_offset=[0, 0, 0]))
                    s.position = [0, 0, 0]

                print(
                    f'Starting a Neuroglancer instance at {ng_viewer}, centered at x,y,x {0,0,0}')

        # test if the created/provided json is valid by loading it
        try:
            with open(filename_json, 'r') as f:
                json.load(f)
            flash('Data ready!')
            return render_template('opendata.html', filename=filename_json, modecurrent='disabled', modeform='formFileDisabled')
        except ValueError as e:
            flash('Something is wrong with the loaded JSON!', 'error')
            return render_template('opendata.html', modenext='disabled')
    else:
        flash('Please provide at least the paths to valid source and target .h5 files!', 'error')
        return render_template('opendata.html', modenext='disabled')


@app.route('/neuro', methods=['POST'])
@cross_origin()
def neuro():
    global neuro_version
    global ng_viewer

    oz = int(request.form['cz0'])
    oy = int(request.form['cy0'])
    ox = int(request.form['cx0'])

    if neuro_version is not None:
        # update the view center
        with ng_viewer.txn() as s:
            s.position = [oz, oy, ox]
    else:
        raise Exception('No NG instance running')

    print(f'Neuroglancer instance running at {ng_viewer}, centered at x,y,x {oz,oy,ox}')

    final_json = jsonify({'ng_link':'http://'+app.config['IP']+':9015/v/'+str(neuro_version)+'/'})

    return final_json

def save_file(file, filename, path=os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER'])):
    filename = secure_filename(filename)
    file_ext = os.path.splitext(filename)[1]
    if file_ext not in app.config['UPLOAD_EXTENSIONS']:
        flash('Incorrect file format! Load again.', 'error')
        render_template('opendata.html', modenext='disabled')
        return 0
    else:
        file.save(os.path.join(path, filename))
        return(filename)