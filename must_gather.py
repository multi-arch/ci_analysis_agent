import os
from google.cloud import storage

def get_must_gather(jobURL: str) -> dict:
    """Retrieves the must-gather archive for a specified job.

    Args:
        job (str): The URL of the job (e.g., "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-aws-ovn-techpreview-multi-a-a/1926804852168462336").

    Returns:
        dict: A dictionary containing the must-gather information.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'path' key with filesystem path to untarred must-gather.
              If 'error', includes an 'error_message' key.
    """
    print(f"--- Tool: get_must_gather called for job: {jobURL} ---") # Log tool execution

    gsURL = "gs://test-platform-results/logs/"
    jobPath = ""
    parts = jobURL.split('/')
    if len(parts) >= 2:
        jobPath= parts[-2], parts[-1]
    else:
        return {"status": "error", "error_message": f"Sorry, I couldn't get the job's path from the '{jobURL}'."}
    gsURL = gsURL+"/".join(jobPath)
    download_from_gs(gsURL, TARGET_FOLDER_PATH+"/"+"/".join(jobPath))
    return  {
        "periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-aws-ovn-techpreview-multi-a-a/1926804852168462336": {"status": "success", "path": TARGET_FOLDER_PATH+"/"+"/".join(jobPath)},
    }


def download_from_gs(gs_url, destination_folder):
    """Downloads a file or directory from Google Cloud Storage.

    Args:
        gs_url: The Google Cloud Storage URL (e.g., gs://bucket-name/path/to/file).
        destination_folder: The local folder where the file(s) will be downloaded.
    """
    try:
        # Initialize the Google Cloud Storage client
        storage_client = storage.Client(project="openshift-gce-devel")

        # Parse the GCS URL
        bucket_name = gs_url.split('/')[2]
        blob_prefix = '/'.join(gs_url.split('/')[3:])
        bucket = storage_client.bucket(bucket_name)

        # Create the destination folder if it doesn't exist
        if os.path.exists(destination_folder):
            return
        else:
            os.makedirs(destination_folder)

        # List all blobs with the given prefix
        blobs = bucket.list_blobs(prefix=blob_prefix)

        for blob in blobs:

            # Create the full destination path
            destination_path = os.path.join(destination_folder, blob.name.replace(blob_prefix, '', 1).lstrip('/'))

            # Create any necessary subdirectories
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            # Download the blob to the destination path
            blob.download_to_filename(destination_path)
            print(f"Downloaded {gs_url}/{blob.name} to {destination_path}")

    except Exception as e:
        print(f"Error downloading from GCS: {e}")