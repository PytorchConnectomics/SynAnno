import sys
import os

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, repo_root)

from synanno.backend.data_generator import (
    select_random_instances,
    connect_to_cloudvolumes,
    download_subvolumes,
    generate_training_data,
    cloudvolume_metadata,
)


if __name__ == "__main__":
    n_instances = 200  # Replace with desired number of instances
    bucket_secret = "/home/leander_lauenburg/SynAnno/secrets/google-cloud.json"
    materialization = (
        "/home/leander_lauenburg/SynAnno/h01/synapse-export_000000000000.csv"
    )
    source_url = "gs://h01-release/data/20210601/4nm_raw"
    target_url = "gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol"
    local_dir = "gs://synanno/data"

    random_instance_keys, bbox_dict = select_random_instances(
        n_instances, materialization
    )
    source_cv, target_cv = connect_to_cloudvolumes(
        source_url, target_url, bucket_secret
    )

    print(source_cv.info)
    print(target_cv.info)

    vol_dim, vol_dim_scaled, scale = cloudvolume_metadata(
        source_cv, target_cv, ["x", "y", "z"], ["4", "4", "33"], ["8", "8", "33"]
    )

    print(vol_dim, vol_dim_scaled, scale)

    download_subvolumes(
        random_instance_keys,
        source_cv,
        target_cv,
        local_dir,
        bbox_dict,
        ["x", "y", "z"],
        {"crop_size_x": 128, "crop_size_y": 128, "crop_size_z": 16},
        {c: v for c, v in zip(["x", "y", "z"], vol_dim)},
        scale,
    )

    generate_training_data(
        random_instance_keys,
        bbox_dict,
        local_dir,
        coordinate_order=["x", "y", "z"],
        crop_size_z=16,
    )
