# import global configs
import synanno

# import the package app
from synanno import app

# flask util functions
from flask import render_template, session, request, jsonify, flash

# flask ajax requests
from flask_cors import cross_origin

# retrieve list of all files with in a directory
import os

# track the annotation time
import datetime

# ajax json response
import json

# for type hinting
from jinja2 import Template
from typing import Dict

import synanno.backend.processing as ip


@app.route('/annotation/<int:page>')
@app.route('/annotation')
def annotation(page: int = 0) -> Template:
    ''' Start the proofreading timer and load the annotation view.

        Args:
            page: The current data page that is depicted in the grid view
            view_style: Identifies the view style: view | neuron

        Return:
            The annotation view
    '''

    if session["view_style"] == 'neuron':
    # check if the data for the current page is already loaded
        if session.get('data')[page] is None:
            # compute the data for the current page
            ip.visualize_cv_instances(session.get('patch_size'), session.get('path_json'), page)

            # update the session data
            session.get('data')[page] = None
        
            # open the json data and save it to the session
            f = open(session.get('path_json'))
            data = json.load(f)
            
            session['data'][page] = data[str(page)]
            

    # start the timer for the annotation process
    if synanno.proofread_time['start_grid'] is None:
        synanno.proofread_time['start_grid'] = datetime.datetime.now()

    return render_template('annotation.html', images=session.get('data')[page], page=page, n_pages=session.get('n_pages'), grid_opacity=synanno.grid_opacity, view_style=session["view_style"])


@app.route('/set_grid_opacity', methods=['POST'])
@cross_origin()
def set_grid_opacity() -> Dict[str, object]:
    ''' Serves and Ajax request from annotation.js updating the grid's opacity value

        Return:
            Passes a success confirmation to the frontend
    '''
    # retrieve the current opacity value, only keep first decimal
    synanno.grid_opacity = int(float(request.form['grid_opacity'])*10)/10
    # returning a JSON formatted response to trigger the ajax success logic
    return json.dumps({'success': True}), 200, {'ContentType': 'application/json'}


@app.route('/update-card', methods=['POST'])
@cross_origin()
def update_card() -> Dict[str, object]:
    ''' Updates the label of an instance. The labels switch from Correct, Incorrect to Unsure

        Return:
            Passes the updated label to the frontend
    '''
    # retrieve the passed frontend information
    page = int(request.form['page'])
    index = int(request.form['data_id'])-1
    label = request.form['label']

    # update the session data with the new label
    if (label == 'Incorrect'):
        session.get('data')[page][index]['Label'] = 'Unsure'
    elif (label == 'Unsure'):
        session.get('data')[page][index]['Label'] = 'Correct'
    elif (label == 'Correct'):
        session.get('data')[page][index]['Label'] = 'Incorrect'

    return jsonify({'result': 'success', 'label': session.get('data')[page][index]['Label']})


@app.route('/get_instance', methods=['POST'])
@cross_origin()
def save_slices() -> Dict[str, object]:
    ''' Serves one of two Ajax calls from annotation.js, passing instance specific information 

        Return:
            The instance specific data
    '''

    # retrieve the page and instance index
    mode = str(request.form['mode'])
    page = int(request.form['page'])
    index = int(request.form['data_id']) - 1

    # when first opening a instance modal view
    if mode == 'full':
        # calculating the number of slices
        slices_len = len(os.listdir(
            './synanno' + session.get('data')[page][index]['EM']+'/'))
        # calculating the center slice
        half_len = int(session.get('data')[page][index]['Middle_Slice'])

        # calculating the absolute lower bound z-value with in the image volume
        if (slices_len % 2 == 0):
            range_min = half_len - ((slices_len)//2) + 1
        else:
            range_min = half_len - (slices_len//2)

        final_json = jsonify(data=session.get('data')[page][index], slices_len=slices_len, halflen=half_len,
                             range_min=range_min, host=app.config['IP'], port=app.config['PORT'])

    # when changing the depicted slice with in the modal view
    elif mode == 'single':
        return jsonify(data=session.get('data')[page][index])

    return final_json
