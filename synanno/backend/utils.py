import io
import json
import logging
from typing import Tuple

import numpy as np
from PIL import Image

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)


class NpEncoder(json.JSONEncoder):
    """Encoder for numpy data types.

    Args:
        json (json.JSONEncoder): JSON encoder.

    Returns:
        json.JSONEncoder: JSON encoder.

    Inspired by:
        https://stackoverflow.com/questions/50916422/python-typeerror-object-of-type-int64-is-not-json-serializable # noqa: E501
    """

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NpEncoder, self).default(obj)


def adjust_image_range(image: np.ndarray) -> np.ndarray:
    """Adjust the range of the given image to 0-255.

    Args:
        image: Image to be adjusted.

    Returns:
        Adjusted image.
    """
    if np.max(image) > 1:
        # image is in 0-255 range, convert to np.uint8 directly
        return image.astype(np.uint8)
    else:
        # image is in 0-1 range, scale to 0-255 and then convert to np.uint8
        return (image * 255).astype(np.uint8)


def adjust_datatype(data: np.ndarray) -> Tuple[np.ndarray, str]:
    """Adjust the datatype of the data to the smallest possible NG compatible datatype.

    Args:
        data: Data to be adjusted.

    Returns:
        Adjusted data and its datatype.
    """
    max_val = np.max(data)
    if max_val <= np.iinfo(np.uint8).max:
        return data.astype(np.uint8), "uint8"
    elif max_val <= np.iinfo(np.uint16).max:
        return data.astype(np.uint16), "uint16"
    elif max_val <= np.iinfo(np.uint32).max:
        return data.astype(np.uint32), "uint32"
    else:
        return data.astype(np.uint64), "uint64"


def draw_cylinder(
    image: np.ndarray,
    center_x: int,
    center_y: int,
    center_z: int,
    radius: int,
    color_main: Tuple[int, int, int],
    color_sub: Tuple[int, int, int],
    layout: list[str],
) -> np.ndarray:
    """
    Function to draw a cylinder in a 4D numpy array.

    The color of the cylinder changes based on the distance from the center_z.

    Args:
        image: Input 4D numpy array.
        center_x: X-coordinate of the cylinder center.
        center_y: Y-coordinate of the cylinder center.
        center_z: Z-coordinate of the cylinder center.
        radius: Radius of the cylinder.
        color_main: RGB color of the circle in the center_z layer.
        color_sub: RGB color of the circles in the other layers.
        layout: The layout of the axes, for example, "zyxc".

    Returns:
        4D numpy array with the cylinder drawn.
    """

    # Find the index for each coordinate in the image shape based on the provided layout
    z_index = layout.index("z")
    y_index = layout.index("y")
    x_index = layout.index("x")

    # Get the lengths along each axis
    z_len = image.shape[z_index]
    y_len = image.shape[y_index]
    x_len = image.shape[x_index]

    # Create coordinate grid
    Y, X = np.meshgrid(np.arange(y_len), np.arange(x_len), indexing="ij")

    # Create 3D mask for the cylinder
    mask_cylinder = (X - center_x) ** 2 + (Y - center_y) ** 2 <= radius**2

    # Use a list of slices to index the array dynamically
    slice_list = [slice(None)] * 4

    for i in range(z_len):
        slice_list[z_index] = i
        if i != center_z:
            slice_list[y_index], slice_list[x_index] = (
                np.where(mask_cylinder),
                np.where(mask_cylinder)[1],
            )
            image[tuple(slice_list)] = color_sub
        else:
            slice_list[y_index], slice_list[x_index] = (
                np.where(mask_cylinder),
                np.where(mask_cylinder)[1],
            )
            image[tuple(slice_list)] = color_main

    return image


def img_to_png_bytes(img: np.ndarray) -> bytes:
    """Convert a NumPy array to PNG byte data."""

    # Convert NumPy array to PIL Image if not already
    if not isinstance(img, Image.Image):
        img = Image.fromarray(img)
    img_io = io.BytesIO()
    img.save(img_io, format="PNG")  # Save as PNG into memory
    img_io.seek(0)  # Reset stream position
    return img_io.getvalue()  # Return byte data


def png_bytes_to_pil_img(png_bytes: bytes) -> np.ndarray:
    """Convert PNG byte data back to a NumPy array."""
    img_io = io.BytesIO(png_bytes)  # Convert bytes to BytesIO object
    img = Image.open(img_io)  # Open as PIL Image
    return img  # Convert back to NumPy array
