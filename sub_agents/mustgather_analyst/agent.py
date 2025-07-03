from google.adk import Agent
from . import prompt
from .must_gather import get_must_gather, list_directory, read_drained_file, get_file_info, search_files
MODEL = "gemini-2.0-flash"

mustgather_analyst_agent = Agent(
    model=MODEL,
    name="mustgather_analyst_agent",
    instruction=prompt.MUST_GATHER_SPECIALIST_PROMPT,
    output_key="must_gather_analysis_output",
    tools=[get_must_gather, list_directory, read_drained_file, get_file_info, search_files],
)