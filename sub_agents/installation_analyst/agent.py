"""Installation Analyst Agent for analyzing CI installation logs."""

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from . import prompt

import asyncio
import httpx
import threading
import concurrent.futures
import re
from typing import Dict, Any, Optional

GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

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

# Prow tool functions for installation analysis
async def get_job_metadata_async(job_name: str, build_id: str) -> Dict[str, Any]:
    """Get the metadata and status for a specific Prow job name and build id."""
    url = f"{GCS_URL}/{job_name}/{build_id}/prowjob.json"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
        if not data:
            return {"error": "No response from Prow API"}
            
        job_spec = data.get("spec", {})
        job_status = data.get("status", {})
        
        build_id_from_status = job_status.get("build_id")
        status = job_status.get("state")
        args = job_spec.get("pod_spec", {}).get("containers", [])[0].get("args", [])
        test_name = ""
        for arg in args: 
            if arg.startswith("--target="):
                test_name = arg.replace("--target=", "")
        
        return {
            "status": status, 
            "build_id": build_id_from_status, 
            "job_name": job_name,
            "test_name": test_name
        }
            
    except Exception as e:
        return {"error": f"Failed to fetch job info: {str(e)}"}

async def get_install_logs_async(job_name: str, build_id: str) -> str:
    """Get installation logs from build-log.txt in installation directories."""
    # Extract job short name from full job name
    job_parts = job_name.split('-')
    if len(job_parts) >= 8:
        job_short_name = '-'.join(job_parts[7:])  # Everything after the 7th part
    else:
        job_short_name = job_name.split('-')[-1]  # Fallback to last part
    
    # Try both possible installation directory patterns
    install_dirs = [
        f"artifacts/{job_short_name}/ipi-install-install",
        f"artifacts/{job_short_name}/ipi-install-install-stableinitial"
    ]
    
    base_url = f"{GCS_URL}/{job_name}/{build_id}"
    
    async with httpx.AsyncClient() as client:
        for install_dir in install_dirs:
            try:
                # Get the build-log.txt from this installation directory
                log_url = f"{base_url}/{install_dir}/build-log.txt"
                
                response = await client.get(log_url)
                response.raise_for_status()
                
                log_content = response.text
                
                # Check if we got HTML instead of log content
                if log_content.strip().startswith('<!doctype html>') or log_content.strip().startswith('<html'):
                    continue  # Try next directory pattern
                
                # Extract installation information
                install_info = extract_installation_info(log_content)
                
                # Build enhanced response
                result = f"📋 INSTALLATION ANALYSIS from {install_dir}/build-log.txt:\n\n"
                
                # Add installer information
                result += "🔧 OPENSHIFT-INSTALL BINARY INFO:\n"
                if install_info["installer_version"]:
                    result += f"   Version: {install_info['installer_version']}\n"
                if install_info["installer_commit"]:
                    result += f"   Commit: {install_info['installer_commit']}\n"
                    result += f"   🔗 Installer Source: https://github.com/openshift/installer/commit/{install_info['installer_commit']}\n"
                if install_info["release_image"]:
                    result += f"   Release Image: {install_info['release_image']}\n"
                result += "\n"
                
                # Add cluster configuration
                result += "🏗️ CLUSTER CONFIGURATION:\n"
                if install_info["architecture"]:
                    result += f"   Architecture: {install_info['architecture']}\n"
                if install_info["cluster_config"].get("platform"):
                    result += f"   Platform: {install_info['cluster_config']['platform']}\n"
                if install_info["cluster_config"].get("region"):
                    result += f"   Region: {install_info['cluster_config']['region']}\n"
                if install_info["cluster_config"].get("network_type"):
                    result += f"   Network Type: {install_info['cluster_config']['network_type']}\n"
                
                # Control plane and compute configuration
                if install_info["cluster_config"].get("control_replicas"):
                    result += f"   Control Plane Replicas: {install_info['cluster_config']['control_replicas']}\n"
                if install_info["cluster_config"].get("compute_replicas"):
                    result += f"   Compute Replicas: {install_info['cluster_config']['compute_replicas']}\n"
                result += "\n"
                
                # Add instance types
                if install_info["instance_types"]:
                    result += "💻 INSTANCE TYPES:\n"
                    if install_info["instance_types"].get("control_plane"):
                        result += f"   Control Plane: {install_info['instance_types']['control_plane']}\n"
                    if install_info["instance_types"].get("compute"):
                        result += f"   Compute: {install_info['instance_types']['compute']}\n"
                    result += "\n"
                
                # Add installation results
                result += "⏱️ INSTALLATION RESULTS:\n"
                if install_info["install_duration"]:
                    result += f"   Duration: {install_info['install_duration']}\n"
                
                status_emoji = "✅" if install_info["install_success"] else "❌"
                status_text = "SUCCESS" if install_info["install_success"] else "FAILED"
                result += f"   Status: {status_emoji} {status_text}\n\n"
                
                # Add key logs section (first 50 lines and last 50 lines)
                lines = log_content.split('\n')
                result += "📝 KEY LOG SECTIONS:\n"
                result += "--- First 20 lines ---\n"
                result += '\n'.join(lines[:20]) + "\n\n"
                
                if len(lines) > 40:
                    result += "--- Last 20 lines ---\n"
                    result += '\n'.join(lines[-20:]) + "\n\n"
                
                # Add full log content
                result += f"📋 FULL INSTALLATION LOG:\n{log_content}"
                
                return result
                
            except httpx.HTTPError:
                continue  # Try next directory pattern
            except Exception as e:
                continue  # Try next directory pattern
        
        # If no logs found, return error message with helpful details
        return f"""❌ INSTALLATION ANALYSIS FAILED
        
Could not find installation logs for job: {job_name}
Build ID: {build_id}

🔍 DEBUGGING INFO:
- Job short name extracted: {job_short_name}
- Base URL: {base_url}
- Tried directories: {', '.join(install_dirs)}

🔗 Manual check: {base_url}/

⚠️ POSSIBLE CAUSES:
1. Build ID might be invalid or logs not yet available
2. Job might not have installation logs (e.g., upgrade-only jobs)
3. Directory structure might be different for this job type
4. Logs might be in a different location

💡 SUGGESTIONS:
1. Verify the Prow job URL is correct
2. Check if the job has completed successfully
3. Try browsing the base URL manually to see available directories
4. Use a different job that includes installation steps"""

def run_async_in_thread(coro):
    """Run async function in a thread to avoid event loop conflicts."""
    
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result()

def get_job_metadata_tool(job_name: str, build_id: str):
    """Get metadata and status for a specific Prow job name and build ID."""
    return run_async_in_thread(get_job_metadata_async(job_name, build_id))

def get_install_logs_tool(job_name: str, build_id: str):
    """Get installation logs from build-log.txt in installation directories with detailed analysis."""
    return run_async_in_thread(get_install_logs_async(job_name, build_id))

installation_analyst_agent = Agent(
    model=MODEL,
    name="installation_analyst_agent",
    instruction=prompt.INSTALLATION_SPECIALIST_PROMPT,
    output_key="installation_analysis_output",
    tools=[
        get_job_metadata_tool,
        get_install_logs_tool,
    ],
)