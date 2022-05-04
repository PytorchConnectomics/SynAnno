# flask 
from flask import render_template, session, flash, jsonify, request, send_file, redirect
from flask_cors import cross_origin

# os and process dependent imports
import os
import os.path
import shutil
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
    if not os.path.exists(os.path.join('.', app.config['UPLOAD_FOLDER'])):
        os.mkdir(os.path.join('.', app.config['UPLOAD_FOLDER']))

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
                        app.config['UPLOAD_FOLDER'], file_original.filename),
                    os.path.join(
                        app.config['UPLOAD_FOLDER'], file_gt.filename),
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
            flash('Something is wrong with the loaded JSON!')
            return render_template('opendata.html', modenext='disabled')
    else:
        flash('Please provide at least the paths to valid source and target .h5 files!')
        return render_template('opendata.html', modenext='disabled')


@app.route('/set-data/<data_name>')
@app.route('/set-data')
def set_data(data_name='synAnno.json'):

    # set the number of cards in one page
    per_page = 50
    session['per_page'] = per_page

    # open the json data and save it to the session
    f = open(os.path.join('.', data_name))
    data = json.load(f)

    if not session.get('data'):
        session['data'] = [data['Data'][i:i+per_page]
                           for i in range(0, len(data['Data']), per_page)]

    # save the name of the json file to the session
    session['filename'] = data_name

    # retrive the number of instances in the json {'Data': [ ... ]}
    number_images = len(data['Data'])

    if number_images == 0:
        flash('No synapsis detect in the GT data or the provided JSON does not list any')
        return render_template('opendata.html', modenext='disabled')

    # calculate the number of pages needed for the instance count in the JSON
    number_pages = number_images // per_page
    if not (number_images % per_page == 0):
        number_pages = number_pages + 1

    # save the number of required pages to the session
    if not session.get('n_pages'):
        session['n_pages'] = number_pages

    return render_template('annotation.html', images=session.get('data')[0], page=0, n_pages=session.get('n_pages'))


@app.route('/annotation')
@app.route('/annotation/<int:page>')
def annotation(page=0):
    return render_template('annotation.html', images=session.get('data')[page], page=page, n_pages=session.get('n_pages'))


@app.route('/neuro')
@app.route('/neuro/<int:oz>/<int:oy>/<int:ox>/', methods=['GET'])
def neuro(oz=0, oy=0, ox=0):
    global neuro_version
    global ng_viewer

    if neuro_version is not None:
        # update the view center
        with ng_viewer.txn() as s:
            s.position = [oz, oy, ox]
    else:
        raise Exception('No NG instance running')

    print(
        f'Neuroglancer instance running at {ng_viewer}, centered at x,y,x {oz,oy,ox}')

    return redirect('http://'+app.config['IP']+':9015/v/'+str(neuro_version)+'/', 301)


@app.route('/finalpage')
def final_page():
    return render_template('exportdata.html')


@app.route('/finalize')
def finalize():
    # pop all the session content.
    for key in list(session.keys()):
        session.pop(key)

    # delete all the uploaded h5 files
    if os.path.exists(os.path.join('.', app.config['UPLOAD_FOLDER'])):
        for filename in os.listdir(os.path.join('.', app.config['UPLOAD_FOLDER'])):
            file_path = os.path.join(
                os.path.join('.', app.config['UPLOAD_FOLDER']), filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))

    # delete json file.
    if os.path.isfile(os.path.join('.', 'synAnno.json')):
        os.remove(os.path.join('.', 'synAnno.json'))

    # delete static images
    image_folder = './synanno/static/Images/'
    if os.path.exists(image_folder):
        try:
            shutil.rmtree(image_folder)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    return render_template('opendata.html', modenext='disabled')


@app.route('/export')
def export_data():
    final_filename = 'results-' + session.get('filename')
    # Exporting the final json and pop session
    if session.get('data') and session.get('n_pages'):
        final_file = dict()
        final_file['Data'] = sum(session['data'], [])
        print("----debug---")
        print(app.config['UPLOAD_FOLDER'] + final_filename)
        with open(app.config['UPLOAD_FOLDER'] + final_filename, 'w') as f:
            json.dump(final_file, f)
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'],final_filename), as_attachment=True, attachment_filename=final_filename)
    else:
        return render_template('exportdata.html')


@app.route('/update-card', methods=['POST'])
@cross_origin()
def update_card():
    page = int(request.form['page'])
    index = int(request.form['data_id'])-1
    label = request.form['label']

    data = session.get('data')

    if (label == 'Incorrect'):
        data[page][index]['Label'] = 'Unsure'
    elif (label == 'Unsure'):
        data[page][index]['Label'] = 'Correct'
    elif (label == 'Correct'):
        data[page][index]['Label'] = 'Incorrect'

    session['data'] = data

    return jsonify({'result': 'success', 'label': data[page][index]['Label']})


@app.route('/get_slice', methods=['POST'])
@cross_origin()
def get_slice():
    page = int(request.form['page'])
    index = int(request.form['data_id']) - 1

    data = session.get('data')

    return jsonify(data=data[page][index])


@app.route('/save_slices', methods=['POST'])
@cross_origin()
def save_slices():
    page = int(request.form['page'])
    index = int(request.form['data_id']) - 1

    data = session.get('data')
    slices_len = len(os.listdir('./synanno' + data[page][index]['EM']+'/')) - 1
    half_len = int(data[page][index]['Middle_Slice'])

    if(slices_len % 2 == 0):
        range_min = half_len - ((slices_len)//2) + 1
    else:
        range_min = half_len - (slices_len//2)

    final_json = jsonify(data=data[page][index], slices_len=slices_len, halflen=half_len,
                         range_min=range_min, host=app.config['IP'], port=app.config['PORT'])

    return final_json


@app.context_processor
def utility_functions():
    # function used for debugging on html level
    # add {{ variable }} any where in the html file
    def print_in_console(message):
        print(str(message))
    return dict(mdebug=print_in_console)


def save_file(file, filename, path=app.config['UPLOAD_FOLDER']):
    filename = secure_filename(filename)
    file_ext = os.path.splitext(filename)[1]
    if file_ext not in app.config['UPLOAD_EXTENSIONS']:
        flash('Incorrect file format! Load again.')
        render_template('opendata.html', modenext='disabled')
        return 0
    else:
        file.save(os.path.join(path, filename))
        return(filename)
