# 3D UNet Data Generator for Auto-Depthwise Segmentation

## Overview

The automated segmentation of instances in SynAnno is critically dependent on a robust 3D UNet model that can generalize across various data inputs. The model is trained on a dataset that mirrors the real-world variations in segmentation tasks. To this end, the data generator script creates a diverse and representative dataset for training, ensuring the model accurately handles instances with different slice counts. The script performs the following steps:

1. **Data Collection and Curation**:
   - Randomly selects n instances from the materialization table to encompass a broad range of variations.
   - Extracts corresponding subvolumes from both the raw source data and the target volume.

2. **Data Augmentation**:
   - Generates multiple segmentation scenarios for each selected instance by maintaining one or more seed segmentation layers and setting most slices in the target volumes to zero.
   - Implements a probability model to determine which slices to retain, favoring central slices and varying the number of slices kept.

## Cloud Integration

This tool seamlessly integrates with Google Cloud Platform (GCP) for data storage, processing, and retrieval, enhancing scalability and accessibility. For more details, see the [Data Generator GCP Documentation](DATA_GENERATOR_GCP.md).

## Data

### Source and Target Volume

- The dataset originates from the H01 dataset, containing 3D synaptic data from the Drosophila brain. The source volume refers to the raw data, while the target volume consists of the corresponding segmentation data.
- The data is stored in GCP cloud buckets and accessed using the CloudVolume library.
- The script downloads sub-volumes from both source and target volumes based on instance coordinates in the materialization table. These sub-volumes are then processed and augmented to create training data.

### Outputted Data

The data generator script produces the following data:

- **Target Subvolumes**: These are downloaded from the target volume using instance coordinates from the materialization table and stored locally.
- **Augmented Target Subvolumes**: Target subvolumes are augmented by zeroing most slices while preserving one or more seed segmentation layers. The number of slices retained is based on a probability model that prefers central slices.
- **Scaled Source Subvolumes**: Subvolumes from the source volume are downloaded and scaled to match the dimensions of the source volume, based on instance coordinates in the materialization table.
- **Metadata**: Includes essential information about volume dimensions, scaling factors, and other relevant analytical details.

## Structure and Inner Workings

### Data Generator Module (`data_generator.py`)

1. **Cloud Interaction Functions**: Manages the upload and download of numpy array data to and from GCP buckets.
2. **Data Processing Functions**: Involves selecting random data instances, connecting to cloud volumes, downloading subvolumes, and generating training data.
3. **Utility Functions**: Provides capabilities such as constructing bounding boxes, applying padding, and augmenting target volumes.
4. **Visualization Utility**: Aids in the quick assessment and verification of data through various visualization methods.

### Main Execution Script (`main_data_generator_gcp.py`)

- Coordinates the overall data generation process utilizing functions from `data_generator.py`.
- Configures necessary parameters for cloud connections, volume metadata calculations, and outlines configurations for downloading and processing subvolumes.
- Facilitates the process from data selection to the creation of training data.

## Installation and Setup

1. **Environment Setup**: Prepare the pipenv as detailed in the [Main README](../../README.md).
2. **Cloud Configuration**: Ensure proper setup of your GCP environment, including access rights and bucket configurations, or enable LOCAL_RUN in the script for local execution.
3. **Secrets and Paths**: Update the script with accurate paths for your GCP secrets and data materialization files.

## Usage

1. **Parameter Configuration**: Customize the `main_data_generator_gcp.py` script to specify the desired number of instances, cloud URLs, and local directory paths.
2. **Execution**: Run the script in a Python environment.
3. **Output Verification**: Check the designated local or cloud directory for the processed data.
