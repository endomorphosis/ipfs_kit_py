"""
Tests for MCP server's daemon management functionality with AnyIO support.

These tests verify that the MCP server properly initializes and manages
IPFS daemons using the automatic daemon management capabilities.
This version uses AnyIO for async testing support.
"""

import os
import time
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock
import anyio
import pytest

# Import server components
from ipfs_kit_py.mcp.server import MCPServer


# Keep original unittest class for backward compatibility
class TestMCPServerDaemonManagementAnyIO:
    """Test the MCP server's daemon management capabilities with AnyIO support."""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
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
        auto_start_daemons_patch.start()
        self.patches.append(auto_start_daemons_patch)
        
        # Set up daemon status mocks
        self.mock_ipfs_kit.check_daemon_status.return_value = {
            "success": True,
            "running": True,
            "pid": 12345,
            "uptime": 3600
        }
        
        self.mock_ipfs_kit.is_daemon_health_monitor_running.return_value = True
        
        # Set up async methods
        self.mock_ipfs_kit.check_daemon_status_async = AsyncMock(return_value={
            "success": True,
            "running": True,
            "pid": 12345,
            "uptime": 3600
        })
        
        self.mock_ipfs_kit._start_daemon_async = AsyncMock(return_value={
            "success": True,
            "daemon_type": "ipfs",
            "pid": 12345
        })
        
        self.mock_ipfs_kit._stop_daemon_async = AsyncMock(return_value={
            "success": True,
            "daemon_type": "ipfs",
            "message": "Daemon stopped"
        })
        
        self.mock_ipfs_kit.start_daemon_health_monitor_async = AsyncMock()
        self.mock_ipfs_kit.stop_daemon_health_monitor_async = AsyncMock()
        self.mock_ipfs_kit.reset_daemon_restart_history_async = AsyncMock()
        
        # Initialize the server with our mocked ipfs_kit
        with patch('ipfs_kit_py.mcp.server.ipfs_kit', return_value=self.mock_ipfs_kit):
            self.server = MCPServer(
                debug_mode=True,
                persistence_path=self.temp_dir,
                isolation_mode=True
            )
        
        yield
        
        # Clean up after tests
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Stop all patches
        for p in self.patches:
            p.stop()
    
    @pytest.mark.anyio
    async def test_initialization_with_auto_start_daemons(self):
        """Test that the server initializes ipfs_kit with auto_start_daemons=True."""
        # Create a new server with a clean mock
        mock_kit = MagicMock()
        mock_kit.start_daemon_health_monitor_async = AsyncMock()
        
        with patch('ipfs_kit_py.mcp.server.ipfs_kit', return_value=mock_kit) as mock_ipfs_kit_init:
            server = MCPServer(
                debug_mode=False,
                persistence_path=self.temp_dir,
                isolation_mode=True
            )
            
            # Verify ipfs_kit was initialized with auto_start_daemons=True
            mock_ipfs_kit_init.assert_called_once()
            _, kwargs = mock_ipfs_kit_init.call_args
            assert kwargs['auto_start_daemons']
            
            # Verify daemon health monitor was started
            if hasattr(mock_kit.start_daemon_health_monitor, "assert_called_once"):
                mock_kit.start_daemon_health_monitor.assert_called_once()
            elif hasattr(mock_kit.start_daemon_health_monitor_async, "assert_called_once"):
                mock_kit.start_daemon_health_monitor_async.assert_called_once()
    
    @pytest.mark.anyio
    async def test_health_check_includes_daemon_status(self):
        """Test that the health check endpoint includes daemon status information."""
        # Call the health check endpoint
        health_info = await self.server.health_check()
        
        # Verify daemon status information is included
        assert "ipfs_daemon_running" in health_info
        assert health_info["ipfs_daemon_running"]
        assert "auto_start_daemons_enabled" in health_info
        assert health_info["auto_start_daemons_enabled"]
        assert "daemon_health_monitor_running" in health_info
        assert health_info["daemon_health_monitor_running"]
    
    @pytest.mark.anyio
    async def test_debug_state_includes_daemon_info(self):
        """Test that the debug state endpoint includes daemon management information."""
        # Call the debug state endpoint
        debug_state = await self.server.get_debug_state()
        
        # Verify daemon information is included
        assert "server_info" in debug_state
        assert "daemon_management" in debug_state["server_info"]
        
        daemon_info = debug_state["server_info"]["daemon_management"]
        assert "auto_start_daemons" in daemon_info
        assert daemon_info["auto_start_daemons"]
        assert "daemon_status" in daemon_info
        assert "health_monitor_running" in daemon_info
        assert daemon_info["health_monitor_running"]
    
    @pytest.mark.anyio
    async def test_start_daemon_endpoint(self):
        """Test the start_daemon endpoint."""
        # Call the endpoint
        result = await self.server.start_daemon("ipfs")
        
        # Verify the daemon was started
        self.mock_ipfs_kit._start_daemon_async.assert_called_once_with("ipfs")
        assert result["success"]
    
    @pytest.mark.anyio
    async def test_stop_daemon_endpoint(self):
        """Test the stop_daemon endpoint."""
        # Call the endpoint
        result = await self.server.stop_daemon("ipfs")
        
        # Verify the daemon was stopped
        self.mock_ipfs_kit._stop_daemon_async.assert_called_once_with("ipfs")
        assert result["success"]
    
    @pytest.mark.anyio
    async def test_get_daemon_status_endpoint(self):
        """Test the get_daemon_status endpoint."""
        # Call the endpoint
        result = await self.server.get_daemon_status()
        
        # Verify status was returned
        assert result["success"]
        assert "daemon_status" in result
        assert "ipfs" in result["daemon_status"]
        assert result["daemon_status"]["ipfs"]["running"]
        assert "daemon_monitor_running" in result
        assert result["daemon_monitor_running"]
    
    @pytest.mark.anyio
    async def test_start_daemon_monitor_endpoint(self):
        """Test the start_daemon_monitor endpoint."""
        # Set up mock to indicate monitor is not running
        self.mock_ipfs_kit.is_daemon_health_monitor_running.return_value = False
        
        # Call the endpoint
        result = await self.server.start_daemon_monitor(check_interval=30)
        
        # Verify monitor was started
        self.mock_ipfs_kit.start_daemon_health_monitor_async.assert_called_once_with(
            check_interval=30,
            auto_restart=True
        )
        assert result["success"]
    
    @pytest.mark.anyio
    async def test_stop_daemon_monitor_endpoint(self):
        """Test the stop_daemon_monitor endpoint."""
        # Call the endpoint
        result = await self.server.stop_daemon_monitor()
        
        # Verify monitor was stopped
        self.mock_ipfs_kit.stop_daemon_health_monitor_async.assert_called_once()
        assert result["success"]
    
    @pytest.mark.anyio
    async def test_server_shutdown_stops_daemon_monitor(self):
        """Test that server shutdown stops the daemon health monitor."""
        # Call shutdown
        self.server.shutdown()
        
        # Verify monitor was stopped
        if hasattr(self.mock_ipfs_kit.stop_daemon_health_monitor, "assert_called_once"):
            self.mock_ipfs_kit.stop_daemon_health_monitor.assert_called_once()
        elif hasattr(self.mock_ipfs_kit.stop_daemon_health_monitor_async, "assert_called_once"):
            self.mock_ipfs_kit.stop_daemon_health_monitor_async.assert_called_once()
    
    @pytest.mark.anyio
    async def test_invalid_daemon_type_validation(self):
        """Test validation of daemon type in endpoints."""
        # Call with invalid daemon type
        result = await self.server.start_daemon("invalid_daemon_type")
        
        # Verify validation failed
        assert not result["success"]
        assert "error" in result
        assert "Invalid daemon type" in result["error"]
        
        # Verify no daemon was started
        self.mock_ipfs_kit._start_daemon_async.assert_not_called()
    
    @pytest.mark.anyio
    async def test_restart_history_reset(self):
        """Test that reset_state resets daemon restart history."""
        # Call reset
        self.server.reset_state()
        
        # Verify restart history was reset
        if hasattr(self.mock_ipfs_kit.reset_daemon_restart_history, "assert_called_once"):
            self.mock_ipfs_kit.reset_daemon_restart_history.assert_called_once()
        elif hasattr(self.mock_ipfs_kit.reset_daemon_restart_history_async, "assert_called_once"):
            self.mock_ipfs_kit.reset_daemon_restart_history_async.assert_called_once()
    
    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test integration with anyio.sleep."""
        # Mock check_daemon_status_async to use anyio.sleep
        async def check_with_delay(delay=0.1):
            await anyio.sleep(delay)
            return {
                "success": True,
                "running": True,
                "pid": 12345,
                "uptime": 3600,
                "delay_used": delay
            }
        
        # Apply the mock and test
        self.mock_ipfs_kit.check_daemon_status_async.side_effect = check_with_delay
        
        # Call the endpoint
        result = await self.server.get_daemon_status()
        
        # Verify the async function with anyio.sleep was called and returned
        assert result["success"]
        assert "daemon_status" in result
        assert "ipfs" in result["daemon_status"]
        assert result["daemon_status"]["ipfs"]["running"]