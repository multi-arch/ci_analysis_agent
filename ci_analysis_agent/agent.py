# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CI Analysis coordinator: provide root cause analysis for CI failures"""

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm

from . import prompt
from sub_agents.installation_analyst import installation_analyst_agent
from sub_agents.e2e_test_analyst import e2e_test_analyst_agent
from sub_agents.mustgather_analyst import mustgather_analyst_agent

MODEL = LiteLlm(model="ollama_chat/qwen3:4b")

ci_analysis_advisor = LlmAgent(
    name="ci_analysis_advisor",
    model=MODEL,
    description=(
        "Analyzes CI jobs and provides root cause analysis for failures."
    ),
    instruction=prompt.CI_ANALYSIS_COORDINATOR_PROMPT,
    output_key="ci_analysis_advisor_output",
    tools=[
        AgentTool(agent=installation_analyst_agent),
        AgentTool(agent=e2e_test_analyst_agent),
        AgentTool(agent=mustgather_analyst_agent),
    ],
)

root_agent = ci_analysis_advisor 