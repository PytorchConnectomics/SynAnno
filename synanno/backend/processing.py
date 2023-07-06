'''
*********   Project: SynAnno for synapse annnotation in EM volumes   ********

Directory structure:
.
|__Images
|__Syn;                                         |__Img;       
  |__ Directories named as synapse indexes        |__Directories named as synapse indexes   
    |_label.tif                                     |_image.tif

Metadata JSON file structure:
{
    "Data": [
        {
            "Image_Index": 1,           # synapse index (int)
            "GT": ".\Images\Syn\1",     # folder containing GT images.
            "EM": ".\Images\Img\1",     # folder containing EM images.
            "Correct": "Yes",           # default
            "Annotated": "No",          # default
            "Middle_Slice": 7,          # middle slice of the 3D volume containing synapse
            "Rotation_Info": 67.0       # rotation_angle
            "Original_Bbox": []         # original bounding box
            "Adjusted_Bbox": []         # adjust boundind box based on crop size    
            "Padding": []               # padding size for y and x axes
        },
        *** Similarly for all other synapses ***
    ]
}
'''
from typing import Union, Tuple, Dict
from collections import OrderedDict

import os
import json
import errno
import warnings
import itertools
import numpy as np
from PIL import Image
from scipy import stats
from skimage.morphology import binary_dilation, remove_small_objects
from skimage.measure import label as label_cc
from scipy.ndimage import find_objects

from .utils import *


import synanno # import global configs
from synanno import app # import the package app

from cloudvolume import CloudVolume, Bbox
import pandas as pd

from flask import session

def process_syn(gt: np.ndarray, small_thres: int = 16, view_style: str ='view') -> Tuple[np.ndarray, np.ndarray]:
    """ Convert the semantic segmentation to instance-level segmentation on pre/post synaptic level and synapse level.

    Args:
        gt (np.ndarray): the semantic or instance-level segmentation.
        small_thres (int): the threshold for removing small objects.

    Returns:
        syn (np.ndarray): the instance-level segmentation where each pre and post synaptic region is labeled with an individual index.
        seg (np.ndarray): the instance-level segmentation where each synapse is labeled with an individual index.
        view_style (str): the view style for the dataset: 'view' or 'neuron'
    """
    indices = np.unique(gt)
    is_semantic = len(indices) == 3 and (indices==[0,1,2]).all()
    if not is_semantic: # already an instance-level segmentation
        # merge the pre- and post-synaptic index into a single index for each synapse
        syn, seg = gt, (gt.copy() + 1) // 2
        return syn, seg

    # convert the semantic segmentation to instance-level segmentation
    with warnings.catch_warnings():
        # create the synapse based instance segmentation
        warnings.simplefilter("ignore", category=UserWarning)
        seg = binary_dilation(gt.copy() != 0)
        if view_style == 'view':
            synanno.progress_bar_status['percent'] = int(8) 

        seg = label_cc(seg).astype(int)
        seg = seg * (gt.copy() != 0).astype(int)
        seg = remove_small_objects(seg, small_thres)
        if view_style == 'view':
            synanno.progress_bar_status['percent'] = int(12) 

        # create the pre- and post-synaptic based instance segmentation
        c2 = (gt.copy() == 2).astype(int)
        c1 = (gt.copy() == 1).astype(int)

        syn_pos = np.clip((seg * 2 - 1), a_min=0, a_max=None) * c1
        syn_neg = (seg * 2) * c2
        syn = np.maximum(syn_pos, syn_neg)
        if view_style == 'view':
            synanno.progress_bar_status['percent'] = int(15) 
    return syn, seg


def bbox_ND(img: np.ndarray) -> tuple:
    """Calculate the bounding box coordinates of a N-dimensional array.

    Args:
        img (np.ndarray): the N-dimensional array.

    Returns:
        bbox (tuple): the bounding box coordinates.
    """

    N = img.ndim
    out = []
    for ax in itertools.combinations(reversed(range(N)), N - 1):
        nonzero = np.any(img, axis=ax)
        out.extend(np.where(nonzero)[0][[0, -1]])
    return tuple(out)

def crop_ND(img: np.ndarray, coord: Tuple[int], 
            end_included: bool = False) -> np.ndarray:
    """Crop a chunk from a N-dimensional array based on the 
    bounding box coordinates.

    Args:
        img (np.ndarray): the N-dimensional array.
        coord (tuple): the bounding box coordinates.
        end_included (bool): whether the end coordinates are included.

    Returns:
        cropped (np.ndarray): the cropped chunk.
    """
    N = img.ndim
    assert len(coord) == N * 2
    slicing = []
    for i in range(N):
        start = coord[2*i]
        end = coord[2*i+1] + 1 if end_included else coord[2*i+1]
        slicing.append(slice(start, end))
    slicing = tuple(slicing)
    return img[slicing].copy()

def adjust_bbox(low: int, high: int, sz: int) -> Tuple[int]:
    """Adjust the bounding box coordinates to a given size.

    Args:
        low (int): the lower bound of the bounding box.
        high (int): the upper bound of the bounding box.
        sz (int): the size of the bounding box.

    Returns:
        low (int): the adjusted lower bound of the bounding box.
        high (int): the adjusted upper bound of the bounding box.
    """
    assert high >= low
    bbox_sz = high - low
    diff = abs(sz - bbox_sz) // 2
    if bbox_sz >= sz:
        return low + diff, low + diff + sz

    return low - diff, low - diff + sz

def bounds_2exp(cord: int, exp: int) -> Tuple[int]:
    """ Calculate the lower and upper bounds of the bounding box based on a given coordinate and multiple of 2.
    
    Args:
        cord (int): the coordinate.
        exp (int): the multiple of 2.

    Returns:
        low (int): the lower bound of the bounding box.
        high (int): the upper bound of the bounding box.
    """
    low = cord - (cord % exp)
    high = low + exp
    return low, high

