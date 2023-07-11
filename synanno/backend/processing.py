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
    """Process the ground truth segmentation.

    Args:
        gt (np.ndarray): the ground truth segmentation.
        small_thres (int): the threshold for removing small objects.
        view_style (str): the view style.

    Returns:
        seg (np.ndarray): the processed segmentation.
    """

    # check whether the segmentation is semantic or instance-level
    indices = np.unique(gt)
    is_semantic = len(indices) == 3 and (indices==[0,1,2]).all()
    if not is_semantic: # already an instance-level segmentation
        return gt
    else:
        synanno.progress_bar_status['percent'] = int(8) if view_style == 'view' else None

        # convert the semantic segmentation to instance-level segmentation
        # assign each synapse a unique index
        seg = label_cc(gt).astype(int)
        # mask out unwanted artifacts
        seg *= (gt != 0).astype(int)
        # remove small objects
        seg = remove_small_objects(seg, small_thres)

        return seg



def bbox_ND(img: np.ndarray) -> tuple:
    """Calculate the bounding box coordinates of a N-dimensional array by finding the range of indices in each dimension of the input array that contain non-zero values. 
        For a 2D image, these would correspond to the top-left and bottom-right corners of the bounding box. In a 3D space, it would correspond to the eight corners of the bounding box.
        Please note that the function may not work as expected if there are isolated non-zero elements in the array (outliers). It works best when the non-zero elements are contiguous or close together.

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

def crop_pad_data(data: np.ndarray, z: int, bbox_2d: list, pad_size_x: int = 148, pad_size_y: int = 148, pad_size_z: int = None, mask: np.ndarray = None) -> Union[np.ndarray, Tuple[np.ndarray, list, tuple]]:
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
                         constant_values=0)

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

def visualize(seg: np.ndarray, img: np.ndarray, crop_size_x: int = 148, crop_size_y: int = 148, crop_size_z: int = 16, return_data: bool = False, iterative_bbox: bool = False, path_json: str = None) -> Union[str, None]:
    ''' Visualize the synapse and EM images in 2D slices.
    
    Args:
        seg (np.ndarray): instance-level segmentation where each synapse is labeled with an individual index.
        img (np.ndarray): the original EM image.
        crop_size_x (int): the size of the 2D patch in x direction.
        crop_size_y (int): the size of the 2D patch in y direction.
        crop_size_z (int): the number of the 2D patches in z direction.
        return_data (bool): whether to return the data.
        iterative_bbox (bool): whether to use iterative approach to calculate bounding boxes.
        path_json (str): the path to the JSON file.
        
    Returns:
        synanno_json (str): the path to the JSON file.
    '''

    # list of json objects representing the synapses (ids, middle slices, bounding boxes, etc.)
    json_objects_list = []
    
    # dictionary of synapse ids and their corresponding processed source and target images
    data_dict = {}

    # specify the list we iterate over (index list or json)
    if path_json is not None:
        instance_list = json.load(open(path_json))["Data"]
    else:
        # retrieve the instance level segmentation indices
        instance_list = np.unique(seg)[1:] # ignore background

        # throw a warning if the number of synapses is zero
        if len(instance_list) == 0:
            warnings.warn("No synapses found in the segmentation.")
            raise ValueError("No synapses found in the segmentation. Does the subvolume contain synapses?")

        if not iterative_bbox:
            # calculate the bounding boxes of each segment based on scipy.ndimage.find_objects
            bbox_dict = index2bbox(seg, instance_list, iterative=False)

    # create the directories for saving the source and target images
    idx_dir = create_dir('./synanno/static/', 'Images')
    syn_folder, img_folder = create_dir(idx_dir, 'Syn'), create_dir(idx_dir, 'Img')

    # calculate process time for progress bar
    len_instances = len(instance_list)
    perc = (100)/len_instances 

    # iterate over the synapses. save the middle slices and before/after ones for navigation.
    for i, inst in enumerate(instance_list):

        # retrieve the index of the current synapse from the json file, else use the index from the list
        idx = inst["Image_Index"] if path_json is not None else inst

        # create the instance specific directories for saving the source and target images
        syn_all, img_all = create_dir(syn_folder, str(idx)), create_dir(img_folder, str(idx))

        # create the binary mask of the current synapse based on the index
        instance_binary_mask = (seg == idx)

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
        
            # either retrieve the 3D bounding box from the previous iterative generated bb dict or calculate it on individual basis
            bbox = bbox_ND(instance_binary_mask) if iterative_bbox else bbox_dict[idx]
                    
            # find the most centric slice that contains foreground
            instance_binary_mask_crop = crop_ND(instance_binary_mask, bbox, end_included=True)
            crop_mid = (instance_binary_mask_crop.shape[0]-1) // 2
            idx_t = np.where(np.any(instance_binary_mask_crop, axis=(1,2)))[0] # index of slices containing True values
            z_mid_relative = idx_t[np.argmin(np.abs(idx_t-crop_mid))]
            z_mid_total = z_mid_relative + bbox[0]

            # update the json item with the middle slice and original bounding box
            item["Middle_Slice"] = str(z_mid_total)
            item["Original_Bbox"] = [int(u) for u in list(bbox)]
            item["cz0"] = item["Middle_Slice"]
            item["cy0"] = (item["Original_Bbox"][2] + item["Original_Bbox"][3])//2 
            item["cx0"] = (item["Original_Bbox"][4] + item["Original_Bbox"][5])//2
            item["crop_size_x"] = crop_size_x
            item["crop_size_y"] = crop_size_y
            item["crop_size_z"] = crop_size_z

        else:
            instance_binary_mask = (seg == idx) # binary mask of the current synapse
            bbox = list(map(int,inst["Original_Bbox"]))
            z_mid_total = int(inst["Middle_Slice"])
            crop_size_x = int(inst["crop_size_x"])
            crop_size_y = int(inst["crop_size_y"])
            crop_size_z = int(inst["crop_size_z"])

        y1, y2 = adjust_bbox(bbox[2], bbox[3], crop_size_y)
        x1, x2 = adjust_bbox(bbox[4], bbox[5], crop_size_x)
        bbox = [int(bbox[0]), int(bbox[1])] + [y1, y2, x1, x2]

        image_list, label_list = [], []
        for i, z_index in enumerate(range(bbox[0], bbox[1]+1)):

            cropped_syn, ab_syn, pad_syn = crop_pad_data(seg, z_index, bbox[2:], mask=instance_binary_mask, pad_size_x=crop_size_x, pad_size_y=crop_size_y)
            cropped_img, ab_img, _ = crop_pad_data(img, z_index, bbox[2:], pad_size_x=crop_size_x, pad_size_y=crop_size_y)
            
            assert ab_img == ab_syn, "The bounding boxes of the synapse and EM image do not match."

            if i == 0 and path_json is None:
                item["Adjusted_Bbox"] = [int(u) for u in list([bbox[0], bbox[1]] + ab_syn)]
                item["Padding"] = pad_syn
                json_objects_list.append(item)

            image_list.append(center_crop(cropped_img, (crop_size_y, crop_size_x)))
            label_list.append(center_crop(cropped_syn, (crop_size_y, crop_size_x)))

        vis_image = np.stack(image_list, 0).astype(np.uint8) # z, y, x
        # create an RGB mask of the synapse from the single channel binary mask
        # colors all even values in the mask with turquoise and all odd values with pink
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
        return path_json


def visualize_cv_instances(crop_size_x: int = 148, crop_size_y: int = 148, crop_size_z: int = 16, path_json: str = None, page: int =0) -> Union[str, None]:
    ''' Visualize the synapse and EM images in 2D slices for each instance by cropping the bounding box of the instance.
        Processing each instance individually, retrieving them from the cloud volume and saving them to the local disk.
    
    Args:
        crop_size_x (int): the size of the 2D patch in x direction.
        crop_size_y (int): the size of the 2D patch in y direction.
        crop_size_z (int): the size of the 2D patch in z direction.
        path_json (str): the path to the JSON file.
        page (int): the current page number for which to compute the data.
        
    Returns:
        synanno_json (str): the path to the JSON file.
    '''

    # set the progress bar to zero
    if page != 0:
        synanno.progress_bar_status['percent'] = 0
        synanno.progress_bar_status['status'] = f"Loading page {str(page)}."

    # specify if the current page is already in the json file
    json_page_entry = False

    # specify the list we iterate over (index list or json)
    if path_json is not None:
        json_objects_list = json.load(open(path_json))
        # if int key is in dict, set json_page_entry to True
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

    # retrieve the meta data for the synapses asoociated with the current page
    bbox_dict = get_sub_dict_within_range(session.get('materialization'), 1 + (page * session['per_page']), session['per_page'] + (page * session['per_page']))

    ### iterate over the synapses. save the middle slices and before/after ones for navigation. ###
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

            point = [int(bbox_dict[idx]['z']), int(bbox_dict[idx]['y']), int(bbox_dict[idx]['x'])]

            # create a new item for the JSON file with defaults.
            item = dict()
            item["Image_Index"] = int(idx) + session.get('per_page') * page
            item["GT"] = "/"+"/".join(syn_all.strip(".\\").split("/")[2:])
            item["EM"] = "/"+"/".join(img_all.strip(".\\").split("/")[2:])
            item["Label"] = "Correct"
            item["Annotated"] = "No"            
            item["Error_Description"] = "None"
            item["Middle_Slice"] = int(bbox_dict[idx]['z'])
            item["Center_Point"] = point
            item["cz0"] = int(bbox_dict[idx]['z'])
            item["cy0"] = int(bbox_dict[idx]['y'])
            item["cx0"] = int(bbox_dict[idx]['x'])

        # retrieve the center point for the current synapse
        point = item["Center_Point"] if json_page_entry is False else inst["Center_Point"]
        point = [int(p) for p in point]

        # retrieve the middle slice (relative to the whole volume) for the current synapse
        z_mid_total = int(item["Middle_Slice"]) if json_page_entry is False else int(inst["Middle_Slice"])

        # retrieve the bounding box for the current synapse from the central synapse coordinates
        z1 = point[0] - crop_size_z // 2
        z2 = point[0] + crop_size_z // 2
        y1 = point[1] - crop_size_y // 2
        y2 = point[1] + crop_size_y // 2
        x1 = point[2] - crop_size_x // 2
        x2 = point[2] + crop_size_x // 2

        adjusted_3d_bboxes = [z1, z2, y1, y2, x1, x2]

        # retrieve the actual crop coordinates and possible padding based on the max dimensions of the whole cloud volume
        crop_bbox, img_padding = crop_pad_cloud_volume([synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x], adjusted_3d_bboxes)

        if json_page_entry is False:
            # update the json item with the adjusted bounding box and padding
            item["Adjusted_Bbox"], item["Padding"] = crop_bbox, img_padding

            # write the item to the json file as content for the current page
            json_objects_list[str(page)].append(item)

        synanno.progress_bar_status['status'] = f"Inst.{str(idx)}: Pre-process sub-volume."
        
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

        # create the bounding box for the current synapse
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

        # remove the singleton dimension, take care as the z dimension might be singleton
        cropped_img = cropped_img.squeeze(axis=3)
        cropped_gt = cropped_gt.squeeze(axis=3)

        # given the six cases xyz, xzy, yxz, yzx, zxy, zyx, we have to permute the axes to match the zyx order
        cropped_img = np.transpose(cropped_img, axes=[cord_order.index('z'), cord_order.index('y'), cord_order.index('x')])
        cropped_gt = np.transpose(cropped_gt, axes=[cord_order.index('z'), cord_order.index('y'), cord_order.index('x')])

        # process the 3D gt file by converting the polarity prediction to semantic segmentation and then to instance-level segmentation on pre/post synaptic level and synapse level.
        cropped_seg = process_syn(cropped_gt, view_style='neuron')

        # pad the images and synapse segmentation to fit the crop size (sz)
        cropped_img_pad = np.pad(cropped_img, img_padding, mode='constant', constant_values=148)
        cropped_seg_pad = np.pad(cropped_seg, img_padding, mode='constant', constant_values=0)  
        
        assert cropped_img_pad.shape == cropped_seg_pad.shape, "The shape of the source and target images do not match."

        # create an RGB mask of the synapse from the single channel binary mask
        # colors all non zero values turquoise 
        vis_label = syn2rgb(np.stack(label_list, 0)) # z, y, x, c

        # center slice of padded subvolume
        cs_dix = (cropped_img_pad.shape[0]-1)//2 # assumes even padding

        # overwrite cs incase that object close to boundary
        cs = min(int(z_mid_total), cs_dix)

        synanno.progress_bar_status['status'] = f"Inst.{str(idx)}: Saving 2D Slices"

        # save volume slices
        for s in range(cropped_img_pad.shape[0]):
            img_name = str(int(z_mid_total)-cs+s)+".png"

            # image
            img_c = Image.fromarray((cropped_img_pad[s,:,:]* 255).astype(np.uint8))
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
    
    # read data as dict from path table_name
    synanno.progress_bar_status['status'] = "Retrieving Materialization"

    # Read the CSV file
    df = pd.read_csv(table_name)

    # Select only the necessary columns
    df = df[['pre_pt_x', 'pre_pt_y', 'pre_pt_z', 'post_pt_x', 'post_pt_y', 'post_pt_z', 'x', 'y', 'z']]

    # Convert the DataFrame to a dictionary
    bbox_dict = df.to_dict('index')

    # save the table to the session
    session['materialization'] = bbox_dict

    synanno.progress_bar_status['status'] = "Loading Cloud Volumes"
    synanno.source_cv = CloudVolume(source_url, secrets=bucket_secret_json, fill_missing=True)
    synanno.target_cv = CloudVolume(target_url, secrets=bucket_secret_json, fill_missing=True)

    # assert that both volumes have the same dimensions
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

    session['n_pages'] = number_pages
    
    return visualize_cv_instances(crop_size_x=int(patch_size), crop_size_y=int(patch_size), crop_size_z=16, path_json=path_json, page=0)


def view_centric_cloud_volume(im_file: str, gt_file: str, subvolume: Dict, bucket_secret_json: json = '~/.cloudvolume/secrets') -> Tuple[np.ndarray, np.ndarray]:
    """ Retrieve the view specific subvolume from the cloud target and source volume.

    Args:
        im_file (str): the path to the source cloud volume (EM).
        gt_file (str): the path to the target cloud volume (synapse).
        subvolume (Dict): the subvolume coordinates.
        bucket_secret_json (json): the path to the JSON file.

    Returns:
        img (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
    """
    
    synanno.progress_bar_status['status'] = "Loading Source Cloud Volume"

    # handle to the source cloud volume
    source = CloudVolume(im_file, secrets=bucket_secret_json, fill_missing=True)

    # should now cropping coordinates be provided, use the whole volume
    if subvolume['x2'] == -1:
        subvolume['x2'] = source.info['scales'][0]['size'][2]

    if subvolume['y2'] == -1:
        subvolume['y2'] = source.info['scales'][0]['size'][1]
    
    if subvolume['z2'] == -1:
        subvolume['z2'] = source.info['scales'][0]['size'][0]

    # retrieve the order of the coordinates (xyz, xzy, yxz, yzx, zxy, zyx)
    coordinate_order = list(synanno.coordinate_order.keys())

    # retrieve the image subvolume
    img = np.squeeze(source[subvolume[coordinate_order[0]+'1']:subvolume[coordinate_order[0]+'2'], subvolume[coordinate_order[1]+'1']:subvolume[coordinate_order[1]+'2'], subvolume[coordinate_order[2]+'1']:subvolume[coordinate_order[2]+'2']])

    # transpose the image to match the zyx order
    img = np.transpose(img, axes=[coordinate_order.index('z'), coordinate_order.index('y'), coordinate_order.index('x')])

    synanno.progress_bar_status['status'] = "Loading Target Cloud Volume"

    # handle to the target cloud volume
    gt = CloudVolume(gt_file, secrets=bucket_secret_json, fill_missing=True)

    # retrieve the ground truth subvolume
    gt = np.squeeze(gt[subvolume[coordinate_order[0]+'1']:subvolume[coordinate_order[0]+'2'], subvolume[coordinate_order[1]+'1']:subvolume[coordinate_order[1]+'2'], subvolume[coordinate_order[2]+'1']:subvolume[coordinate_order[2]+'2']])

    # transpose the image to match the zyx order
    gt = np.transpose(gt, axes=[coordinate_order.index('z'), coordinate_order.index('y'), coordinate_order.index('x')])

    return img, gt


def view_centric_3d_data_processing(im: np.ndarray, gt: np.ndarray, crop_size_x: int = 148, crop_size_y: int = 148, crop_size_z: int = 16, path_json: str = None, view_style: str ='view') -> Union[str, Tuple[np.ndarray, np.ndarray]]:
    """ Render the 3D data as 2D images.

    Args:
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
        patch_size (int): the size of the 2D patch.
        path_json (str): the path to the JSON file.
        view_style (str): the view style of the synapse (view, neuron, synapse).
    
    Returns:
        synanno_json (str): the path to the JSON file.
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
    """

    # retrieve the dimensions of the cropped volume, after the dimension swap
    synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x = tuple([s-1 for s in gt.shape])

    # retrieve the instance level segmentation
    seg = process_syn(gt, view_style=view_style)

    synanno.progress_bar_status['status'] = "Retrieve 2D patches from 3D volume"
    # if a json was provided process the data accordingly
    path_json = visualize(seg, im, crop_size_x=crop_size_x, crop_size_y=crop_size_y, crop_size_z=crop_size_z, path_json=path_json, return_data=False) 
    synanno.progress_bar_status['percent'] = int(100) 
    return im, gt, path_json

