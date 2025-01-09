from flask import Blueprint
from flask import current_app
import os
from flask import request
from glob import glob

# open, resize and transform images
from PIL import Image
import numpy as np

# define a Blueprint for manual_annotate routes
# blueprint = Blueprint("auto_annotate", __name__)


# @blueprint.route("/auto_annotate", methods=["POST"])
def auto_annotate() -> dict[str, object]:
    """Serves an Ajax request from draw.js, downloading, converting, and saving
    the canvas as image.

    Return:
        Passes the instance specific session information as JSON to draw.js
    """
    # page = int(request.form["page"])
    # index = int(request.form["data_id"])

    # static_folder = os.path.join(current_app.root_path, current_app.config["STATIC_FOLDER"])
    static_folder = "/Users/lando/Code/SynAnno/synanno/static/"
    image_folder = os.path.join(static_folder, "Images/")
    img_folder = os.path.join(image_folder, "Img/")
    mask_folder = os.path.join(image_folder, "Mask/")

    mask_sub_folder = os.path.join(mask_folder, str(2))
    curve_masks_path = glob(mask_sub_folder + "/curve_*.png")

    img_sub_folder = os.path.join(img_folder, str(2))
    img_path = glob(img_sub_folder + "/*.png")

    # sort both images and masks to ensure they are in the same order
    curve_masks_path.sort()
    img_path.sort()

    map_slice_to_idx = {}

    img_np_3d = np.ndarray

    image_np_list = []

    for i, img_path in enumerate(img_path):
        folder_name = img_path.split("/")[-1]
        map_slice_to_idx[folder_name.split(".")[0]] = i

        img = Image.open(img_path)

        image_np_list.append(np.array(img))

    img_np_3d = np.stack(image_np_list, axis=0)

    mask_np_3d = np.zeros_like(img_np_3d)

    for mask_path in curve_masks_path:
        print(map_slice_to_idx)

        folder_name = mask_path.split("/")[-1]
        img_slice = folder_name.split("_")[4]

        mask = Image.open(mask_path)
        binary_mask = np.array(mask)[:, :, 0] > 0
        mask_np_3d[map_slice_to_idx[img_slice], :, :] = binary_mask

    sample = np.stack([img_np_3d, mask_np_3d], axis=0)
    print(sample.shape)


if __name__ == "__main__":
    auto_annotate()
