from flask import render_template, session, request, jsonify
from flask_cors import cross_origin


import synanno
from synanno import app

from PIL import Image
from io import BytesIO
import numpy as np
import base64
import json
import re
import os

# import processing functions
from synanno.backend.processing import crop_pad_data, create_dir
from synanno.backend.utils import NpEncoder

# import json util
import synanno.routes.utils.json_util as json_util


@app.route('/draw')
def draw():
    # careful: The draw view can also be invoked via "/set-data/draw" - see annotation.py 


    # overwrite data in session if json has been changed

    if synanno.new_json:
        json_util.reload_json(path=os.path.join('.', 'synAnno.json'))
        synanno.new_json = False


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

@app.route('/ng_bbox_fp', methods=['POST'])
@cross_origin()
def ng_bbox_fp():
    # retrive the coordinates

    cz1 = int(synanno.cz) - 10 if int(synanno.cz) - 10 > 0 else 0
    cz2 = int(synanno.cz) + 10 if int(synanno.cz) + 10 < synanno.vol_dim_z else synanno.vol_dim_z

    return jsonify({
                    'z1': str(cz1),
                    'z2': str(cz2),
                    'my': str(synanno.cy),
                    'mx': str(synanno.cx),
                    })


@app.route('/ng_bbox_fp_save', methods=['POST'])
@cross_origin()
def ng_bbox_fp_save():

    # retrieve manual correction of coordinates
    cz1 = int(request.form["z1"])
    cz2 = int(request.form["z2"])
    synanno.cy = int(request.form["my"])
    synanno.cx = int(request.form["mx"])

    # log the coordinates center z, x, and y value and the expended z1 and z2 value
    synanno.cus_fp_bbs.append((synanno.cz, synanno.cy, synanno.cx, cz1, cz2))

    # add to json

    ## open json and retrieve data
    filename_json = os.path.join('.', 'synAnno.json')
    item_list = json.load(open(filename_json))["Data"]

    ## create new item
    item = dict()
    item["Image_Index"] = len(item_list) + 1 + 1 # index starts at one, increment by one
    
    item["Label"] = "Incorrect"
    item["Annotated"] = "No"            
    item["Error_Description"] = "False Negatives"

    # use the marked slice incase that it is not sufficently far awy enough from the boarder
    # - the true center might not depict the marked instance
    if int(synanno.cz) - 10 > 0 and int(synanno.cz) + 10 < synanno.vol_dim_z:
        item["Middle_Slice"] = str(int(cz1 + ((cz2-cz1) // 2)))
    else:
        item["Middle_Slice"] = str(int(synanno.cz))

    ### define the bbox

    bb_x1 = int(synanno.cx) - 100 if int(synanno.cx) - 100 > 0 else 0
    bb_x2 = int(synanno.cx) + 100 if int(synanno.cx) + 100 < synanno.vol_dim_x else synanno.vol_dim_x
    
    bb_y1 = int(synanno.cy) - 100 if int(synanno.cy) - 100 > 0 else 0
    bb_y2 = int(synanno.cy) + 100 if int(synanno.cy) + 100 < synanno.vol_dim_y else synanno.vol_dim_y

    item["Original_Bbox"] = [cz1, cz2, bb_y1, bb_y2, bb_x1, bb_x2]
    item["cz0"] = item["Middle_Slice"]
    item["cy0"] = int(synanno.cy)
    item["cx0"] = int(synanno.cx)
    item["Adjusted_Bbox"] = item["Original_Bbox"]
    item["Padding"] = [[0, 0], [0, 0]]

    ### crop out and save the relevant gt and im
    

    idx_dir = create_dir('./synanno/static/', 'Images')
    img_folder = create_dir(idx_dir, 'Img')
    img_all = create_dir(img_folder, str(item["Image_Index"]))

    image_list = []
    crop_2d = item["Original_Bbox"][2:]
    for z_index in range(item["Original_Bbox"][0], item["Original_Bbox"][1]+1):
        cropped_img = crop_pad_data(synanno.im, z_index, crop_2d, pad_val=0)
        image_list.append(cropped_img)
    vis_image = np.stack(image_list, 0)

    # center slice of padded subvolume
    cs_dix = (vis_image.shape[0]-1)//2 # assumes even padding

    # overwrite cs incase that object close to boundary
    z_mid_total = item["Middle_Slice"]
    cs = min(int(z_mid_total), cs_dix)

    # save volume slices
    for s in range(vis_image.shape[0]):
        img_name = str(int(z_mid_total)-cs+s)+".png"

        # image
        img_c = Image.fromarray(vis_image[s,:,:])
        img_c.save(os.path.join(img_all,img_name), "PNG")

    item["GT"] = "None" # do not save the GT as we do not have masks for the FPs
    item["EM"] = "/"+"/".join(img_all.strip(".\\").split("/")[2:])
    item["Rotation_Angle"] = 0.0

    
    ## add item to list
    item_list.append(item)


    ## dump and save json
    final_file = dict()
    final_file["Data"] = item_list
    json_obj = json.dumps(final_file, indent=4, cls=NpEncoder)
    with open("synAnno.json", "w") as outfile:
        outfile.write(json_obj)

    # mark that json was updated
    synanno.new_json = True

    return jsonify({
                    'z1': str(int(cz1)),
                    'z2': str(int(cz2)),
                    'my': str(int(synanno.cy)), 
                    'mx': str(int(synanno.cx))
                    })