def bbox_relax(coord: Union[tuple, list], 
               shape: tuple, 
               relax: int = 0) -> tuple:
    """Relax the bounding box coordinates by a given value.

    Args:
        coord (tuple): the bounding box coordinates.
        shape (tuple): the shape of the image.
        relax (int): the relaxation size for the bounding box.

    Returns:
        coord (tuple): the relaxed bounding box coordinates.
    """
    assert len(coord) == len(shape) * 2
    coord = list(coord)
    for i in range(len(shape)):
        coord[2*i] = max(0, coord[2*i]-relax)
        coord[2*i+1] = min(shape[i], coord[2*i+1]+relax)

    return tuple(coord)


def index2bbox(seg: np.ndarray, indices: list, relax: int = 0,
               iterative: bool = False) -> dict:
    """Calculate the bounding boxes associated with the given mask indices. 
    For a small number of indices, the iterative approach may be preferred.
    Note:
        Since labels with value 0 are ignored in ``scipy.ndimage.find_objects``,
        the first tuple in the output list is associated with label index 1. 

    Args:
        seg (np.ndarray): the binary mask of the segmentation.
        indices (list): the list of indices.
        relax (int): the relaxation size for the bounding box.
        iterative (bool): whether to use iterative approach to calculate bounding boxes.

    Returns:
        bbox_dict (dict): the dictionary of bounding boxes.
    """
    bbox_dict = OrderedDict()

    if iterative:
        # calculate the bounding boxes of each segment iteratively
        for idx in indices:
            temp = (seg == idx) # binary mask of the current seg
            bbox = bbox_ND(temp, relax=relax)
            bbox_dict[idx] = bbox
        return bbox_dict

    # calculate the bounding boxes using scipy.ndimage.find_objects
    loc = find_objects(seg)
    seg_shape = seg.shape
    for idx, item in enumerate(loc):
        if item is None:
            # For scipy.ndimage.find_objects, if a number is 
            # missing, None is returned instead of a slice.
            continue

        object_idx = idx + 1 # 0 is ignored in find_objects
        if object_idx not in indices:
            continue

        bbox = []
        for x in item: # slice() object
            bbox.append(x.start)
            bbox.append(x.stop-1) # bbox is inclusive by definition
        bbox_dict[object_idx] = bbox_relax(bbox, seg_shape, relax)
    return bbox_dict

def crop_pad_data(data: np.ndarray, z: int, bbox_2d: list, pad_val: int = 0, mask: np.ndarray = None, return_box: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, list, tuple]]:
    ''' Crop a 2D patch from 3D volume.

    Args:   
        data (np.ndarray): the 3D volume.
        z (int): the z index of the 2D patch.   
        bbox_2d (list): the bounding box of the 2D patch.
        pad_val (int): the value used for padding.
        mask (np.ndarray): the binary mask of the synapse.
        return_box (bool): whether to return the bounding box.

    Returns:
        cropped (np.ndarray): the cropped 2D patch.
        [y1, y2, x1, x2] (list): the bounding box of the 2D patch.
        pad (tuple): the padding size for y and x axes.
    '''
    sz = data.shape[1:]
    y1o, y2o, x1o, x2o = bbox_2d  # region to crop
    y1m, y2m, x1m, x2m = 0, sz[0], 0, sz[1]
    y1, x1 = max(y1o, y1m), max(x1o, x1m)
    y2, x2 = min(y2o, y2m), min(x2o, x2m)
    cropped = data[z, y1:y2, x1:x2]

    if mask is not None:
        mask_2d = mask[z, y1:y2, x1:x2]
        cropped = cropped * (mask_2d != 0).astype(cropped.dtype)

    pad = ((y1 - y1o, y2o - y2), (x1 - x1o, x2o - x2))
    if not all(v == 0 for v in pad):
        cropped = np.pad(cropped, pad, mode='constant',
                         constant_values=pad_val)

    if not return_box:
        return cropped

    return cropped, [y1, y2, x1, x2], pad

def crop_pad_cloud_volume(vs, bbox_3d: list) -> Union[np.ndarray, Tuple[np.ndarray, list, tuple]]:
    ''' Crop a 3D patch from 3D volume.

    Args:   
        vs (list): the size of the 3D volume.
        bbox_3d (list): the bounding box of the 3D patch.

    Returns:
        [z1, z2, y1, y2, x1, x2] (list): the bounding box of the 3D patch.
        pad (tuple): the padding size for y and x axes.
    '''
    z1o, z2o, y1o, y2o, x1o, x2o = bbox_3d  # region to crop
    z1m, z2m, y1m, y2m, x1m, x2m = 0, vs[0], 0, vs[1], 0, vs[2]
    z1, y1, x1 = max(z1o, z1m), max(y1o, y1m), max(x1o, x1m)
    z2, y2, x2 = min(z2o, z2m), min(y2o, y2m), min(x2o, x2m)

    pad = ((z1 - z1o, z2o - z2), (y1 - y1o, y2o - y2), (x1 - x1o, x2o - x2))

    return [z1, z2, y1, y2, x1, x2], pad



def syn2rgb(label: np.ndarray) -> np.ndarray:
    ''' Convert the binary mask of the synapse to RGB format.
    
    Args:
        label (np.ndarray): the binary mask of the synapse.
        
    Returns:
        out (np.ndarray): the RGB mask of the synapse.
    '''
    tmp = [None] * 3
    tmp[0] = np.logical_and((label % 2) == 1, label > 0)
    tmp[1] = np.logical_and((label % 2) == 0, label > 0)
    tmp[2] = (label > 0)
    out = np.stack(tmp, -1).astype(np.uint8) # shape is (*, 3)
    return out * 255


def create_dir(parent_dir_path: str, dir_name: str) -> str:
    ''' Create a directory if it does not exist.
    
    Args:
        parent_dir_path (str): the path to the parent directory.
        dir_name (str): the name of the directory.
        
    '''
    dir_path = os.path.join(parent_dir_path, dir_name)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    return dir_path


