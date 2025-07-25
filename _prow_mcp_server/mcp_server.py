import os
import asyncio
from typing import Any, Optional, Dict
from dateutil.parser import parse as parse_date
import re

from drain import DrainExtractor

import httpx
from fastmcp import FastMCP

mcp = FastMCP(name="prow-mcp-server", stateless_http=True, host="0.0.0.0", port=9000)

GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

_drain_extractor: Optional['DrainExtractor'] = None

def extract_installation_info(log_content: str) -> Dict[str, Any]:
    """Extract installation information from build-log.txt."""
    install_info = {
        "installer_version": None,
        "installer_commit": None,
        "release_image": None,
        "instance_types": {},
        "install_duration": None,
        "architecture": None,
        "cluster_config": {},
        "install_success": False
    }
    
    # Extract openshift-install version and commit (can be on separate lines)
    version_patterns = [
        r'openshift-install v([^\s"]+)',
        r'"openshift-install v([^\s"]+)"'
    ]
    
    for pattern in version_patterns:
        version_match = re.search(pattern, log_content)
        if version_match:
            install_info["installer_version"] = version_match.group(1)
            break
    
    # Extract commit (separate pattern)
    commit_patterns = [
        r'built from commit ([a-f0-9]+)',
        r'"built from commit ([a-f0-9]+)"'
    ]
    
    for pattern in commit_patterns:
        commit_match = re.search(pattern, log_content)
        if commit_match:
            install_info["installer_commit"] = commit_match.group(1)
            break
    
    # Extract release image
    release_patterns = [
        r'Installing from release ([^\s]+)',
        r'release image "([^"]+)"',
        r'RELEASE_IMAGE_LATEST for release image "([^"]+)"'
    ]
    for pattern in release_patterns:
        release_match = re.search(pattern, log_content)
        if release_match:
            install_info["release_image"] = release_match.group(1)
            break
    
    # Extract instance types from install-config.yaml section
    # Look for compute and controlPlane sections
    compute_type_pattern = r'compute:.*?type:\s*([^\s\n]+)'
    control_type_pattern = r'controlPlane:.*?type:\s*([^\s\n]+)'
    
    compute_match = re.search(compute_type_pattern, log_content, re.DOTALL)
    if compute_match:
        install_info["instance_types"]["compute"] = compute_match.group(1)
    
    control_match = re.search(control_type_pattern, log_content, re.DOTALL)
    if control_match:
        install_info["instance_types"]["control_plane"] = control_match.group(1)
    
    # Extract architecture
    arch_pattern = r'architecture:\s*([^\s\n]+)'
    arch_match = re.search(arch_pattern, log_content)
    if arch_match:
        install_info["architecture"] = arch_match.group(1)
    
    # Extract cluster configuration details
    # Replicas
    compute_replicas_pattern = r'compute:.*?replicas:\s*(\d+)'
    control_replicas_pattern = r'controlPlane:.*?replicas:\s*(\d+)'
    
    compute_replicas_match = re.search(compute_replicas_pattern, log_content, re.DOTALL)
    if compute_replicas_match:
        install_info["cluster_config"]["compute_replicas"] = int(compute_replicas_match.group(1))
    
    control_replicas_match = re.search(control_replicas_pattern, log_content, re.DOTALL)
    if control_replicas_match:
        install_info["cluster_config"]["control_replicas"] = int(control_replicas_match.group(1))
    
    # Network type
    network_pattern = r'networkType:\s*([^\s\n]+)'
    network_match = re.search(network_pattern, log_content)
    if network_match:
        install_info["cluster_config"]["network_type"] = network_match.group(1)
    
    # Platform and region
    platform_pattern = r'platform:\s*([^\s\n]+):'
    region_pattern = r'region:\s*([^\s\n]+)'
    
    platform_match = re.search(platform_pattern, log_content)
    if platform_match:
        install_info["cluster_config"]["platform"] = platform_match.group(1)
    
    region_match = re.search(region_pattern, log_content)
    if region_match:
        install_info["cluster_config"]["region"] = region_match.group(1)
    
    # Extract install duration (clean up quotes)
    duration_patterns = [
        r'Time elapsed:\s*([^\n"]+)',
        r'Install complete!.*?Time elapsed:\s*([^\n"]+)'
    ]
    
    for pattern in duration_patterns:
        duration_match = re.search(pattern, log_content, re.DOTALL)
        if duration_match:
            duration = duration_match.group(1).strip().strip('"')
            install_info["install_duration"] = duration
            break
    
    # Check if installation was successful
    if "Install complete!" in log_content:
        install_info["install_success"] = True
    elif "level=error" in log_content or "FATAL" in log_content:
        install_info["install_success"] = False
    
    return install_info

