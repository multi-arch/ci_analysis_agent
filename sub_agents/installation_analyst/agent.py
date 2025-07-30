"""Installation Analyst Agent for analyzing CI installation logs."""

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from . import prompt
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams
import re
from typing import Dict, Any

MODEL = LiteLlm(model="ollama_chat/qwen3:4b")

def extract_installation_info(log_content: str) -> Dict[str, Any]:
    """Extract installation information from build-log.txt."""
    install_info = {
        "installer_version": None,
        "installer_commit": None,
        "release_image": None,
        "instance_types": {},
        "install_duration": None,
        "architecture": None,
        "cluster_config": {},
        "install_success": False
    }
    
    # Extract openshift-install version and commit (can be on separate lines)
    version_patterns = [
        r'openshift-install v([^\s"]+)',
        r'"openshift-install v([^\s"]+)"'
    ]
    
    for pattern in version_patterns:
        version_match = re.search(pattern, log_content)
        if version_match:
            install_info["installer_version"] = version_match.group(1)
            break
    
    # Extract commit (separate pattern)
    commit_patterns = [
        r'built from commit ([a-f0-9]+)',
        r'"built from commit ([a-f0-9]+)"'
    ]
    
    for pattern in commit_patterns:
        commit_match = re.search(pattern, log_content)
        if commit_match:
            install_info["installer_commit"] = commit_match.group(1)
            break
    
    # Extract release image
    release_patterns = [
        r'Installing from release ([^\s]+)',
        r'release image "([^"]+)"',
        r'RELEASE_IMAGE_LATEST for release image "([^"]+)"'
    ]
    for pattern in release_patterns:
        release_match = re.search(pattern, log_content)
        if release_match:
            install_info["release_image"] = release_match.group(1)
            break
    
    # Extract instance types from install-config.yaml section
    # Look for compute and controlPlane sections
    compute_type_pattern = r'compute:.*?type:\s*([^\s\n]+)'
    control_type_pattern = r'controlPlane:.*?type:\s*([^\s\n]+)'
    
    compute_match = re.search(compute_type_pattern, log_content, re.DOTALL)
    if compute_match:
        install_info["instance_types"]["compute"] = compute_match.group(1)
    
    control_match = re.search(control_type_pattern, log_content, re.DOTALL)
    if control_match:
        install_info["instance_types"]["control_plane"] = control_match.group(1)
    
    # Extract architecture
    arch_pattern = r'architecture:\s*([^\s\n]+)'
    arch_match = re.search(arch_pattern, log_content)
    if arch_match:
        install_info["architecture"] = arch_match.group(1)
    
    # Extract cluster configuration details
    # Replicas
    compute_replicas_pattern = r'compute:.*?replicas:\s*(\d+)'
    control_replicas_pattern = r'controlPlane:.*?replicas:\s*(\d+)'
    
    compute_replicas_match = re.search(compute_replicas_pattern, log_content, re.DOTALL)
    if compute_replicas_match:
        install_info["cluster_config"]["compute_replicas"] = int(compute_replicas_match.group(1))
    
    control_replicas_match = re.search(control_replicas_pattern, log_content, re.DOTALL)
    if control_replicas_match:
        install_info["cluster_config"]["control_replicas"] = int(control_replicas_match.group(1))
    
    # Network type
    network_pattern = r'networkType:\s*([^\s\n]+)'
    network_match = re.search(network_pattern, log_content)
    if network_match:
        install_info["cluster_config"]["network_type"] = network_match.group(1)
    
    # Platform and region
    platform_pattern = r'platform:\s*([^\s\n]+):'
    region_pattern = r'region:\s*([^\s\n]+)'
    
    platform_match = re.search(platform_pattern, log_content)
    if platform_match:
        install_info["cluster_config"]["platform"] = platform_match.group(1)
    
    region_match = re.search(region_pattern, log_content)
    if region_match:
        install_info["cluster_config"]["region"] = region_match.group(1)
    
    # Extract install duration (clean up quotes)
    duration_patterns = [
        r'Time elapsed:\s*([^\n"]+)',
        r'Install complete!.*?Time elapsed:\s*([^\n"]+)'
    ]
    
    for pattern in duration_patterns:
        duration_match = re.search(pattern, log_content, re.DOTALL)
        if duration_match:
            duration = duration_match.group(1).strip().strip('"')
            install_info["install_duration"] = duration
            break
    
    # Check if installation was successful
    if "Install complete!" in log_content:
        install_info["install_success"] = True
    elif "level=error" in log_content or "FATAL" in log_content:
        install_info["install_success"] = False
    
    return install_info

installation_analyst_agent = Agent(
    model=MODEL,
    name="installation_analyst_agent",
    instruction=prompt.INSTALLATION_SPECIALIST_PROMPT,
    output_key="installation_analysis_output",
    tools=[   MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url="http://127.0.0.1:9000/mcp",
            tool_filter=['get_install_logs', 'get_job_metadata'],
        )
    ), 
    ],
)

root_agent = installation_analyst_agent