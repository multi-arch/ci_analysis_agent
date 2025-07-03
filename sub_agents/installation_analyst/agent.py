from google.adk import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from . import prompt

MODEL = "gemini-2.0-flash"


installation_analyst_agent = Agent(
    model=MODEL,
    name="installation_analyst_agent",
    instruction=prompt.INSTALLATION_SPECIALIST_PROMPT,
    output_key="installation_analysis_output",
    tools=[   MCPToolset(
        connection_params=StdioServerParameters(
            command='podman',
            args=["run", "-i", "-p", "9000:8000", "--rm",  "-e", "MCP_TRANSPORT=stdio", "localhost/mcp-server-template:latest"],
            tool_filter=['get_install_logs', 'get_job_metadata'],
        )
    ), 
    ],
)