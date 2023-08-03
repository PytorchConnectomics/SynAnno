from __future__ import print_function, division
from typing import Dict

import os
import json
import numpy as np


class NpEncoder(json.JSONEncoder):
    """Encoder for numpy data types.

    Args:
        json (json.JSONEncoder): JSON encoder.

    Returns:
        json.JSONEncoder: JSON encoder.

    Inspired by: https://stackoverflow.com/questions/50916422/python-typeerror-object-of-type-int64-is-not-json-serializable
    """
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)
    
def adjust_image_range(image):
    """Adjust the range of the given image to 0-255.

    Args:
        image (np.ndarray): Image to be adjusted.

    Returns:
        np.ndarray: Adjusted image.
    """
    if np.max(image) > 1:
        # image is in 0-255 range, convert to np.uint8 directly
        return image.astype(np.uint8)
    else:
        # image is in 0-1 range, scale to 0-255 and then convert to np.uint8
        return (image * 255).astype(np.uint8)

def adjust_datatype(data):
    """Adjust the datatype of the given data to the smallest possible NG compatible datatype.
    
    Args:
        data (np.ndarray): Data to be adjusted.
        
    Returns:
        np.ndarray: Adjusted data.
        str: Datatype of the adjusted data.
    """
    max_val = np.max(data)
    if max_val <= np.iinfo(np.uint8).max:
        return data.astype(np.uint8), 'uint8'
    elif max_val <= np.iinfo(np.uint16).max:
        return data.astype(np.uint16), 'uint16'
    elif max_val <= np.iinfo(np.uint32).max:
        return data.astype(np.uint32), 'uint32'
    else:
        return data.astype(np.uint64), 'uint64'

def mkdir(folder_name):
    """Create a folder if it does not exist.

    Args:
        folder_name (str): Name of the folder to be created.
    """
    if not os.path.exists(folder_name):
        os.mkdir(folder_name)

def get_sub_dict_within_range(dictionary: Dict, start_key: int, end_key: int) -> Dict:
    """Get a sub-dictionary of the given dictionary within the given key range.

    Args:
        dictionary (Dict): Dictionary to be sliced.
        start_key (int): Start key of the sub-dictionary.
        end_key (int): End key of the sub-dictionary.

    Returns:
        Dict: Sub-dictionary within the given key range.
    """
    return {key: value for key, value in dictionary.items() if start_key <= int(key) <= end_key}