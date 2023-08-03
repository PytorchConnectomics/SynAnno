from typing import Union, Tuple, Dict
from collections import OrderedDict

import os
import json
import shutil
import warnings
import itertools
import numpy as np
from PIL import Image
from skimage.morphology import remove_small_objects
from skimage.measure import label as label_cc
from skimage.transform import resize
from scipy.ndimage import find_objects, center_of_mass

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
    # this can only hold true if we did not up- or down-sample the data
    if view_style == 'view':    
        indices = np.unique(gt)
        is_semantic = len(indices) == 2 and (indices==[0,1]).all()
        if not is_semantic: # already an instance-level segmentation
            return gt

    synanno.progress_bar_status['percent'] = int(8) if view_style == 'view' else None

    # convert the semantic segmentation to instance-level segmentation
    # assign each synapse a unique index
    seg = label_cc(gt).astype(int)
    # mask out unwanted artifacts
    if view_style == 'view':
        seg *= (gt != 0).astype(int)
        # remove small objects
        seg = remove_small_objects(seg, small_thres)
    elif view_style == 'neuron':
        # identify the largest connected component in the center of the volume and mask out the rest
        center_blob_value = get_center_blob_value_vectorized(seg, np.unique(seg)[1:])
        seg *= (seg == center_blob_value)
    return seg


def get_center_blob_value_vectorized(labeled_array: np.ndarray, blob_values: np.ndarray) -> int:
    ''' Get the value of the non-zero blob closest to the center of the labeled array.
    
    Args:
        labeled_array (np.ndarray): 3D numpy array where different blobs are represented by different integers.
        blob_values (np.ndarray): Array of unique blob values in the labeled_array.
        
    Returns:
        center_blob_value (int): Value of the center blob.
    '''
    # Calculate the center of the entire array
    array_center = np.array(labeled_array.shape) / 2.0

    # Create a 4D array where the first dimension is equal to the number of blobs
    # and the last three dimensions are equal to the dimensions of the original array
    blob_masks = np.equal.outer(blob_values, labeled_array)

    # Compute the center of mass for each blob
    blob_centers = np.array([center_of_mass(mask) for mask in blob_masks])

    # Calculate the distance from each blob center to the array center
    distances = np.linalg.norm(blob_centers - array_center, axis=1)

    # Find the index of the blob with the minimum distance
    center_blob_index = np.argmin(distances)

    # Return the value of the blob with the minimum distance
    return blob_values[center_blob_index]


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

def calculate_crop_pad(bbox_3d: list, volume_shape: tuple, pad_z: bool = False) -> Tuple[list, tuple]:
    """Calculate the crop and pad parameters for the given bounding box and volume shape.
    
    Args:
        bbox_3d (list): the bounding box of the 3D volume.
        volume_shape (tuple): the shape of the 3D volume.
        pad_z (bool): whether to pad the z dimension.

    Returns:
        bbox (list): the bounding box of the 3D volume.
        pad (tuple): the padding parameters.

    """
    z1o, z2o, y1o, y2o, x1o, x2o = bbox_3d  # region to crop
    z1m, z2m, y1m, y2m, x1m, x2m = 0, volume_shape[0], 0, volume_shape[1], 0, volume_shape[2]
    z1, y1, x1 = max(z1o, z1m), max(y1o, y1m), max(x1o, x1m)
    z2, y2, x2 = min(z2o, z2m), min(y2o, y2m), min(x2o, x2m)
    if pad_z:
        pad = [[z1 - z1o, z2o - z2], [y1 - y1o, y2o - y2], [x1 - x1o, x2o - x2]]
    else:
        pad = [[0,0], [y1 - y1o, y2o - y2], [x1 - x1o, x2o - x2]]

    return [z1, z2, y1, y2, x1, x2], pad

