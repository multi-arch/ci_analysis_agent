import os

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

import json
from typing import Any, Dict, Optional, Type
from pydantic import Field
import httpx

import os
from google.cloud import storage


# TARGET_FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))
 
root_agent = LlmAgent(
    name="root_agent_v1",
    # model="gemini-2.5-pro-preview-05-06",
    model="gemini-2.0-flash",
    # model=LiteLlm(model="ollama/qwen3:4b"),
    description="Provides analysis of CI jobs, and determines failure root cause.",
    global_instruction="You are a helpful Kubernetes and Prow assistant. "
                "Your main goal is to analyze the root cause of a job failure."
                "you can get a job's logs by using the 'get_build_logs' tool"
                "Don't use the tool 'get_latest_job_run'."
                "If you don't know, don't speculate, just say so.",
                # "Important information will come from checking the newest 5 job runs, which you find in  'Job History' link at the top of the page."
                # "This can guide you to understand if the failure is due to flakiness."
                # "You should also compare the test results with the x86 job",
                # "use the 'get_must_gather' tool to download the must-gather archive. "
                # "If the tool returns an error, inform the user politely. "
                # "If the tool is successful, analyze the file content for the root cause."
                # "You can use the 'server-filesystem' MCP Server in order to read the contents of must-gather from the filesystem.",
    # tools=[load_web_page] #get_must_gather,
    tools=[ 

        #    MCPToolset(
        #     connection_params=StdioServerParameters(
        #         command='npx',
        #         args=["@browsermcp/mcp@latest"],
        #         tool_filter=['browser_navigate','browser_click', 'browser_wait', 'browser_go_back', 'browser_go_forward', 'browser_press_key', 'browser_screenshot', 'browser_snapshot', 'browser_select_option'],
        #     )
        #    ), 
           MCPToolset(
            connection_params=StdioServerParameters(
                command='podman',
                args=["run", "-i", "-p", "9000:8000", "--rm",  "-e", "MCP_TRANSPORT=stdio", "localhost/mcp-server-template:latest"],
                tool_filter=['get_job_logs','get_build_logs'],
            )
           ), 
        #    MCPToolset(
        #     connection_params=StdioServerParameters(
        #         command='npx',
        #         args=[
        #             "-y",  # Argument for npx to auto-confirm install
        #             "@modelcontextprotocol/server-filesystem",
        #             # IMPORTANT: This MUST be an ABSOLUTE path to a folder the
        #             # npx process can access.
        #             # Replace with a valid absolute path on your system.
        #             # For example: "/Users/youruser/accessible_mcp_files"
        #             # or use a dynamically constructed absolute path:
        #             os.path.abspath(TARGET_FOLDER_PATH),
        #         ],
        #     ),
        #     # Optional: Filter which tools from the MCP server are exposed
        #     tool_filter=['list_directory', 'read_file']
        # )
        ], # Pass the function directly
)

