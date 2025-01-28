import fastavro
import pandas as pd
from tqdm import tqdm
from typing import Optional, Any


def safe_int(value: Optional[Any]) -> int:
    """Safely convert a value to an integer, replacing None with -1.

    Args:
        value (Optional[Any]): The value to be converted.

    Returns:
        int: The converted integer, or -1 if the value is None.
    """
    return int(value) if value is not None else -1


def initialize_csv(output_csv_path: str):
    """Initialize the output CSV file with headers.

    Args:
        output_csv_path (str): Path to the output CSV file.
    """
    headers = "pre_pt_x,pre_pt_y,pre_pt_z,post_pt_x,post_pt_y,post_pt_z,x,y,z,pre_neuron_id,post_neuron_id\n"
    with open(output_csv_path, "w") as f:
        f.write(headers)


def list_avro_files(avro_dir_path: str) -> list[str]:
    """List all Avro files in the given directory.

    Args:
        avro_dir_path (str): Path to the directory containing Avro files.

    Returns:
        list[str]: List of Avro file names.
    """
    return [f for f in os.listdir(avro_dir_path) if f.endswith(".avro") or "." not in f]


def load_avro_records(avro_file_path: str) -> list[dict[str, Any]]:
    """Load records from an Avro file.

    Args:
        avro_file_path (str): Path to the Avro file.

    Returns:
        list[dict[str, Any]]: List of records loaded from the Avro file.
    """
    with open(avro_file_path, "rb") as f:
        reader = fastavro.reader(f)
        return list(reader)


def process_avro_file(avro_file_path: str, output_csv_path: str):
    """Process a single Avro file and append data to the output CSV.

    Args:
        avro_file_path (str): Path to the Avro file.
        output_csv_path (str): Path to the output CSV file.
    """
    # Load Avro records into a DataFrame
    records = load_avro_records(avro_file_path)
    df = pd.DataFrame(records)

    # Extract relevant fields and construct the materialization data
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
        "pre_neuron_id": df["pre_synaptic_site"].progress_apply(
            lambda x: safe_int(x.get("neuron_id"))
        ),
        "post_neuron_id": df["post_synaptic_partner"].progress_apply(
            lambda x: safe_int(x.get("neuron_id"))
        ),
    }

    # Create the materialization DataFrame
    materialization_df = pd.DataFrame(materialization_data)

    # Append to the output CSV
    materialization_df.to_csv(output_csv_path, mode="a", header=False, index=False)


def process_avro_files(avro_dir_path: str, output_csv_path: str):
    """Process all Avro files in the specified directory.

    Args:
        avro_dir_path (str): Path to the directory containing Avro files.
        output_csv_path (str): Path to the output CSV file.
    """
    # Initialize tqdm for pandas apply
    tqdm.pandas()

    # Initialize the CSV file
    initialize_csv(output_csv_path)

    # List Avro files
    avro_files = list_avro_files(avro_dir_path)

    # Process each Avro file
    for avro_file in tqdm(avro_files, desc="Processing Avro Files"):
        avro_file_path = os.path.join(avro_dir_path, avro_file)
        process_avro_file(avro_file_path, output_csv_path)

    print(f"Materialization table saved to {output_csv_path}")


if __name__ == "__main__":
    # Path to the folder containing Avro files
    avro_dir_path = "PATH_TO_FOLDER"

    # Path to the output CSV file
    output_csv_path = "synapse-export_combined.csv"

    # Process all Avro files
    process_avro_files(avro_dir_path, output_csv_path)
