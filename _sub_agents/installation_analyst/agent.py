from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from . import prompt

MODEL = LiteLlm(model="ollama_chat/qwen3:4b")

installation_analyst_agent = Agent(
    model=MODEL,
    name="installation_analyst_agent",
    instruction=prompt.INSTALLATION_SPECIALIST_PROMPT,
    output_key="installation_analysis_output",
    tools=[
        # MCPToolset temporarily disabled to fix podman error
        # TODO: Configure MCP server to run directly instead of in separate container
    ],
)