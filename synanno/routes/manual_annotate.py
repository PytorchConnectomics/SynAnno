from flask import render_template, session, request, jsonify

from synanno import app

from PIL import Image
from io import BytesIO
import numpy as np
import base64
import json
import re
import os


@app.route('/draw')
def draw():
    return render_template('draw.html', pages=session.get('data'))

@app.route('/save_canvas', methods=['POST'])
def save_canvas():
    image_data = re.sub('^data:image/.+;base64,', '', request.form['imageBase64'])
    
    page = int(request.form['page'])
    index = int(request.form['data_id']) - 1

    im = Image.open(BytesIO(base64.b64decode(image_data)))

    patch_size = session['patch_size']
    im = im.resize((patch_size, patch_size), Image.ANTIALIAS)

    # create folder
    folder_path = os.path.join(os.path.join(app.root_path,app.config['STATIC_FOLDER']),'custom_masks')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)


    # retrieve relevant information
    data = session.get('data')
    coordinates = "_".join(map(str,data[page][index]['Adjusted_Bbox']))
    middle_slice = str(data[page][index]['Middle_Slice'])
    img_index =  str(data[page][index]['Image_Index'])

    img_name = 'idx_'+img_index +'_ms_'+ middle_slice +'_cor_'+coordinates+'.png'

    # save the mask
    im.save(os.path.join(folder_path, img_name))

    final_json = jsonify(data=data[page][index])

    return final_json