def calculate_rot(syn: np.ndarray, struct_sz: int = 3, return_overlap: bool = False, mode: str = 'linear') -> Union[float, np.ndarray]:
    ''' Calculate the rotation angle to align masks with different orientations.

    Args:
        syn (np.ndarray): the binary mask of the synapse.
        struct_sz (int): the size of the structuring element used in dilation.
        return_overlap (bool): whether to return the overlap mask.
        mode (str): the mode used in regression.

    Returns:
        angle (float): the rotation angle.
        slope (float): the slope of the regression line.
    '''

    assert mode in ['linear', 'siegel', 'theil']
    struct = np.ones((struct_sz, struct_sz), np.uint8)
    pos = binary_dilation(np.logical_and((syn % 2) == 1, syn > 0), struct)
    neg = binary_dilation(np.logical_and((syn % 2) == 0, syn > 0), struct)
    overlap = pos.astype(np.uint8) * neg.astype(np.uint8)
    if overlap.sum() <= 20: # (almost) no overlap
        overlap = (syn!=0).astype(np.uint8)

    pt = np.where(overlap != 0)
    if len(np.unique(pt[0]))==1: # only contains one value
        angle, slope = 90, 1e6 # approximation of infty
        if return_overlap:
            return angle, slope, overlap

        return angle, slope

    if mode == 'linear':
        slope, _, _, _, _ = stats.linregress(pt[0], pt[1])
    elif mode == 'siegel':
        slope, _ = stats.siegelslopes(pt[1], pt[0])
    elif mode == 'theil':
        slope, _, _, _ = stats.theilslopes(pt[1], pt[0])
    else:
        raise ValueError("Unknown mode %s in regression." % mode)
        
    angle = np.arctan(slope) / np.pi * 180
    if return_overlap:
        return angle, slope, overlap
    
    return angle, slope


