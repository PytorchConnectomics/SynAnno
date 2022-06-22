# flask 
from flask import render_template, session, flash, jsonify, request
from flask_cors import cross_origin

# os and process dependent imports
import os
import os.path

# import the package app 
from synanno import app

# for access to the timing variable
import synanno
import datetime

# json dependent imports
import json

global grid_opacity
grid_opacity = 0.5

@app.route('/set-data/<task>/<data_name>')
@app.route('/set-data/<data_name>')
@app.route('/set-data')
def set_data(task='annotate',data_name='synAnno.json'):
    global grid_opacity

    # set the number of cards in one page
    per_page = 18
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

    if task == 'annotate':
        return render_template('annotation.html', images=session.get('data')[0], page=0, n_pages=session.get('n_pages'), grid_opacity=grid_opacity)
    elif task == 'draw':
        return render_template('draw.html', pages=session.get('data'))

@app.route('/annotation')
@app.route('/annotation/<int:page>')
def annotation(page=0):
    global grid_opacity
    if synanno.proofread_time["start_grid"] is None:
        synanno.proofread_time["start_grid"] = datetime.datetime.now()
    return render_template('annotation.html', images=session.get('data')[page], page=page, n_pages=session.get('n_pages'), grid_opacity=grid_opacity)

@app.route('/set_grid_opacity', methods=['POST'])
@cross_origin()
def set_grid_opacity():
    global grid_opacity
    grid_opacity = float(request.form['grid_opacity'])
    grid_opacity = int(grid_opacity*10)/10 # only keep first decimal
    # returning a JSON formatted response to trigger the ajax success logic
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 


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
    slices_len = len(os.listdir('./synanno'+ data[page][index]['EM']+'/'))
    half_len = int(data[page][index]['Middle_Slice'])

    if(slices_len % 2 == 0):
        range_min = half_len - ((slices_len)//2) + 1
    else:
        range_min = half_len - (slices_len//2)

    final_json = jsonify(data=data[page][index], slices_len=slices_len, halflen=half_len,
                         range_min=range_min, host=app.config['IP'], port=app.config['PORT'])

    return final_json