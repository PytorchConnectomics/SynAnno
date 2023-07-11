from __future__ import print_function, division
from typing import Optional, List, Union, Dict

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

def get_sub_dict_within_range(dictionary: Dict, start_key: int, end_key: int) -> Dict:
    return {key: value for key, value in dictionary.items() if start_key <= int(key) <= end_key}