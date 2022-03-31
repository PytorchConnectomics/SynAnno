from __future__ import print_function, division
from typing import Optional, List, Union

import os
import cv2
import h5py
import json
import glob
import imageio
import numpy as np
from skimage.measure import label
from skimage.transform import resize
from skimage.morphology import dilation
from skimage.morphology import remove_small_objects


class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


def readh5(filename, dataset=None):
    fid = h5py.File(filename, 'r')
    if dataset is None:
        # load the first dataset in the h5 file
        dataset = list(fid)[0]
    return np.array(fid[dataset])


def readimgs(filename):
    filelist = sorted(glob.glob(filename))
    num_imgs = len(filelist)

    # decide numpy array shape:
    img = imageio.imread(filelist[0])
    data = np.zeros((num_imgs, img.shape[0], img.shape[1]), dtype=np.uint8)
    data[0] = img

    # load all images
    if num_imgs > 1:
        for i in range(1, num_imgs):
            data[i] = imageio.imread(filelist[i])

    return data


def readvol(filename: str, dataset: Optional[str]=None, drop_channel: bool=False):
    r"""Load volumetric data in HDF5, TIFF or PNG formats.
    """
    img_suf = filename[filename.rfind('.')+1:]
    if img_suf in ['h5', 'hdf5']:
        data = readh5(filename, dataset)
    elif 'tif' in img_suf:
        data = imageio.volread(filename).squeeze()
        if data.ndim == 4:
            # convert (z,c,y,x) to (c,z,y,x) order
            data = data.transpose(1,0,2,3)
    elif 'png' in img_suf:
        data = readimgs(filename)
        if data.ndim == 4:
            # convert (z,y,x,c) to (c,z,y,x) order
            data = data.transpose(3,0,1,2)
    else:
        raise ValueError('unrecognizable file format for %s' % (filename))

    assert data.ndim in [3, 4], "Currently supported volume data should " + \
        "be 3D (z,y,x) or 4D (c,z,y,x), got {}D".format(data.ndim)
    if drop_channel and data.ndim == 4:
        # merge multiple channels to grayscale by average
        orig_dtype = data.dtype
        data = np.mean(data, axis=0).astype(orig_dtype)
 
    return data


def writeh5(filename, dtarray, dataset='main'):
    fid = h5py.File(filename, 'w')
    if isinstance(dataset, (list,)):
        for i, dd in enumerate(dataset):
            ds = fid.create_dataset(
                dd, dtarray[i].shape, compression="gzip", dtype=dtarray[i].dtype)
            ds[:] = dtarray[i]
    else:
        ds = fid.create_dataset(dataset, dtarray.shape,
                                compression="gzip", dtype=dtarray.dtype)
        ds[:] = dtarray
    fid.close()
    

def mkdir(folder_name):
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)


def writetxt(filename, content):
    a= open(filename,'w')
    if isinstance(content, (list,)):
        for ll in content:
            a.write(ll)
            if '\n' not in ll:
                a.write('\n')
    else:
        a.write(content)
    a.close()


def readtxt(filename):
    a= open(filename)
    content = a.readlines()
    a.close()
    return content


