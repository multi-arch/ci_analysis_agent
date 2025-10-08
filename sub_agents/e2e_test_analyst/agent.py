"""E2E Test Analyst Agent for analyzing CI e2e test logs."""

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field
from . import prompt
from ..common_drain import SimpleDrainExtractor

import asyncio
import httpx
import concurrent.futures
import re
import os
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List


GCS_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/test-platform-results/logs"

MODEL = os.environ.get("MODEL", "qwen3:1.7b")


class E2ETestAnalystInput(BaseModel):
    """Input schema for E2E Test Analyst Agent."""
    job_name: str = Field(
        description="The Prow job name extracted from the URL (e.g., 'periodic-ci-openshift-multiarch-master-nightly-4.21-ocp-e2e-ovn-remote-s2s-libvirt-ppc64le')"
    )
    build_id: str = Field(
        description="The build ID extracted from the Prow job URL (e.g., '1964900126069624832')"
    )

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

async def get_e2e_test_logs_async(job_name: str, build_id: str, test_name: str) -> str:
    """Get e2e test logs from Prow."""
   
    # E2E test logs are typically in openshift-e2e-test directory
    if "sno" in test_name:
        e2e_test_path = f"artifacts/{test_name}/single-node-e2e-test/build-log.txt"
    elif "libvirt" in test_name:
        e2e_test_path = f"artifacts/{test_name}/openshift-e2e-libvirt-test/build-log.txt"
    else:
        e2e_test_path = f"artifacts/{test_name}/openshift-e2e-test/build-log.txt"
    
    base_url = f"{GCS_URL}/{job_name}/{build_id}"
    e2e_test_url = f"{base_url}/{e2e_test_path}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(e2e_test_url)
            response.raise_for_status()
            
            log_content = response.text
            
            # Check if we got HTML instead of log content
            if log_content.strip().startswith('<!doctype html>') or log_content.strip().startswith('<html'):
                return f"""❌ E2E TEST LOGS NOT FOUND

Job: {job_name} (Build: {build_id})
Path tried: {e2e_test_path}

This job may not include e2e tests or logs are in a different location.
Manual check: {base_url}/"""
            
            # Extract commit and test information
            commit_info = extract_test_commit_info(log_content)
            failed_tests = extract_failed_tests(log_content)
            
            # Build enhanced response
            result = f"🧪 E2E TEST ANALYSIS from {e2e_test_path}:\n\n"
            
            # Add commit information
            if commit_info["release_image"]:
                result += "🔍 OPENSHIFT-TESTS BINARY INFO:\n"
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
                    
                    # Add single consolidated source code link
                    commit_hash = commit_info.get('commit_hash')
                    links = generate_source_code_links(test['test_name'], commit_hash)
                    result += f"     🔗 Source: {links['search_url']}\n"
                
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
            
            # Add filtered log content using drain - exclude passing/skipped tests
            try:
                config_path = f"{os.path.dirname(__file__)}/drain3.ini"
                # Exclude patterns for non-failure content
                # Be aggressive: exclude ALL routine operations, keep ONLY failures/errors/warnings
                exclude_patterns = [
                    r'^\s*PASS:',                    # Passing tests
                    r'^\s*\[PASSED\]',               # Passed marker
                    r'^\s*• \[PASSED\]',             # Ginkgo passed
                    r'^\s*✓',                        # Checkmark for pass
                    r'^\s*\[SKIPPED\]',              # Skipped tests
                    r'^\s*• \[SKIPPED\]',            # Ginkgo skipped
                    r'skip \[',                       # Skip marker
                    r'Skipping',                      # Skipping marker
                    r'passed: .*',                    # Explicit pass
                    r'skipped: .*',                   # Explicit skip
                    r'started: .*',                   # Test start notifications
                    r'level=info(?!.*(fail|error|timeout|unhealthy|unable|denied|refused|fatal|panic))',
                    r'^I\d{4} \d{2}:\d{2}:\d{2}\.\d+ \d+ (?!.*(fail|error|fatal))',
                ]
                drain_extractor = SimpleDrainExtractor(config_path, verbose=False, max_clusters=12, 
                                                      exclude_patterns=exclude_patterns)
                filtered_log = drain_extractor.filter_log(log_content, max_lines=75)
                result += f"📋 FILTERED E2E TEST LOG (failure-focused):\n{filtered_log}"
            except Exception as e:
                # Fallback to truncated log if drain fails
                lines = log_content.split('\n')
                truncated_log = '\n'.join(lines[:50] + ['...(truncated)...'] + lines[-50:])
                result += f"📋 E2E TEST LOG (truncated - drain failed: {str(e)}):\n{truncated_log}"
            
            return result
            
        except httpx.HTTPError as e:
            return f"""❌ E2E TEST LOGS NOT FOUND

Job: {job_name} (Build: {build_id})
Path tried: {e2e_test_path}
Error: {str(e)}

Manual check: {base_url}/"""
        except Exception as e:
            return f"❌ E2E TEST ANALYSIS ERROR: {str(e)}"

