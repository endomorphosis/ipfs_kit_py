#!/usr/bin/env python
"""
Test cases for IPFS Cluster auto-retry functionality in ipfs_kit_py.

This module tests the auto_retry_on_daemon_failure decorator for IPFS Cluster
operations, verifying that cluster operations automatically retry when the
cluster daemon is not running and auto_start_daemons is enabled.
"""

import os
import unittest
import logging
import pytest
from unittest.mock import patch, MagicMock

# Import the ipfs_kit module
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.error import IPFSError, create_result_dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestClusterAutoRetry(unittest.TestCase):
    """Test cases for automatic daemon retry functionality with IPFS Cluster."""

    # # # @pytest.mark.skip(reason="Method _ensure_daemon_running not found in ipfs_kit") - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py
    @patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service.ipfs_cluster_service_start')
    @patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service.run_cluster_service_command')
    @patch('ipfs_kit_py.ipfs_cluster_ctl.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin')
    def test_cluster_pin_add_auto_retry(self, mock_add_pin, mock_run_cmd, mock_daemon_start):
        """Test auto retry for cluster_pin_add when daemon is not running."""
        # Mock behavior for checking daemon status (not running)
        def mock_ps_effect(*args, **kwargs):
            return {"success": True, "stdout": "process info without ipfs-cluster-service daemon"}

        # Mock daemon start (successful)
        mock_daemon_start.return_value = {"success": True, "status": "started"}

        # Mock run command for checking status
        mock_run_cmd.side_effect = mock_ps_effect

        # Mock successful pin add after daemon start
        mock_add_pin.return_value = {
            "success": True,
            "stdout": "pinned QmTestCid locally"
        }

        # Create ipfs_kit instance with auto_start_daemons=True
        with patch('ipfs_kit_py.ipfs_kit.ipfs_kit._ensure_daemon_running') as mock_ensure_daemon:
            # First call will report daemon not running, second call will report success
            mock_ensure_daemon.side_effect = [
                {"success": False, "error": "IPFS Cluster daemon is not running"},
                {"success": True, "message": "IPFS Cluster daemon started automatically"}
            ]

            kit = ipfs_kit(auto_start_daemons=True)

            # Add properties to make the instance look initialized
            kit.ipfs_cluster_ctl = MagicMock()
            kit.ipfs_cluster_ctl.ipfs_cluster_ctl_add_pin = mock_add_pin

            # Call method that should trigger the retry
            result = kit.cluster_pin_add(cid="QmTestCid")

            # Verify daemon_start was attempted via ensure_daemon_running
            self.assertEqual(mock_ensure_daemon.call_count, 2)

            # Verify operation succeeded after retry
            self.assertTrue(result["success"])
            self.assertTrue(mock_add_pin.called)

    # # # @pytest.mark.skip(reason="Method _ensure_daemon_running not found in ipfs_kit") - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py
    @patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service.ipfs_cluster_service_start')
    @patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service.run_cluster_service_command')
    @patch('ipfs_kit_py.ipfs_cluster_ctl.ipfs_cluster_ctl.ipfs_cluster_get_pinset')
    def test_cluster_pin_ls_auto_retry(self, mock_pin_ls, mock_run_cmd, mock_daemon_start):
        """Test auto retry for cluster_pin_ls when daemon is not running."""
        # Mock behavior for checking daemon status (not running)
        def mock_ps_effect(*args, **kwargs):
            return {"success": True, "stdout": "process info without ipfs-cluster-service daemon"}

        # Mock daemon start (successful)
        mock_daemon_start.return_value = {"success": True, "status": "started"}

        # Mock run command for checking status
        mock_run_cmd.side_effect = mock_ps_effect

        # Mock successful pin ls after daemon start
        mock_pin_ls.return_value = {
            "success": True,
            "stdout_json": [
                {"cid": "QmTestCid1", "name": "test1", "status": "pinned"},
                {"cid": "QmTestCid2", "name": "test2", "status": "pinned"}
            ]
        }

        # Create ipfs_kit instance with auto_start_daemons=True
        with patch('ipfs_kit_py.ipfs_kit.ipfs_kit._ensure_daemon_running') as mock_ensure_daemon:
            # First call will report daemon not running, second call will report success
            mock_ensure_daemon.side_effect = [
                {"success": False, "error": "IPFS Cluster daemon is not running"},
                {"success": True, "message": "IPFS Cluster daemon started automatically"}
            ]

            kit = ipfs_kit(auto_start_daemons=True)

            # Add properties to make the instance look initialized
            kit.ipfs_cluster_ctl = MagicMock()
            kit.ipfs_cluster_ctl.ipfs_cluster_get_pinset = mock_pin_ls

            # Call method that should trigger the retry
            result = kit.cluster_pin_ls()

            # Verify operation succeeded after retry
            self.assertTrue(result["success"])
            self.assertTrue(mock_pin_ls.called)
            self.assertEqual(len(result.get("pins", [])), 2)

    # # # @pytest.mark.skip(reason="Method _ensure_daemon_running not found in ipfs_kit") - removed by fix_all_tests.py - removed by fix_all_tests.py - removed by fix_all_tests.py
    @patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service.ipfs_cluster_service_start')
    @patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service.run_cluster_service_command')
    @patch('ipfs_kit_py.ipfs_cluster_ctl.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_pin')
    def test_cluster_pin_rm_auto_retry(self, mock_pin_rm, mock_run_cmd, mock_daemon_start):
        """Test auto retry for cluster_pin_rm when daemon is not running."""
        # Mock behavior for checking daemon status (not running)
        def mock_ps_effect(*args, **kwargs):
            return {"success": True, "stdout": "process info without ipfs-cluster-service daemon"}

        # Mock daemon start (successful)
        mock_daemon_start.return_value = {"success": True, "status": "started"}

        # Mock run command for checking status
        mock_run_cmd.side_effect = mock_ps_effect

        # Mock successful pin rm after daemon start
        mock_pin_rm.return_value = {
            "success": True,
            "stdout": "unpinned QmTestCid"
        }

        # Create ipfs_kit instance with auto_start_daemons=True
        with patch('ipfs_kit_py.ipfs_kit.ipfs_kit._ensure_daemon_running') as mock_ensure_daemon:
            # First call will report daemon not running, second call will report success
            mock_ensure_daemon.side_effect = [
                {"success": False, "error": "IPFS Cluster daemon is not running"},
                {"success": True, "message": "IPFS Cluster daemon started automatically"}
            ]

            kit = ipfs_kit(auto_start_daemons=True)

            # Add properties to make the instance look initialized
            kit.ipfs_cluster_ctl = MagicMock()
            kit.ipfs_cluster_ctl.ipfs_cluster_ctl_remove_pin = mock_pin_rm

            # Call method that should trigger the retry
            result = kit.cluster_pin_rm(cid="QmTestCid")

            # Verify operation succeeded after retry
            self.assertTrue(result["success"])
            self.assertTrue(mock_pin_rm.called)

    # @pytest.mark.skip(reason="Issue with auto_retry_on_daemon_failure decorator") - removed by fix_all_tests.py
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit.auto_retry_on_daemon_failure')
    def test_decorator_parameters(self, mock_decorator):
        """Test that the decorator is called with correct parameters."""
        # This test verifies that our methods use the correct daemon type

        # Access the class directly to check decorator usage
        # Note: This doesn't instantiate the class
        cluster_pin_add = getattr(ipfs_kit, 'cluster_pin_add')
        cluster_pin_rm = getattr(ipfs_kit, 'cluster_pin_rm')
        cluster_pin_ls = getattr(ipfs_kit, 'cluster_pin_ls')
        cluster_status = getattr(ipfs_kit, 'cluster_status')

        # Verify decorator calls (these were made during class definition)
        mock_decorator.assert_any_call(daemon_type="ipfs_cluster_service", max_retries=3)

        # The decorator should have been called at least 4 times (once for each cluster method)
        self.assertGreaterEqual(mock_decorator.call_count, 4)


if __name__ == "__main__":
    unittest.main()