def visualize(syn: np.ndarray, seg: np.ndarray, img: np.ndarray, sz: int, return_data: bool = False, iterative_bbox: bool = False, path_json: str = None) -> Union[str, None]:
    ''' Visualize the synapse and EM images in 2D slices.
    
    Args:
        syn (np.ndarray): instance-level segmentation where each pre and post synaptic region is labeled with an individual index.
        seg (np.ndarray): instance-level segmentation where each synapse is labeled with an individual index.
        img (np.ndarray): the original EM image.
        sz (int): the size of the 2D patch.
        return_data (bool): whether to return the data.
        iterative_bbox (bool): whether to use iterative approach to calculate bounding boxes.
        path_json (str): the path to the JSON file.
        
    Returns:
        synanno_json (str): the path to the JSON file.
    '''

    # calculate the bounding boxes of each synapse
    crop_size = int(sz * 1.415) # considering rotation 

    # list of json objects representing the synapses (ids, middle slices, bounding boxes, etc.)
    json_objects_list = []
    
    # dictionary of synapse ids and their corresponding processed source and target images
    data_dict = {}

    # specify the list we iterate over (index list or json)
    if path_json is not None:
        json_objects_list = json.load(open(path_json))["Data"]
    else:
        # retrieve the instance level segmentation indices
        seg_idx = np.unique(seg)[1:] # ignore background
        if not iterative_bbox:
            # calculate the bounding boxes of each segment based on scipy.ndimage.find_objects
            bbox_dict = index2bbox(seg, seg_idx, iterative=False)


    # derive list for loop enumeration (json or index list)
    instance_list = []
    if path_json is not None:
        instance_list = json_objects_list
    else:
        instance_list = seg_idx

    
    # create the directories for saving the source and target images
    idx_dir = create_dir('./synanno/static/', 'Images')
    syn_folder, img_folder = create_dir(idx_dir, 'Syn'), create_dir(idx_dir, 'Img')

    # calculate process time for progess bar
    len_instances = len(instance_list)
    perc = (100)/len_instances 

    # iterate over the synapses. save the middle slices and before/after ones for navigation.
    for i, inst in enumerate(instance_list):

        # retrieve the index of the current synapse from the json file, else use the index from the list
        if path_json is not None:
            idx = inst["Image_Index"]
        else:
            idx = inst

        # create the instance specific directories for saving the source and target images
        syn_all, img_all = create_dir(syn_folder, str(idx)), create_dir(img_folder, str(idx))

        # create the binary mask of the current synapse based on the index
        temp = (seg == idx)

        # create a new item for the JSON file with defaults.
        if path_json is None:
            # create a new item for the JSON file with defaults.
            item = dict()
            item["Image_Index"] = int(idx)
            item["GT"] = "/"+"/".join(syn_all.strip(".\\").split("/")[2:])
            item["EM"] = "/"+"/".join(img_all.strip(".\\").split("/")[2:])
            item["Label"] = "Correct"
            item["Annotated"] = "No"            
            item["Error_Description"] = "None"
        
            # either retrieve the bounding box from the previous iterative generated bb dict or calculate it on individual basis
            bbox = bbox_ND(temp) if iterative_bbox else bbox_dict[idx]
                    
            # find the most view_style slice that contains foreground
            temp_crop = crop_ND(temp, bbox, end_included=True)
            crop_mid = (temp_crop.shape[0]-1) // 2
            idx_t = np.where(np.any(temp_crop, axis=(1,2)))[0] # index of slices containing True values
            z_mid_relative = idx_t[np.argmin(np.abs(idx_t-crop_mid))]
            z_mid_total = z_mid_relative + bbox[0]

            # update the json item with the middle slice and original bounding box
            item["Middle_Slice"] = str(z_mid_total)
            item["Original_Bbox"] = [int(u) for u in list(bbox)]
            item["cz0"] = item["Middle_Slice"]
            item["cy0"] = (item["Original_Bbox"][2] + item["Original_Bbox"][3])//2 
            item["cx0"] = (item["Original_Bbox"][4] + item["Original_Bbox"][5])//2
        

            temp_2d = temp[z_mid_total]
            bbox_2d = bbox_ND(temp_2d)    

            y1, y2 = adjust_bbox(bbox_2d[0], bbox_2d[1], crop_size)
            x1, x2 = adjust_bbox(bbox_2d[2], bbox_2d[3], crop_size)
            crop_2d = [y1, y2, x1, x2]

            cropped_syn, syn_bbox, padding = crop_pad_data(syn, z_mid_total, crop_2d, mask=temp, return_box=True)
            cropped_img = crop_pad_data(img, z_mid_total, crop_2d, pad_val=128)

            # calculate the padding for frontend display, later used for unpadding
            item["Adjusted_Bbox"] = [bbox[0], bbox[1]] + syn_bbox

            item["Padding"] = padding

            # calculate and save the angle of rotation
            angle, _ = calculate_rot(cropped_syn, return_overlap=False, mode='linear')

            img_dtype, syn_dtype = cropped_img.dtype, cropped_syn.dtype
            rotate_img_zmid, rotate_syn_zmid, angle = rotateIm_polarity(
                cropped_img.astype(np.float32), cropped_syn.astype(np.float32), -angle)
            rotate_img_zmid = center_crop(rotate_img_zmid.astype(img_dtype), sz)
            rotate_syn_zmid = center_crop(rotate_syn_zmid.astype(syn_dtype), sz)

            item["Rotation_Angle"] = angle
            json_objects_list.append(item)
        else:
            temp = (seg == idx) # binary mask of the current synapse
            bbox = list(map(int,inst["Original_Bbox"]))
            z_mid_total = int(inst["Middle_Slice"])
            angle = float(inst["Rotation_Angle"])

            temp_2d = temp[z_mid_total]
            bbox_2d = bbox_ND(temp_2d)    

            y1, y2 = adjust_bbox(bbox_2d[0], bbox_2d[1], crop_size)
            x1, x2 = adjust_bbox(bbox_2d[2], bbox_2d[3], crop_size)
            crop_2d = [y1, y2, x1, x2]

            cropped_syn, syn_bbox, padding = crop_pad_data(syn, z_mid_total, crop_2d, mask=temp, return_box=True)
            cropped_img = crop_pad_data(img, z_mid_total, crop_2d, pad_val=128)

            img_dtype, syn_dtype = cropped_img.dtype, cropped_syn.dtype
            rotate_img_zmid, rotate_syn_zmid, angle = rotateIm_polarity(
                cropped_img.astype(np.float32), cropped_syn.astype(np.float32), -angle)
            rotate_img_zmid = center_crop(rotate_img_zmid.astype(img_dtype), sz)
            rotate_syn_zmid = center_crop(rotate_syn_zmid.astype(syn_dtype), sz)

        image_list, label_list = [], []
        for z_index in range(bbox[0], bbox[1]+1):
            if z_index == z_mid_total:
                image_list.append(rotate_img_zmid)
                label_list.append(rotate_syn_zmid)
                continue

            cropped_syn = crop_pad_data(syn, z_index, crop_2d, mask=temp)
            cropped_img = crop_pad_data(img, z_index, crop_2d, pad_val=128)
            rotate_img = rotateIm(cropped_img.astype(np.float32), angle, target_type='img')
            rotate_syn = rotateIm(cropped_syn.astype(np.float32), angle, target_type='mask')

            image_list.append(center_crop(rotate_img.astype(img_dtype), sz))
            label_list.append(center_crop(rotate_syn.astype(img_dtype), sz))

        vis_image = np.stack(image_list, 0)
        vis_label = syn2rgb(np.stack(label_list, 0)) # z, y, x, c

        data_dict[idx] = [vis_image, vis_label]

        if not return_data:
            # center slice of padded subvolume
            cs_dix = (vis_image.shape[0]-1)//2 # assumes even padding

            # overwrite cs incase that object close to boundary
            cs = min(int(z_mid_total), cs_dix)

            # save volume slices
            for s in range(vis_image.shape[0]):
                img_name = str(int(z_mid_total)-cs+s)+".png"

                # image
                img_c = Image.fromarray(vis_image[s,:,:])
                img_c.save(os.path.join(img_all,img_name), "PNG")

                # label
                lab_c = Image.fromarray(vis_label[s,:,:,:])

                # reduce the opacity of all black pixels to zero
                lab_c = lab_c.convert("RGBA")

                lab_c = np.asarray(lab_c) 
                r, g, b, a = np.rollaxis(lab_c, axis=-1) # split into 4 n x m arrays 
                r_m = r != 0 # binary mask for red channel, True for all non black values
                g_m = g != 0 # binary mask for green channel, True for all non black values
                b_m = b != 0 # binary mask for blue channel, True for all non black values

                # combine the three binary masks by multiplying them (1*1=1, 1*0=0, 0*1=0, 0*0=0)
                # multiply the combined binary mask with the alpha channel
                a = a * ((r_m == 1) | (g_m == 1) | (b_m == 1))

                lab_c = Image.fromarray(np.dstack([r, g, b, a]), 'RGBA') # stack the img back together 

                lab_c.save(os.path.join(syn_all,img_name), "PNG")

                # update progress bar
                synanno.progress_bar_status['percent'] = min(int(i * perc) + 15, 100)

    if return_data:
        return data_dict

    # create and export the JSON File
    if path_json is None:
        final_file = dict()
        final_file["Data"] = json_objects_list
        json_obj = json.dumps(final_file, indent=4, cls=NpEncoder)

        path_json = os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER'])
        name_json = app.config['JSON']

        with open(os.path.join(path_json, name_json), "w") as outfile:
            outfile.write(json_obj)

        synanno_json = os.path.join(path_json, name_json)
        return synanno_json
    else:
        return


