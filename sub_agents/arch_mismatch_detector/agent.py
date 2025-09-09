"""Installation Analyst Agent for analyzing CI installation logs."""

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from . import prompt
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams


import asyncio
import httpx
import re
import threading
import concurrent.futures
import re
import os
from typing import Dict, Any, Optional

GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

MODEL = os.environ.get("MODEL", "qwen3:4b")


arch_mismatch_detector_agent = Agent(
    model=LiteLlm(model=MODEL),
    name="arch_mismatch_detector_agent",
    instruction=prompt.ARCH_MISMATCH_DETECTOR_PROMPT,
    output_key="installation_analysis_output",
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://127.0.0.1:9000/mcp",
                tool_filter=[
                    "loki_query",
                    "loki_label_names",
                    "loki_label_values",
                ],
            ),
        ),

    ],
)