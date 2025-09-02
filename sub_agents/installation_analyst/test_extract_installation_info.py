"""Tests for the extract_installation_info function."""

import pytest
import os
import sys
from pathlib import Path
from .agent import extract_installation_info

class TestExtractInstallationInfo:
    """Test cases for extract_installation_info function."""
    
    @pytest.fixture
    def sample_log_content(self):
        """Load the sample build-log.txt content for testing."""
        current_dir = Path(__file__).parent
        artifacts_dir = current_dir / "test_artifacts"
        build_log_path = artifacts_dir / "install-build-log.txt"
        print(f"build_log_path: {build_log_path}")
        with open(build_log_path, 'r') as f:
            return f.read()
    
    def test_extract_installation_info_with_sample_log(self, sample_log_content):
        """Test extraction with the actual sample log file."""
        result = extract_installation_info(sample_log_content)
        
        # Verify the structure exists
        assert isinstance(result, dict)
        assert "installer_version" in result
        assert "installer_commit" in result
        assert "release_image" in result
        assert "instance_types" in result
        assert "install_duration" in result
        assert "architecture" in result
        assert "cluster_config" in result
        assert "install_success" in result
        
        # Verify extracted values match the actual log content
        # Note: Current regex incorrectly captures "ersion" from header line - this is a known issue
        # The actual version line is "openshift-install v4.20.0" but the pattern matches the header first
        assert result["installer_version"] == "4.20.0"  # TODO: Fix regex to capture correct version
        assert result["installer_commit"] == "26d807e98014ca0c26bf4d0f219a3aaed2cd5405"
        assert result["release_image"] == "registry.build03.ci.openshift.org/ci-op-i1xhw661/release@sha256:3b8516fb6f45f612d9612a3524b20abf3e8922422e35499321ff06b5e6b13866"
        
        # Verify instance types
        assert result["instance_types"]["compute"] == "m6a.xlarge"
        assert result["instance_types"]["control_plane"] == "m6a.xlarge"
        
        # Verify architecture
        assert result["architecture"] == "amd64"
        
        # Verify cluster configuration
        assert result["cluster_config"]["compute_replicas"] == 3
        assert result["cluster_config"]["control_replicas"] == 3
        assert result["cluster_config"]["platform"] == "aws"
        assert result["cluster_config"]["region"] == "us-west-2"
        
        # Verify installation duration and success
        # Note: There are multiple "Time elapsed" entries, function returns the first one found
        assert result["install_duration"] == "15m44s"  # First occurrence in the log
        assert result["install_success"] is True
    
    def test_extract_installation_info_empty_log(self):
        """Test extraction with empty log content."""
        result = extract_installation_info("")
        
        # Should return default structure with None/False values
        expected_defaults = {
            "installer_version": None,
            "installer_commit": None,
            "release_image": None,
            "instance_types": {},
            "install_duration": None,
            "architecture": None,
            "cluster_config": {},
            "install_success": False
        }
        
        assert result == expected_defaults
    
    def test_extract_installation_info_partial_data(self):
        """Test extraction with partial log data."""
        partial_log = """
        openshift-install v4.19.0
        built from commit abc123def456
        Install complete!
        Time elapsed: 30m15s
        """
        
        result = extract_installation_info(partial_log)
        
        assert result["installer_version"] == "4.19.0"
        assert result["installer_commit"] == "abc123def456"
        assert result["install_duration"] == "30m15s"
        assert result["install_success"] is True
        assert result["release_image"] is None
        assert result["architecture"] is None
    
    def test_extract_installation_info_failed_install(self):
        """Test extraction with failed installation log."""
        failed_log = """
        openshift-install v4.18.0
        level=error msg="Installation failed"
        FATAL: Cluster installation failed
        """
        
        result = extract_installation_info(failed_log)
        
        assert result["installer_version"] == "4.18.0"
        assert result["install_success"] is False
    
    def test_extract_installation_info_quoted_version(self):
        """Test extraction with quoted version strings."""
        quoted_log = '''
        "openshift-install v4.17.0"
        "built from commit 26d807e98014ca0c26bf4d0f219a3aaed2cd5405
"
        '''
        
        result = extract_installation_info(quoted_log)
        
        assert result["installer_version"] == "4.17.0"
        assert result["installer_commit"] == "26d807e98014ca0c26bf4d0f219a3aaed2cd5405"
    
    def test_extract_installation_info_complex_config(self):
        """Test extraction of complex cluster configuration."""
        complex_log = """
        architecture: arm64
        platform:
          gcp:
            region: us-central1
        controlPlane:
          replicas: 5
          platform:
            gcp:
              type: n2-standard-8
        compute:
        - replicas: 10
          platform:
            gcp:
              type: n2-standard-4
        networkType: OVNKubernetes
        """
        
        result = extract_installation_info(complex_log)
        
        assert result["architecture"] == "arm64"
        assert result["cluster_config"]["platform"] == "gcp"
        assert result["cluster_config"]["region"] == "us-central1"
        assert result["cluster_config"]["control_replicas"] == 5
        assert result["cluster_config"]["compute_replicas"] == 10
        assert result["cluster_config"]["network_type"] == "OVNKubernetes"
        assert result["instance_types"]["control_plane"] == "n2-standard-8"
        assert result["instance_types"]["compute"] == "n2-standard-4"
    
    def test_extract_installation_info_multiple_release_patterns(self):
        """Test extraction with different release image patterns."""
        release_log1 = 'Installing from release registry.example.com/release:4.20'
        result1 = extract_installation_info(release_log1)
        assert result1["release_image"] == "registry.example.com/release:4.20"
        
        release_log2 = 'release image "registry.example.com/custom:latest"'
        result2 = extract_installation_info(release_log2)
        assert result2["release_image"] == "registry.example.com/custom:latest"
        
        release_log3 = 'RELEASE_IMAGE_LATEST for release image "registry.ci.openshift.org/release:v4.19"'
        result3 = extract_installation_info(release_log3)
        assert result3["release_image"] == "registry.ci.openshift.org/release:v4.19"
    
    def test_extract_installation_info_duration_formats(self):
        """Test extraction with different duration formats."""
        duration_log1 = 'Time elapsed: 1h30m45s'
        result1 = extract_installation_info(duration_log1)
        assert result1["install_duration"] == "1h30m45s"
        
        duration_log2 = '''Install complete!
        Some other text
        Time elapsed: 25m10s'''
        result2 = extract_installation_info(duration_log2)
        assert result2["install_duration"] == "25m10s"
    
    def test_extract_installation_info_network_type_variations(self):
        """Test extraction of different network types."""
        network_logs = [
            ("networkType: OpenShiftSDN", "OpenShiftSDN"),
            ("networkType: OVNKubernetes", "OVNKubernetes"),
            ("networkType: Calico", "Calico")
        ]
        
        for log_content, expected_network_type in network_logs:
            result = extract_installation_info(log_content)
            assert result["cluster_config"]["network_type"] == expected_network_type
    
    def test_extract_installation_info_instance_types_only_control_plane(self):
        """Test extraction when only control plane instance type is specified."""
        log_content = """
        controlPlane:
          platform:
            aws:
              type: m5.2xlarge
        """
        
        result = extract_installation_info(log_content)
        
        assert result["instance_types"]["control_plane"] == "m5.2xlarge"
        assert "compute" not in result["instance_types"]
    
    def test_extract_installation_info_instance_types_only_compute(self):
        """Test extraction when only compute instance type is specified."""
        log_content = """
        compute:
        - platform:
            aws:
              type: m5.large
        """
        
        result = extract_installation_info(log_content)
        
        assert result["instance_types"]["compute"] == "m5.large"
        assert "control_plane" not in result["instance_types"]
