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