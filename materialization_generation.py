import fastavro
import pandas as pd
from tqdm import tqdm
import os

# initialize tqdm for pandas apply
tqdm.pandas()

# insert path to folder with precomputer ng files
avro_dir_path = "PATH_TO_FOLDER"


# safe conversion function to handle NoneType for neuron_id
def safe_int(value):
    return int(value) if value is not None else -1  # replace None with -1


# output CSV path
output_csv_path = "synapse-export_combined.csv"

# initialize the CSV file with headers
with open(output_csv_path, "w") as f:
    f.write(
        "pre_pt_x,pre_pt_y,pre_pt_z,post_pt_x,post_pt_y,post_pt_z,x,y,z,pre_neuron_id,post_neuron_id\n"
    )

# list all Avro files in the directory
avro_files = [
    f for f in os.listdir(avro_dir_path) if f.endswith(".avro") or "." not in f
]

# process each Avro file in the directory with a parent tqdm bar
for avro_file in tqdm(avro_files, desc="Processing Avro Files"):
    avro_file_path = os.path.join(avro_dir_path, avro_file)

    # open and read the Avro file into a DataFrame
    with open(avro_file_path, "rb") as f:
        reader = fastavro.reader(f)
        records = list(
            tqdm(reader, desc=f"Loading Avro Records from {avro_file}", leave=False)
        )

    # convert the Avro records to a DataFrame
    df = pd.DataFrame(records)

    # extract relevant fields and construct the materialization table with progress
    materialization_data = {
        "pre_pt_x": df["pre_synaptic_site"].progress_apply(
            lambda x: int(x["centroid"]["x"])
        ),
        "pre_pt_y": df["pre_synaptic_site"].progress_apply(
            lambda x: int(x["centroid"]["y"])
        ),
        "pre_pt_z": df["pre_synaptic_site"].progress_apply(
            lambda x: int(x["centroid"]["z"])
        ),
        "post_pt_x": df["post_synaptic_partner"].progress_apply(
            lambda x: int(x["centroid"]["x"])
        ),
        "post_pt_y": df["post_synaptic_partner"].progress_apply(
            lambda x: int(x["centroid"]["y"])
        ),
        "post_pt_z": df["post_synaptic_partner"].progress_apply(
            lambda x: int(x["centroid"]["z"])
        ),
        "x": df["location"].progress_apply(lambda x: int(x["x"])),
        "y": df["location"].progress_apply(lambda x: int(x["y"])),
        "z": df["location"].progress_apply(lambda x: int(x["z"])),
        # apply safe conversion for neuron IDs
        "pre_neuron_id": df["pre_synaptic_site"].progress_apply(
            lambda x: safe_int(x.get("neuron_id"))
        ),
        "post_neuron_id": df["post_synaptic_partner"].progress_apply(
            lambda x: safe_int(x.get("neuron_id"))
        ),
    }

    # create the updated materialization DataFrame
    materialization_df = pd.DataFrame(materialization_data)

    # append to CSV with progress bar
    materialization_df.to_csv(output_csv_path, mode="a", header=False, index=False)

    # clear the DataFrame to free up memory
    del df
    del materialization_df

print(f"Materialization table saved to {output_csv_path}")
