# import global configs
import synanno

# import the package app
from synanno import app

# flask util functions
from flask import render_template, flash, request, jsonify, session, flash

# flask ajax requests
from flask_cors import cross_origin

# backend package
import synanno.backend.processing as ip

# import json util
import synanno.routes.utils.json_util as json_util

# load existing json
import json

# setup and configuration of Neuroglancer instances
import synanno.routes.utils.ng_util as ng_util

# access and remove files
import os

# for type hinting
from jinja2 import Template
from werkzeug.datastructures import MultiDict

# global variables
global draw_or_annotate  # defines the downstream task; either draw or annotate - default to annotate
draw_or_annotate = 'annotate'

@app.route('/open_data', defaults={'task': 'annotate'})
@app.route('/open_data/<string:task>', methods=['GET'])
def open_data(task: str) -> Template:
    ''' Renders the open-data view that lets the user specify the source, target, and json file.

        Args:
            task: Defined through the path chosen by the user |  'draw', 'annotate' 

        Return:
            Renders the open-data view
    '''

    # defines the downstream task | 'draw', 'annotate'
    global draw_or_annotate

    draw_or_annotate = task

    if os.path.isdir('./synanno/static/Images/Img'):
        flash('Click \"Reset Backend\" to clear the memory, start a new task, and start up a Neuroglancer instance.')
        return render_template('opendata.html', modecurrent='d-none', modenext='d-none', modereset='inline', mode=draw_or_annotate, json_name=app.config['JSON'])
    return render_template('opendata.html', modenext='disabled', mode=draw_or_annotate)


@app.route('/upload', methods=['GET', 'POST'])
def upload_file() -> Template:
    ''' Upload the source, target, and json file specified by the user.
        Rerender the open-data view, enabling the user to start the annotation or draw process. 

        Return:
            Renders the open-data view, with additional buttons enabled
    '''

    # defines the downstream task, set by the open-data view | 'draw', 'annotate'
    global draw_or_annotate

    # Check if files folder exists, if not create it
    if not os.path.exists(os.path.join('.', os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']))):
        os.mkdir(os.path.join('.', os.path.join(
            app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER'])))

    # retrieve the file paths from the corresponding html fields
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

        # retrieve the names of the provided files
        original_name = save_file(file_original, file_original.filename)
        gt_name = save_file(file_gt, file_gt.filename)

        # if the source and target path are valid
        if original_name and gt_name:

            # remove existing json file
            if os.path.isfile(os.path.join(os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), app.config['JSON'])):
                os.remove(os.path.join(os.path.join(
                    app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), app.config['JSON']))

            # if a json got provided save it locally and process the data based on the JSON info
            if file_json.filename:
                path_json = save_file(file_json, app.config['JSON'])
                _, source_img, target_seg = ip.load_3d_files(
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), file_original.filename),
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), file_gt.filename),
                    patch_size=patch_size,
                    path_json=path_json)
            # else compute the bounding box information and write them to a json
            else:
                path_json, source_img, target_seg = ip.load_3d_files(
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), file_original.filename),
                    os.path.join(
                        os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), file_gt.filename),
                    patch_size)

            # if the NG version number is None setup a new NG viewer
            if synanno.ng_version is None:
                ng_util.setup_ng(source_img, target_seg)

        # test if the created/provided json is valid by loading it an rerender the open-data view
        try:
            with open(path_json, 'r') as f:
                json.load(f)
            flash('Data ready!')
            return render_template('opendata.html', json_name=path_json.split('/')[-1], modecurrent='disabled', modeform='formFileDisabled', mode=draw_or_annotate)
        except ValueError as e:
            flash('Something is wrong with the loaded JSON!', 'error')
            return render_template('opendata.html', modenext='disabled', mode=draw_or_annotate)
    else:
        flash('Please provide at least the paths to valid source and target .h5 files!', 'error')
        return render_template('opendata.html', modenext='disabled', mode=draw_or_annotate)