def visualize_cv_instances(crop_size: int, path_json: str = None, page: int =0, bbox_exists=False) -> Union[str, None]:
    ''' Visualize the synapse and EM images in 2D slices for each instance by cropping the bounding box of the instance.
        Processing each instance individually, retrieving them from the cloud volume and saving them to the local disk.
    
    Args:
        sz (int): the size of the 2D patch.
        path_json (str): the path to the JSON file.
        page (int): the current page number for which to compute the data.
        bbox_exists (bool): whether the bounding box is already calculated, else retrieve it from the central synapse coordinates.
        
    Returns:
        synanno_json (str): the path to the JSON file.
    '''

    # set the progress bar to zero
    if page != 0:
        synanno.progress_bar_status['percent'] = 0
        synanno.progress_bar_status['status'] = f"Loading page {str(page)}."

    json_page_entry = False

    # specify the list we iterate over (index list or json)
    if path_json is not None:
        json_objects_list = json.load(open(path_json))
        print(json_objects_list)
        # if int key is in dict, retrieve the page entry
        if str(page) in json_objects_list.keys():
            json_page_entry = True
        else:
            json_objects_list[str(page)] = []
    else:
        # list of json objects representing the synapses (ids, middle slices, bounding boxes, etc.)
        json_objects_list = {str(page): []}

    # create the directories for saving the source and target images
    idx_dir = create_dir('./synanno/static/', 'Images')
    syn_folder, img_folder = create_dir(idx_dir, 'Syn'), create_dir(idx_dir, 'Img')

    # retrieve the synapse coordinates for the current page
    bbox_dict = get_sub_dict_within_range(session.get('materialization'), 1 + (page * session['per_page']), session['per_page'] + (page * session['per_page']))

    # iterate over the synapses. save the middle slices and before/after ones for navigation.
    for i, inst in enumerate(bbox_dict.keys() if json_page_entry is False else json_objects_list[str(page)]):
        # retrieve the index of the current synapse from the json file, else use the index from the list
        if json_page_entry is True:
            idx = inst["Image_Index"] % session.get('per_page')
        else:
            idx = inst
        synanno.progress_bar_status['status'] = f"Inst.{str(idx)}: Calculate bounding box."

        # create the instance specific directories for saving the source and target images
        syn_all, img_all = create_dir(syn_folder, str(idx)), create_dir(img_folder, str(idx))

        # create a new item for the JSON file with defaults.
        if json_page_entry is False:
            # retrieve the bounding box for the current synapse
            if bbox_exists:
                bbox = bbox_dict[idx]
            else:
                bbox = [int(bbox_dict[idx]['z']), int(bbox_dict[idx]['z']), int(bbox_dict[idx]['y']), int(bbox_dict[idx]['y']), int(bbox_dict[idx]['x']), int(bbox_dict[idx]['x'])]
            
            # calculate the middle slice (relative to the whole volume)
            # TODO: currently does not check if the center slice contains foreground
            z_mid_total = bbox[0] + (bbox[1] - bbox[0])//2

            # create a new item for the JSON file with defaults.
            item = dict()
            item["Image_Index"] = int(idx) + session.get('per_page') * page
            item["GT"] = "/"+"/".join(syn_all.strip(".\\").split("/")[2:])
            item["EM"] = "/"+"/".join(img_all.strip(".\\").split("/")[2:])
            item["Label"] = "Correct"
            item["Annotated"] = "No"            
            item["Error_Description"] = "None"
            item["Middle_Slice"] = str(z_mid_total)
            item["Original_Bbox"] = [int(u) for u in list(bbox)]
            item["cz0"] = item["Middle_Slice"]
            item["cy0"] = (item["Original_Bbox"][2] + item["Original_Bbox"][3])//2 
            item["cx0"] = (item["Original_Bbox"][4] + item["Original_Bbox"][5])//2

        # test if the original bounding box is with in the volume size and if not print a warning and skip the instance 
        if item["Original_Bbox"][1] > synanno.vol_dim_z or item["Original_Bbox"][3] > synanno.vol_dim_y or item["Original_Bbox"][5] > synanno.vol_dim_x:
            print("WARNING: The original bounding box of the current instance is outside of the volume size. -> Skipping instance.")
            continue

        # retrieve the bounding box for the current synapse
        bbox = bbox if json_page_entry is False else list(map(int,item["Original_Bbox"]))
        # retrieve the middle slice (relative to the whole volume) for the current synapse
        z_mid_total = z_mid_total if json_page_entry is False else int(item["Middle_Slice"])

        if bbox_exists:
            # adjust the bounding box in x and y direction to fit the crop size
            y1, y2 = adjust_bbox(bbox[2], bbox[3], crop_size)
            x1, x2 = adjust_bbox(bbox[4], bbox[5], crop_size)
            if bbox[0] == bbox[1]:
                z1, z2 = adjust_bbox(bbox[0], bbox[1], 16)
                adjusted_3d_bboxes = [z1, z2, y1, y2, x1, x2]
            else:
                adjusted_3d_bboxes = bbox[:2] + [y1, y2, x1, x2]
        else:
            # TODO: DO NOT HARD CODE THE CROP SIZE
            z1, z2 = bounds_2exp(bbox[0], 32)
            y1, y2 = bounds_2exp(bbox[2], 128)
            x1, x2 = bounds_2exp(bbox[4], 128)
            adjusted_3d_bboxes = [z1, z2, y1, y2, x1, x2]

        # retrieve the actual crop coordinates and possible padding based on the max dimensions of the whole cloud volume
        crop_bbox, img_padding = crop_pad_cloud_volume([synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x], adjusted_3d_bboxes)

        if json_page_entry is False:
            # update the json item with the adjusted bounding box and padding
            adjusted_box_syn, item["Padding_Syn"] = adjusted_box_img, item["Padding_Img"] = crop_bbox, img_padding

            assert adjusted_box_img == adjusted_box_syn, "The adjusted bounding boxes of the source and target images do not match."

            item["Adjusted_Bbox"] = adjusted_box_img

            json_objects_list[str(page)].append(item)

        synanno.progress_bar_status['status'] = f"Inst.{str(idx)}: Pre-process sub-volume."
        
        # Map the bounding box coordinates to a dictionary
        crop_box_dict = {
            'z1': crop_bbox[0],
            'z2': crop_bbox[1],
            'y1': crop_bbox[2],
            'y2': crop_bbox[3],
            'x1': crop_bbox[4],
            'x2': crop_bbox[5]
        }

        # Retrieve the order of the coordinates (xyz, xzy, yxz, yzx, zxy, zyx)
        cord_order = list(synanno.coordinate_order.keys())

        # Create the bounding box for the current synapse
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
        coord_resolution = [int(res) for res in synanno.coordinate_order.values()]

        # Retrieve the source and target images from the cloud volume
        cropped_img = synanno.source_cv.download(bound, coord_resolution=coord_resolution, mip=0)
        cropped_gt = synanno.target_cv.download(bound, coord_resolution=coord_resolution, mip=0)

        # Download based on a point
        # Retrieve the source and target images from the cloud volume
        size = {'x':128, 'y':128, 'z':32}
        size_order = [size[cord_order[0]], size[cord_order[1]], size[cord_order[2]]]
        point = [bbox_dict[idx][cord_order[0]], bbox_dict[idx][cord_order[1]], bbox_dict[idx][cord_order[2]]]
        cropped_img = synanno.source_cv.download_point(point, size=size_order, coord_resolution=coord_resolution, mip=0)          
        cropped_gt = synanno.target_cv.download_point(point, size=size_order, coord_resolution=coord_resolution, mip=0)

        # remove the singleton dimension, take care as the z dimension might be singleton
        cropped_img = cropped_img.squeeze(axis=3)
        cropped_gt = cropped_gt.squeeze(axis=3)

        # given the six cases xyz, xzy, yxz, yzx, zxy, zyx, we have to permute the axes to match the zyx order
        cropped_img = np.transpose(cropped_img, axes=[cord_order.index('z'), cord_order.index('y'), cord_order.index('x')])
        cropped_gt = np.transpose(cropped_gt, axes=[cord_order.index('z'), cord_order.index('y'), cord_order.index('x')])
        
        # process the 3D gt file by converting the polarity prediction to semantic segmentation and then to instance-level segmentation on pre/post synaptic level and synapse level.
        cropped_img, cropped_gt, cropped_syn, cropped_seg = retrieve_instance_seg(cropped_img, cropped_gt, view_style='neuron')

        # create the binary mask of the current synapse based on the index
        # TODO: I have to identify the correct index for the synapse
        cropped_syn_mask = (cropped_seg != 0)

        # mask the synapse with the binary mask
        cropped_syn = cropped_syn * (cropped_syn_mask != 0).astype(cropped_syn.dtype)

        # pad the images and synapse segmentation to fit the crop size (sz)
        cropped_img_pad = np.pad(cropped_img, img_padding, mode='constant', constant_values=128)
        cropped_syn_pad = np.pad(cropped_syn, img_padding, mode='constant', constant_values=0)  
        
        assert cropped_img_pad.shape == cropped_syn_pad.shape, "The shape of the source and target images do not match."

        image_list, label_list = [], []
        for z in range(cropped_img_pad.shape[0]):
            image_list.append(cropped_img_pad[z])
            label_list.append(cropped_syn_pad[z])

        vis_image = np.stack(image_list, 0)
        print("vis_image.shape")
        print(vis_image.shape)
        vis_label = syn2rgb(np.stack(label_list, 0)) # z, y, x, c

        # center slice of padded subvolume
        cs_dix = (vis_image.shape[0]-1)//2 # assumes even padding

        # overwrite cs incase that object close to boundary
        cs = min(int(z_mid_total), cs_dix)

        synanno.progress_bar_status['status'] = f"Inst.{str(idx)}: Saving 2D Slices"

        # save volume slices
        for s in range(vis_image.shape[0]):
            img_name = str(int(z_mid_total)-cs+s)+".png"

            # image
            img_c = Image.fromarray((vis_image[s,:,:]* 255).astype(np.uint8))
            img_c.save(os.path.join(img_all,img_name), "PNG")

            # label
            lab_c = Image.fromarray(vis_label[s,:,:,:])

            # reduce the opacity of all black pixels to zero
            lab_c = lab_c.convert("RGBA")

            lab_c = np.asarray(lab_c) 
            r, g, b, a = np.rollaxis(lab_c, axis=-1) # split into 4 n x m arrays 
            r_m = r != 0 # binary mask for red channel, True for all non black values
            g_m = g != 0 # binary mask for green channel, True for all non black values
            b_m = b != 0 # binary mask for blue channel, True for all non black values

            # combine the three binary masks by multiplying them (1*1=1, 1*0=0, 0*1=0, 0*0=0)
            # multiply the combined binary mask with the alpha channel
            a = a * ((r_m == 1) | (g_m == 1) | (b_m == 1))

            lab_c = Image.fromarray(np.dstack([r, g, b, a]), 'RGBA') # stack the img back together 

            lab_c.save(os.path.join(syn_all,img_name), "PNG")

        synanno.progress_bar_status['percent'] = int((90/session.get('per_page')) * i) 

    # create and export the JSON File
    synanno.progress_bar_status['status'] = "Saving information to JSON file"
    if json_page_entry is False:
        # save the data as page in the json file
        json_obj = json.dumps(json_objects_list, indent=4, cls=NpEncoder)

        path_json = os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER'])
        name_json = app.config['JSON']
            

        with open(os.path.join(path_json, name_json), "w") as outfile:
            outfile.write(json_obj)
            synanno.progress_bar_status['percent'] = int(100) 
        synanno_json = os.path.join(path_json, name_json)

        return synanno_json
    else:
        return None
    