def rotateIm(image, angle, center=None, scale=1.0, 
             target_type: str = 'img'):
    if angle == 0:
        return image

    interpolation = {'img': cv2.INTER_LINEAR,
                     'mask': cv2.INTER_NEAREST}
    assert image.dtype == np.float32
    (h, w) = image.shape[:2]
    if center is None:
        center = (w // 2, h // 2)

    # perform the rotation
    M = cv2.getRotationMatrix2D(center, angle, scale)
    rotated = cv2.warpAffine(
        image, M, (h, w), 1.0, borderMode=cv2.BORDER_CONSTANT,
        flags=interpolation[target_type]
    )
    return rotated


def rotateIm_polarity(image, label, angle, center=None, scale=1.0):
    rotated = rotateIm(label, angle, center, scale, target_type='mask')
    pos = np.logical_and((rotated % 2) == 1, rotated > 0)
    neg = np.logical_and((rotated % 2) == 0, rotated > 0)
    pos_coord = np.where(pos!=0)
    neg_coord = np.where(neg!=0)
    pos_center = pos_coord[1].mean() if len(pos_coord[1]) >= 1 else None
    neg_center = neg_coord[1].mean() if len(neg_coord[1]) >= 1 else None

    if (pos_center is not None) and (neg_center is not None) and (pos_center > neg_center):
        rotated = np.rot90(rotated, 2, axes=(0, 1))
        angle = angle-180 if angle >= 0 else angle+180

    rotated_image = rotateIm(image, angle, center, scale, target_type='img')
    return rotated_image, rotated, angle


def center_crop(image, out_size):
    if isinstance(out_size, int):
        out_size = (out_size, out_size)

    # channel-last image in (h, w, c) format
    assert image.ndim in [2, 3]
    h, w = image.shape[:2]
    assert h >= out_size[0] and w >= out_size[1]
    margin_h = int((h - out_size[0]) // 2)
    margin_w = int((w - out_size[1]) // 2)

    h0, h1 = margin_h, margin_h + out_size[0]
    w0, w1 = margin_w, margin_w + out_size[1]
    return image[h0:h1, w0:w1]


# Post-processing functions for synaptic polarity model outputs as described
# in "Two-Stream Active Query Suggestion for Active Learning in Connectomics
# (ECCV 2020, https://zudi-lin.github.io/projects/#two_stream_active)".
def polarity2instance(volume, thres=0.5, thres_small=128,
                      scale_factors=(1.0, 1.0, 1.0), semantic=False):
    r"""From synaptic polarity prediction to instance masks via connected-component
    labeling. The input volume should be a 3-channel probability map of shape :math:`(C, Z, Y, X)`
    where :math:`C=3`, representing pre-synaptic region, post-synaptic region and their
    union, respectively.
    Note:
        For each pair of pre- and post-synaptic segmentation, the decoding function will
        annotate pre-synaptic region as :math:`2n-1` and post-synaptic region as :math:`2n`,
        for :math:`n>0`. If :attr:`semantic=True`, all pre-synaptic pixels are labeled with
        while all post-synaptic pixels are labeled with 2. Both kinds of annotation are compatible
        with the ``TARGET_OPT: ['1']`` configuration in training.
    Note:
        The number of pre- and post-synaptic segments will be reported when setting :attr:`semantic=False`.
        Note that the numbers can be different due to either incomplete syanpses touching the volume borders,
        or errors in the prediction. We thus make a conservative estimate of the total number of synapses
        by using the relatively small number among the two.
    Args:
        volume (numpy.ndarray): 3-channel probability map of shape :math:`(3, Z, Y, X)`.
        thres (float): probability threshold of foreground. Default: 0.5
        thres_small (int): size threshold of small objects to remove. Default: 128
        scale_factors (tuple): scale factors for resizing the output volume in :math:`(Z, Y, X)` order. Default: :math:`(1.0, 1.0, 1.0)`
        semantic (bool): return only the semantic mask of pre- and post-synaptic regions. Default: False
    Examples::
        >>> from connectomics.data.utils import readvol, savevol
        >>> from connectomics.utils.processing import polarity2instance
        >>> volume = readvol(input_name)
        >>> instances = polarity2instance(volume)
        >>> savevol(output_name, instances)
    """
    thres = int(255.0 * thres)
    temp = (volume > thres).astype(np.uint8)

    syn_pre = temp[0] * temp[2]
    syn_pre = remove_small_objects(syn_pre,
                min_size=thres_small, connectivity=1)
    syn_post = temp[1] * temp[2]
    syn_post = remove_small_objects(syn_post,
                min_size=thres_small, connectivity=1)

    if semantic:
        # Generate only the semantic mask. The pre-synaptic region is labeled
        # with 1, while the post-synaptic region is labeled with 2.
        segm = np.maximum(syn_pre.astype(np.uint8),
                          syn_post.astype(np.uint8) * 2)

    else:
        # Generate the instance mask.
        foreground = dilation(temp[2].copy(), np.ones((1,5,5)))
        foreground = label(foreground)

        # Since non-zero pixels in seg_pos and seg_neg are subsets of temp[2],
        # they are naturally subsets of non-zero pixels in foreground.
        seg_pre = (foreground*2 - 1) * syn_pre.astype(foreground.dtype)
        seg_post = (foreground*2) * syn_post.astype(foreground.dtype)
        segm = np.maximum(seg_pre, seg_post)

        # Report the number of synapses
        num_syn_pre = len(np.unique(seg_pre))-1
        num_syn_post = len(np.unique(seg_post))-1
        num_syn = min(num_syn_pre, num_syn_post) # a conservative estimate
        print("Stats: found %d pre- and %d post-" % (num_syn_pre, num_syn_post) +
              "synaptic segments in the volume")
        print("There are %d synapses under a conservative estimate." % num_syn)

    # resize the segmentation based on specified scale factors
    if not all(x==1.0 for x in scale_factors):
        target_size = (int(segm.shape[0]*scale_factors[0]),
                       int(segm.shape[1]*scale_factors[1]),
                       int(segm.shape[2]*scale_factors[2]))
        segm = resize(segm, target_size, order=0, anti_aliasing=False, preserve_range=True)

    return cast2dtype(segm)


def cast2dtype(segm):
    """Cast the segmentation mask to the best dtype to save storage.
    """
    max_id = np.amax(np.unique(segm))
    m_type = getSegType(int(max_id))
    return segm.astype(m_type)


def getSegType(mid):
    # reduce the label dtype
    m_type = np.uint64
    if mid < 2**8:
        m_type = np.uint8
    elif mid < 2**16:
        m_type = np.uint16
    elif mid < 2**32:
        m_type = np.uint32
    return m_type
