"""
WebRTC Event Loop Fix for MCP Server

This module contains both:
1. The AsyncEventLoopHandler utility class for proper event loop management
2. Patched versions of the problematic WebRTC methods for the IPFS model
3. Async versions of these methods for use in FastAPI routes
"""

import anyio
import time
import logging
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

class AsyncEventLoopHandler:
    """
    Handler for properly managing async-io operations in different contexts.
    This class provides methods to safely execute coroutines whether within 
    a running event loop (e.g., FastAPI) or standalone.
    """
    
    @staticmethod
    async def run_coroutine_safely(coro, fallback_result=None):
        """
        Safely runs a coroutine whether in a running event loop or not.
        
        Args:
            coro: The coroutine to run
            fallback_result: Result to return if we can't run the coroutine
                             in the current event loop
        
        Returns:
            Result of the coroutine or fallback_result
        """
        try:
            # Just await the coroutine directly since we're already in an async context
            return await coro
        except Exception as e:
            logger.error(f"Error running coroutine: {e}")
            if fallback_result is not None:
                return fallback_result
            raise
    
    @staticmethod
    def run_coroutine(coro, fallback_result=None):
        """
        Run a coroutine in any context (sync or async).
        
        This method will:
        1. Try to get the current event loop
        2. If the loop is running (e.g., in FastAPI), create a Task and return a fallback
        3. If no loop is running, create one and run_until_complete
        
        Args:
            coro: The coroutine to run
            fallback_result: Result to return if we're in a running event loop
        
        Returns:
            Result of the coroutine, or fallback_result if in a running loop
        """
        try:
            # Try to get the current event loop
            loop = anyio.get_event_loop()
            
            # Check if the loop is already running (e.g., in FastAPI)
            if loop.is_running():
                logger.info("Event loop already running, scheduling background task and returning fallback result")
                if fallback_result is None:
                    fallback_result = {
                        "success": True,
                        "simulated": True,
                        "note": "Operation scheduled in background due to running event loop"
                    }
                
                # Schedule the coroutine to run in the background, but don't wait for it
                # This allows the operation to run eventually without blocking
                anyio.create_task(coro)
                
                return fallback_result
            else:
                # If loop exists but isn't running, we can run_until_complete
                logger.info("Running coroutine in existing event loop")
                return loop.run_until_complete(coro)
                
        except RuntimeError:
            # No event loop in this thread, create a new one
            logger.info("Creating new event loop for operation")
            loop = anyio.new_event_loop()
            anyio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

# Patched methods for the IPFS model

def patched_stop_webrtc_streaming(self, server_id: str) -> Dict[str, Any]:
    """
    Patched version of stop_webrtc_streaming that handles event loops properly.
    
    Args:
        server_id: ID of the WebRTC streaming server to stop
        
    Returns:
        Dictionary with operation results
    """
    operation_id = f"stop_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()
    
    # Initialize result dictionary
    result = {
        "success": False,
        "operation_id": operation_id,
        "operation": "stop_webrtc_streaming",
        "server_id": server_id,
        "start_time": start_time
    }
    
    # Check WebRTC availability
    if not hasattr(self, 'webrtc_manager') or self.webrtc_manager is None:
        result["error"] = "WebRTC manager not available"
        result["error_type"] = "dependency_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.warning(f"WebRTC stop failed: manager not available")
        return result
    
    try:
        # Get current connection count for fallback result
        stats = self.webrtc_manager.get_stats()
        connection_count = len(stats.get("connections", {}))
        
        # Prepare fallback result for when we can't run_until_complete
        fallback_result = {
            "connections_closed": connection_count,
            "simulated": True,
            "note": "Operation scheduled in background due to running event loop"
        }
        
        # Use the utility method to run the coroutine safely
        stop_result = AsyncEventLoopHandler.run_coroutine(
            self.webrtc_manager.close_all_connections(),
            fallback_result=fallback_result
        )
        
        # Update the result with success
        result["success"] = True
        result["server_stopped"] = True
        result["connections_closed"] = stop_result.get("connections_closed", 0)
        result["simulated"] = stop_result.get("simulated", False)
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(f"Stopped WebRTC stream for server {server_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error stopping WebRTC stream: {e}")
        
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        return result