def load_3d_files(im_file: str, gt_file: str) -> Tuple[np.ndarray, np.ndarray]:
    """Load the 3D image and ground truth files.
    
    Args:
        im_file (str): path to the image file.
        gt_file (str): path to the ground truth file.
        
    Returns:
        source (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
    """
    synanno.progress_bar_status['status'] = "Loading Source File"
    img = readvol(im_file)  # The original image (EM)


    synanno.progress_bar_status['status'] = "Loading Target File"
    gt = readvol(gt_file)  # The mask annotation (GT: ground truth)

    return img, gt


def neuron_centric_3d_data_processing(source_url: str, target_url: str, table_name: str, preid: int, postid: int, bucket_secret_json: json = '~/.cloudvolume/secrets', patch_size: int = 142, path_json: str = None) -> Union[str, Tuple[np.ndarray, np.ndarray]]:
    """ Retrieve the bounding boxes and instances indexes from the table and call the render function to render the 3D data as 2D images.

    Args:
        source_url (str): the url to the source cloud volume (EM).
        target_url (str): the url to the target cloud volume (synapse).
        table_name (str): the path to the JSON file.
        preid (int): the id of the pre synaptic region.
        postid (int): the id of the post synaptic region.
        bucket_secret_json (json): the path to the JSON file.
        patch_size (int): the size of the 2D patch.
        path_json (str): the path to the JSON file.
    """

    # TODO: Update with real materialization
    # handling both suitcases: the bounding box was already calculated and stored in the table or it has to be calculated on the fly from a synapse centric point
    bbox_exists = False
    
    # read data as dict from path table_name
    synanno.progress_bar_status['status'] = "Retrieving Materialization"
    if bbox_exists:

        table = json.load(open(table_name))
        # convert table to pandas dataframe
        df = pd.DataFrame(table["Data"])

        # dict that contains the bounding boxes for each synapse and the corresponding id
        bbox_dict = dict()

        # loop over the rows of the df reading them as dic
        for row in df.to_dict(orient="records"):
            # retrieve the bounding box for the current synapse
            bbox_dict[int(row["Image_Index"])] = list(map(int, row["Original_Bbox"]))
    else:
        # Read the CSV file
        df = pd.read_csv(table_name)

        # Select only the necessary columns
        df = df[['pre_pt_x', 'pre_pt_y', 'pre_pt_z', 'post_pt_x', 'post_pt_y', 'post_pt_z', 'x', 'y', 'z']]

        # Convert the DataFrame to a dictionary
        bbox_dict = df.to_dict('index')

    # save the table to the session
    session['materialization'] = bbox_dict

    synanno.progress_bar_status['status'] = "Loading Cloud Volumes"
    synanno.source_cv = CloudVolume(source_url, secrets=bucket_secret_json)
    synanno.target_cv = CloudVolume(target_url, secrets=bucket_secret_json)

    # assert that both volumes have the same dimensions
    print(synanno.source_cv.volume_size, synanno.target_cv.volume_size)

    if list(synanno.source_cv.volume_size) == list(synanno.target_cv.volume_size):
        vol_dim = tuple([s-1 for s in synanno.source_cv.volume_size]) 
    else:
        # print a warning if the dimensions do not match, stating that we use the smaller size of the two volumes
        print(f"The dimensions of the source ({synanno.source_cv.volume_size}) and target ({synanno.target_cv.volume_size}) volumes do not match. We use the smaller size of the two volumes.")

        # test which size is smaller
        if np.prod(synanno.source_cv.volume_size) < np.prod(synanno.target_cv.volume_size):
            vol_dim = {c: dim for c, dim in zip(synanno.coordinate_order.keys(), synanno.source_cv.volume_size)}
        else:
            vol_dim = {c: dim for c, dim in zip(synanno.coordinate_order.keys(), synanno.target_cv.volume_size)}

    synanno.vol_dim_x, synanno.vol_dim_y, synanno.vol_dim_z = vol_dim['x'], vol_dim['y'], vol_dim['z']

    # number of rows in df
    session['n_images'] = df.shape[0]

    # calculate the number of pages needed for the instance count in the JSON
    number_pages = session.get('n_images') // session.get('per_page')
    if not (session.get('n_images') % session.get('per_page') == 0):
        number_pages = number_pages + 1

    # calculate the number of pages, use by the set_data function
    session['n_pages'] = number_pages
    
    return visualize_cv_instances(patch_size, path_json=path_json, page=0)


