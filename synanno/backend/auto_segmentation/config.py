import numpy as np

CONFIG = {
    "source_bucket_url": "gs://h01-release/data/20210601/4nm_raw",
    "target_bucket_url": "gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol",
    "cv_secret": "~/.cloudvolume/secrets",
    "target_dir": "/content/drive/My Drive/SynAnno/",
    "coordinate_order": ["x", "y", "z"],
    "coord_resolution_target": np.array([8, 8, 33]),
    "coord_resolution_source": np.array([4, 4, 33]),
    "crop_size_x": 256,
    "crop_size_y": 256,
    "crop_size_z": 16,
    "slices_to_generate": 3,
    "target_range": (0, 15),
    "unet3d": {
        "in_channels": 2,
        "out_channels": 1,
        "bilinear": True,
        "features": [32, 64, 96, 128, 256],
    },
    "dataset": {
        "num_pools": 50,
        "maxsize": 50,
        "max_workers": 8,
        "timeout": 15,
        "resize_depth": 16,
        "resize_height": 256,
        "resize_width": 256,
    },
}
