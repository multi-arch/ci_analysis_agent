"""Tests for the get_job_metadata function."""

import pytest
import os
import sys
from pathlib import Path
from .agent import get_job_metadata

class TestExtractInstallationInfo:
    """Test cases for get_job_metadata function."""
    
    @pytest.fixture
    def sample_log_content(self):
        """Load the sample build-log.txt content for testing."""
        current_dir = Path(__file__).parent
        artifacts_dir = current_dir / "test_artifacts"
        build_log_path = artifacts_dir / "build-log.txt"
        print(f"build_log_path: {build_log_path}")
        with open(build_log_path, 'r') as f:
            return f.read()

    @pytest.fixture
    def sample_failing_log_content(self):
        """Load the sample failing-build-log.txt content for testing."""
        current_dir = Path(__file__).parent
        artifacts_dir = current_dir / "test_artifacts"
        build_log_path = artifacts_dir / "failing-build-log.txt"
        print(f"build_log_path: {build_log_path}")
        with open(build_log_path, 'r') as f:
            return f.read()

    @pytest.fixture
    def sample_failing_log_content2(self):
        """Load the sample failing-build-log.txt content for testing."""
        current_dir = Path(__file__).parent
        artifacts_dir = current_dir / "test_artifacts"
        build_log_path = artifacts_dir / "failing-build-log-2.txt"
        print(f"build_log_path: {build_log_path}")
        with open(build_log_path, 'r') as f:
            return f.read()

    def test_extract_installation_info_from_passing_log(self, sample_log_content):
        """Test extraction with the actual sample log file."""
        result = get_job_metadata(sample_log_content)
  
  # Verify the structure exists
        assert isinstance(result, dict)
        assert "test_name" in result
        assert "status" in result
        assert "failure_reason" not in result

        # Verify extracted values match the actual log content
        assert result["test_name"] == "ocp-e2e-aws-ovn-multi-a-a"
        assert result["status"] == "succeeded"
        
    def test_extract_installation_info_from_failing_log1(self, sample_failing_log_content):
        """Test extraction with an actual failing sample log file."""
        result = get_job_metadata(sample_failing_log_content)
  
  # Verify the structure exists
        assert isinstance(result, dict)
        assert "test_name" in result
        assert "status" in result
        assert "failure_reason" in result

        # Verify extracted values match the actual log content
        assert result["test_name"] == None
        assert result["status"] == "failed"
        assert result["failure_reason"] == "resolving_inputs:resolving_release"


    def test_extract_installation_info_from_failing_log2(self, sample_failing_log_content2):
        """Test extraction with an actual failing sample log file."""
        result = get_job_metadata(sample_failing_log_content2)
  
  # Verify the structure exists
        assert isinstance(result, dict)
        assert "test_name" in result
        assert "status" in result
        assert "failure_reason" in result

        # Verify extracted values match the actual log content
        assert result["test_name"] == "ocp-e2e-gcp-ovn-multi-x-ax"
        assert result["status"] == "failed"
        assert result["failure_reason"] == "executing_graph:step_failed:utilizing_lease:executing_test:executing_multi_stage_test"