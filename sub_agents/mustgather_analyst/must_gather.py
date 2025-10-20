import os
import tarfile
from datetime import datetime
from typing import Optional

from google.cloud import storage

try:
    from .drain import DrainExtractor
except ImportError:
    from drain import DrainExtractor

# Global DrainExtractor instance
_drain_extractor = DrainExtractor(verbose=False, context=False, max_clusters=1000)


def get_must_gather(job_name: str, build_id: str, test_name: str, target_folder: str = "/tmp/must_gather_analysis") -> dict:
    """Downloads and extracts must-gather archive from a failed CI job for analysis.

    This tool retrieves the must-gather diagnostic data collected during a CI job failure.
    Must-gather archives contain cluster state information like pod logs, events, and resource definitions
    that are essential for root cause analysis of OpenShift cluster issues.

    Args:
        job_name (str): The name of the Prow job that failed
        build_id (str): The specific build ID from the job run
        test_name (str): The test component name that generated must-gather (e.g., 'ocp-e2e-aws-ovn-sno-multi-a-a')
        target_folder (str, optional): Local directory to download and extract the archive. Defaults to '/tmp/must_gather_analysis'.
    
    Returns:
        dict: A dictionary containing the must-gather retrieval result.
              - If successful: {'status': 'success', 'path': '/path/to/extracted/files'}
              - If failed: {'status': 'error', 'error_message': 'description of the error'}
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
        raise

def read_drained_file(path: str, max_lines: Optional[int] = None) -> dict:
    """Analyze log file using Drain algorithm to extract structured patterns from unstructured logs.
    
    This tool applies the Drain log parsing algorithm to identify common patterns in log files
    by clustering similar log entries together. This is especially useful for analyzing 
    repetitive error messages, warnings, and events in OpenShift cluster logs.

    Args:
        path (str): The absolute path to the log file to analyze
        max_lines (int, optional): Maximum number of lines to read from the file. 
                                 If None, reads the entire file. Defaults to None.
    
    Returns:
        dict: A dictionary containing the Drain analysis results.
              - If successful: {'status': 'success', 'patterns': [{'line_number': int, 'chunk': str, 'chunk_length': int}]}  
              - If failed: {'status': 'error', 'error_message': 'description of the error'}
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            if max_lines is not None:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    lines.append(line)
                content = ''.join(lines)
            else:
                content = f.read()
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


def list_directory(path: str, show_hidden: bool = False, sort_by: str = "name") -> dict:
    """Lists files and directories in a must-gather archive or local filesystem.
    
    This tool helps navigate the directory structure of extracted must-gather archives,
    which typically contain organized diagnostic data like namespaces, cluster-scoped-resources,
    host_service_logs, and other OpenShift cluster information.

    Args:
        path (str): The directory path to list contents of
        show_hidden (bool, optional): Whether to include hidden files/directories (starting with '.'). 
                                     Defaults to False.
        sort_by (str, optional): How to sort the directory listing. Options: 'name', 'size', 'modified'. 
                                Defaults to 'name'.
    
    Returns:
        dict: A dictionary containing the directory listing results.
              - If successful: {'status': 'success', 'entries': ['[DIR] dirname', '[FILE] filename', ...]}
              - If failed: {'status': 'error', 'error_message': 'description of the error'}
    """
    try:
        entries = []
        with os.scandir(path) as it:
            dir_entries = []
            for entry in it:
                # Skip hidden files unless requested
                if not show_hidden and entry.name.startswith('.'):
                    continue
                    
                prefix = "[DIR]" if entry.is_dir() else "[FILE]"
                
                # Get additional info for sorting
                try:
                    stat_info = entry.stat()
                    size = stat_info.st_size
                    modified = stat_info.st_mtime
                except OSError:
                    size = 0
                    modified = 0
                
                dir_entries.append({
                    'name': entry.name,
                    'prefix': prefix,
                    'size': size,
                    'modified': modified,
                    'is_dir': entry.is_dir()
                })
        
        # Sort entries based on sort_by parameter
        if sort_by == "size":
            dir_entries.sort(key=lambda x: x['size'], reverse=True)
        elif sort_by == "modified":
            dir_entries.sort(key=lambda x: x['modified'], reverse=True)
        else:  # default to name
            dir_entries.sort(key=lambda x: x['name'].lower())
        
        # Format output
        for entry in dir_entries:
            entries.append(f"{entry['prefix']} {entry['name']}")
            
        return {"status": "success", "entries": entries}
    except Exception as e:
        return {"status": "error", "error_message": f"Error listing directory {path}: {e}"}


