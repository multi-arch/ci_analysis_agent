from google.adk.agents import LlmAgent
from . import prompt
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field
import os
import requests
from typing import Dict, Any
from .must_gather import get_must_gather, list_directory, read_drained_file, get_file_info, search_files


GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

MODEL = os.environ.get("MODEL", "qwen3:1.7b")


class MustGatherAnalystInput(BaseModel):
    """Input schema for Must-Gather Analyst Agent."""
    job_name: str = Field(
        description="The Prow job name extracted from the URL (e.g., 'periodic-ci-openshift-multiarch-master-nightly-4.21-ocp-e2e-ovn-remote-s2s-libvirt-ppc64le')"
    )
    build_id: str = Field(
        description="The build ID extracted from the Prow job URL (e.g., '1964900126069624832')"
    )

def get_job_metadata(job_name: str, build_id: str) -> Dict[str, Any]:
    """Get the metadata and status for a specific Prow job name and build id."""
    url = f"{GCS_URL}/{job_name}/{build_id}/prowjob.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
            
        if not data:
            return {"error": "No response from Prow API"}
            
        job_spec = data.get("spec", {})
        job_status = data.get("status", {})
        
        build_id_from_status = job_status.get("build_id")
        status = job_status.get("state")
        args = job_spec.get("pod_spec", {}).get("containers", [])[0].get("args", [])
        test_name = ""
        for arg in args: 
            if arg.startswith("--target="):
                test_name = arg.replace("--target=", "")
        
        return {
            "status": status, 
            "build_id": build_id_from_status, 
            "job_name": job_name,
            "test_name": test_name
        }
            
    except Exception as e:
        return {"error": f"Failed to fetch job info: {str(e)}"}

def get_job_metadata_tool(job_name: str, build_id: str):
    """Retrieves comprehensive metadata and status information for a specific Prow CI job.
    
    This tool fetches the prowjob.json metadata which contains essential information about
    the CI job execution, including current status, build configuration, test targets,
    and execution parameters. This is typically the first tool to use when analyzing a failed CI job.

    Args:
        job_name (str): The name of the Prow job
        build_id (str): The specific build ID for the job run
    
    Returns:
        dict: Job metadata including status, build_id, job_name, test_name, and error details if applicable
    """
    return get_job_metadata(job_name, build_id)

mustgather_analyst_agent = LlmAgent(
    model=LiteLlm(model=MODEL),
    name="mustgather_analyst_agent",
    instruction=prompt.MUST_GATHER_SPECIALIST_PROMPT,
    output_key="must_gather_analysis_output",
    input_schema=MustGatherAnalystInput,
    tools=[
        get_job_metadata_tool,
        get_must_gather,
        list_directory,
        read_drained_file,
        get_file_info,
        search_files,
    ],
)