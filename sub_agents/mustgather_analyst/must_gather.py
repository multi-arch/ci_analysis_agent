import os
import tarfile
from datetime import datetime
from google.cloud import storage
from typing import List, Dict, Any, Optional
try:
    from .drain import DrainExtractor
except ImportError:
    from drain import DrainExtractor

# Global DrainExtractor instance
_drain_extractor = DrainExtractor(verbose=False, context=False, max_clusters=1000)

def get_must_gather(job_name: str, build_id: str, test_name: str, target_folder: str) -> dict:
    """Retrieves the must-gather archive for a specified job.

    Args:
        job_name: The name of the job
        build_id: The build ID for which to get install logs
        test_name: The name of the test for which to get install logs
    Returns:
        dict: A dictionary containing the must-gather information.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'path' key pointing to must-gather logs.
              If 'error', includes an 'error_message' key.
    """
   

    gsURL = "gs://test-platform-results/logs/"+job_name+"/"+build_id+"/artifacts/"+test_name+"/gather-must-gather/artifacts"
    destination_folder = target_folder+"/"+job_name+"/"+build_id+"/"+test_name
    try:
        download_from_gs(gsURL, destination_folder)
    except Exception as e:
        return {"status": "error", "error_message": f"Error downloading from GCS: {e}"}
    
    print(f"Downloaded must-gather tar to {destination_folder}")
    
    # Look for must-gather.tar in the destination folder
    must_gather_tar_path = os.path.join(destination_folder, "must-gather.tar")
    
    if os.path.exists(must_gather_tar_path):
        try:
            # Extract the tar file
            with tarfile.open(must_gather_tar_path, 'r') as tar:
                tar.extractall(path=destination_folder)
        except Exception as e:
            return {"status": "error", "error_message": f"Error extracting must-gather.tar: {e}"}
    else:
         return {"status": "error", "error_message": f"must-gather.tar not found in {destination_folder}"}
    return  {"status": "success", "path": destination_folder}
    


def download_from_gs(gs_url, destination_folder):
    """Downloads a file or directory from Google Cloud Storage.

    Args:
        gs_url: The Google Cloud Storage URL (e.g., gs://bucket-name/path/to/file).
        destination_folder: The local folder where the file(s) will be downloaded.
    """
    print(f"download_from_gs called with{gs_url} to {destination_folder}")
    try:
        # Initialize the Google Cloud Storage client
        storage_client = storage.Client(project="openshift-gce-devel")

        # Parse the GCS URL
        bucket_name = gs_url.split('/')[2]
        blob_prefix = '/'.join(gs_url.split('/')[3:])
        bucket = storage_client.bucket(bucket_name)
        print(f"bucket_name: {bucket_name}, blob_prefix: {blob_prefix}")
        # Create the destination folder if it doesn't exist
        if os.path.exists(destination_folder):
            return
        else:
            os.makedirs(destination_folder)

        # List all blobs with the given prefix
        blobs = bucket.list_blobs(prefix=blob_prefix)
        print(f" {blobs} ")
        for blob in blobs:
            # Create the full destination path
            destination_path = os.path.join(destination_folder, blob.name.replace(blob_prefix, '', 1).lstrip('/'))
            print(f"Downloading {gs_url}/{blob.name} to {destination_path}")

            # Create any necessary subdirectories
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            # Download the blob to the destination path
            blob.download_to_filename(destination_path)
            print(f"Downloaded {gs_url}/{blob.name} to {destination_path}")

    except Exception as e:
        print(f"Error downloading from GCS: {e}")



        


def read_drained_file(path: str) -> dict:
    """Read contents of a file
    Args:
        path: The path to the file to read
    Returns:
        dict: A dictionary containing the file contents.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'patterns' key pointing to a list of patterns found in the file.
              If 'error', includes an 'error_message' key.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content= f.read()
            patterns = _drain_extractor(content)
    
    # Convert patterns to a more structured format
        pattern_results = []
        for line_number, chunk in patterns:
            pattern_results.append({
                "line_number": line_number,
                "chunk": chunk.strip(),
                "chunk_length": len(chunk)
            })
    except Exception as e:
        return {"status": "error", "error_message": f"Error reading file {path}: {e}"}
    return {"status": "success", "patterns": pattern_results}

    

def list_directory( path: str) -> dict:
    """List contents of a directory
    Args:
        path: The path to list the contents of
    Returns:
        dict: A dictionary containing the directory contents.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes an 'entries' key pointing to a list of directory entries.
              If 'error', includes an 'error_message' key.
    """
    try:
        entries = []
        with os.scandir(path) as it:
            for entry in it:
                prefix = "[DIR]" if entry.is_dir() else "[FILE]"
                entries.append(f"{prefix} {entry.name}")
        return {"status": "success", "entries": entries}
    except Exception as e:
        return {"status": "error", "error_message": f"Error listing directory {path}: {e}"}

    

def get_file_info(path: str) -> dict:
    """Get file/directory metadata
    Args:
        path: The path to get the file/directory metadata for
    Returns:
        dict: A dictionary containing the file/directory metadata.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes an 'info' key pointing to a dictionary containing the file/directory metadata.
              If 'error', includes an 'error_message' key.
    """
    try:
        stats = os.stat(path)
        return  {"status": "success", "info": {
            "size": stats.st_size,
            "created": datetime.fromtimestamp(stats.st_ctime),
            "modified": datetime.fromtimestamp(stats.st_mtime),
            "accessed": datetime.fromtimestamp(stats.st_atime),
            "is_directory": os.path.isdir(path),
            "is_file": os.path.isfile(path),
            "permissions": oct(stats.st_mode)[-3:]
        }}
    except Exception as e:
        return {"status": "error", "error_message": f"Error getting file info for {path}: {e}"}

def search_files(start_path: str, pattern: str) -> dict:
    """Search for files matching a pattern
    Args:
        start_path: The path to start searching from
        pattern: The pattern to search for
    Returns:
        dict: A dictionary containing the search results.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'results' key pointing to a list of matching files.
              If 'error', includes an 'error_message' key.
    """
    results = []
    
    try:
        for root, _, files in os.walk(start_path):
            for name in files:
                if pattern.lower() in name.lower():
                    full_path = os.path.join(root, name)
                    results.append(full_path)
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "error_message": f"Error searching files from {start_path}: {e}"}
        

# if __name__ == "__main__":
#     # Test list_directory function
#     test_path = "/tmp"  # Use a common directory that should exist
    
#     print("Testing get_must_gather function...")
#     result = get_must_gather("periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-aws-ovn-sno-multi-a-a", "1940296163760541696", "ocp-e2e-aws-ovn-sno-multi-a-a",test_path)
    
#     print(f"Result: {result}")
    
#     if result["status"] == "success":
#         print(f"Successfully downloaded tar: {test_path}")
        
#     else:
#         print(f"Error: {result['error_message']}")