async def async_stop_webrtc_streaming(self, server_id: str) -> Dict[str, Any]:
    """
    Async version of stop_webrtc_streaming that works in FastAPI context.
    
    Args:
        server_id: ID of the WebRTC streaming server to stop
        
    Returns:
        Dictionary with operation results
    """
    operation_id = f"stop_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()
    
    # Initialize result dictionary
    result = {
        "success": False,
        "operation_id": operation_id,
        "operation": "stop_webrtc_streaming",
        "server_id": server_id,
        "start_time": start_time
    }
    
    # Check WebRTC availability
    if not hasattr(self, 'webrtc_manager') or self.webrtc_manager is None:
        result["error"] = "WebRTC manager not available"
        result["error_type"] = "dependency_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.warning(f"WebRTC stop failed: manager not available")
        return result
    
    try:
        # Since we're already in an async function, we can directly await
        stop_result = await self.webrtc_manager.close_all_connections()
        
        # Update the result with success
        result["success"] = True
        result["server_stopped"] = True
        result["connections_closed"] = stop_result.get("connections_closed", 0)
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(f"Stopped WebRTC stream for server {server_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error stopping WebRTC stream: {e}")
        
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        return result

def patched_close_webrtc_connection(self, connection_id: str) -> Dict[str, Any]:
    """
    Patched version of close_webrtc_connection that handles event loops properly.
    
    Args:
        connection_id: ID of the WebRTC connection to close
        
    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()
    
    # Initialize result dictionary
    result = {
        "success": False,
        "operation_id": operation_id,
        "operation": "close_webrtc_connection",
        "connection_id": connection_id,
        "start_time": start_time
    }
    
    # Check WebRTC availability
    if not hasattr(self, 'webrtc_manager') or self.webrtc_manager is None:
        result["error"] = "WebRTC manager not available"
        result["error_type"] = "dependency_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.warning(f"WebRTC connection close failed: manager not available")
        return result
    
    try:
        # Prepare fallback result for when we can't run_until_complete
        fallback_result = {
            "success": True,
            "simulated": True,
            "note": "Operation scheduled in background due to running event loop"
        }
        
        # Use the utility method to run the coroutine safely
        close_result = AsyncEventLoopHandler.run_coroutine(
            self.webrtc_manager.close_connection(connection_id),
            fallback_result=fallback_result
        )
        
        if not close_result.get("success", False) and not close_result.get("simulated", False):
            result["error"] = close_result.get("error", "Unknown error")
            result["error_type"] = "close_error"
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result
        
        # Update the result with success
        result["success"] = True
        result["simulated"] = close_result.get("simulated", False)
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(f"Closed WebRTC connection {connection_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error closing WebRTC connection: {e}")
        
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        return result

async def async_close_webrtc_connection(self, connection_id: str) -> Dict[str, Any]:
    """
    Async version of close_webrtc_connection that works in FastAPI context.
    
    Args:
        connection_id: ID of the WebRTC connection to close
        
    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()
    
    # Initialize result dictionary
    result = {
        "success": False,
        "operation_id": operation_id,
        "operation": "close_webrtc_connection",
        "connection_id": connection_id,
        "start_time": start_time
    }
    
    # Check WebRTC availability
    if not hasattr(self, 'webrtc_manager') or self.webrtc_manager is None:
        result["error"] = "WebRTC manager not available"
        result["error_type"] = "dependency_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.warning(f"WebRTC connection close failed: manager not available")
        return result
    
    try:
        # Since we're already in an async function, we can directly await
        close_result = await self.webrtc_manager.close_connection(connection_id)
        
        if not close_result.get("success", False):
            result["error"] = close_result.get("error", "Unknown error")
            result["error_type"] = "close_error"
            result["duration_ms"] = (time.time() - start_time) * 1000
            return result
        
        # Update the result with success
        result["success"] = True
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(f"Closed WebRTC connection {connection_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error closing WebRTC connection: {e}")
        
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        return result

