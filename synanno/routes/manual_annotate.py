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

# base64 decoder to convert canvas
import base64

# regular expression matching
import re

# manage paths and files
import os

# import processing functions
from synanno.backend.processing import calculate_crop_pad, crop_pad_mask_data_3d, create_dir

# for type hinting
from jinja2 import Template
from typing import Dict

import json 

from cloudvolume import Bbox

import numpy as np

import pandas as pd

@app.route('/draw')
def draw() -> Template:
    ''' Reload the updated JSON and render the draw view.
        Careful: The draw view can also be invoked via '/set-data/draw' - see opendata.py

        Return:
            Renders the draw view.
    '''

    # retrieve the data from the dataframe for which the user has marked the instance as "Incorrect" or "Unsure"
    data = synanno.df_metadata[synanno.df_metadata['Label'].isin(['Incorrect', 'Unsure'])].to_dict('records')
    return render_template('draw.html', images=data, view_style=synanno.view_style)


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
    index = int(request.form['data_id']) 
    viewed_instance_slice = int(request.form['viewed_instance_slice'])

    # convert the canvas to PIL image format
    im = Image.open(BytesIO(base64.b64decode(image_data)))

    # adjust the size of the PIL Image in accordance with the session's path size 
    im = im.resize((session['crop_size_y'], session['crop_size_x']), Image.ANTIALIAS)

    # create folder where to save the image
    folder_path = os.path.join(os.path.join(
        app.root_path, app.config['STATIC_FOLDER']), 'custom_masks')
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # retrieve the instance specific information for naming the image

    data = synanno.df_metadata.query('Page == @page & Image_Index == @index').to_dict('records')[0]
    coordinates = '_'.join(map(str, data['Adjusted_Bbox']))
    img_index = str(data['Image_Index'])

    # image name
    img_name = 'idx_'+img_index + '_ms_' + str(viewed_instance_slice) + '_cor_'+coordinates+'.png'

    # save the mask
    im.save(os.path.join(folder_path, img_name))

    # send the instance specific information to draw.js
    data = json.dumps(data)
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
    cz1 = int(synanno.cz) - session['crop_size_z'] if int(synanno.cz) - session['crop_size_z'] > 0 else 0
    cz2 = int(synanno.cz) + session['crop_size_z'] if int(synanno.cz) + \
        session['crop_size_z'] < synanno.vol_dim_z else synanno.vol_dim_z

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
        updates the metadata dataframe.

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

    # create new item
    item = dict()

    # index starts at one, adding item, therefore, incrementing by one

    # calculate the number of pages needed for the instance count in the JSON
    item['Page'] = len(synanno.df_metadata) + 1 // session.get('per_page')
    if not (len(synanno.df_metadata) + 1 % session.get('per_page') == 0):
        item['Page'] = item['Page'] + 1

    item['Image_Index'] = len(synanno.df_metadata) + 1

    # crop out and save the relevant gt and im
    idx_dir = create_dir('./synanno/static/', 'Images')
    img_folder = create_dir(idx_dir, 'Img')
    img_all = create_dir(img_folder, str(item['Image_Index']))

    item['GT'] = 'None'  # do not save the GT as we do not have masks for the FPs
    item['EM'] = '/'+'/'.join(img_all.strip('.\\').split('/')[2:])
    
    item['Label'] = 'Incorrect'
    item['Annotated'] = 'No'
    item['Error_Description'] = 'False Negatives'

    # use the marked slice incase that it is not sufficiently far awy enough from the boarder
    # - the true center might not depict the marked instance
    if int(synanno.cz) - session['crop_size_z'] > 0 and int(synanno.cz) + session['crop_size_z'] < synanno.vol_dim_z:
        item['Middle_Slice'] = str(int(cz1 + ((cz2-cz1) // 2)))
    else:
        item['Middle_Slice'] = str(int(synanno.cz))
    
    item['cz0'] = item['Middle_Slice']
    item['cy0'] = int(synanno.cy)
    item['cx0'] = int(synanno.cx)

    # define the bbox
    expand_x = session['crop_size_x'] // 2
    expand_y = session['crop_size_y'] // 2
    bb_x1 = int(synanno.cx) - expand_x if int(synanno.cx) - expand_x > 0 else 0
    bb_x2 = int(synanno.cx) + expand_x if int(synanno.cx) + \
        expand_x < synanno.vol_dim_x else synanno.vol_dim_x

    bb_y1 = int(synanno.cy) - expand_y if int(synanno.cy) - expand_y > 0 else 0
    bb_y2 = int(synanno.cy) + expand_y if int(synanno.cy) + \
        expand_y < synanno.vol_dim_y else synanno.vol_dim_y

    item['crop_size_x'] = session['crop_size_x']
    item['crop_size_y'] = session['crop_size_y']
    item['crop_size_z'] = session['crop_size_z']
    
    item['Original_Bbox'] = [cz1, cz2, bb_y1, bb_y2, bb_x1, bb_x2]

    view_style = synanno.view_style

    if view_style == 'neuron':
        crop_bbox, img_padding = calculate_crop_pad(item["Original_Bbox"] , [synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x])
        # map the bounding box coordinates to a dictionary
        crop_box_dict = {
            'z1': crop_bbox[0],
            'z2': crop_bbox[1],
            'y1': crop_bbox[2],
            'y2': crop_bbox[3],
            'x1': crop_bbox[4],
            'x2': crop_bbox[5]
        }

        # retrieve the order of the coordinates (xyz, xzy, yxz, yzx, zxy, zyx)
        cord_order = list(synanno.coordinate_order.keys())

        # create the bounding box for the current synapse based on the order of the coordinates
        bound = Bbox(
            [
                crop_box_dict[cord_order[0] + '1'],
                crop_box_dict[cord_order[1] + '1'],
                crop_box_dict[cord_order[2] + '1']
            ],
            [
                crop_box_dict[cord_order[0] + '2'],
                crop_box_dict[cord_order[1] + '2'],
                crop_box_dict[cord_order[2] + '2']
            ]
        )

        # Convert coordinate resolution values to integers
        # Each coordinate resolution is a tuple where the first value is the resolution of the source image 
        # and the second value is the resolution of the target image 
        coord_resolution = [int(res[0]) for res in synanno.coordinate_order.values()]

        # Retrieve the source and target images from the cloud volume
        cropped_img = synanno.source_cv.download(bound, coord_resolution=coord_resolution, mip=0)

        # remove the singleton dimension, take care as the z dimension might be singleton
        cropped_img = cropped_img.squeeze(axis=3)

        # given the six cases xyz, xzy, yxz, yzx, zxy, zyx, we have to permute the axes to match the zyx order
        cropped_img = np.transpose(cropped_img, axes=[cord_order.index('z'), cord_order.index('y'), cord_order.index('x')])

        # pad the images and synapse segmentation to fit the crop size (sz)
        cropped_img = np.pad(cropped_img, img_padding, mode='constant', constant_values=148)

    elif view_style == 'view':
        cropped_img, crop_bbox, img_padding = crop_pad_mask_data_3d(synanno.source, item["Original_Bbox"])

    item["Adjusted_Bbox"] = [int(u) for u in crop_bbox]
    item["Padding"] = img_padding

    # save volume slices
    for s in range(cropped_img.shape[0]):
        img_name = str(item["Adjusted_Bbox"][0]+s)+'.png'

        # image
        img_c = Image.fromarray((cropped_img[s,:,:]* 255).astype(np.uint8))
        img_c.save(os.path.join(img_all, img_name), 'PNG')

    assert set(item.keys()) == set(synanno.df_metadata.columns), f"Difference: {set(item.keys()).symmetric_difference(set(synanno.df_metadata.columns))}"

    df_item = pd.DataFrame([item])
    synanno.df_metadata = pd.concat([synanno.df_metadata, df_item], ignore_index=True)

    return jsonify({
        'z1': str(int(cz1)),
        'z2': str(int(cz2)),
        'my': str(int(synanno.cy)),
        'mx': str(int(synanno.cx))
    })