async def make_request(
    url: str, method: str = "GET", data: dict[str, Any] = None
) -> dict[str, Any] | None:
    api_key = os.environ.get("API_KEY")
    if api_key:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }
    else:
        headers = {}

    async with httpx.AsyncClient() as client:
        if method.upper() == "GET":
            response = await client.request(method, url, headers=headers, params=data)
        else:
            response = await client.request(method, url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()



@mcp.tool()
async def get_job_metadata(job_name: str, build_id: str) -> dict: 
    """Get the metadata and status for a specific Prow job name and build id.
    
    Args:
        job_name: The name of the job to get metadata for
        build_id: The ID of the build to get metadata for
        
    Returns:
        Dictionary containing the job metadata or error information
        or an error if either build_id or  job_name are not provided
    """
    url = f"{GCS_URL}/{job_name}/{build_id}/prowjob.json"
    try:
        response = await make_request(url)
        if not response:
            return {"error": "No response from Prow API"}
            
        job_spec = response.get("spec", {})
        job_status = response.get("status", {})
        
        build_id = job_status.get("build_id")
        status=job_status.get("state")
        args = job_spec.get("pod_spec",{}).get("containers",[])[0].get("args",[])
        test_name=""
        for arg in args: 
            if arg.startswith("--target="):
                test_name=arg.replace("--target=","")
       
        return {"status": status, "build_id": build_id, "job_name": job_name, "test_name": test_name}
            
    except Exception as e:
        return {"error": f"Failed to fetch job info: {str(e)}"}

async def initialize_drain_extractor(verbose: bool = False, context: bool = False, max_clusters: int = 8) -> Dict[str, Any]:
    """Initialize a DrainExtractor instance with specified parameters.
    
    Args:
        verbose: Enable verbose/profiling mode
        context: Enable context mode
        max_clusters: Maximum number of clusters to create
        
    Returns:
        Dictionary containing initialization status and configuration
    """
    global _drain_extractor
    try:
        _drain_extractor = DrainExtractor(verbose=verbose, context=context, max_clusters=max_clusters)
        return {
            "status": "success",
            "message": "DrainExtractor initialized successfully",
            "config": {
                "verbose": verbose,
                "context": context,
                "max_clusters": max_clusters
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to initialize DrainExtractor: {str(e)}"
        }

@mcp.tool()
async def get_build_logs(job_name: str, build_id: str) -> dict:
    """Get the logs for a specific build ID and job name.
    
    Args:
        job_name: The name of the job
        build_id: The build ID to get logs for
        
    Returns:
        Dictionary containing the job logs or error information
    """
    global _drain_extractor
    
    if _drain_extractor is None:
        # Initialize with default settings if not already initialized
        init_result = await initialize_drain_extractor()
        if init_result["status"] == "error":
            return init_result
    
    try:
        if _drain_extractor is None:
            return {
                "status": "error",
                "message": "DrainExtractor not initialized"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to extract patterns: {str(e)}"
        } 
        
    try:
        # Construct the artifacts URL
        artifacts_url = f"{GCS_URL}/{job_name}/{build_id}/artifacts"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GCS_URL}/{job_name}/{build_id}/build-log.txt")
            response.raise_for_status()
            logs = response.text
            patterns = _drain_extractor(logs)
        
        # Convert patterns to a more structured format
            pattern_results = []
            for line_number, chunk in patterns:
                pattern_results.append({
                    "line_number": line_number,
                    "chunk": chunk.strip(),
                    "chunk_length": len(chunk)
                })
            return {
                "build_id": build_id,
                "job_name": job_name,
                "logs": pattern_results,
                "artifacts_url": artifacts_url
            }
    except Exception as e:
        return {
            "error": f"Failed to fetch logs: {str(e)}",
            "artifacts_url": artifacts_url if 'artifacts_url' in locals() else None
        }


@mcp.tool()
async def get_install_logs(job_name: str, build_id: str, test_name: str):
    """Get the install logs for a specific build ID and job name.
    
    This function looks specifically in the installation directories:
    <job_name>/<build_id>/artifacts/<test_name>/<ipi-install-*>/
    
    It tries multiple installation directory patterns:
    - ipi-install-install
    - ipi-install-install-stableinitial
    
    Args:
        job_name: The name of the job
        build_id: The build ID for which to get install logs
        test_name: The name of the test for which to get install logs
        
    Returns:
        Dictionary containing the job metadata(job_name, build_id, test_name), installation logs or error information
    """
    # List of possible installation directory patterns
    install_dirs = [
        "ipi-install-install",
        "ipi-install-install-stableinitial"
    ]
    
    # Construct the base artifacts URL
    artifacts_url = f"{GCS_URL}/{job_name}/{build_id}/artifacts"
    
    # Try each installation directory pattern
    for install_dir in install_dirs:
        try:
            async with httpx.AsyncClient() as client:
                # Try to get finished.json from this installation directory
                finished_url = f"{artifacts_url}/{test_name}/{install_dir}/finished.json"
                response = await client.get(finished_url)
                response.raise_for_status()
                json_resp = response.json()
                result = json_resp["result"]
                passed = json_resp["passed"]

            async with httpx.AsyncClient() as client:
                # Get build-log.txt from the same installation directory
                log_url = f"{artifacts_url}/{test_name}/{install_dir}/build-log.txt"
                response = await client.get(log_url)
                response.raise_for_status()
                logs = response.text
                
                return {
                    "build_id": build_id,
                    "job_name": job_name,
                    "test_name": test_name,
                    "install_dir": install_dir,
                    "passed": passed,
                    "result": result,
                    "logs": logs,
                    "artifacts_url": artifacts_url,
                    "log_url": log_url
                }
        except Exception as e:
            # Continue to try the next directory pattern
            continue
    
    # If none of the patterns worked, return an error
    return {
        "error": f"Failed to fetch install logs from any installation directory. Tried: {', '.join(install_dirs)}",
        "build_id": build_id,
        "job_name": job_name,
        "test_name": test_name,
        "artifacts_url": artifacts_url,
        "tried_directories": [f"{artifacts_url}/{test_name}/{d}" for d in install_dirs]
    }



# async def main():
#     jobname="periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-gcp-ovn-multi-x-ax"
#     jobid = "1936114476847730688"  # Replace with actual job name you want to test
#     md = await get_job_metadata(jobname,jobid)
#     print (md)
#     result = await get_install_logs(jobname,jobid,md["test_name"])
#     print(result)

if __name__ == "__main__":
    # mcp.streamable_http_app()
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9000)