def crop_pad_mask_data_3d(data: np.ndarray, bbox_3d: list, mask: np.ndarray = None) -> Union[np.ndarray, Tuple[np.ndarray, list, tuple]]:
    """Crop and pad the 3D volume based on the given bounding box.

    Args:
        data (np.ndarray): the 3D volume.
        bbox_3d (list): the bounding box of the 3D volume.
        mask (np.ndarray): the binary mask of the 3D volume.

    Returns:
        cropped (np.ndarray): the cropped and padded 3D volume.
        bbox (list): the bounding box of the 3D volume.
        pad (tuple): the padding parameters.
    """
    bbox, pad = calculate_crop_pad(bbox_3d, data.shape)

    cropped = data[bbox[0]:bbox[1], bbox[2]:bbox[3], bbox[4]:bbox[5]]

    if mask is not None:
        mask_3d = mask[bbox[0]:bbox[1], bbox[2]:bbox[3], bbox[4]:bbox[5]]
        cropped = cropped * (mask_3d != 0).astype(cropped.dtype)

    if not all(v == 0 for v in pad):
        cropped = np.pad(cropped, pad, mode='constant', constant_values=0)

    return cropped, bbox, pad

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
    out = adjust_image_range(np.stack(tmp, -1)) # shape is (*, 3))
    return out

