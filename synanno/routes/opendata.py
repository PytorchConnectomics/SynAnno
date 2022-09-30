# flask 
from flask import render_template, flash, request, jsonify, session
from flask_cors import cross_origin

# os and process dependent imports
import os
import os.path
from werkzeug.utils import secure_filename

# backend package
import synanno.backend.processing as ip

# import the package app 
from synanno import app
import synanno

# json dependent imports
import json

# neuroglancer dependent imports
import synanno.routes.utils.ng_util as ng_util

# import json util
import synanno.routes.utils.json_util as json_util

# global variables
global source_img  # path to the images
global target_seg  # path to the segmentation masks
global draw_or_annotate # defines the downstream task; either draw or annotate


@app.route('/open_data', defaults={'task': 'annotate'})
@app.route('/open_data/<string:task>', methods=['GET'])
def open_data(task):
    global draw_or_annotate

    draw_or_annotate = task
    if os.path.isdir('./synanno/static/Images/Img'):
        flash('Click \"Reset Backend\" to clear the memory and start a new task.')
        return render_template('opendata.html', modecurrent='d-none', modenext='d-none', modereset='inline', mode=draw_or_annotate, filename=secure_filename(app.config['JSON']))
    return render_template('opendata.html', modenext='disabled', mode=draw_or_annotate)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    global source_img
    global target_seg
    global draw_or_annotate

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

    session['patch_size'] = patch_size

    # check if the path to the required files (source and target) are not None
    if file_original.filename and file_gt.filename:

        # retrive the names of the provided files
        original_name = save_file(file_original, file_original.filename)
        gt_name = save_file(file_gt, file_gt.filename)

        # if the source and target path are valid
        if original_name and gt_name:

            # remove existing json file
            if os.path.isfile(os.path.join('.', app.config['JSON'])):
                os.remove(os.path.join('.', app.config['JSON']))

            # if a json got provided save it locally and process the data based on the JSON info
            if file_json.filename:
                filename_json = save_file(file_json, app.config['JSON'], '.')
                _, source_img, target_seg = ip.load_3d_files(
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']), file_original.filename),
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']), file_gt.filename),
                    patch_size=patch_size,
                    filename_json=filename_json)
            # else compute the bounding box information and write them to a json
            else:
                filename_json, source_img, target_seg = ip.load_3d_files(
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']), file_original.filename),
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER']), file_gt.filename),
                    patch_size)

            # if the NG version number is None setup a new NG viewer
            if synanno.ng_version is None:
                ng_util.setup_ng(source_img, target_seg)

        # test if the created/provided json is valid by loading it
        try:
            with open(filename_json, 'r') as f:
                json.load(f)
            flash('Data ready!')
            return render_template('opendata.html', filename=filename_json, modecurrent='disabled', modeform='formFileDisabled', mode=draw_or_annotate)
        except ValueError as e:
            flash('Something is wrong with the loaded JSON!', 'error')
            return render_template('opendata.html', modenext='disabled', mode=draw_or_annotate)
    else:
        flash('Please provide at least the paths to valid source and target .h5 files!', 'error')
        return render_template('opendata.html', modenext='disabled', mode=draw_or_annotate)


@app.route('/progress', methods=['POST'])
@cross_origin()
def progress():
    return jsonify({
                    'status': synanno.progress_bar_status['status'], 
                    'progress': synanno.progress_bar_status['percent']
                    })

@app.route('/neuro', methods=['POST'])
@cross_origin()
def neuro():

    oz = int(request.form['cz0'])
    oy = int(request.form['cy0'])
    ox = int(request.form['cx0'])

    if synanno.ng_version is not None:
        # update the view center
        with synanno.ng_viewer.txn() as s:
            s.position = [oz, oy, ox]
    else:
        raise Exception('No NG instance running')

    print(f'Neuroglancer instance running at {synanno.ng_viewer}, centered at x,y,x {oz,oy,ox}')

    final_json = jsonify({'ng_link':'http://'+app.config['IP']+':9015/v/'+str(synanno.ng_version)+'/'})

    return final_json

def save_file(file, filename, path=os.path.join(app.config['PACKAGE_NAME'],app.config['UPLOAD_FOLDER'])):
    global draw_or_annotate
    filename = secure_filename(filename)
    file_ext = os.path.splitext(filename)[1]
    if file_ext not in app.config['UPLOAD_EXTENSIONS']:
        flash('Incorrect file format! Load again.', 'error')
        render_template('opendata.html', modenext='disabled', mode=draw_or_annotate)
        return 0
    else:
        file.save(os.path.join(path, filename))
        return(filename)
