import numpy as np

CONFIG = {
    "source_bucket_url": "gs://h01-release/data/20210601/4nm_raw",
    "target_bucket_url": "gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol",
    "materialization_csv": "/mmfs1/data/lauenbur/synapse-export_000000000000.csv",
    "cv_secret": "/mmfs1/data/lauenbur/secrets",
    "coordinate_order": ["x", "y", "z"],
    "coord_resolution_target": np.array([8, 8, 33]),
    "coord_resolution_source": np.array([4, 4, 33]),
}

UNET3D_CONFIG = {
    "in_channels": 2,
    "out_channels": 1,
    "bilinear": True,
    "features": [32, 64, 96, 128, 256],
}

DATASET_CONFIG = {
    "num_pools": 50,
    "maxsize": 50,
    "max_workers": 8,
    "timeout": 15,
    "resize_depth": 16,
    "resize_height": 256,
    "resize_width": 256,
    "crop_size_x": 256,
    "crop_size_y": 256,
    "crop_size_z": 16,
    "slices_to_generate": 3,
    "target_range": (0, 15),
}

TRAINING_CONFIG = {
    "batch_size": 4,
    "num_workers": 4,
    "pos_weight": 4.0,
    "learning_rate": 1e-4,
    "scheduler_step_size": 10,
    "schedular_gamma": 0.1,
    "num_epochs": 5,
    "patience": 5,
    "train_range": (0, 16),
    "val_range": (16, 20),
    "test_range": (3, 4),
    "checkpoints": "/mmfs1/data/lauenbur/syn_anno_checkpoints/",
}
