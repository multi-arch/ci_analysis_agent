from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters


# TARGET_FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))
 
root_agent = LlmAgent(
    name="root_agent_v1",
    # model="gemini-2.5-pro-preview-05-06",
    model="gemini-2.0-flash",
    # model=LiteLlm(model="ollama/qwen3:4b"),
    description="Provides analysis of CI jobs, and determines if the cluster installation was successful or not.",
    global_instruction="You are a helpful Kubernetes and Prow expert assistant. "
        "You are specialized in Openshift installation."
        "Your main goal is to analyze the Prow job's installation logs and diagnose possible failures of the cluster installation for the Prow job."
        "You provide root cause analysis for installation failures and propose solutions if possible."
        "You are truthful, concise, and helpful."
        "You never speculate about clusters being installed or fabricate information."
        "If you do not know the answer, you acknowledge the fact and end your response."
        "Your responses must be as short as possible."
        "CI JOB ANALYSIS WORKFLOW:"
        "-------------------------"
        "When analyzing a job failure, follow this recommended workflow:"
        "1. First, get a job's metadata (including test_name) and status by using 'get_job_metadata' tool."
        "2. Then, once you have the metadata, you can get install logs by using the 'get_install_logs' tool."
        "3. Check that the installation was successful by looking at the install logs."
        "4. Only if installation is successful, use 'get_build_logs' to get the job logs." 
        "5. Analyze the job build logs to determine the root cause of the failure.",
        
    tools=[ 
           MCPToolset(
            connection_params=StdioServerParameters(
                command='podman',
                args=["run", "-i", "-p", "9000:8000", "--rm",  "-e", "MCP_TRANSPORT=stdio", "localhost/mcp-server-template:latest"],
                tool_filter=['get_build_logs','get_install_logs', 'get_job_metadata'],
            )
           ), 
        ], 
)

