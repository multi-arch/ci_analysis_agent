import datetime
import os

from zoneinfo import ZoneInfo
# from google.adk.agents import Agent
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.cloud import storage

TARGET_FOLDER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "/home/skhoury/go/src/github.com/sherine-k/adk-test")

# @title Define the get_weather Tool
def get_must_gather(jobURL: str) -> dict:
    """Retrieves the must-gather archive for a specified job.

    Args:
        job (str): The URL of the job (e.g., "https://prow.ci.openshift.org/view/gs/test-platform-results/logs/periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-aws-ovn-techpreview-multi-a-a/1926804852168462336").

    Returns:
        dict: A dictionary containing the must-gather information.
              Includes a 'status' key ('success' or 'error').
              If 'success', includes a 'path' key with filesystem path to untarred must-gather.
              If 'error', includes an 'error_message' key.
    """
    print(f"--- Tool: get_must_gather called for job: {jobURL} ---") # Log tool execution

    gsURL = "gs://test-platform-results/logs/"
    jobPath = ""
    parts = jobURL.split('/')
    if len(parts) >= 2:
        jobPath= parts[-2], parts[-1]
    else:
        return {"status": "error", "error_message": f"Sorry, I couldn't get the job's path from the '{jobURL}'."}
    gsURL = gsURL+"/".join(jobPath)
    download_from_gs(gsURL, TARGET_FOLDER_PATH+"/"+"/".join(jobPath))
    return  {
        "periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-aws-ovn-techpreview-multi-a-a/1926804852168462336": {"status": "success", "path": TARGET_FOLDER_PATH+"/"+"/".join(jobPath)},
    }


def download_from_gs(gs_url, destination_folder):
    """Downloads a file or directory from Google Cloud Storage.

    Args:
        gs_url: The Google Cloud Storage URL (e.g., gs://bucket-name/path/to/file).
        destination_folder: The local folder where the file(s) will be downloaded.
    """
    try:
        # Initialize the Google Cloud Storage client
        storage_client = storage.Client(project="openshift-gce-devel")

        # Parse the GCS URL
        bucket_name = gs_url.split('/')[2]
        blob_prefix = '/'.join(gs_url.split('/')[3:])
        bucket = storage_client.bucket(bucket_name)

        # Create the destination folder if it doesn't exist
        if os.path.exists(destination_folder):
            return
        else:
            os.makedirs(destination_folder)

        # List all blobs with the given prefix
        blobs = bucket.list_blobs(prefix=blob_prefix)

        for blob in blobs:

            # Create the full destination path
            destination_path = os.path.join(destination_folder, blob.name.replace(blob_prefix, '', 1).lstrip('/'))

            # Create any necessary subdirectories
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            # Download the blob to the destination path
            blob.download_to_filename(destination_path)
            print(f"Downloaded {gs_url}/{blob.name} to {destination_path}")

    except Exception as e:
        print(f"Error downloading from GCS: {e}")

root_agent = LlmAgent(
    name="root_agent_v1",
    # model="gemini-2.0-flash", # Can be a string for Gemini or a LiteLlm object
    model=LiteLlm(model="ollama_chat/qwen3:4b"),
    description="Provides analysis of CI jobs, and determines failure root cause.",
    global_instruction="You are a helpful Kubernetes and Prow assistant. "
                "When the user asks for the root cause of a job failure, "
                "use the 'get_must_gather' tool to download the must-gather archive. "
                "If the tool returns an error, inform the user politely. "
                "If the tool is successful, analyze the file content for the root cause."
                "You can use the 'server-filesystem' MCP Server in order to read the contents of must-gather from the filesystem.",
    tools=[get_must_gather,
           MCPToolset(
            connection_params=StdioServerParameters(
                command='npx',
                args=[
                    "-y",  # Argument for npx to auto-confirm install
                    "@modelcontextprotocol/server-filesystem",
                    # IMPORTANT: This MUST be an ABSOLUTE path to a folder the
                    # npx process can access.
                    # Replace with a valid absolute path on your system.
                    # For example: "/Users/youruser/accessible_mcp_files"
                    # or use a dynamically constructed absolute path:
                    os.path.abspath(TARGET_FOLDER_PATH),
                ],
            ),
            # Optional: Filter which tools from the MCP server are exposed
            # tool_filter=['list_directory', 'read_file']
        )
        ], # Pass the function directly
)


# def main():
#   """
#   Prompts the user for a job URL, extracts the last two parts, and prints them.
#   """
#   job_url = input("Enter the job URL: ")
#   last_two_parts = get_must_gather(job_url)

#   if last_two_parts:
#     print(f"The last two parts of the URL are: {last_two_parts}")
#   else:
#     print("The URL does not have enough parts.")

# if __name__ == "__main__":
#   main()

# # @title Setup Session Service and Runner

# # --- Session Management ---
# # Key Concept: SessionService stores conversation history & state.
# # InMemorySessionService is simple, non-persistent storage for this tutorial.
# session_service = InMemorySessionService()

# # Define constants for identifying the interaction context
# APP_NAME = "weather_tutorial_app"
# USER_ID = "user_1"
# SESSION_ID = "session_001" # Using a fixed ID for simplicity

# # Create the specific session where the conversation will happen
# session = await session_service.create_session(
#     app_name=APP_NAME,
#     user_id=USER_ID,
#     session_id=SESSION_ID
# )
# print(f"Session created: App='{APP_NAME}', User='{USER_ID}', Session='{SESSION_ID}'")

# # --- Runner ---
# # Key Concept: Runner orchestrates the agent execution loop.
# runner = Runner(
#     agent=root_agent, # The agent we want to run
#     app_name=APP_NAME,   # Associates runs with our app
#     session_service=session_service # Uses our session manager
# )
# print(f"Runner created for agent '{runner.agent.name}'.")