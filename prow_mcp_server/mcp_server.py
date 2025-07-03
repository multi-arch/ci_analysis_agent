import os
import asyncio
from typing import Any, Optional, Dict
from dateutil.parser import parse as parse_date

from drain import DrainExtractor

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("prow-mcp-server")

GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

_drain_extractor: Optional['DrainExtractor'] = None

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
    
    Args:
        job_name: The name of the job
        build_id: The build ID for which to get install logs
        test_name: The name of the test for which to get install logs
        
    Returns:
        Dictionary containing the job metadata(job_name, build_id, test_name), installation logs or error information
    """
    try:
        # Construct the artifacts URL
        artifacts_url = f"{GCS_URL}/{job_name}/{build_id}/artifacts"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{artifacts_url}/{test_name}/ipi-install-install/finished.json")
            response.raise_for_status()
            json_resp = response.json()
            result = json_resp["result"]
            passed = json_resp["passed"]

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{artifacts_url}/{test_name}/ipi-install-install/build-log.txt")
            response.raise_for_status()
            logs = response.text
            return {
                "build_id": build_id,
                "job_name": job_name,
                "test_name": test_name,
                "passed": passed,
                "result": result,
                "logs": logs,
                "artifacts_url": artifacts_url
            }
    except Exception as e:
        return {
            "error": f"Failed to fetch logs: {str(e)}",
            "artifacts_url": artifacts_url if 'artifacts_url' in locals() else None
        }



# async def main():
#     jobname="periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-gcp-ovn-multi-x-ax"
#     jobid = "1936114476847730688"  # Replace with actual job name you want to test
#     md = await get_job_metadata(jobname,jobid)
#     print (md)
#     result = await get_install_logs(jobname,jobid,md["test_name"])
#     print(result)

if __name__ == "__main__":
#    asyncio.run(main())
    mcp.run(transport=os.environ.get("MCP_TRANSPORT", "stdio"))
