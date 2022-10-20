# import global configs
import synanno

# import the package app
from synanno import app

# flask util functions
from flask import render_template, session, request, jsonify

# flask ajax requests
from flask_cors import cross_origin

# update the json file
import json

# track the annotation time
import datetime

# for sleep to provide sufficient time for JSON updates
import time

# for joining paths
import os

# for type hinting
from jinja2 import Template 
from werkzeug.datastructures import MultiDict 


# global variable defining if instances marked as false positives are directly discarded
global delete_fp

delete_fp = False

@app.route('/categorize')
def categorize() -> Template:
    ''' Stop the annotation timer, start the categorization timer, and render the categorize view

        Return:
            Categorization view that enables the user the specify the fault of instance masks
            marked as "Incorrect" or "Unsure". 
    '''

    # stop the annotation timer
    if synanno.proofread_time['finish_grid'] is None:
        if synanno.proofread_time['start_grid'] is None:
            synanno.proofread_time['difference_grid'] = 'Non linear execution of the grid process - time invalid'
        else:
            synanno.proofread_time['finish_grid'] = datetime.datetime.now()
            synanno.proofread_time['difference_grid'] = synanno.proofread_time['finish_grid'] - synanno.proofread_time['start_grid']
    # start the categorization timer 
    if synanno.proofread_time['start_categorize'] is None:
        synanno.proofread_time['start_categorize'] = datetime.datetime.now()
    return render_template('categorize.html', pages=session.get('data'))


@app.route('/pass_flags', methods=['GET','POST'])
@cross_origin()
def pass_flags() -> dict[str, object]:
    ''' Serves an Ajax request from categorize.js, retrieving the new error tags from the
        frontend and updating the session information as well as the JSON.

        Return:
            Confirms the successful update to the frontend
    '''

    # variable specifying if instances marked as FP are discarded, the default is False
    global delete_fp 

    # retrieve the  frontend data
    flags = request.get_json()['flags']
    data = session.get('data')
    pages = len(data)

    # first update all flags and then delete the FP
    false_positives = {p:[] for p in range(0,pages)}

    # updated all flags
    for flag in flags:
        page_nr, img_nr, f = dict(flag).values()
        # deleting false positives
        if f == 'falsePositive' and delete_fp:
            false_positives[int(page_nr)].append(int(img_nr))
        else:
            data[int(page_nr)][int(img_nr)]['Error_Description'] = str(f)

    if delete_fp:
        # delete the FPs
        for p in range(0,pages):
            # sort the indexes that should be deleted
            # adjust them based on the # of images deleted and the page number
            false_positives[p] = [ (fp - i) for i, fp in enumerate(sorted(false_positives[p]))]
            for id in false_positives[p]:
                del data[p][id]

    # stop the time
    if synanno.proofread_time['finish_categorize'] is None:
        synanno.proofread_time['finish_categorize'] = datetime.datetime.now()
        synanno.proofread_time['difference_categorize'] = synanno.proofread_time['finish_categorize'] - synanno.proofread_time['start_categorize']
    
    # Exporting the final json and pop session
    if session.get('data') and session.get('n_pages'):
        final_file = dict()
        final_file['Data'] = sum(session['data'], [])
        final_file['Proofread Time'] = synanno.proofread_time
        with open(os.path.join(app.config['PACKAGE_NAME'],os.path.join(app.config['UPLOAD_FOLDER']),app.config['JSON']), 'w') as f:
            json.dump(final_file, f, default=json_serial)

        # provide sufficient time for the json update
        time.sleep(len(data)*0.2*session['per_page'])

        # pass the data to the session
        session['data'] = data

        # returning a JSON formatted response to trigger the ajax success logic
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 
    else:
        return json.dumps({'success':False}), 400, {'ContentType':'application/json'} 

@app.route('/custom_flag', methods=['GET','POST'])
@cross_origin()
def custom_flag() -> dict[str, object]:
    # used by frontend to retrieve custom error messages from the JSON
    page = request.get_json()['page']
    img_id = request.get_json()['img_id']
    data = session.get('data')
    return jsonify(message=data[int(page)][int(img_id)]['Error_Description'])

# handle non json serializable data 
def json_serial(obj):
    '''JSON serializer for objects not serializable by default json code
    '''

    if isinstance(obj, (datetime.timedelta)):
        return str(obj)
    if isinstance(obj, (datetime.datetime)):
        return obj.isoformat()
    raise TypeError ('Type %s not serializable' % type(obj))