def visualize(seg: np.ndarray, img: np.ndarray, crop_size_x: int = 148, crop_size_y: int = 148, crop_size_z: int = 16, iterative_bbox: bool = False) -> Union[str, None]:
    ''' Visualize the synapse and EM images in 2D slices.
    
    Args:
        seg (np.ndarray): instance-level segmentation where each synapse is labeled with an individual index.
        img (np.ndarray): the original EM image.
        crop_size_x (int): the size of the 2D patch in x direction.
        crop_size_y (int): the size of the 2D patch in y direction.
        crop_size_z (int): the number of the 2D patches in z direction.
        iterative_bbox (bool): whether to use iterative approach to calculate bounding boxes.
        
    Returns:
        synanno_json (str): the path to the JSON file.
    '''

    item_list = [] # collect all items before appending them to the df

    if synanno.df_metadata.empty:
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
    len_instances = len(synanno.df_metadata) if not synanno.df_metadata.empty else len(instance_list)
    perc = (100)/len_instances 

    # iterate over the synapses. save the middle slices and before/after ones for navigation.
    for i, inst in synanno.df_metadata.iterrows() if not synanno.df_metadata.empty else enumerate(instance_list):

        # retrieve the index of the current synapse
        idx = inst["Image_Index"] if not synanno.df_metadata.empty else inst

        # create the instance specific directories for saving the source and target images
        syn_all, img_all = create_dir(syn_folder, str(idx)), create_dir(img_folder, str(idx))

        # create the binary mask of the current synapse based on the index
        instance_binary_mask = (seg == idx)

        # create a new item for the pandas dataframe
        if synanno.df_metadata.empty:
            item = dict()
            item['Page'] = int(int(idx)//session.get('per_page'))
            item["Image_Index"] = int(idx)
            item["GT"] = "/"+"/".join(syn_all.strip(".\\").split("/")[2:])
            item["EM"] = "/"+"/".join(img_all.strip(".\\").split("/")[2:])
            item["Label"] = "Correct"
            item["Annotated"] = "No"            
            item["Error_Description"] = "None"
        
            # either retrieve the 3D bounding box from the previous iterative generated bb dict or calculate it on individual basis
            bbox = bbox_ND(instance_binary_mask) if iterative_bbox else bbox_dict[idx]

            # update the item with the middle slice and original bounding box
            item["Original_Bbox"] = [int(u) for u in list(bbox)]
            item["Middle_Slice"] = (item["Original_Bbox"][1] + item["Original_Bbox"][0])//2 
            item["cz0"] = (item["Original_Bbox"][1] + item["Original_Bbox"][0])//2 
            item["cy0"] = (item["Original_Bbox"][2] + item["Original_Bbox"][3])//2 
            item["cx0"] = (item["Original_Bbox"][4] + item["Original_Bbox"][5])//2
            item["crop_size_x"] = crop_size_x
            item["crop_size_y"] = crop_size_y
            item["crop_size_z"] = crop_size_z

        else:
            instance_binary_mask = (seg == idx) # binary mask of the current synapse
            bbox = list(map(int,inst["Original_Bbox"]))
            crop_size_x = int(inst["crop_size_x"])
            crop_size_y = int(inst["crop_size_y"])
            crop_size_z = int(inst["crop_size_z"])

        z1, z2 = adjust_bbox(bbox[0], bbox[1], crop_size_z//2) if bbox[1]-bbox[0] < 2 else (bbox[0], bbox[1])
        y1, y2 = adjust_bbox(bbox[2], bbox[3], crop_size_y)
        x1, x2 = adjust_bbox(bbox[4], bbox[5], crop_size_x)
        bbox = [z1, z2, y1, y2, x1, x2]

        cropped_syn, ab_syn, pad_syn = crop_pad_mask_data_3d(seg, bbox, mask=instance_binary_mask)
        cropped_img, ab_img, _ = crop_pad_mask_data_3d(img, bbox)

        # convert the images to uint8
        cropped_img = adjust_image_range(cropped_img)

        assert ab_img == ab_syn, "The bounding boxes of the synapse and EM image do not match."

        if synanno.df_metadata.empty:
            item["Adjusted_Bbox"] = [int(u) for u in list(ab_syn)]
            item["Padding"] = pad_syn
            item_list.append(item)
        else:
            inst["Adjusted_Bbox"] = [int(u) for u in list(ab_syn)]
            inst["Padding"] = pad_syn
            item_list.append(inst)
        
        # create an RGB mask of the synapse from the single channel binary mask
        # colors all even values in the mask with turquoise and all odd values with pink
        vis_label = syn2rgb(cropped_syn) # z, y, x, c

        # save volume slices
        for s in range(cropped_img.shape[0]):
            img_name = str(item["Adjusted_Bbox"][0] + s if synanno.df_metadata.empty else inst["Adjusted_Bbox"][0] + s)+".png"

            img_c = Image.fromarray(cropped_img[s,:,:])
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

    if synanno.df_metadata.empty:
        # write all items to the df
        # convert the list to a data frame
        df_list = pd.DataFrame(item_list)
        # concatenate the metadata and the df_list data frame
        synanno.df_metadata = pd.concat([synanno.df_metadata, df_list], ignore_index=True)
    else:
        for item in item_list:
            # check if the data frame already contains the current instance based on the image index
            if item["Image_Index"] in synanno.df_metadata["Image_Index"].values:
                # assert that the keys in the item and the data frame match
                assert set(item.keys()) == set(synanno.df_metadata.keys()), "The keys in the item and the data frame do not match."
                # update the data frame with the new item
                synanno.df_metadata.loc[synanno.df_metadata["Image_Index"] == item["Image_Index"]] = [pd.Series(item)]
            else:
                df_list = pd.DataFrame([item])
                # concatenate the metadata and the df_list data frame
                synanno.df_metadata = pd.concat([synanno.df_metadata, df_list], ignore_index=True)


def free_page() -> None:
    ''' Remove the segmentation and images from the EM and GT folder for the previous and next page.'''

    # create the handles to the directories
    base_folder = os.path.join(os.path.join(app.config['PACKAGE_NAME'], app.config['STATIC_FOLDER']), 'Images')
    syn_folder, img_folder = os.path.join(base_folder, 'Syn'), os.path.join(base_folder, 'Img')

    # retrieve the image index for all instances that are not labeled as "Correct"
    key_list = synanno.df_metadata.query('Label == "Correct"')["Image_Index"].values.tolist()

    # remove the segmentation and images from the EM and GT folder for the previous and next page.
    for key in key_list:
                
        # remove the segmentation and images from the EM and GT folder for the previous page.
        syn_folder_idx = os.path.join(syn_folder, str(key))
        img_folder_idx = os.path.join(img_folder, str(key))

        if os.path.exists(syn_folder_idx):
            try:
                shutil.rmtree(syn_folder_idx)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (syn_folder_idx, e))
        if os.path.exists(img_folder_idx):
            try:
                shutil.rmtree(img_folder_idx)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (img_folder_idx, e))
    


