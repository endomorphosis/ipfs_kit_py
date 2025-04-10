"""
Tests for MCP server's daemon management functionality.

These tests verify that the MCP server properly initializes and manages
IPFS daemons using the automatic daemon management capabilities.
"""

import unittest
import os
import time
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock, PropertyMock

# Import server components
from ipfs_kit_py.mcp.server import MCPServer

class TestMCPServerDaemonManagement(unittest.TestCase):
    """Test the MCP server's daemon management capabilities."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temp dir for persistence
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock the daemon management methods
        self.patches = []
        
        # Patch ipfs_kit initialization to return our mock
        self.mock_ipfs_kit = MagicMock()
        self.mock_auto_start_daemons = True
        
        # Set up property mocks for ipfs_kit attributes
        # Mock auto_start_daemons as a property
        auto_start_daemons_patch = patch.object(
            type(self.mock_ipfs_kit), 
            'auto_start_daemons', 
            new_callable=PropertyMock, 
            return_value=self.mock_auto_start_daemons
        )
        self.patches.append(auto_start_daemons_patch)
        
        # Start all patches
        for p in self.patches:
            p.start()
        
        # Set up daemon status mocks
        self.mock_ipfs_kit.check_daemon_status.return_value = {
            "success": True,
            "running": True,
            "pid": 12345,
            "uptime": 3600
        }
        
        self.mock_ipfs_kit.is_daemon_health_monitor_running.return_value = True
        
        # Initialize the server with our mocked ipfs_kit
        with patch('ipfs_kit_py.mcp.server.ipfs_kit', return_value=self.mock_ipfs_kit):
            self.server = MCPServer(
                debug_mode=True,
                persistence_path=self.temp_dir,
                isolation_mode=True
            )
    
    def tearDown(self):
        """Clean up after tests."""
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Stop all patches
        for p in self.patches:
            p.stop()
    
    def test_initialization_with_auto_start_daemons(self):
        """Test that the server initializes ipfs_kit with auto_start_daemons=True."""
        # Create a new server with a clean mock
        mock_kit = MagicMock()
        
        with patch('ipfs_kit_py.mcp.server.ipfs_kit', return_value=mock_kit) as mock_ipfs_kit_init:
            server = MCPServer(
                debug_mode=False,
                persistence_path=self.temp_dir,
                isolation_mode=True
            )
            
            # Verify ipfs_kit was initialized with auto_start_daemons=True
            mock_ipfs_kit_init.assert_called_once()
            _, kwargs = mock_ipfs_kit_init.call_args
            self.assertTrue(kwargs['auto_start_daemons'])
            
            # Verify daemon health monitor was started
            mock_kit.start_daemon_health_monitor.assert_called_once()
    
    def test_health_check_includes_daemon_status(self):
        """Test that the health check endpoint includes daemon status information."""
        # Call the health check endpoint
        health_info = self.server.health_check()
        
        # Immediately convert to dict to handle the async result
        if hasattr(health_info, "__await__"):
            health_info = health_info.__await__.__self__
        
        # Verify daemon status information is included
        self.assertIn("ipfs_daemon_running", health_info)
        self.assertTrue(health_info["ipfs_daemon_running"])
        self.assertIn("auto_start_daemons_enabled", health_info)
        self.assertTrue(health_info["auto_start_daemons_enabled"])
        self.assertIn("daemon_health_monitor_running", health_info)
        self.assertTrue(health_info["daemon_health_monitor_running"])
    
    def test_debug_state_includes_daemon_info(self):
        """Test that the debug state endpoint includes daemon management information."""
        # Call the debug state endpoint
        debug_state = self.server.get_debug_state()
        
        # Immediately convert to dict to handle the async result
        if hasattr(debug_state, "__await__"):
            debug_state = debug_state.__await__.__self__
        
        # Verify daemon information is included
        self.assertIn("server_info", debug_state)
        self.assertIn("daemon_management", debug_state["server_info"])
        
        daemon_info = debug_state["server_info"]["daemon_management"]
        self.assertIn("auto_start_daemons", daemon_info)
        self.assertTrue(daemon_info["auto_start_daemons"])
        self.assertIn("daemon_status", daemon_info)
        self.assertIn("health_monitor_running", daemon_info)
        self.assertTrue(daemon_info["health_monitor_running"])
    
    def test_start_daemon_endpoint(self):
        """Test the start_daemon endpoint."""
        # Set up mock for _start_daemon
        self.mock_ipfs_kit._start_daemon.return_value = {
            "success": True,
            "daemon_type": "ipfs",
            "pid": 12345
        }
        
        # Call the endpoint
        result = self.server.start_daemon("ipfs")
        
        # Immediately convert to dict to handle the async result
        if hasattr(result, "__await__"):
            result = result.__await__.__self__
        
        # Verify the daemon was started
        self.mock_ipfs_kit._start_daemon.assert_called_once_with("ipfs")
        self.assertTrue(result["success"])
    
    def test_stop_daemon_endpoint(self):
        """Test the stop_daemon endpoint."""
        # Set up mock for _stop_daemon
        self.mock_ipfs_kit._stop_daemon.return_value = {
            "success": True,
            "daemon_type": "ipfs",
            "message": "Daemon stopped"
        }
        
        # Call the endpoint
        result = self.server.stop_daemon("ipfs")
        
        # Immediately convert to dict to handle the async result
        if hasattr(result, "__await__"):
            result = result.__await__.__self__
        
        # Verify the daemon was stopped
        self.mock_ipfs_kit._stop_daemon.assert_called_once_with("ipfs")
        self.assertTrue(result["success"])
    
    def test_get_daemon_status_endpoint(self):
        """Test the get_daemon_status endpoint."""
        # Call the endpoint
        result = self.server.get_daemon_status()
        
        # Immediately convert to dict to handle the async result
        if hasattr(result, "__await__"):
            result = result.__await__.__self__
        
        # Verify status was returned
        self.assertTrue(result["success"])
        self.assertIn("daemon_status", result)
        self.assertIn("ipfs", result["daemon_status"])
        self.assertTrue(result["daemon_status"]["ipfs"]["running"])
        self.assertIn("daemon_monitor_running", result)
        self.assertTrue(result["daemon_monitor_running"])
    
    def test_start_daemon_monitor_endpoint(self):
        """Test the start_daemon_monitor endpoint."""
        # Set up mock to indicate monitor is not running
        self.mock_ipfs_kit.is_daemon_health_monitor_running.return_value = False
        
        # Call the endpoint
        result = self.server.start_daemon_monitor(check_interval=30)
        
        # Immediately convert to dict to handle the async result
        if hasattr(result, "__await__"):
            result = result.__await__.__self__
        
        # Verify monitor was started
        self.mock_ipfs_kit.start_daemon_health_monitor.assert_called_once_with(
            check_interval=30,
            auto_restart=True
        )
        self.assertTrue(result["success"])
    
    def test_stop_daemon_monitor_endpoint(self):
        """Test the stop_daemon_monitor endpoint."""
        # Call the endpoint
        result = self.server.stop_daemon_monitor()
        
        # Immediately convert to dict to handle the async result
        if hasattr(result, "__await__"):
            result = result.__await__.__self__
        
        # Verify monitor was stopped
        self.mock_ipfs_kit.stop_daemon_health_monitor.assert_called_once()
        self.assertTrue(result["success"])
    
    def test_server_shutdown_stops_daemon_monitor(self):
        """Test that server shutdown stops the daemon health monitor."""
        # Call shutdown
        self.server.shutdown()
        
        # Verify monitor was stopped
        self.mock_ipfs_kit.stop_daemon_health_monitor.assert_called_once()
    
    def test_invalid_daemon_type_validation(self):
        """Test validation of daemon type in endpoints."""
        # Call with invalid daemon type
        result = self.server.start_daemon("invalid_daemon_type")
        
        # Immediately convert to dict to handle the async result
        if hasattr(result, "__await__"):
            result = result.__await__.__self__
        
        # Verify validation failed
        self.assertFalse(result["success"])
        self.assertIn("error", result)
        self.assertIn("Invalid daemon type", result["error"])
        
        # Verify no daemon was started
        self.mock_ipfs_kit._start_daemon.assert_not_called()
    
    def test_restart_history_reset(self):
        """Test that reset_state resets daemon restart history."""
        # Call reset
        self.server.reset_state()
        
        # Verify restart history was reset
        self.mock_ipfs_kit.reset_daemon_restart_history.assert_called_once()
    

if __name__ == '__main__':
    unittest.main()