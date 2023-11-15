# README for Setting Up a GCP VM, Cloud Bucket, and Service Account

This README outlines the steps to set up a Google Cloud Platform (GCP) Virtual Machine (VM), configure a Cloud Storage bucket, assign a service account with appropriate roles, and authenticate the service account on the VM.

## Step 1: Set Up GCP Virtual Machine (VM)

1. **Log in to the Google Cloud Console.**
2. **Navigate to the Compute Engine and click on "Create Instance".**
    - Name: Give your VM a name.
    - Region and Zone: Select a region and zone for your VM.
    - Machine Type: Choose an appropriate machine type based on your workload. For data processing, you might need a high-memory or high-CPU machine.
    - Boot Disk: Choose an operating system and disk size. Common choices are Ubuntu or Debian for data science tasks.
    - Firewall: Check both ‘Allow HTTP traffic’ and ‘Allow HTTPS traffic’ if your pipeline requires internet access.
    - GPU (Optional): If your tasks require a GPU, add it in the machine configuration.
    - Step 4: Set Up Your Environment
    - SSH into Your VM: Once the VM is set up, click ‘SSH’ to open a terminal window directly in your

## Step 2: Set Up Cloud Storage Bucket

1. **In the Cloud Console, go to the Cloud Storage section.**
2. **Click "Create bucket" and follow the prompts to create a new bucket.**
   - Choose a unique name for your bucket.
   - Select the desired storage class and location for the bucket.

## Step 3: Assign Service Account as Principal to Cloud Bucket

1. **Go to IAM & Admin in the Cloud Console.**
2. **Click "Service Accounts" and create a new service account or select an existing one.**
3. **Assign roles to the service account that will allow it to interact with the Cloud Storage bucket:**
   - `Storage Object Admin`: Full control over GCS objects.
   - `Storage Object Creator`: Ability to create objects in the bucket.
   - `Storage Object Viewer`: Read-only access to GCS objects.
4. **Download the service account key in JSON format.**

## Step 4: Copy Service Account Key to VM

1. **Use `gcloud compute scp` or `scp` to securely copy the service account key file to your VM:**
   ```sh
   gcloud compute scp /local/path/to/key.json [VM_INSTANCE_NAME]:/remote/path/to/key.json
   ```
   or
   ```sh
   scp /local/path/to/key.json [USERNAME]@[VM_EXTERNAL_IP]:/remote/path/to/key.json
   ```

## Step 5: Setup the Key on the VM

1. **SSH into your VM:**
   ```sh
   gcloud compute ssh [VM_INSTANCE_NAME]
   ```
   or
   ```sh
   ssh [USERNAME]@[VM_EXTERNAL_IP]
   ```
2. **Move the service account key to a secure location on your VM if necessary.**

## Step 6: Authenticate Service Account on the VM

1. **Activate the service account using the key file:**
   ```sh
   gcloud auth activate-service-account --key-file=/path/to/service-account-key.json
   ```
2. **Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to the key file:**
   ```sh
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
   ```

## Additional Information

- **Make sure that you have installed the Google Cloud SDK on your local machine and VM for using `gcloud` commands.**
- **Ensure that you have appropriate permissions to create and manage VM instances, Cloud Storage buckets, and IAM service accounts in your GCP project.**
- **Regularly monitor your VM and Cloud Storage usage to avoid unexpected charges.**

By following these steps, you should have a fully configured VM with a service account authenticated and ready to interact with your Cloud Storage bucket.