@app.route('/set-data/<task>/<json_name>')
@app.route('/set-data/<json_name>')
@app.route('/set-data')
def set_data(task: str = 'annotate', json_name: str = app.config['JSON']) -> Template:
    ''' Used by the annotation and the draw view to set up the session.
        Annotation view: Setup the session, calculate the grid view, render the annotation view
        Draw view: Reload the updated JSON, render the draw view

        Args:
            task: Identifies and links the downstream process: annotate | draw
            json_path: Path to the json file containing the label information

        Return:
            Renders either the annotation or the draw view dependent on the user action
    '''

    # update session['data'] and render the draw view
    if task == 'draw' and synanno.new_json:
        # reload the json, if the user added new FP instances and by doing so updated the JSON
        json_util.reload_json(path=os.path.join(os.path.join(
            app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), app.config['JSON']))
        synanno.new_json = False
        return render_template('draw.html', pages=session.get('data'))
    # setup the session
    else:
        json_path = os.path.join(os.path.join(
            app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), json_name)

        # set the number of cards in one page
        per_page = 18
        session['per_page'] = per_page

        # open the json data and save it to the session
        f = open(json_path)
        data = json.load(f)

        # write the data to the session
        if not session.get('data'):
            session['data'] = [data['Data'][i:i+per_page]
                               for i in range(0, len(data['Data']), per_page)]

        # save the name of the json file to the session
        session['path_json'] = json_path

        # retrive the number of instances in the json {'Data': [ ... ]}
        number_images = len(data['Data'])

        if number_images == 0:
            flash(
                'No synapsis detect in the GT data or the provided JSON does not list any')
            return render_template('opendata.html', modenext='disabled')

        # calculate the number of pages needed for the instance count in the JSON
        number_pages = number_images // per_page
        if not (number_images % per_page == 0):
            number_pages = number_pages + 1

        # save the number of required pages to the session
        if not session.get('n_pages'):
            session['n_pages'] = number_pages

        # link the relevant HTML page based on the defined task
        if task == 'annotate':
            return render_template('annotation.html', images=session.get('data')[0], page=0, n_pages=session.get('n_pages'), grid_opacity=synanno.grid_opacity)
        elif task == 'draw':
            return render_template('draw.html', pages=session.get('data'))


@app.route('/progress', methods=['POST'])
@cross_origin()
def progress() -> dict[str, object]:
    ''' Serves an Ajax request from progressbar.js passing information about the loading
        process to the frontend.

        Return:
            Passes progress status, in percentage, to the frontend as json.
    '''
    return jsonify({
        'status': synanno.progress_bar_status['status'],
        'progress': synanno.progress_bar_status['percent']
    })


@app.route('/neuro', methods=['POST'])
@cross_origin()
def neuro() -> dict[str, object]:
    ''' Serves an Ajax request from annotation.js or draw_module.js, shifting the view focus with
        in the running NG instance and passing the link for the instance to the frontend.

        Return:
            Passes the link to the NG instance as json.
    '''

    # unpack the coordinates for the new focus point of the view
    mode = str(request.form['mode'])

    if mode == "annotate":
        oz = int(request.form['cz0'])
        oy = int(request.form['cy0'])
        ox = int(request.form['cx0'])
    elif mode == 'draw':
        oz = synanno.vol_dim_z // 2
        oy = synanno.vol_dim_y // 2
        ox = synanno.vol_dim_x // 2
        
    if synanno.ng_version is not None:
        # update the view focus of the running NG instance
        with synanno.ng_viewer.txn() as s:
            s.position = [oz, oy, ox]
    else:
        raise Exception('No NG instance running')

    print(
        f'Neuroglancer instance running at {synanno.ng_viewer}, centered at x,y,x {oz,oy,ox}')

    final_json = jsonify(
        {'ng_link': 'http://'+app.config['IP']+':9015/v/'+str(synanno.ng_version)+'/'})

    return final_json


def save_file(file: MultiDict, filename: str, path: str = os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER'])) -> str:
    ''' Saves the provided file at the specified location.

        Args:
            file: The file to be saved
            filename: The name of the file
            path: Path where to save the file

        Return:
            None if the provided file does not match one of the required extensions,
            else the full path where the file got saved.
    '''

    # defines the downstream task, set by the open-data view | 'draw', 'annotate'
    global draw_or_annotate

    file_ext = os.path.splitext(filename)[1]
    if file_ext not in app.config['UPLOAD_EXTENSIONS']:
        flash('Incorrect file format! Load again.', 'error')
        render_template('opendata.html', modenext='disabled',
                        mode=draw_or_annotate)
        return None
    else:
        file.save(os.path.join(path, filename))
        return (os.path.join(path, filename))