def view_centric_cloud_volume(im_file: str, gt_file: str, z1: int, z2: int, y1: int, y2: int, x1: int, x2: int, bucket_secret_json: json = '~/.cloudvolume/secrets') -> Tuple[np.ndarray, np.ndarray]:
    """Load the 3D image and ground truth volumes.
    
    Args:
        im_file (str): path to the image file.
        gt_file (str): path to the ground truth file.
        x1 (int): x1 coordinate of the bounding box.
        x2 (int): x2 coordinate of the bounding box.
        y1 (int): y1 coordinate of the bounding box.
        y2 (int): y2 coordinate of the bounding box.
        z1 (int): z1 coordinate of the bounding box.
        z2 (int): z2 coordinate of the bounding box.
        
    Returns:
        source (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
    """
    
    synanno.progress_bar_status['status'] = "Loading Source Cloud Volume"

    # handle to cloud volume
    source = CloudVolume(im_file, secrets=bucket_secret_json)

    if x2 == -1:
        x2 = source.info['scales'][0]['size'][2]

    if y2 == -1:
        y2 = source.info['scales'][0]['size'][1]
    
    if z2 == -1:
        z2 = source.info['scales'][0]['size'][0]

    # retrieve the subvolume
    img = np.squeeze(source[z1:z2, y1:y2, x1:x2])

    img = img[:,:,:]

    synanno.progress_bar_status['status'] = "Loading Target Cloud Volume"

    # handle to cloud volume
    gt = CloudVolume(gt_file, secrets=bucket_secret_json)

    
    gt = np.squeeze(gt[z1:z2, y1:y2, x1:x2])

    gt = gt[:,:,:]

    return img, gt

