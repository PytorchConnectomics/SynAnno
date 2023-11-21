import sys
import os

repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, repo_root)

from synanno.backend.data_generator import SynANNODataset

if __name__ == "__main__":
    n_instances = 200  # Replace with desired number of instances
    bucket_secret = "/home/leander_lauenburg/SynAnno/secrets/google-cloud.json"
    materialization = (
        "/home/leander_lauenburg/SynAnno/h01/synapse-export_000000000000.csv"
    )
    source_url = "gs://h01-release/data/20210601/4nm_raw"
    target_url = "gs://h01-release/data/20210729/c3/synapses/whole_ei_onlyvol"
    local_dir = "gs://synanno/data"
    crop_sizes = {"crop_size_x": 128, "crop_size_y": 128, "crop_size_z": 16}

    dataset = SynANNODataset(
        materialization_table_path=materialization,
        source_url=source_url,
        target_url=target_url,
        bucket_secret_json_path=bucket_secret,
        local_dir=local_dir,
        crop_sizes=crop_sizes,
    )
