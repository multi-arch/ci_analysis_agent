"""Installation Analyst Agent for analyzing CI installation logs."""

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from . import prompt
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams
from dotenv import load_dotenv


import asyncio
import httpx
import threading
import concurrent.futures
import os
from typing import Dict, Any
from datetime import datetime

GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

MODEL = os.environ.get("MODEL", "qwen3:4b")

load_dotenv()

def run_async_in_thread(coro):
    """Run async function in a thread to avoid event loop conflicts."""
    
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result()

def get_job_start_and_end_time_tool(job_name: str, build_id: str)-> Dict[str, Any]:
    """Get the start and end time of a job."""
    return run_async_in_thread(get_job_start_and_end_time_async(job_name, build_id))

async def get_job_start_and_end_time_async(job_name: str, build_id: str)-> Dict[str, Any]:
    """Get the start and end time of a job."""
    start_time = None
    end_time = None
    url_started = f"{GCS_URL}/{job_name}/{build_id}/started.json"
    url_finished = f"{GCS_URL}/{job_name}/{build_id}/finished.json"
    try:
        async with httpx.AsyncClient() as client:
            response_started = await client.get(url_started)
            response_started.raise_for_status()
            data_started = response_started.json()
            if not data_started:
                return {"error": "No response from Prow API for started.json"}
            start_time = data_started["timestamp"]
        async with httpx.AsyncClient() as client:
            response_finished = await client.get(url_finished)
            response_finished.raise_for_status()
            data_finished = response_finished.json()
            if not data_finished:
                return {"error": "No response from Prow API for finished.json"}
            end_time = data_finished["timestamp"]   
        # Convert epoch timestamps to RFC 3339 format
        if start_time:
            start_time = datetime.fromtimestamp(start_time).strftime('%Y-%m-%dT%H:%M:%SZ')
        if end_time:
            end_time = datetime.fromtimestamp(end_time).strftime('%Y-%m-%dT%H:%M:%SZ')
        return {
            "start_time": start_time,
            "end_time": end_time
        }
    except Exception as e:
        return {"error": f"Failed to fetch job start and end time: {str(e)}"}

arch_mismatch_detector_agent = Agent(
    model=LiteLlm(model=MODEL),
    # model="gemini-2.0-flash",
    name="arch_mismatch_detector_agent",
    instruction=prompt.ARCH_MISMATCH_DETECTOR_PROMPT,
    output_key="installation_analysis_output",
    tools=[
        get_job_start_and_end_time_tool,
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://127.0.0.1:8888/stream"
            ),
            tool_filter=[
                "grafana_loki_query",
            ],
            
        ),

    ],
)

root_agent = arch_mismatch_detector_agent