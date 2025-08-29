from google.adk import Agent
from . import prompt
from google.adk.models.lite_llm import LiteLlm
import os
from .must_gather import get_must_gather, list_directory, read_drained_file, get_file_info, search_files

MODEL = os.environ.get("MODEL", "qwen3:4b")

mustgather_analyst_agent = Agent(
    model=LiteLlm(model=MODEL),
    name="mustgather_analyst_agent",
    instruction=prompt.MUST_GATHER_SPECIALIST_PROMPT,
    output_key="must_gather_analysis_output",
    tools=[get_must_gather, list_directory, read_drained_file, get_file_info, search_files],
)