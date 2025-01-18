#!/bin/bash
#SBATCH --job-name=synanno_setup_and_training  # Job name
#SBATCH --nodes=1                             # Number of nodes
#SBATCH --ntasks=1                            # Number of tasks
#SBATCH --cpus-per-task=4                     # Number of CPU cores per task
#SBATCH --gpus-per-task=1                     # Number of GPUs per task
#SBATCH --mem=128GB                           # Memory per node
#SBATCH --time=02:00:00                       # Time limit (hrs:min:sec)
#SBATCH --mail-type=ALL                       # Email notifications (NONE, BEGIN, END, FAIL, ALL)
#SBATCH --mail-user="lauenbur@bc.edu"         # Where to send email notifications
#SBATCH --partition=weidf                     # Partition to run your job on
#SBATCH --output=synanno_training_%j.out      # Standard output file
#SBATCH --error=synanno_training_%j.err       # Standard error file

# Print node information
echo "Running on node: $(hostname)"

# Load necessary modules
module purge
module load anaconda
module load git
module load python/3.9  # Adjust the version if necessary

# Activate the Conda environment
source ~/.bashrc
conda activate lauenbur_syn_anno

# Define repository and branch information
REPO_URL="https://github.com/PytorchConnectomics/SynAnno.git"
BRANCH_NAME="leander/auto-seg-model"

# Adjust to your preferred directory
INSTALL_DIR="/mmfs1/data/lauenbur/SynAnno"

# Set the environment variable for SLURM execution
export EXECUTION_ENV="slurm"

# Clone the repository if not already done
echo "Cloning repository..."
if [ ! -d "$INSTALL_DIR" ]; then
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    echo "Repository already cloned at $INSTALL_DIR"
fi

# Move to installation repo
cd "$INSTALL_DIR" || exit 1

# Checkout the desired branch
echo "Switching to branch: $BRANCH_NAME"
git fetch origin
git checkout "$BRANCH_NAME"

# Install the module with extras_require under "seg"
echo "Installing the SynAnno module with extras..."
pip install .[seg]

# Run the auto_segmentation main script
MAIN_SCRIPT="synanno/backend/auto_segmentation/main.py"

if [ -f "$MAIN_SCRIPT" ]; then
    echo "Executing $MAIN_SCRIPT..."
    python "$MAIN_SCRIPT"
else
    echo "Error: $MAIN_SCRIPT not found!"
    exit 1
fi

echo "Job completed."