def patched_close_all_webrtc_connections(self) -> Dict[str, Any]:
    """
    Patched version of close_all_webrtc_connections that handles event loops properly.
    
    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_all_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()
    
    # Initialize result dictionary
    result = {
        "success": False,
        "operation_id": operation_id,
        "operation": "close_all_webrtc_connections",
        "start_time": start_time
    }
    
    # Check WebRTC availability
    if not hasattr(self, 'webrtc_manager') or self.webrtc_manager is None:
        result["error"] = "WebRTC manager not available"
        result["error_type"] = "dependency_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.warning(f"WebRTC close all connections failed: manager not available")
        return result
    
    try:
        # Get current connection count
        stats = self.webrtc_manager.get_stats()
        connection_count = len(stats.get("connections", {}))
        
        # Prepare fallback result for when we can't run_until_complete
        fallback_result = {
            "connections_closed": connection_count,
            "simulated": True,
            "note": "Operation scheduled in background due to running event loop"
        }
        
        # Use the utility method to run the coroutine safely
        close_result = AsyncEventLoopHandler.run_coroutine(
            self.webrtc_manager.close_all_connections(),
            fallback_result=fallback_result
        )
        
        # Update the result with success
        result["success"] = True
        result["connections_closed"] = connection_count
        result["simulated"] = close_result.get("simulated", False)
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(f"Closed all WebRTC connections ({connection_count})")
        return result
        
    except Exception as e:
        logger.error(f"Error closing all WebRTC connections: {e}")
        
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        return result

async def async_close_all_webrtc_connections(self) -> Dict[str, Any]:
    """
    Async version of close_all_webrtc_connections that works in FastAPI context.
    
    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_all_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()
    
    # Initialize result dictionary
    result = {
        "success": False,
        "operation_id": operation_id,
        "operation": "close_all_webrtc_connections",
        "start_time": start_time
    }
    
    # Check WebRTC availability
    if not hasattr(self, 'webrtc_manager') or self.webrtc_manager is None:
        result["error"] = "WebRTC manager not available"
        result["error_type"] = "dependency_error"
        result["duration_ms"] = (time.time() - start_time) * 1000
        logger.warning(f"WebRTC close all connections failed: manager not available")
        return result
    
    try:
        # Get current connection count
        stats = self.webrtc_manager.get_stats()
        connection_count = len(stats.get("connections", {}))
        
        # Since we're already in an async function, we can directly await
        close_result = await self.webrtc_manager.close_all_connections()
        
        # Update the result with success
        result["success"] = True
        result["connections_closed"] = connection_count
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        logger.info(f"Closed all WebRTC connections ({connection_count})")
        return result
        
    except Exception as e:
        logger.error(f"Error closing all WebRTC connections: {e}")
        
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["duration_ms"] = (time.time() - start_time) * 1000
        
        return result

# Integration with WebRTC Controller
def patch_webrtc_controller_methods(controller):
    """
    Update WebRTC controller to use async methods.
    
    Args:
        controller: WebRTC controller instance to patch
    """
    # Store original methods
    original_stop_streaming = controller.stop_streaming
    original_close_connection = controller.close_connection
    original_close_all_connections = controller.close_all_connections
    
    # Replace with async implementations
    async def patched_stop_streaming(server_id: str) -> Dict[str, Any]:
        logger.debug(f"Using patched async stop_streaming for server ID: {server_id}")
        try:
            # Use async version directly instead of sync version
            result = await async_stop_webrtc_streaming(controller.ipfs_model, server_id)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                raise HTTPException(status_code=500, detail=error_msg)
                
            return result
            
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def patched_close_connection(connection_id: str) -> Dict[str, Any]:
        logger.debug(f"Using patched async close_connection for connection ID: {connection_id}")
        try:
            # Use async version directly
            result = await async_close_webrtc_connection(controller.ipfs_model, connection_id)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                raise HTTPException(status_code=404, detail=error_msg)
                
            return result
            
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    async def patched_close_all_connections() -> Dict[str, Any]:
        logger.debug("Using patched async close_all_connections")
        try:
            # Use async version directly
            result = await async_close_all_webrtc_connections(controller.ipfs_model)
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                raise HTTPException(status_code=500, detail=error_msg)
                
            return result
            
        except Exception as e:
            logger.error(f"Error closing all connections: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    # Apply patches
    controller.stop_streaming = patched_stop_streaming
    controller.close_connection = patched_close_connection
    controller.close_all_connections = patched_close_all_connections
    
    logger.info("WebRTC controller methods patched to use async implementations")
    return controller

# Integration with IPFS Model
def patch_ipfs_model_methods(model):
    """
    Update IPFS model to use patched methods.
    
    Args:
        model: IPFS model instance to patch
    """
    # Store original methods (optional, for reference or restoration)
    original_stop_streaming = model.stop_webrtc_streaming
    original_close_connection = model.close_webrtc_connection
    original_close_all_connections = model.close_all_webrtc_connections
    
    # Replace with patched implementations
    model.stop_webrtc_streaming = lambda server_id: patched_stop_webrtc_streaming(model, server_id)
    model.close_webrtc_connection = lambda connection_id: patched_close_webrtc_connection(model, connection_id)
    model.close_all_webrtc_connections = lambda: patched_close_all_webrtc_connections(model)
    
    # Add async methods for use with FastAPI
    model.async_stop_webrtc_streaming = lambda server_id: async_stop_webrtc_streaming(model, server_id)
    model.async_close_webrtc_connection = lambda connection_id: async_close_webrtc_connection(model, connection_id)
    model.async_close_all_webrtc_connections = lambda: async_close_all_webrtc_connections(model)
    
    logger.info("IPFS model WebRTC methods patched for proper event loop handling")
    return model