def get_file_info(path: str, include_content_preview: bool = False) -> dict:
    """Retrieves detailed metadata about files or directories in must-gather archives.
    
    This tool provides comprehensive information about files, including size, timestamps,
    and permissions. For log files, it can also provide a content preview to help determine
    if the file contains relevant diagnostic information.

    Args:
        path (str): The file or directory path to get metadata for
        include_content_preview (bool, optional): For text files smaller than 10KB, include 
                                                first 10 lines as preview. Defaults to False.
    
    Returns:
        dict: A dictionary containing the file metadata.
              - If successful: {'status': 'success', 'info': {size, created, modified, accessed, is_directory, is_file, permissions, [content_preview]}}
              - If failed: {'status': 'error', 'error_message': 'description of the error'}
    """
    try:
        stats = os.stat(path)
        info = {
            "size": stats.st_size,
            "created": datetime.fromtimestamp(stats.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
            "accessed": datetime.fromtimestamp(stats.st_atime).isoformat(),
            "is_directory": os.path.isdir(path),
            "is_file": os.path.isfile(path),
            "permissions": oct(stats.st_mode)[-3:]
        }
        
        # Add content preview for small text files if requested
        if include_content_preview and os.path.isfile(path) and stats.st_size < 10240:  # 10KB limit
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= 10:  # First 10 lines only
                            break
                        lines.append(line.rstrip())
                    if lines:
                        info["content_preview"] = lines
            except (UnicodeDecodeError, IOError):
                # Skip preview for binary or unreadable files
                pass
        
        return {"status": "success", "info": info}
    except Exception as e:
        return {"status": "error", "error_message": f"Error getting file info for {path}: {e}"}

def search_files(start_path: str, pattern: str, max_results: int = 100, search_content: bool = False) -> dict:
    """Search for files in must-gather archives by filename pattern or content.
    
    This tool helps locate specific diagnostic files within large must-gather archives.
    It's particularly useful for finding log files, configuration files, or resources
    related to specific namespaces, pods, or error conditions.

    Args:
        start_path (str): The directory path to start searching from (typically the must-gather root)
        pattern (str): The search pattern to match against filenames (case-insensitive substring match)
        max_results (int, optional): Maximum number of matching files to return. Defaults to 100.
        search_content (bool, optional): Whether to also search within file contents (slower). 
                                       Only applies to text files under 1MB. Defaults to False.
    
    Returns:
        dict: A dictionary containing the search results.
              - If successful: {'status': 'success', 'results': ['path1', 'path2', ...]}
              - If failed: {'status': 'error', 'error_message': 'description of the error'}
    """
    results = []
    
    try:
        for root, _, files in os.walk(start_path):
            for name in files:
                full_path = os.path.join(root, name)
                matched = False
                
                # Check filename match
                if pattern.lower() in name.lower():
                    matched = True
                
                # Check content match if requested
                elif search_content:
                    try:
                        file_size = os.path.getsize(full_path)
                        if file_size < 1048576:  # 1MB limit for content search
                            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if pattern.lower() in content.lower():
                                    matched = True
                    except (IOError, UnicodeDecodeError):
                        continue  # Skip files that can't be read
                
                if matched:
                    results.append(full_path)
                    if len(results) >= max_results:
                        break
            
            if len(results) >= max_results:
                break
                
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

