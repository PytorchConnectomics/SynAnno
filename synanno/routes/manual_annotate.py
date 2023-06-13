# import global configs
import synanno

# import the package app
from synanno import app

# flask util functions
from flask import render_template, request, jsonify, session

# flask ajax requests
from flask_cors import cross_origin

# open, resize and transform images
from PIL import Image

# handle binary stream from base64 decoder
from io import BytesIO

# stack individual slices to an image volume
import numpy as np

# base64 decoder to convert canvas
import base64

# read and write JSON files
import json

# regular expression matching
import re

# manage paths and files
import os

# import processing functions
from synanno.backend.processing import crop_pad_data, create_dir
from synanno.backend.utils import NpEncoder

# reload the json and update the session data
import synanno.routes.utils.json_util as json_util

# for type hinting
from jinja2 import Template
from typing import Dict


@app.route('/draw')
def draw() -> Template:
    ''' Reload the updated JSON and render the draw view.
        Careful: The draw view can also be invoked via '/set-data/draw' - see opendata.py

        Return:
            Renders the draw view.
    '''

    # overwrite the session data if json has been changed
    if synanno.new_json:
        json_util.reload_json(path=os.path.join(os.path.join(
            app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), app.config['JSON']))
        synanno.new_json = False

    return render_template('draw.html', pages=session.get('data'))


@app.route('/save_canvas', methods=['POST'])
def save_canvas() -> Dict[str, object]:
    ''' Serves an Ajax request from draw.js, downloading, converting, and saving
        the canvas as image.

        Return:
            Passes the instance specific session information as JSON to draw.js
    '''

    # retrieve the canvas 
    image_data = re.sub('^data:image/.+;base64,', '',
                        request.form['imageBase64'])

    # retrieve the instance specifiers
    page = int(request.form['page'])
    index = int(request.form['data_id']) - 1

    # convert the canvas to PIL image format
    im = Image.open(BytesIO(base64.b64decode(image_data)))

    # adjust the size of the PIL Image in accordance with the session's path size 
    patch_size = session['patch_size']
    im = im.resize((patch_size, patch_size), Image.ANTIALIAS)

    # create folder where to save the image
    folder_path = os.path.join(os.path.join(
        app.root_path, app.config['STATIC_FOLDER']), 'custom_masks')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # retrieve the instance specific information for naming the image
    data = session.get('data')[page][index]
    coordinates = '_'.join(map(str, data['Adjusted_Bbox']))
    middle_slice = str(data['Middle_Slice'])
    img_index = str(data['Image_Index'])

    # image name
    img_name = 'idx_'+img_index + '_ms_' + middle_slice + '_cor_'+coordinates+'.png'

    # save the mask
    im.save(os.path.join(folder_path, img_name))

    # send the instance specific information to draw.js
    final_json = jsonify(data=data)

    return final_json


@app.route('/ng_bbox_fp', methods=['POST'])
@cross_origin()
def ng_bbox_fp()-> Dict[str, object]:
    ''' Serves an Ajax request by draw_module.js, passing the coordinates of the center point of a newly marked FP to the front end, 
        enabling the front end to depict the values and the user to manual update/correct them.

        Return:
            The x and y coordinates of the center of the newly added instance as well as the upper and the
            lower z bound of the instance as JSON to draw_module.js
    '''

    # expand the bb in in z direction
    # we expand the front and the back z value dependent on their proximity to the boarders
    cz1 = int(synanno.cz) - synanno.z_default if int(synanno.cz) - synanno.z_default > 0 else 0
    cz2 = int(synanno.cz) + synanno.z_default if int(synanno.cz) + \
        synanno.z_default < synanno.vol_dim_z else synanno.vol_dim_z

    # server the coordinates to the front end
    return jsonify({
        'z1': str(cz1),
        'z2': str(cz2),
        'my': str(synanno.cy),
        'mx': str(synanno.cx),
    })


