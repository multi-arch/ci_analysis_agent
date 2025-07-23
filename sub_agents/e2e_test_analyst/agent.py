"""E2E Test Analyst Agent for analyzing CI e2e test logs."""

from google.adk import Agent
from google.adk.models.lite_llm import LiteLlm
from . import prompt

import asyncio
import httpx
import threading
import concurrent.futures
import re
from typing import Dict, Any, Optional, List

GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

MODEL = LiteLlm(model="ollama_chat/qwen3:4b")

# Prow tool functions for e2e test analysis
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

def extract_test_commit_info(log_content: str) -> Dict[str, Any]:
    """Extract openshift-tests binary commit information from logs."""
    commit_info = {
        "release_image": None,
        "commit_hash": None,
        "origin_repo": "https://github.com/openshift/origin",
        "binary_info": {}
    }
    
    # Extract release image information (handle escaped quotes)
    release_image_patterns = [
        r'release image "([^"]+)"',
        r'release image \\"([^"]+)\\"',
        r'RELEASE_IMAGE_LATEST for release image \\"([^"]+)\\"'
    ]
    
    for pattern in release_image_patterns:
        release_match = re.search(pattern, log_content)
        if release_match:
            commit_info["release_image"] = release_match.group(1)
            break
    
    # Extract commit hash from release image SHA
    sha_pattern = r'sha256:([a-f0-9]+)'
    sha_match = re.search(sha_pattern, log_content)
    if sha_match:
        commit_info["commit_hash"] = sha_match.group(1)[:12]  # Use first 12 chars
    
    # Extract binary path information
    binary_path_pattern = r'Using path for binaries ([^\s]+)'
    binary_match = re.search(binary_path_pattern, log_content)
    if binary_match:
        commit_info["binary_info"]["path"] = binary_match.group(1)
    
    # Extract test count information
    test_count_pattern = r'Found (\d+) internal tests in openshift-tests binary'
    test_count_match = re.search(test_count_pattern, log_content)
    if test_count_match:
        commit_info["binary_info"]["test_count"] = int(test_count_match.group(1))
    
    return commit_info

def extract_failed_tests(log_content: str) -> List[Dict[str, str]]:
    """Extract failed test information from logs."""
    failed_tests = []
    
    # Common failure patterns in openshift-tests
    failure_patterns = [
        r'FAIL: (.*?) \((\d+\.\d+s)\)',  # Standard test failure
        r'• Failure \[(\d+\.\d+) seconds\]\n(.*?)\n',  # Ginkgo failure
        r'Test Failed: (.*?) - (.*?)\n',  # Direct test failure
        r'\[FAILED\] (.*?) \[(\d+\.\d+) seconds\]',  # Another format
    ]
    
    for pattern in failure_patterns:
        matches = re.findall(pattern, log_content, re.MULTILINE | re.DOTALL)
        for match in matches:
            if len(match) >= 2:
                test_name = match[0].strip() if match[0] else match[1].strip()
                failed_tests.append({
                    "test_name": test_name,
                    "duration": match[1] if len(match) > 1 else "unknown"
                })
    
    return failed_tests

def generate_source_code_links(test_name: str, commit_hash: Optional[str] = None) -> Dict[str, str]:
    """Generate source code links for a test."""
    base_url = "https://github.com/openshift/origin"
    
    # Clean up test name to extract the actual test function/describe block
    cleaned_test_name = test_name.replace("[", "").replace("]", "") if test_name else ""
    
    # Create search URLs
    links = {
        "repo_url": base_url,
        "search_url": f"{base_url}/search?q={cleaned_test_name.replace(' ', '+')}&type=code",
        "tests_directory": f"{base_url}/tree/master/test/extended"
    }
    
    if commit_hash:
        links["commit_url"] = f"{base_url}/commit/{commit_hash}"
        links["tests_at_commit"] = f"{base_url}/tree/{commit_hash}/test/extended"
    
    return links