async def get_junit_results_async(job_name: str, build_id: str, test_name: str) -> str:
    """Get JUnit test results from Prow."""
      # E2E test logs are typically in openshift-e2e-test directory
    if "sno" in test_name:
        e2e_test_path = f"artifacts/{test_name}/single-node-e2e-test"
    elif "libvirt" in test_name:
        e2e_test_path = f"artifacts/{test_name}/openshift-e2e-libvirt-test"
    else:
        e2e_test_path = f"artifacts/{test_name}/openshift-e2e-test"

    
    base_url = f"{GCS_URL}/{job_name}/{build_id}"
    
    async with httpx.AsyncClient() as client:
        try:
            # Try common JUnit file patterns
            junit_patterns = [
                f"{e2e_test_path}/junit_e2e.xml",
                f"{e2e_test_path}/junit_e2e_20*.xml",
                f"{e2e_test_path}/artifacts/junit_e2e.xml",
                f"{e2e_test_path}/artifacts/junit/junit_e2e.xml",
                f"{e2e_test_path}/artifacts/junit/junit_e2e_20*.xml"
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

def parse_junit_xml_failures(xml_content: str) -> Dict[str, Any]:
    """Parse JUnit XML and extract only failed/errored tests.
    
    Args:
        xml_content: Raw JUnit XML content
        
    Returns:
        dict with summary stats and list of failed tests
    """
    try:
        root = ET.fromstring(xml_content)
        
        # Handle both <testsuite> root and <testsuites> wrapper
        if root.tag == 'testsuites':
            testsuites = root.findall('testsuite')
        else:
            testsuites = [root]
        
        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0
        failed_tests = []
        
        for testsuite in testsuites:
            # Get suite-level stats
            suite_name = testsuite.get('name', 'unknown')
            total_tests += int(testsuite.get('tests', 0))
            total_failures += int(testsuite.get('failures', 0))
            total_errors += int(testsuite.get('errors', 0))
            total_skipped += int(testsuite.get('skipped', 0))
            
            # Find all testcases with failures or errors
            for testcase in testsuite.findall('testcase'):
                failure = testcase.find('failure')
                error = testcase.find('error')
                
                if failure is not None or error is not None:
                    test_info = {
                        'name': testcase.get('name', 'unknown'),
                        'time': testcase.get('time', '0'),
                        'classname': testcase.get('classname', ''),
                    }
                    
                    if failure is not None:
                        test_info['type'] = 'failure'
                        test_info['message'] = failure.get('message', '')
                        test_info['details'] = (failure.text or '').strip()[:500]  # Limit details
                    elif error is not None:
                        test_info['type'] = 'error'
                        test_info['message'] = error.get('message', '')
                        test_info['details'] = (error.text or '').strip()[:500]
                    
                    failed_tests.append(test_info)
        
        return {
            'success': True,
            'total_tests': total_tests,
            'total_failures': total_failures,
            'total_errors': total_errors,
            'total_skipped': total_skipped,
            'failed_tests': failed_tests
        }
        
    except ET.ParseError as e:
        return {
            'success': False,
            'error': f'XML parsing error: {str(e)}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Error processing JUnit XML: {str(e)}'
        }

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
    """Retrieves comprehensive metadata and status information for a specific Prow CI job.
    
    This tool fetches the prowjob.json metadata which contains essential information about
    the CI job execution, including current status, build configuration, test targets,
    and execution parameters. This is typically the first tool to use when analyzing a failed CI job.

    Args:
        job_name (str): The name of the Prow job (e.g., 'periodic-ci-openshift-multiarch-master-nightly-4.20-ocp-e2e-aws-ovn-sno')
        build_id (str): The specific build ID for the job run (e.g., '1940296163760541696')
    
    Returns:
        dict: Job metadata including status, build_id, job_name, test_name, and error details if applicable
    """
    return run_async_in_thread(get_job_metadata_async(job_name, build_id))

def get_e2e_test_logs_tool(job_name: str, build_id: str, test_name: str, include_full_log: bool = False):
    """Analyzes end-to-end test execution logs with source code tracing and failure analysis.
    
    This tool retrieves and analyzes e2e test logs from the openshift-e2e-test directory,
    extracting critical information including failed test details, openshift-tests binary version,
    source code commit information, and direct links to test source code for debugging.

    Args:
        job_name (str): The name of the Prow job containing e2e tests
        build_id (str): The specific build ID for the job run  
        test_name (str): The test component name (e.g., 'ocp-e2e-aws-ovn-sno-multi-a-a')
        include_full_log (bool, optional): Whether to include the complete log content in response.
                                         If False, only provides summary and key sections. Defaults to True.
    
    Returns:
        str: Comprehensive e2e test analysis including failed tests with source links, 
             openshift-tests binary info, and formatted log content
    """
    result = run_async_in_thread(get_e2e_test_logs_async(job_name, build_id, test_name))
    
    # If include_full_log is False, remove the full log section to reduce response size
    if not include_full_log and isinstance(result, str):
        lines = result.split('\n')
        filtered_lines = []
        skip_full_log = False
        
        for line in lines:
            if line.startswith('📋 FULL E2E TEST LOG:'):
                skip_full_log = True
                continue
            if not skip_full_log:
                filtered_lines.append(line)
        
        result = '\n'.join(filtered_lines)
    
    return result

def get_junit_results_tool(job_name: str, build_id: str, test_name: str, parse_xml: bool = True):
    """Retrieves JUnit XML test results from e2e test execution with structured failure analysis.
    
    This tool fetches JUnit XML files generated by e2e test runs, which contain structured
    test results including pass/fail status, execution times, error messages, and detailed
    failure information. The XML is automatically parsed to extract ONLY failed/errored tests.

    Args:
        job_name (str): The name of the Prow job containing e2e tests
        build_id (str): The specific build ID for the job run
        test_name (str): The test component name that generated JUnit results
        parse_xml (bool, optional): Whether to parse XML and extract only failures.
                                   If True, returns structured failure data. If False, returns raw XML.
                                   Defaults to True.
    
    Returns:
        str: Structured failure summary if parse_xml=True, or raw XML if False.
             Returns error message if results are not found.
    """
    result = run_async_in_thread(get_junit_results_async(job_name, build_id, test_name))
    
    # Check if we got an error message
    if isinstance(result, str) and (result.startswith("Could not find") or result.startswith("Error")):
        return result
    
    # Parse XML content if requested
    if parse_xml and isinstance(result, str) and result.startswith("JUnit test results"):
        # Extract the XML content (it comes after the first line)
        lines = result.split('\n', 1)
        if len(lines) > 1:
            xml_content = lines[1]
            parsed = parse_junit_xml_failures(xml_content)
            
            if not parsed['success']:
                # Fall back to raw XML if parsing fails
                return f"⚠️ XML parsing failed: {parsed['error']}\n\nRaw content:\n{result[:2000]}..."
            
            # Format the parsed results nicely
            output = "📊 JUNIT TEST RESULTS SUMMARY:\n\n"
            output += f"📈 Overall Statistics:\n"
            output += f"   Total Tests: {parsed['total_tests']}\n"
            output += f"   ✅ Passed: {parsed['total_tests'] - parsed['total_failures'] - parsed['total_errors'] - parsed['total_skipped']}\n"
            output += f"   ❌ Failed: {parsed['total_failures']}\n"
            output += f"   💥 Errors: {parsed['total_errors']}\n"
            output += f"   ⏭️  Skipped: {parsed['total_skipped']}\n\n"
            
            if parsed['failed_tests']:
                output += f"❌ FAILED/ERRORED TESTS ({len(parsed['failed_tests'])} tests):\n\n"
                for i, test in enumerate(parsed['failed_tests'][:20], 1):  # Limit to 20
                    output += f"{i}. {test['name']}\n"
                    output += f"   Type: {test['type'].upper()}\n"
                    output += f"   Duration: {test['time']}s\n"
                    if test['message']:
                        output += f"   Message: {test['message']}\n"
                    if test['details']:
                        # Truncate long details
                        details = test['details'][:300]
                        if len(test['details']) > 300:
                            details += "..."
                        output += f"   Details: {details}\n"
                    output += "\n"
                
                if len(parsed['failed_tests']) > 20:
                    output += f"   ... and {len(parsed['failed_tests']) - 20} more failures\n"
            else:
                output += "✅ NO FAILURES OR ERRORS FOUND\n"
            
            return output
    
    # Return raw result if not parsing
    return result

e2e_test_analyst_agent = LlmAgent(
    model=LiteLlm(model=MODEL),
    name="e2e_test_analyst_agent",
    instruction=prompt.E2E_TEST_SPECIALIST_PROMPT,
    output_key="e2e_test_analysis_output",
    input_schema=E2ETestAnalystInput,
    tools=[
        get_job_metadata_tool,
        get_e2e_test_logs_tool,
        get_junit_results_tool,
    ],
)