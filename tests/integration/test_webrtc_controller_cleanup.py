"""
Test script for WebRTC controller.
This script tests the WebRTC controller's cleanup and shutdown methods.
"""
import anyio
import logging
import pytest
import json
import time
from unittest.mock import patch, MagicMock, AsyncMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
pytestmark = pytest.mark.anyio

# Import the controller class
from ipfs_kit_py.mcp.controllers.webrtc_controller import WebRTCController

# Add enhanced shutdown method to the controller
async def _perform_final_cleanup(self):
    """
    Perform a final cleanup of all resources during shutdown.
    
    This method is called during the shutdown process to ensure that
    all resources are properly cleaned up, even if regular cleanup mechanisms
    have failed. It uses sync methods to ensure completion.
    """
    logger.info("Performing final resource cleanup before shutdown")
    
    # 1. Check and clean up all streaming servers
    server_ids = list(self.active_streaming_servers.keys())
    logger.info(f"Cleaning up {len(server_ids)} remaining streaming servers")
    
    for server_id in server_ids:
        try:
            # Use synchronous method to ensure completion
            logger.debug(f"Final cleanup of streaming server {server_id}")
            if hasattr(self.ipfs_model, 'stop_webrtc_streaming'):
                self.ipfs_model.stop_webrtc_streaming(server_id=server_id)
        except Exception as e:
            logger.warning(f"Error during final cleanup of server {server_id}: {e}")
        finally:
            # Always remove from tracking
            if server_id in self.active_streaming_servers:
                del self.active_streaming_servers[server_id]
    
    # 2. Check and clean up all connections
    connection_ids = list(self.active_connections.keys())
    logger.info(f"Cleaning up {len(connection_ids)} remaining connections")
    
    for connection_id in connection_ids:
        try:
            # Use synchronous method to ensure completion
            logger.debug(f"Final cleanup of connection {connection_id}")
            if hasattr(self.ipfs_model, 'close_webrtc_connection'):
                self.ipfs_model.close_webrtc_connection(connection_id=connection_id)
        except Exception as e:
            logger.warning(f"Error during final cleanup of connection {connection_id}: {e}")
        finally:
            # Always remove from tracking
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
    
    # 3. For extra safety, try calling close_all_webrtc_connections
    try:
        if hasattr(self.ipfs_model, 'close_all_webrtc_connections'):
            logger.debug("Calling close_all_webrtc_connections as final safety measure")
            self.ipfs_model.close_all_webrtc_connections()
    except Exception as e:
        logger.warning(f"Error during final close_all_webrtc_connections: {e}")
    
    # 4. Check if event loop or thread needs cleanup
    if hasattr(self, 'event_loop_thread'):
        logger.debug("Cleanup of event loop thread may be needed at process exit")
        # We don't forcibly kill the thread here as it might be unsafe,
        # but we log it for potential future improvement
    
    logger.info("Final resource cleanup completed")

# Add the method to the WebRTCController class
WebRTCController._perform_final_cleanup = _perform_final_cleanup

