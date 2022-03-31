# Importing the required libraries
import itertools
import numpy as np
from skimage.morphology import binary_dilation, remove_small_objects
from skimage.measure import label as label_cc 
from matplotlib import pyplot as plt
import cv2
import os, sys
import io
from util import bfly, rotateIm, readvol
import PIL
from PIL import Image
import json
import util
import base64
import h5py
from matplotlib.pyplot import imread, imsave
import shutil
from scipy.stats import linregress
from datetime import datetime

# Calculating the bounding boxes for every synpase in N-dimensions (3D as well as 2D)
def bbox2_ND(img):
    N = img.ndim
    out = []
    for ax in itertools.combinations(reversed(range(N)), N - 1):
        nonzero = np.any(img, axis=ax)
        try:
            out.extend(np.where(nonzero)[0][[0, -1]])
        except:
            continue
    return tuple(out)

# Reversing the rotation on synapses based on provided rotation info.
def reverse_rotation(syn_path, angle, pt_m):
    img_names = os.listdir(syn_path)
    
    for img in img_names:
        syn = plt.imread(os.path.join(syn_path,img))
        rot_syn = rotateIm(syn, -angle, tuple(pt_m))
        plt.imsave(os.path.join(syn_path,img), rot_syn)

# Processing the JSON file. (Used for synAnno.json)
def json_processor(json_path):
    # Opening JSON file
    with open(json_path) as json_file:
        f = json.load(json_file)

    items = dict()
    for j in f['Data']:
        items[j["Image_Index"]] = j
    
    return items

# Writing data to .h5 files.
def h5_writer(data,file_name,dataset_name):
    hf = h5py.File(file_name+'.h5', 'w')
    hf.create_dataset(dataset_name, data=data)
    hf.close()

def replace_crop(idx,seg,items,syn_path):
    
    syn_idx_path = os.path.join(syn_path,str(idx))
    
    item = items[idx]
    
    angle = item["Rotation_Info"][0]
    tup = tuple(item["Rotation_Info"][1])
    reverse_rotation(syn_idx_path,angle,tup)       # Reversing the rotation of every synapse before replacing.
    
    syn = (seg==idx)                          # Keeping only a specific synapse
    x = [int(o.strip('.png')) for o in os.listdir(syn_idx_path)]
    syn_min,syn_max = min(x),max(x)
    
    for syn_slice in range(syn_min,syn_max+1):      #Iterating through all slices in 3d volume
        syn_bbox_2d = item["Bounding_Boxes"][syn_slice-syn_min]                 #Calculating 2d bbox on the slice for locating synapse
        y1,y2 = syn_bbox_2d[0],syn_bbox_2d[1]
        x1,x2 = syn_bbox_2d[2],syn_bbox_2d[3]
        
        bbox_pad = item["Padding"][syn_slice-syn_min]      #Calculating the padding that is adding to 2d img for frontend display. Later used for user synapses.

        syn_2d_user = cv2.imread('./Images-1/Syn/'+str(idx)+'/'+str(syn_slice)+'.png',cv2.IMREAD_GRAYSCALE)
        syn_user_bbox = bbox2_ND(syn_2d_user)
        
        # Cropping the user synapse appropriately using bbox_pad
        y1o,y2o = max(syn_user_bbox[0]-bbox_pad[0],0), min(syn_user_bbox[1]+bbox_pad[1],syn_2d_user.shape[0])
        x1o,x2o = max(syn_user_bbox[2]-bbox_pad[2],0), min(syn_user_bbox[3]+bbox_pad[3],syn_2d_user.shape[1])
        
        syn_2d_img = seg[syn_slice][y1:y2,x1:x2]
        user_2d_img = syn_2d_user[y1o:y2o,x1o:x2o]
        
        # Replacing the existing mask with the updated one.
        try:
            seg[syn_slice][y1:y2,x1:x2]  = syn_2d_user[y1o:y2o,x1o:x2o]
        except:
            continue

    seg[syn>0] = idx      # Re-labelling the pixels with idx value to avoid conflict.
    return seg

# Iterating through the JSON file to check for annotated synapse(s) and update only them.
def processing(gt_file):
    
    syn = readvol(gt_file)
    json_path = './synAnno.json'
    items = json_processor(json_path)
    
    targets = []

    for o in items:
        item = items[o]
        if(item["Annotated"]=="Yes"):
            targets.append(int(item["Image_Index"]))

    for idx in targets:
        syn = replace_crop(idx,syn,items,syn_path='./Images/Syn')

    h5_writer(syn,'result_gt_'+str(datetime.now().strftime("%Y_%m_%d-%I_%M_%S_%p")),'main')
    os.remove('./seg.h5')
    
    return("Task completed!")