@app.route('/ng_bbox_fp_save', methods=['POST'])
@cross_origin()
def ng_bbox_fp_save()-> Dict[str, object]:
    ''' Serves an Ajax request by draw_module.js, that passes the manual updated/corrected bb coordinates
        to this backend function. Additionally, the function creates a new item instance and 
        updates the json file.

        Return:
            The x and y coordinates of the center of the newly added instance as well as the upper and the
            lower z bound of the instance as JSON to draw_module.js
    '''

    # retrieve manual correction of coordinates
    cz1 = int(request.form['z1'])
    cz2 = int(request.form['z2'])
    synanno.cy = int(request.form['my'])
    synanno.cx = int(request.form['mx'])

    # log the coordinates center z, x, and y value and the expended z1 and z2 value
    synanno.cus_fp_bbs.append((synanno.cz, synanno.cy, synanno.cx, cz1, cz2))

    ## add the new instance to the the json und update the session data

    # open json and retrieve data
    path_json = os.path.join(os.path.join(
        app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), app.config['JSON'])
    item_list = json.load(open(path_json))['Data']

    # create new item
    item = dict()

    # index starts at one, adding item, therefore, incrementing by one
    item['Image_Index'] = len(item_list) + 1 + 1

    item['Label'] = 'Incorrect'
    item['Annotated'] = 'No'
    item['Error_Description'] = 'False Negatives'

    # use the marked slice incase that it is not sufficiently far awy enough from the boarder
    # - the true center might not depict the marked instance
    if int(synanno.cz) - synanno.z_default > 0 and int(synanno.cz) + synanno.z_default < synanno.vol_dim_z:
        item['Middle_Slice'] = str(int(cz1 + ((cz2-cz1) // 2)))
    else:
        item['Middle_Slice'] = str(int(synanno.cz))

    # define the bbox
    expand = session['patch_size'] // 2
    bb_x1 = int(synanno.cx) - expand if int(synanno.cx) - expand > 0 else 0
    bb_x2 = int(synanno.cx) + expand if int(synanno.cx) + \
        expand < synanno.vol_dim_x else synanno.vol_dim_x

    bb_y1 = int(synanno.cy) - expand if int(synanno.cy) - expand > 0 else 0
    bb_y2 = int(synanno.cy) + expand if int(synanno.cy) + \
        expand < synanno.vol_dim_y else synanno.vol_dim_y

    item['Original_Bbox'] = [cz1, cz2, bb_y1, bb_y2, bb_x1, bb_x2]
    item['cz0'] = item['Middle_Slice']
    item['cy0'] = int(synanno.cy)
    item['cx0'] = int(synanno.cx)
    item['Adjusted_Bbox'] = item['Original_Bbox']
    item['Padding'] = [[0, 0], [0, 0]]

    # crop out and save the relevant gt and im
    idx_dir = create_dir('./synanno/static/', 'Images')
    img_folder = create_dir(idx_dir, 'Img')
    img_all = create_dir(img_folder, str(item['Image_Index']))

    image_list = []
    crop_2d = item['Original_Bbox'][2:]
    for z_index in range(item['Original_Bbox'][0], item['Original_Bbox'][1]+1):
        cropped_img = crop_pad_data(synanno.source, z_index, crop_2d, pad_val=0)
        image_list.append(cropped_img)
    vis_image = np.stack(image_list, 0)

    # center slice of padded subvolume
    cs_dix = (vis_image.shape[0]-1)//2  # assumes even padding

    # overwrite cs incase that object close to boundary
    z_mid_total = item['Middle_Slice']
    cs = min(int(z_mid_total), cs_dix)

    # save volume slices
    for s in range(vis_image.shape[0]):
        img_name = str(int(z_mid_total)-cs+s)+'.png'

        # image
        img_c = Image.fromarray(vis_image[s, :, :])
        img_c.save(os.path.join(img_all, img_name), 'PNG')

    item['GT'] = 'None'  # do not save the GT as we do not have masks for the FPs
    item['EM'] = '/'+'/'.join(img_all.strip('.\\').split('/')[2:])
    item['Rotation_Angle'] = 0.0

    # add item to list
    item_list.append(item)

    # dump and save json
    final_file = dict()
    final_file['Data'] = item_list
    json_obj = json.dumps(final_file, indent=4, cls=NpEncoder)
    with open(os.path.join(os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER']), app.config['JSON']), 'w') as outfile:
        outfile.write(json_obj)

    # mark that json was updated
    synanno.new_json = True

    return jsonify({
        'z1': str(int(cz1)),
        'z2': str(int(cz2)),
        'my': str(int(synanno.cy)),
        'mx': str(int(synanno.cx))
    })