def visualize_cv_instances(crop_size_x: int = 148, crop_size_y: int = 148, crop_size_z: int = 16, page: int =0, mode: str = 'annotate') -> Union[str, None]:
    ''' Visualize the synapse and EM images in 2D slices for each instance by cropping the bounding box of the instance.
        Processing each instance individually, retrieving them from the cloud volume and saving them to the local disk.
    
    Args:
        crop_size_x (int): the size of the 2D patch in x direction.
        crop_size_y (int): the size of the 2D patch in y direction.
        crop_size_z (int): the size of the 2D patch in z direction.
        page (int): the current page number for which to compute the data.
        
    Returns:
        synanno_json (str): the path to the JSON file.
    '''

    # create the handles to materialization data object
    global materialization

    # set the progress bar to zero
    if page != 0:      
        synanno.progress_bar_status['percent'] = 0
        synanno.progress_bar_status['status'] = f"Loading page {str(page)}."

    if mode == 'annotate':
        page_metadata = synanno.df_metadata.query('Page == @page')
    elif mode == 'draw':
        page_metadata = synanno.df_metadata.query('Label != "Correct"')
    else:
        raise ValueError('The mode should either be \'annotate\' or \'draw\'')

    if page_metadata.empty:
        print(f"Page number {page} does not exists yet in the DataFrame. Generating the page's data.")
        page_exists = False
    else:
        page_metadata = page_metadata.sort_values(by='Image_Index').to_dict('records')  # convert dataframe to list of dicts
        page_exists = True

    # create the directories for saving the source and target images
    idx_dir = create_dir('./synanno/static/', 'Images')
    syn_folder, img_folder = create_dir(idx_dir, 'Syn'), create_dir(idx_dir, 'Img')

    # retrieve the meta data for the synapses associated with the current page
    bbox_dict = get_sub_dict_within_range(materialization, (page * session['per_page']), session['per_page'] + (page * session['per_page']) - 1)

    # collect the instances to only write to the metadata frame once
    if not page_exists:
        instance_list = []

    ### iterate over the synapses. save the middle slices and before/after ones for navigation. ###
    for i, inst in enumerate(bbox_dict.keys() if page_exists is False else page_metadata):
        # retrieve the index of the current synapse
        if page_exists is True:
            idx = inst["Image_Index"]
        else:
            idx = inst

        synanno.progress_bar_status['status'] = f"Inst.{str(idx)}: Calculate bounding box."

        # create the instance specific directories for saving the source and target images
        syn_all, img_all = create_dir(syn_folder, str(idx)), create_dir(img_folder, str(idx))

        # create a new item for the current page
        if page_exists is False:

            # create a new item
            item = dict()
            item["Page"] = int(page)
            item["Image_Index"] = int(idx)
            item["GT"] = "/"+"/".join(syn_all.strip(".\\").split("/")[2:])
            item["EM"] = "/"+"/".join(img_all.strip(".\\").split("/")[2:])
            item["Label"] = "Correct"
            item["Annotated"] = "No"            
            item["Error_Description"] = "None"
            item["Middle_Slice"] = int(bbox_dict[idx]['z'])
            item["cz0"] = int(bbox_dict[idx]['z'])
            item["cy0"] = int(bbox_dict[idx]['y'])
            item["cx0"] = int(bbox_dict[idx]['x'])
            item["crop_size_x"] = crop_size_x
            item["crop_size_y"] = crop_size_y
            item["crop_size_z"] = crop_size_z

    
            # retrieve the bounding box for the current synapse from the central synapse coordinates
            z1 = item["cz0"] - crop_size_z // 2
            z2 = item["cz0"] + crop_size_z // 2
            y1 = item["cy0"] - crop_size_y // 2
            y2 = item["cy0"] + crop_size_y // 2
            x1 = item["cx0"] - crop_size_x // 2
            x2 = item["cx0"] + crop_size_x // 2

            item["Original_Bbox"]  = [z1, z2, y1, y2, x1, x2]

            # retrieve the actual crop coordinates and possible padding based on the max dimensions of the whole cloud volume
            crop_bbox, img_padding = calculate_crop_pad(item["Original_Bbox"] , [synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x])

            item["Adjusted_Bbox"], item["Padding"] = crop_bbox, img_padding
            instance_list.append(item)
            z_mid_total = int(item["Middle_Slice"])
        else:
            crop_bbox = inst['Adjusted_Bbox']
            img_padding = inst['Padding']
            # retrieve the middle slice (relative to the whole volume) for the current synapse
            z_mid_total = int(inst["Middle_Slice"])

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
        
        # Convert coordinate resolution values to integers
        coord_resolution_source = np.array([int(res[0]) for res in synanno.coordinate_order.values()]).astype(int)
        coord_resolution_target = np.array([int(res[1]) for res in synanno.coordinate_order.values()]).astype(int)

        # calculate the scale factor for the source and target cloud volume
        scale = np.where(coord_resolution_target/coord_resolution_source > 0, coord_resolution_target/coord_resolution_source, 1)
        
        # create the bounding box for the current synapse based on the order of the coordinates
        bound_target = Bbox(
            [crop_box_dict[cord_order[i] + '1'] for i in range(3)],
            [crop_box_dict[cord_order[i] + '2'] for i in range(3)]
        )

        # scale the bounding box to the resolution of the source cloud volume
        bound_source = Bbox((bound_target.minpt * scale).astype(int), (bound_target.maxpt * scale).astype(int))

        # retrieve the source and target images from the cloud volume
        cropped_img = synanno.source_cv.download(bound_source, coord_resolution=coord_resolution_source, mip=0)
        cropped_gt = synanno.target_cv.download(bound_target, coord_resolution=coord_resolution_target, mip=0)

        # remove the singleton dimension, take care as the z dimension might be singleton
        cropped_img = cropped_img.squeeze(axis=3)
        cropped_gt = cropped_gt.squeeze(axis=3)

        # adjust the scale of the label volume
        if sum(cropped_img.shape) > sum(cropped_gt.shape): # up-sampling
            cropped_gt = resize(cropped_gt, cropped_img.shape, mode='constant', preserve_range=True, anti_aliasing=False)
            cropped_gt = (cropped_gt > 0.5).astype(int) # convert to binary mask
        elif sum(cropped_img.shape) < sum(cropped_gt.shape): # down-sampling
            cropped_gt = resize(cropped_gt, cropped_img.shape, mode='constant', preserve_range=True, anti_aliasing=True)
            cropped_gt = (cropped_gt > 0.5).astype(int) # convert to binary mask

        # given the six cases xyz, xzy, yxz, yzx, zxy, zyx, we have to permute the axes to match the zyx order
        cropped_img = np.transpose(cropped_img, axes=[cord_order.index('z'), cord_order.index('y'), cord_order.index('x')])
        cropped_gt = np.transpose(cropped_gt, axes=[cord_order.index('z'), cord_order.index('y'), cord_order.index('x')])

        # process the 3D gt segmentation by removing small objects and converting it to instance-level segmentation.
        cropped_seg = process_syn(cropped_gt, view_style='neuron')

        # pad the images and synapse segmentation to fit the crop size (sz)
        cropped_img_pad = np.pad(cropped_img, img_padding, mode='constant', constant_values=148)
        cropped_seg_pad = np.pad(cropped_seg, img_padding, mode='constant', constant_values=0)  
        
        assert cropped_img_pad.shape == cropped_seg_pad.shape, "The shape of the source and target images do not match."

        # create an RGB mask of the synapse from the single channel binary mask
        # colors all non zero values turquoise 
        vis_label = syn2rgb(cropped_seg_pad) # z, y, x, c

        synanno.progress_bar_status['status'] = f"Inst.{str(idx)}: Saving 2D Slices"

        # save volume slices
        for s in range(cropped_img_pad.shape[0]):
            img_name = str(item["Adjusted_Bbox"][0] + s if synanno.df_metadata.empty else inst["Adjusted_Bbox"][0] + s)+".png"

            # image
            img_c = Image.fromarray(adjust_image_range(cropped_img_pad[s,:,:]))
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

    # write the instance list to the dataframe
    if not page_exists:
        # convert the list to a dataframe
        df_list = pd.DataFrame(instance_list)
        # concatenate the metadata and the df_list dataframe
        synanno.df_metadata = pd.concat([synanno.df_metadata, df_list], ignore_index=True)
    
    synanno.progress_bar_status['percent'] = int(100) 