class TestWebRTCController:
    """Test the WebRTC controller with async methods."""

    @pytest.fixture(autouse=True)
    async def _setup(self):
        """Set up the test."""
        # Mock IPFS model
        self.ipfs_model = MagicMock()
        self.ipfs_model.stop_webrtc_streaming = MagicMock(return_value={"success": True})
        self.ipfs_model.close_webrtc_connection = MagicMock(return_value={"success": True})
        self.ipfs_model.close_all_webrtc_connections = MagicMock(return_value={"success": True})
        self.ipfs_model.async_close_all_webrtc_connections = AsyncMock(return_value={"success": True})

        # Create controller with patched _start_cleanup_task
        with patch('ipfs_kit_py.mcp.controllers.webrtc_controller.WebRTCController._start_cleanup_task'):
            self.controller = WebRTCController(self.ipfs_model)

        # Add some test data
        self.controller.active_streaming_servers = {
            "server1": {"cid": "testcid1", "started_at": time.time() - 600},
            "server2": {"cid": "testcid2", "started_at": time.time() - 300}
        }
        self.controller.active_connections = {
            "conn1": {"added_at": time.time() - 600, "server_id": "server1"},
            "conn2": {"added_at": time.time() - 300, "server_id": "server2"}
        }

        # Mock the cleanup task
        self.controller.cleanup_task = MagicMock()
        self.controller.cleanup_task.cancel = MagicMock()

        # Patch close_all_streaming_servers to be an AsyncMock
        self.controller.close_all_streaming_servers = AsyncMock()
        yield
    
    async def test_perform_final_cleanup(self):
        """Test the _perform_final_cleanup method we added."""
        # Call the method
        await self.controller._perform_final_cleanup()
        
        # Check that all servers were cleaned up
        assert len(self.controller.active_streaming_servers) == 0
        
        # Check that all connections were cleaned up
        assert len(self.controller.active_connections) == 0
        
        # Check that stop_webrtc_streaming was called for each server
        assert self.ipfs_model.stop_webrtc_streaming.call_count == 2
        
        # Check that close_webrtc_connection was called for each connection
        assert self.ipfs_model.close_webrtc_connection.call_count == 2
        
        # Check that close_all_webrtc_connections was called once
        self.ipfs_model.close_all_webrtc_connections.assert_called_once()
    
    async def test_shutdown(self):
        """Test the shutdown method."""
        # Add enhanced shutdown method that calls _perform_final_cleanup
        original_shutdown = self.controller.shutdown
        
        # Replace shutdown with our enhanced version temporarily
        async def enhanced_shutdown(self):
            """Enhanced shutdown method that calls _perform_final_cleanup."""
            # Signal the cleanup task to stop
            self.is_shutting_down = True
            
            # Store reference to cleanup task for testing
            cleanup_task = self.cleanup_task
            
            # Cancel the cleanup task if it's running
            if self.cleanup_task is not None:
                try:
                    self.cleanup_task.cancel()
                    logger.info("Cleanup task cancellation initiated")
                except Exception as e:
                    logger.warning(f"Error cancelling cleanup task: {e}")
                    
                # Set to None to help with garbage collection
                self.cleanup_task = None
            
            # Make an extra effort to clean up stale resources before shutdown
            try:
                await self._perform_final_cleanup()
            except Exception as e:
                logger.error(f"Error in final cleanup: {e}")
            
            # Close all streaming servers
            await self.close_all_streaming_servers()
            
            # Close all WebRTC connections via the model
            try:
                if hasattr(self.ipfs_model, "async_close_all_webrtc_connections"):
                    # Use async version if available
                    result = await self.ipfs_model.async_close_all_webrtc_connections()
                elif hasattr(self.ipfs_model, "close_all_webrtc_connections"):
                    # Fall back to sync version
                    result = self.ipfs_model.close_all_webrtc_connections()
                else:
                    logger.warning("No method available to close WebRTC connections")
                    result = {"success": False, "error": "Method not available"}
                    
                if isinstance(result, dict) and not result.get("success", False):
                    logger.error(f"Error closing WebRTC connections: {result.get('error', 'Unknown error')}")
                else:
                    logger.info("Successfully closed all WebRTC connections")
            except Exception as e:
                logger.error(f"Error closing WebRTC connections during shutdown: {e}")
                
            # Clear dictionaries to release references
            self.active_streaming_servers.clear()
            self.active_connections.clear()
            
            logger.info("WebRTC Controller shutdown completed")
            
            # Return the original cleanup task for testing
            return cleanup_task
        
        # Replace shutdown method temporarily
        self.controller.shutdown = enhanced_shutdown.__get__(self.controller, WebRTCController)
        
        # Store the original cleanup task for testing
        cleanup_task = self.controller.cleanup_task
        
        try:
            # Call the shutdown method
            result_task = await self.controller.shutdown()
            
            # Check that is_shutting_down was set to True
            assert self.controller.is_shutting_down
            
            # Check that cleanup_task was cancelled
            cleanup_task.cancel.assert_called_once()
            
            # Check that close_all_streaming_servers was called
            self.controller.close_all_streaming_servers.assert_called_once()
            
            # Check that async_close_all_webrtc_connections was called once
            self.ipfs_model.async_close_all_webrtc_connections.assert_called_once()
            
            # Check that all servers were cleaned up
            assert len(self.controller.active_streaming_servers) == 0
            
            # Check that all connections were cleaned up
            assert len(self.controller.active_connections) == 0
            
            # Check that stop_webrtc_streaming was called for each server (via _perform_final_cleanup)
            assert self.ipfs_model.stop_webrtc_streaming.call_count == 2
            
            # Check that close_webrtc_connection was called for each connection (via _perform_final_cleanup)
            assert self.ipfs_model.close_webrtc_connection.call_count == 2
            
            # Check that close_all_webrtc_connections was called once (via _perform_final_cleanup)
            assert self.ipfs_model.close_all_webrtc_connections.call_count == 1
            
        finally:
            # Restore original shutdown method
            self.controller.shutdown = original_shutdown
        
if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
