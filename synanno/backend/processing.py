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
from typing import Union, Tuple
from collections import OrderedDict

from typing import Union, Tuple
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

from cloudvolume import CloudVolume


# Processing the synpases using binary dilation as well as by removing small objects.
def process_syn(gt: np.ndarray, small_thres: int = 16) -> Tuple[np.ndarray, np.ndarray]:
    """Process the synapses using binary dilation as well as by removing small objects.

    Args:
        gt (np.ndarray): the binary mask of the synapse.
        small_thres (int): the threshold for removing small objects.

    Returns:
        syn (np.ndarray): the binary mask of the synapse.
        seg (np.ndarray): the binary mask of the segmentation.
    """
    indices = np.unique(gt)
    is_semantic = len(indices) == 3 and (indices==[0,1,2]).all()
    if not is_semantic: # already an instance-level segmentation
        syn, seg = gt, (gt.copy() + 1) // 2
        return syn, seg

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        seg = binary_dilation(gt.copy() != 0)
        synanno.progress_bar_status['percent'] = int(8) 

        seg = label_cc(seg).astype(int)
        seg = seg * (gt.copy() != 0).astype(int)
        seg = remove_small_objects(seg, small_thres)
        synanno.progress_bar_status['percent'] = int(12) 

        c2 = (gt.copy() == 2).astype(int)
        c1 = (gt.copy() == 1).astype(int)

        syn_pos = np.clip((seg * 2 - 1), a_min=0, a_max=None) * c1
        syn_neg = (seg * 2) * c2
        syn = np.maximum(syn_pos, syn_neg)
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
        syn (np.ndarray): the binary mask of the synapse.
        seg (np.ndarray): the binary mask of the segmentation.
        img (np.ndarray): the original EM image.
        sz (int): the size of the 2D patch.
        return_data (bool): whether to return the data.
        iterative_bbox (bool): whether to use iterative approach to calculate bounding boxes.
        path_json (str): the path to the JSON file.
        
    Returns:
        synanno_json (str): the path to the JSON file.
    '''
    crop_size = int(sz * 1.415) # considering rotation 

    item_list, data_dict = [], {}

    if path_json is not None:
        item_list = json.load(open(path_json))["Data"]
    else:
        seg_idx = np.unique(seg)[1:] # ignore background
        if not iterative_bbox:
            bbox_dict = index2bbox(seg, seg_idx, iterative=False)
    
    idx_dir = create_dir('./synanno/static/', 'Images')
    syn_folder, img_folder = create_dir(idx_dir, 'Syn'), create_dir(idx_dir, 'Img')

    # specify the list we iterate over (index list or json)
    instance_list = []
    if path_json is not None:
        instance_list = item_list
    else:
        instance_list = seg_idx

    # calculate process time for progess bar
    len_instances = len(instance_list)
    perc = (100)/len_instances 

    # iterate over the synapses. save the middle slices and before/after ones for navigation.
    for i, inst in enumerate(instance_list):

        if path_json is not None:
            idx = inst["Image_Index"]
        else:
            idx = inst

        syn_all, img_all = create_dir(syn_folder, str(idx)), create_dir(img_folder, str(idx))

        temp = (seg == idx) # binary mask of the current synapse

        # create a new item for the JSON file with defaults.
        if path_json is None:
            item = dict()
            item["Image_Index"] = int(idx)
            item["GT"] = "/"+"/".join(syn_all.strip(".\\").split("/")[2:])
            item["EM"] = "/"+"/".join(img_all.strip(".\\").split("/")[2:])
            item["Label"] = "Correct"
            item["Annotated"] = "No"            
            item["Error_Description"] = "None"
        
            
            bbox = bbox_ND(temp) if iterative_bbox else bbox_dict[idx]
                    
            # find the most centric slice that contains foreground
            temp_crop = crop_ND(temp, bbox, end_included=True)
            crop_mid = (temp_crop.shape[0]-1) // 2
            idx_t = np.where(np.any(temp_crop, axis=(1,2)))[0] # index of slices containing True values
            z_mid_relative = idx_t[np.argmin(np.abs(idx_t-crop_mid))]
            z_mid_total = z_mid_relative + bbox[0]

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
            item_list.append(item)
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
        final_file["Data"] = item_list
        json_obj = json.dumps(final_file, indent=4, cls=NpEncoder)

        path_json = os.path.join(app.config['PACKAGE_NAME'], app.config['UPLOAD_FOLDER'])
        name_json = app.config['JSON']

        with open(os.path.join(path_json, name_json), "w") as outfile:
            outfile.write(json_obj)

        synanno_json = os.path.join(path_json, name_json)
        return synanno_json
    else:
        return


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

def load_3d_cloud_volume(im_file: str, gt_file: str, x1: int, x2: int, y1: int, y2: int, z1: int, z2: int, bucket_secret_json: json = '~/.cloudvolume/secrets'):
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
    
    synanno.progress_bar_status['status'] = "Loading Source File"

    print("#"*40)
    print(bucket_secret_json)
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

    # remove the first 128 pixels from the x axis, as they got weirdly shifted by cloudvolume
    img = img[:,:,128:]
    img_np = np.zeros(img.shape).astype(np.uint8)
    img_np[:,:,:] = img[:,:,:]


    synanno.progress_bar_status['status'] = "Loading Target File"

    # handle to cloud volume
    gt = CloudVolume(gt_file, secrets=bucket_secret_json)

    
    gt = np.squeeze(gt[z1:z2, y1:y2, x1:x2])

    # remove the first 128 pixels from the x axis, as they got weirdly shifted by cloudvolume
    gt = gt[:,:,128:]
    gt_np = np.zeros(gt.shape).astype(np.uint8)
    gt_np[:,:,:] = gt[:,:,:]

    return img, gt

def process_3d_data(im: np.ndarray, gt: np.ndarray, patch_size: int = 142, path_json: str = None):

    synanno.progress_bar_status['status'] = "Convert Polarity Prediction to Segmentation"
    if gt.ndim != 3:
        # If the gt is not segmentation mask but predicted polarity, generate
        # the individual synapses using the polarity2instance function from
        # https://github.com/zudi-lin/pytorch_connectomics/blob/master/connectomics/utils/process.py
        assert (gt.ndim == 4 and gt.shape[0] == 3)
        warnings.warn("Converting polarity prediction into segmentation, which can be very slow!")
        scales = (im.shape[0]/gt.shape[1], im.shape[1]/gt.shape[2], im.shape[2]/gt.shape[3])
        gt = polarity2instance(gt.astype(np.uint8), semantic=False, scale_factors=scales)
    synanno.progress_bar_status['percent'] = int(5) 

    # set max dimensions
    synanno.vol_dim_z, synanno.vol_dim_y, synanno.vol_dim_x = tuple([s-1 for s in gt.shape])

    synanno.progress_bar_status['status'] = "Retrive 2D patches from 3D volume"
    # Processing the 3D volume to get 2D patches.
    syn, synanno.target = process_syn(gt)


    synanno.progress_bar_status['status'] = "Render Images"
    
    # if a json was provided process the data accordingly
    if path_json is not None:
        visualize(syn, synanno.target, im, sz=patch_size, path_json=path_json)
        synanno.progress_bar_status['percent'] = int(100) 
        return None, im, gt
    # if no json was provided create a json file and process the data
    else:
        synanno_json = visualize(syn, synanno.target,im, sz=patch_size)
        synanno.progress_bar_status['percent'] = int(100) 
        if os.path.isfile(synanno_json):
            return synanno_json, im, gt
        else:
            # the json file should have been created by the visualize function
            raise FileNotFoundError(
                errno.ENOENT, os.strerror(errno.ENOENT), 'synAnno.json')

