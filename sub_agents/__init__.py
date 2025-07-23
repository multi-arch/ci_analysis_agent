"""Sub-agents package for CI Analysis Agent.

This directory contains specialized sub-agents for different analysis tasks.
This is not a standalone agent, but a package containing other agents.
"""
from . import installation_analyst

# This directory is not an agent itself, but contains sub-agents
# Individual agents are in subdirectories:
# - installation_analyst/
# - e2e_test_analyst/
# - mustgather_analyst/ 