async def get_e2e_test_logs_async(job_name: str, build_id: str) -> str:
    """Get e2e test logs from Prow."""
    # Extract job short name from full job name
    job_parts = job_name.split('-')
    if len(job_parts) >= 8:
        job_short_name = '-'.join(job_parts[7:])  # Everything after the 7th part
    else:
        job_short_name = job_name.split('-')[-1]  # Fallback to last part
    
    # E2E test logs are typically in openshift-e2e-test directory
    e2e_test_path = f"artifacts/{job_short_name}/openshift-e2e-test/build-log.txt"
    
    base_url = f"{GCS_URL}/{job_name}/{build_id}"
    e2e_test_url = f"{base_url}/{e2e_test_path}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(e2e_test_url)
            response.raise_for_status()
            
            log_content = response.text
            
            # Check if we got HTML instead of log content
            if log_content.strip().startswith('<!doctype html>') or log_content.strip().startswith('<html'):
                return f"""❌ E2E TEST ANALYSIS FAILED
                
Could not find e2e test logs for job: {job_name}
Build ID: {build_id}

🔍 DEBUGGING INFO:
- Job short name extracted: {job_short_name}
- Base URL: {base_url}
- Tried path: {e2e_test_path}

🔗 Manual check: {base_url}/

⚠️ POSSIBLE CAUSES:
1. Build ID might be invalid or logs not yet available
2. Job might not have e2e test logs (e.g., installation-only jobs)
3. Directory structure might be different for this job type
4. Logs might be in a different location

💡 SUGGESTIONS:
1. Verify the Prow job URL is correct
2. Check if the job has completed successfully
3. Try browsing the base URL manually to see available directories
4. Use a different job that includes e2e test steps"""
            
            # Extract commit and test information
            commit_info = extract_test_commit_info(log_content)
            failed_tests = extract_failed_tests(log_content)
            
            # Build enhanced response
            result = f"🧪 E2E TEST ANALYSIS from {e2e_test_path}:\n\n"
            
            # Add commit information
            if commit_info["release_image"]:
                result += f"🔍 OPENSHIFT-TESTS BINARY INFO:\n"
                result += f"   Release Image: {commit_info['release_image']}\n"
                if commit_info["commit_hash"]:
                    result += f"   Commit Hash: {commit_info['commit_hash']}\n"
                    result += f"   Origin Repo: {commit_info['origin_repo']}\n"
                    result += f"   Source Code: {commit_info['origin_repo']}/tree/{commit_info['commit_hash']}/test/extended\n"
                if commit_info["binary_info"].get("test_count"):
                    result += f"   Test Count: {commit_info['binary_info']['test_count']} tests\n"
                result += "\n"
            
            # Add failed tests with source links
            if failed_tests:
                result += f"❌ FAILED TESTS ({len(failed_tests)} failures):\n"
                for test in failed_tests[:10]:  # Limit to first 10 failures
                    result += f"   • {test['test_name']}\n"
                    if test['duration'] != "unknown":
                        result += f"     Duration: {test['duration']}\n"
                    
                    # Add source code links
                    commit_hash = commit_info.get('commit_hash')
                    links = generate_source_code_links(test['test_name'], commit_hash)
                    result += f"     🔗 Search in source: {links['search_url']}\n"
                    result += f"     📁 Tests directory: {links['tests_directory']}\n"
                    result += "\n"
                
                if len(failed_tests) > 10:
                    result += f"   ... and {len(failed_tests) - 10} more failures\n\n"
            else:
                result += "✅ NO FAILED TESTS DETECTED\n\n"
            
            # Add key logs section (first 50 lines and last 50 lines)
            lines = log_content.split('\n')
            result += "📝 KEY LOG SECTIONS:\n"
            result += "--- First 20 lines ---\n"
            result += '\n'.join(lines[:20]) + "\n\n"
            
            if len(lines) > 40:
                result += "--- Last 20 lines ---\n"
                result += '\n'.join(lines[-20:]) + "\n\n"
            
            # Add the full log content
            result += f"📋 FULL E2E TEST LOG:\n{log_content}"
            
            return result
            
        except httpx.HTTPError as e:
            return f"""❌ E2E TEST ANALYSIS FAILED
            
Could not find e2e test logs for job: {job_name}
Build ID: {build_id}

🔍 DEBUGGING INFO:
- Job short name extracted: {job_short_name}
- Base URL: {base_url}
- Tried path: {e2e_test_path}
- HTTP Error: {str(e)}

🔗 Manual check: {base_url}/

⚠️ POSSIBLE CAUSES:
1. Build ID might be invalid or logs not yet available
2. Job might not have e2e test logs (e.g., installation-only jobs)
3. Directory structure might be different for this job type
4. Logs might be in a different location

💡 SUGGESTIONS:
1. Verify the Prow job URL is correct
2. Check if the job has completed successfully
3. Try browsing the base URL manually to see available directories
4. Use a different job that includes e2e test steps"""
        except Exception as e:
            return f"❌ E2E TEST ANALYSIS ERROR: {str(e)}"

async def get_junit_results_async(job_name: str, build_id: str) -> str:
    """Get JUnit test results from Prow."""
    # Extract job short name from full job name
    job_parts = job_name.split('-')
    if len(job_parts) >= 8:
        job_short_name = '-'.join(job_parts[7:])  # Everything after the 7th part
    else:
        job_short_name = job_name.split('-')[-1]  # Fallback to last part
    
    # JUnit results are typically in junit directory
    junit_path = f"artifacts/{job_short_name}/openshift-e2e-test/junit_e2e_*.xml"
    
    base_url = f"{GCS_URL}/{job_name}/{build_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            # Try common JUnit file patterns
            junit_patterns = [
                f"artifacts/{job_short_name}/openshift-e2e-test/junit_e2e.xml",
                f"artifacts/{job_short_name}/openshift-e2e-test/junit_e2e_20*.xml",
                f"artifacts/{job_short_name}/openshift-e2e-test/artifacts/junit_e2e.xml"
            ]
            
            for pattern in junit_patterns:
                junit_url = f"{base_url}/{pattern}"
                try:
                    response = await client.get(junit_url)
                    response.raise_for_status()
                    return f"JUnit test results from {pattern}:\n\n{response.text}"
                except httpx.HTTPError:
                    continue
            
            return f"Could not find JUnit test results for {job_name}/{build_id}. Tried patterns: {', '.join(junit_patterns)}"
            
        except Exception as e:
            return f"Error fetching JUnit results: {str(e)}"

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

def get_e2e_test_logs_tool(job_name: str, build_id: str):
    """Get e2e test logs from the openshift-e2e-test directory with commit info and source code links."""
    return run_async_in_thread(get_e2e_test_logs_async(job_name, build_id))

def get_junit_results_tool(job_name: str, build_id: str):
    """Get JUnit test results from the e2e test artifacts."""
    return run_async_in_thread(get_junit_results_async(job_name, build_id))

e2e_test_analyst_agent = Agent(
    model=MODEL,
    name="e2e_test_analyst_agent",
    instruction=prompt.E2E_TEST_SPECIALIST_PROMPT,
    output_key="e2e_test_analysis_output",
    tools=[
        get_job_metadata_tool,
        get_e2e_test_logs_tool,
        get_junit_results_tool,
    ],
) 