# TODO: Can be delete if we are able to view precomputed in NG
def instance_based_ng_preprocessing(z1: int, z2: int, y1: int, y2: int, x1: int, x2: int, crop_size: int=128, crop_depth: int=12) -> Tuple[np.ndarray, np.ndarray]:    
    # adjust the bounding box in x and y direction to fit the crop size
    z1, z2 = adjust_bbox(z1, z2, crop_depth)
    y1, y2 = adjust_bbox(y1, y2, crop_size)
    x1, x2 = adjust_bbox(x1, x2, crop_size)

    adjusted_3d_bboxes = [z1, z2, y1, y2, x1, x2]
    
    # retrieve the actual crop coordinates and possible padding based on the max dimensions of the whole cloud volume
    img_bbox, _ = crop_pad_cloud_volume([synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x], adjusted_3d_bboxes)
    syn_bbox, _ = crop_pad_cloud_volume([synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x], adjusted_3d_bboxes)
    
    # assert that both voluems have the same dimensions
    assert img_bbox == syn_bbox, "The dimensions of the source and target volumes do not match."

    # calculate the center
    cz0 = (img_bbox[0] + img_bbox[1])//2
    cy0 = (img_bbox[2] + img_bbox[3])//2
    cx0 = (img_bbox[4] + img_bbox[5])//2

    # squeeze the last dimension as it is singleton
    img = synanno.source_cv[img_bbox[0]:img_bbox[1], img_bbox[2]:img_bbox[3], img_bbox[4]:img_bbox[5]].squeeze(axis=3)
    gt = synanno.target_cv[syn_bbox[0]:syn_bbox[1], syn_bbox[2]:syn_bbox[3], syn_bbox[4]:syn_bbox[5]].squeeze(axis=3)
    return [cz0, cy0, cx0], retrieve_instance_seg(img, gt, view_style='neuron')

def view_centric_3d_data_processing(im: np.ndarray, gt: np.ndarray, patch_size: int = 142, path_json: str = None) -> Union[str, Tuple[np.ndarray, np.ndarray]]:
    """ Process the 3D gt file by converting the polarity prediction to semantic segmentation and then to instance-level segmentation on pre/post synaptic level and synapse level.
        Call to the render function to render the 3D data as 2D images.

    Args:
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
        patch_size (int): the size of the 2D patch.
        path_json (str): the path to the JSON file.

    Returns:
        synanno_json (str): the path to the JSON file.
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
    """
    im, gt, syn, seg= retrieve_instance_seg(im, gt)    
    return render_3d_data(im, gt, syn, seg, patch_size, path_json)


def retrieve_instance_seg(im: np.ndarray, gt: np.ndarray, view_style: str ='view') -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ Process the 3D gt file by converting the polarity prediction to semantic segmentation and then to instance-level segmentation on pre/post synaptic level and synapse level.
    
    Args:
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
        
    Returns:
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
        syn (np.ndarray): the instance-level segmentation on pre/post synaptic level.
    """

    if view_style == 'view':
        synanno.progress_bar_status['status'] = "Convert Polarity Prediction to Segmentation"


    if gt.ndim != 3:
        # If the gt is not a segmentation mask but predicted polarity, generate
        # the individual synapses using the polarity2instance function from
        # https://github.com/zudi-lin/pytorch_connectomics/blob/master/connectomics/utils/process.py
        assert (gt.ndim == 4 and gt.shape[0] == 3)
        warnings.warn("Converting polarity prediction into segmentation, which can be very slow!")
        scales = (im.shape[0]/gt.shape[1], im.shape[1]/gt.shape[2], im.shape[2]/gt.shape[3])
        gt = polarity2instance(gt.astype(np.uint8), semantic=False, scale_factors=scales)

    if view_style == 'view':
        synanno.progress_bar_status['percent'] = int(5) 

    # set max dimensions, start count at 0
    if view_style == 'view':
        synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x = tuple([s-1 for s in gt.shape])

    if view_style == 'view':
        synanno.progress_bar_status['status'] = "Retrieve 2D patches from 3D volume"
    
    # convert the semantic segmentation to instance-level segmentation on pre/post synaptic level and synapse level
    syn, seg = process_syn(gt, view_style=view_style)

    if view_style == 'view':
        synanno.progress_bar_status['status'] = "Render Images"

    return im, gt, syn, seg


def render_3d_data(im: np.ndarray, gt: np.ndarray, syn: np.ndarray, seg: np.ndarray, patch_size: int = 142, path_json: str = None) -> Union[str, Tuple[np.ndarray, np.ndarray]]:
    """ Render the 3D data as 2D images.

    Args:
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
        syn (np.ndarray): the instance-level segmentation on pre/post synaptic level.
        seg (np.ndarray): the instance-level segmentation on synapse level.
        patch_size (int): the size of the 2D patch.
        path_json (str): the path to the JSON file.
    
    Returns:
        synanno_json (str): the path to the JSON file.
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
    """
    # if a json was provided process the data accordingly
    if path_json is not None:
        visualize(syn, seg, im, sz=patch_size, path_json=path_json)
        synanno.progress_bar_status['percent'] = int(100) 
        return None, im, gt
    # if no json was provided create a json file and process the data
    else:
        synanno_json = visualize(syn, seg,im, sz=patch_size)
        synanno.progress_bar_status['percent'] = int(100) 
        if os.path.isfile(synanno_json):
            return synanno_json, im, gt
        else:
            # the json file should have been created by the visualize function
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), 'synAnno.json')

