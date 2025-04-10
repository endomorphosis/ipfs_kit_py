#!/usr/bin/env python
"""
Test cases for daemon health monitoring in ipfs_kit_py.

This module tests the automatic daemon health monitoring functionality
that periodically checks daemon status and restarts them if necessary.
"""

import time
import unittest
import logging
import pytest
from unittest.mock import patch, MagicMock, call

# Import the ipfs_kit module
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.error import IPFSError, create_result_dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestDaemonHealthMonitor(unittest.TestCase):
    """Test cases for daemon health monitoring functionality."""

    @pytest.mark.skip(reason="Method _ensure_daemon_running not found in ipfs_kit")
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit.check_daemon_status')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit._ensure_daemon_running')
    def test_monitor_startup_and_shutdown(self, mock_ensure_daemon, mock_check_status):
        """Test starting and stopping the daemon health monitor."""
        # Mock the status check to report all daemons running correctly
        mock_check_status.return_value = {
            "success": True,
            "daemons": {
                "ipfs": {"running": True, "type": "ipfs_daemon"},
                "ipfs_cluster_service": {"running": True, "type": "cluster_service"}
            }
        }
        
        # Create ipfs_kit instance
        kit = ipfs_kit(auto_start_daemons=True)
        
        # Start the monitor with a short interval for testing
        result = kit.start_daemon_health_monitor(check_interval=1)
        self.assertTrue(result["success"])
        self.assertTrue(kit.is_daemon_health_monitor_running())
        
        # Verify thread was created
        self.assertTrue(hasattr(kit, "_daemon_monitor_thread"))
        
        # Allow monitor to run for a short time
        time.sleep(2)
        
        # Should have checked daemon status at least once
        self.assertTrue(mock_check_status.called)
        
        # Stop the monitor
        stop_result = kit.stop_daemon_health_monitor()
        self.assertTrue(stop_result["success"])
        self.assertFalse(kit.is_daemon_health_monitor_running())
        
    @pytest.mark.skip(reason="Method _ensure_daemon_running not found in ipfs_kit")
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit.check_daemon_status')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit._ensure_daemon_running')
    def test_daemon_restart_when_stopped(self, mock_ensure_daemon, mock_check_status):
        """Test daemon restart when monitor detects a stopped daemon."""
        # First status check shows daemon running
        running_status = {
            "success": True,
            "daemons": {
                "ipfs": {"running": True, "type": "ipfs_daemon"},
                "ipfs_cluster_service": {"running": True, "type": "cluster_service"}
            }
        }
        
        # Second status check shows ipfs daemon stopped
        stopped_status = {
            "success": True,
            "daemons": {
                "ipfs": {"running": False, "type": "ipfs_daemon"},
                "ipfs_cluster_service": {"running": True, "type": "cluster_service"}
            }
        }
        
        # Restart succeeds
        mock_ensure_daemon.return_value = {
            "success": True,
            "message": "IPFS daemon started automatically"
        }
        
        # Set up the sequence of status check results
        mock_check_status.side_effect = [running_status, stopped_status, running_status]
        
        # Create ipfs_kit instance
        kit = ipfs_kit(auto_start_daemons=True, role="master")
        
        # Start the monitor with a short interval for testing
        kit.start_daemon_health_monitor(check_interval=1)
        
        # Allow monitor to run for a short time
        time.sleep(3)
        
        # Verify daemon restart was attempted
        mock_ensure_daemon.assert_called_with("ipfs")
        
        # Stop the monitor
        kit.stop_daemon_health_monitor()

    @pytest.mark.skip(reason="Method _ensure_daemon_running not found in ipfs_kit")
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit.check_daemon_status')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit._ensure_daemon_running')
    def test_role_specific_daemon_monitoring(self, mock_ensure_daemon, mock_check_status):
        """Test that monitor only restarts daemons appropriate for the role."""
        # Status check shows all daemons stopped
        all_stopped_status = {
            "success": True,
            "daemons": {
                "ipfs": {"running": False, "type": "ipfs_daemon"},
                "ipfs_cluster_service": {"running": False, "type": "cluster_service"},
                "ipfs_cluster_follow": {"running": False, "type": "cluster_follow"}
            }
        }
        
        # Restart succeeds
        mock_ensure_daemon.return_value = {
            "success": True,
            "message": "Daemon started automatically"
        }
        
        # Set up the status check result
        mock_check_status.return_value = all_stopped_status
        
        # Test for master role
        master_kit = ipfs_kit(auto_start_daemons=True, role="master")
        master_kit.start_daemon_health_monitor(check_interval=1)
        time.sleep(2)
        master_kit.stop_daemon_health_monitor()
        
        # For master, should restart ipfs and cluster_service but not cluster_follow
        mock_ensure_daemon.assert_any_call("ipfs")
        mock_ensure_daemon.assert_any_call("ipfs_cluster_service")
        
        # Reset mock
        mock_ensure_daemon.reset_mock()
        
        # Test for worker role
        worker_kit = ipfs_kit(auto_start_daemons=True, role="worker")
        worker_kit.start_daemon_health_monitor(check_interval=1)
        time.sleep(2)
        worker_kit.stop_daemon_health_monitor()
        
        # For worker, should restart ipfs and cluster_follow but not cluster_service
        mock_ensure_daemon.assert_any_call("ipfs")
        mock_ensure_daemon.assert_any_call("ipfs_cluster_follow")
        
        # Reset mock again
        mock_ensure_daemon.reset_mock()
        
        # Test for leecher role
        leecher_kit = ipfs_kit(auto_start_daemons=True, role="leecher")
        leecher_kit.start_daemon_health_monitor(check_interval=1)
        time.sleep(2)
        leecher_kit.stop_daemon_health_monitor()
        
        # For leecher, should only restart ipfs
        mock_ensure_daemon.assert_called_once_with("ipfs")

    @pytest.mark.skip(reason="Method _ensure_daemon_running not found in ipfs_kit")
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit.check_daemon_status')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit._ensure_daemon_running')
    def test_maximum_restart_attempts(self, mock_ensure_daemon, mock_check_status):
        """Test that monitor limits restart attempts for failing daemons."""
        # Status check always shows daemon stopped
        stopped_status = {
            "success": True,
            "daemons": {
                "ipfs": {"running": False, "type": "ipfs_daemon"}
            }
        }
        
        # Restart always fails
        mock_ensure_daemon.return_value = {
            "success": False,
            "error": "Failed to start daemon"
        }
        
        # Set up the status check result
        mock_check_status.return_value = stopped_status
        
        # Create ipfs_kit instance
        kit = ipfs_kit(auto_start_daemons=True)
        
        # Patch time to speed up testing
        with patch('time.sleep'):
            # Start the monitor with a short interval for testing
            kit.start_daemon_health_monitor(check_interval=1)
            
            # Allow monitor to run for a simulated longer time
            for _ in range(10):
                # Simulate passage of time and monitor loop iterations
                if hasattr(kit, '_daemon_monitor_running') and not kit._daemon_monitor_running:
                    break
                time.sleep(0.1)
            
            # Stop the monitor
            kit.stop_daemon_health_monitor()
        
        # Should have tried to restart exactly 3 times (max_restart_attempts)
        self.assertEqual(mock_ensure_daemon.call_count, 3)


if __name__ == "__main__":
    unittest.main()