def neuron_centric_3d_data_processing(source_url: str, target_url: str, table_name: str, preid: int = None, postid: int = None, bucket_secret_json: json = '~/.cloudvolume/secrets', crop_size_x: int = 148, crop_size_y: int = 148, crop_size_z: int = 16, mode: str = 'annotate') -> Union[str, Tuple[np.ndarray, np.ndarray]]:
    """ Retrieve the bounding boxes and instances indexes from the table and call the render function to render the 3D data as 2D images.

    Args:
        source_url (str): the url to the source cloud volume (EM).
        target_url (str): the url to the target cloud volume (synapse).
        table_name (str): the path to the JSON file.
        preid (int): the id of the pre synaptic region.
        postid (int): the id of the post synaptic region.
        bucket_secret_json (json): the path to the JSON file.
        patch_size (int): the size of the 2D patch.
    """

    # create the handles to the global materialization data object
    global materialization
    
    # read data as dict from path table_name
    synanno.progress_bar_status['status'] = "Retrieving Materialization"

    # Read the CSV file
    df = pd.read_csv(table_name)

    # Select only the necessary columns
    df = df[['pre_pt_x', 'pre_pt_y', 'pre_pt_z', 'post_pt_x', 'post_pt_y', 'post_pt_z', 'x', 'y', 'z']]

    # Convert the DataFrame to a dictionary
    bbox_dict = df.to_dict('index')

    if preid is None:
        preid = 0

    if postid is None:
        postid = len(df.index)

    # cut the dictionary to the desired number of instances
    bbox_dict = get_sub_dict_within_range(bbox_dict, preid, postid)

    # save the table to the session
    materialization = bbox_dict

    # number of rows in df
    session['n_images'] = len(bbox_dict.keys())

    # calculate the number of pages needed for the instance count in the JSON
    number_pages = session.get('n_images') // session.get('per_page')
    if not (session.get('n_images') % session.get('per_page') == 0):
        number_pages = number_pages + 1

    session['n_pages'] = number_pages

    synanno.progress_bar_status['status'] = "Loading Cloud Volumes"
    synanno.source_cv = CloudVolume(source_url, secrets=bucket_secret_json, fill_missing=True, parallel=True)
    synanno.target_cv = CloudVolume(target_url, secrets=bucket_secret_json, fill_missing=True, parallel=True)

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

    return visualize_cv_instances(crop_size_x=crop_size_x, crop_size_y=crop_size_y, crop_size_z=crop_size_z, page=0, mode=mode)


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

    # retrieve the order of the coordinates (xyz, xzy, yxz, yzx, zxy, zyx)
    coordinate_order = list(synanno.coordinate_order.keys())

    # convert coordinate resolution values to integers
    coord_resolution_source = np.array([int(res[0]) for res in synanno.coordinate_order.values()]).astype(int)
        
    # convert coordinate resolution values to integers
    coord_resolution_target = np.array([int(res[1]) for res in synanno.coordinate_order.values()]).astype(int)

    # calculate the scale factor for the source and target cloud volume
    scale = np.where(coord_resolution_target/coord_resolution_source > 0, coord_resolution_target/coord_resolution_source, 1)

    synanno.progress_bar_status['status'] = "Loading Source Cloud Volume"

    # handle to the source cloud volume
    source = CloudVolume(im_file, secrets=bucket_secret_json, fill_missing=True, parallel=True)

    # should no cropping coordinates be provided, use the whole volume
    if subvolume['x2'] == -1:
        subvolume['x2'] = source.info['scales'][0]['size'][2]

    if subvolume['y2'] == -1:
        subvolume['y2'] = source.info['scales'][0]['size'][1]
    
    if subvolume['z2'] == -1:
        subvolume['z2'] = source.info['scales'][0]['size'][0]

    # create the bounding box for the current synapse based on the order of the coordinates
    bound_target = Bbox(
        [subvolume[coordinate_order[i]+'1'] for i in range(3)],
        [subvolume[coordinate_order[i]+'2'] for i in range(3)]
    )

    # scale the bounding box to the resolution of the source cloud volume
    bound_source = Bbox((bound_target.minpt * scale).astype(int), (bound_target.maxpt * scale).astype(int))

    # retrieve the image subvolume
    img = np.squeeze(source.download(bound_source, coord_resolution=coord_resolution_source, mip=0))

    synanno.progress_bar_status['status'] = "Loading Target Cloud Volume"

    # handle to the target cloud volume
    target = CloudVolume(gt_file, secrets=bucket_secret_json, fill_missing=True, parallel=True)

    # retrieve the image subvolume
    gt = np.squeeze(target.download(bound_target, coord_resolution=coord_resolution_target, mip=0))

    synanno.progress_bar_status['status'] = "Adjust the scale of the label volume"

    # adjust the scale of the label volume
    if sum(img.shape) > sum(gt.shape): # up-sampling
        gt = resize(gt, img.shape, mode='constant', preserve_range=True, anti_aliasing=False)
        gt = (gt > 0.5).astype(int) # convert to binary mask
    elif sum(img.shape) < sum(gt.shape): # down-sampling
        gt = resize(gt, img.shape, mode='constant', preserve_range=True, anti_aliasing=True)
        gt = (gt > 0.5).astype(int) # convert to binary mask
    
    # transpose the image to match the zyx order
    img = np.transpose(img, axes=[coordinate_order.index('z'), coordinate_order.index('y'), coordinate_order.index('x')])

    # transpose the image to match the zyx order
    gt = np.transpose(gt, axes=[coordinate_order.index('z'), coordinate_order.index('y'), coordinate_order.index('x')])

    return img, gt


def view_centric_3d_data_processing(im: np.ndarray, gt: np.ndarray, crop_size_x: int = 148, crop_size_y: int = 148, crop_size_z: int = 16, view_style: str ='view') -> Union[str, Tuple[np.ndarray, np.ndarray]]:
    """ Render the 3D data as 2D images.

    Args:
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
        patch_size (int): the size of the 2D patch.
        view_style (str): the view style of the synapse (view, neuron, synapse).
    
    Returns:
        im (np.ndarray): the original image (EM).
        gt (np.ndarray): the mask annotation (GT: ground truth).
    """

    # retrieve the dimensions of the cropped volume, after the dimension swap
    synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x = tuple([s-1 for s in gt.shape])

    # retrieve the instance level segmentation
    seg = process_syn(gt, view_style=view_style)

    # adjust the datatype of the given data to the smallest possible NG compatible datatype
    seg, _ = adjust_datatype(seg)

    assert seg.shape == gt.shape, "The shape of the segmentation and the ground truth do not match."

    synanno.progress_bar_status['status'] = "Retrieve 2D patches from 3D volume"
    # if a json was provided process the data accordingly
    visualize(seg, im, crop_size_x=crop_size_x, crop_size_y=crop_size_y, crop_size_z=crop_size_z) 
    synanno.progress_bar_status['percent'] = int(100) 
    return im, seg

