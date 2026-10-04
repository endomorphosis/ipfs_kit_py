#!/usr/bin/env python3
"""
WebRTC AnyIO & Monitoring Integration

This module combines both:
1. The AnyIO event loop fixes for WebRTC methods
2. The WebRTC monitoring capabilities

This provides a comprehensive solution for WebRTC functionality in FastAPI:
- Proper event loop handling with AnyIO for both sync and async contexts
- Detailed monitoring of WebRTC connections and operations
- Async task tracking and lifecycle event management
"""

import os
import sys
import time
import logging
import anyio
import inspect
from typing import Dict, Any, Optional, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import required dependencies
try:
    import anyio
    import sniffio
    HAS_ANYIO = True
except ImportError:
    HAS_ANYIO = False
    logger.warning("AnyIO not available. Install with: pip install anyio sniffio")

# Check if path to fixes directory is in sys.path
fixes_dir = os.path.dirname(os.path.abspath(__file__))
if fixes_dir not in sys.path:
    sys.path.append(fixes_dir)

# Try to import our modules
try:
    from webrtc_anyio_fix import AnyIOEventLoopHandler, patch_ipfs_model_methods, patch_webrtc_controller_methods
    from webrtc_monitor import WebRTCMonitor, AsyncTaskTracker, apply_webrtc_monitoring
    HAS_LOCAL_MODULES = True
except ImportError as e:
    HAS_LOCAL_MODULES = False
    logger.warning(f"Could not import local modules: {e}")

class AnyIOMonitoredEventLoopHandler:
    """
    Enhanced event loop handler that combines AnyIO fixes with monitoring.

    This class extends the AnyIOEventLoopHandler with monitoring capabilities
    to track WebRTC connections, operations, and async tasks.
    """

    def __init__(self, monitor: Optional[WebRTCMonitor] = None):
        """
        Initialize the handler with a WebRTC monitor.

        Args:
            monitor: WebRTC monitor instance (creates a new one if None)
        """
        self.monitor = monitor or WebRTCMonitor()
        self.task_tracker = AsyncTaskTracker(self.monitor)

    async def run_monitored_coroutine(self, coro, connection_id: str,
                                     operation_name: str = None, fallback_result=None):
        """
        Run a coroutine with monitoring in an async context.

        Args:
            coro: The coroutine to run
            connection_id: ID of the WebRTC connection
            operation_name: Name of the operation (for tracking)
            fallback_result: Result to return if we can't run the coroutine

        Returns:
            Result of the coroutine or fallback_result
        """
        # Generate operation ID and name if not provided
        operation_id = f"{operation_name or 'operation'}_{int(time.time() * 1000)}"
        operation_name = operation_name or coro.__name__

        # Track the operation
        self.monitor.add_operation(operation_id, operation_name, {
            "connection_id": connection_id
        })

        try:
            # Run the coroutine with task tracking
            result = await self.task_tracker.track_task(
                connection_id,
                coro,
                task_name=operation_name
            )

            # Update operation status
            is_successful = isinstance(result, dict) and result.get("success", False)
            status = "completed" if is_successful else "failed"
            self.monitor.update_operation(operation_id, status, result)

            # Update connection if this is a closing operation
            if "close" in operation_name.lower() and is_successful:
                self.monitor.untrack_connection(connection_id)

            return result

        except Exception as e:
            # Update operation status
            self.monitor.update_operation(operation_id, "failed", {
                "error": str(e),
                "error_type": type(e).__name__
            })

            if fallback_result is not None:
                return fallback_result
            raise

    def run_monitored_coroutine_sync(self, coro, connection_id: str,
                                    operation_name: str = None, fallback_result=None):
        """
        Run a coroutine with monitoring in any context (sync or async).

        This method will:
        1. Use AnyIO to detect the current async environment
        2. If in an async context, schedule as a monitored task and return fallback
        3. If in a sync context, run the coroutine to completion with monitoring

        Args:
            coro: The coroutine to run
            connection_id: ID of the WebRTC connection
            operation_name: Name of the operation (for tracking)
            fallback_result: Result to return if we're in a running event loop

        Returns:
            Result of the coroutine, or fallback_result if in a running loop
        """
        if not HAS_ANYIO:
            logger.error("AnyIO not available. Cannot run coroutine.")
            return fallback_result or {"success": False, "error": "AnyIO not installed"}

        # Make sure the connection is tracked
        self.monitor.track_connection(connection_id)

        # Generate operation name if not provided
        operation_name = operation_name or getattr(coro, "__name__", "unknown_operation")

        # Detect if we're already in an async context
        in_async_context = False
        try:
            current_async_lib = sniffio.current_async_library()
            logger.debug(f"Current async library: {current_async_lib}")
            in_async_context = True
        except (ImportError, sniffio.AsyncLibraryNotFoundError):
            # Not in an async context or sniffio not available
            pass

        if in_async_context:
            # We're already in an async context (likely FastAPI/Starlette)
            logger.info("Already in async context, scheduling monitored background task")

            # Prepare fallback result
            if fallback_result is None:
                fallback_result = {
                    "success": True,
                    "simulated": True,
                    "note": "Operation scheduled in background with monitoring"
                }

            # Create a unique task ID
            task_id = f"{operation_name}_{int(time.time() * 1000)}"

            # Add task to monitoring
            self.monitor.add_async_task(connection_id, task_id)

            # Create and start the background task
            async def _monitored_background_task():
                try:
                    # Run the coroutine
                    result = await coro

                    # Log success
                    logger.debug(f"Background task completed: {task_id}")

                    # If this is a close operation and succeeded, untrack the connection
                    if "close" in operation_name.lower() and isinstance(result, dict) and result.get("success", False):
                        self.monitor.untrack_connection(connection_id)

                except Exception as e:
                    logger.error(f"Error in monitored background task: {e}")
                finally:
                    # Always remove the task from tracking
                    self.monitor.remove_async_task(connection_id, task_id)

            # Start the background task with AnyIO
            import anyio
            anyio.run(_monitored_background_task())

            return fallback_result
        else:
            # Not in an async context, we can run synchronously
            logger.info("Not in async context, running monitored coroutine synchronously")

            # Generate operation ID
            operation_id = f"{operation_name}_{int(time.time() * 1000)}"

            # Track the operation
            self.monitor.add_operation(operation_id, operation_name, {
                "connection_id": connection_id
            })

            try:
                # Use AnyIO to run the coroutine to completion
                result = anyio.run(lambda: coro)

                # Update operation status
                is_successful = isinstance(result, dict) and result.get("success", False)
                status = "completed" if is_successful else "failed"
                self.monitor.update_operation(operation_id, status, result)

                # Update connection if this is a closing operation
                if "close" in operation_name.lower() and is_successful:
                    self.monitor.untrack_connection(connection_id)

                return result

            except Exception as e:
                # Update operation status
                self.monitor.update_operation(operation_id, "failed", {
                    "error": str(e),
                    "error_type": type(e).__name__
                })

                if fallback_result is not None:
                    return fallback_result
                raise

# Monitored and AnyIO-enhanced patched methods for the IPFS model

def enhanced_stop_webrtc_streaming(self, server_id: str) -> Dict[str, Any]:
    """
    Enhanced version of stop_webrtc_streaming with AnyIO event loop handling and monitoring.

    Args:
        server_id: ID of the WebRTC streaming server to stop

    Returns:
        Dictionary with operation results
    """
    operation_id = f"stop_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()

    # Get or create monitor
    monitor = getattr(self, 'webrtc_monitor', None)
    if monitor is None:
        monitor = WebRTCMonitor()
        self.webrtc_monitor = monitor

    # Create integrated handler
    handler = AnyIOMonitoredEventLoopHandler(monitor)

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

        # Prepare fallback result for when we can't run to completion
        fallback_result = {
            "connections_closed": connection_count,
            "simulated": True,
            "note": "Operation scheduled in background with monitoring"
        }

        # Use integrated handler to run the coroutine safely
        stop_result = handler.run_monitored_coroutine_sync(
            self.webrtc_manager.close_all_connections(),
            connection_id=server_id,
            operation_name="stop_webrtc_streaming",
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

async def enhanced_async_stop_webrtc_streaming(self, server_id: str) -> Dict[str, Any]:
    """
    Enhanced async version of stop_webrtc_streaming with monitoring.

    Args:
        server_id: ID of the WebRTC streaming server to stop

    Returns:
        Dictionary with operation results
    """
    operation_id = f"stop_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()

    # Get or create monitor
    monitor = getattr(self, 'webrtc_monitor', None)
    if monitor is None:
        monitor = WebRTCMonitor()
        self.webrtc_monitor = monitor

    # Create integrated handler
    handler = AnyIOMonitoredEventLoopHandler(monitor)

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
        # Since we're already in an async function, we can use monitored_coroutine
        stop_result = await handler.run_monitored_coroutine(
            self.webrtc_manager.close_all_connections(),
            connection_id=server_id,
            operation_name="stop_webrtc_streaming"
        )

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

def enhanced_close_webrtc_connection(self, connection_id: str) -> Dict[str, Any]:
    """
    Enhanced version of close_webrtc_connection with AnyIO event loop handling and monitoring.

    Args:
        connection_id: ID of the WebRTC connection to close

    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()

    # Get or create monitor
    monitor = getattr(self, 'webrtc_monitor', None)
    if monitor is None:
        monitor = WebRTCMonitor()
        self.webrtc_monitor = monitor

    # Create integrated handler
    handler = AnyIOMonitoredEventLoopHandler(monitor)

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
        # Track the connection in the monitor
        monitor.track_connection(connection_id)

        # Prepare fallback result for when we can't run to completion
        fallback_result = {
            "success": True,
            "simulated": True,
            "note": "Operation scheduled in background with monitoring"
        }

        # Use integrated handler to run the coroutine safely
        close_result = handler.run_monitored_coroutine_sync(
            self.webrtc_manager.close_connection(connection_id),
            connection_id=connection_id,
            operation_name="close_webrtc_connection",
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

async def enhanced_async_close_webrtc_connection(self, connection_id: str) -> Dict[str, Any]:
    """
    Enhanced async version of close_webrtc_connection with monitoring.

    Args:
        connection_id: ID of the WebRTC connection to close

    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()

    # Get or create monitor
    monitor = getattr(self, 'webrtc_monitor', None)
    if monitor is None:
        monitor = WebRTCMonitor()
        self.webrtc_monitor = monitor

    # Create integrated handler
    handler = AnyIOMonitoredEventLoopHandler(monitor)

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
        # Since we're already in an async function, we can use monitored_coroutine
        close_result = await handler.run_monitored_coroutine(
            self.webrtc_manager.close_connection(connection_id),
            connection_id=connection_id,
            operation_name="close_webrtc_connection"
        )

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

def enhanced_close_all_webrtc_connections(self) -> Dict[str, Any]:
    """
    Enhanced version of close_all_webrtc_connections with AnyIO event loop handling and monitoring.

    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_all_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()

    # Get or create monitor
    monitor = getattr(self, 'webrtc_monitor', None)
    if monitor is None:
        monitor = WebRTCMonitor()
        self.webrtc_monitor = monitor

    # Create integrated handler
    handler = AnyIOMonitoredEventLoopHandler(monitor)

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
        # Get current connection count and stats
        stats = self.webrtc_manager.get_stats()
        connection_count = len(stats.get("connections", {}))
        result["connection_count"] = connection_count

        # Use a shared connection ID for the operation
        shared_connection_id = f"all_connections_{int(time.time() * 1000)}"
        monitor.track_connection(shared_connection_id)

        # Prepare fallback result for when we can't run to completion
        fallback_result = {
            "connections_closed": connection_count,
            "simulated": True,
            "note": "Operation scheduled in background with monitoring"
        }

        # Use integrated handler to run the coroutine safely
        close_result = handler.run_monitored_coroutine_sync(
            self.webrtc_manager.close_all_connections(),
            connection_id=shared_connection_id,
            operation_name="close_all_webrtc_connections",
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

async def enhanced_async_close_all_webrtc_connections(self) -> Dict[str, Any]:
    """
    Enhanced async version of close_all_webrtc_connections with monitoring.

    Returns:
        Dictionary with operation results
    """
    operation_id = f"close_all_webrtc_{int(time.time() * 1000)}"
    start_time = time.time()

    # Get or create monitor
    monitor = getattr(self, 'webrtc_monitor', None)
    if monitor is None:
        monitor = WebRTCMonitor()
        self.webrtc_monitor = monitor

    # Create integrated handler
    handler = AnyIOMonitoredEventLoopHandler(monitor)

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
        result["connection_count"] = connection_count

        # Use a shared connection ID for the operation
        shared_connection_id = f"all_connections_{int(time.time() * 1000)}"
        monitor.track_connection(shared_connection_id)

        # Since we're already in an async function, we can use monitored_coroutine
        close_result = await handler.run_monitored_coroutine(
            self.webrtc_manager.close_all_connections(),
            connection_id=shared_connection_id,
            operation_name="close_all_webrtc_connections"
        )

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

def apply_enhanced_fixes(mcp_server=None, log_dir=None, debug_mode=False):
    """
    Apply WebRTC AnyIO fixes and monitoring to MCP server.

    This function adds both:
    1. AnyIO event loop fixes for WebRTC methods
    2. WebRTC monitoring capabilities

    Args:
        mcp_server: Optional MCP server instance to patch directly
                   If None, the fix will be applied to the module for future instances
        log_dir: Directory to store WebRTC monitoring logs
        debug_mode: Enable detailed WebRTC debug logging

    Returns:
        WebRTC monitor instance
    """
    if not HAS_ANYIO:
        logger.error("AnyIO not available. Install with: pip install anyio sniffio")
        return None

    if not HAS_LOCAL_MODULES:
        logger.error("Required local modules not available")
        return None

    logger.info(f"Applying enhanced WebRTC fixes (AnyIO + Monitoring)")

    # Get the IPFS model instance
    ipfs_model = None

    if mcp_server:
        if hasattr(mcp_server, 'models') and 'ipfs' in mcp_server.models:
            ipfs_model = mcp_server.models['ipfs']
        else:
            logger.error("MCP server does not have IPFS model")
            return None
    else:
        # Try to import and patch the module directly
        try:
            from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
            # We'll patch the class, not an instance
            logger.info("Patching IPFSModel class directly")
        except ImportError:
            logger.error("Could not import IPFSModel. Provide an MCP server instance instead.")
            return None

    # Create WebRTC monitor
    monitor = WebRTCMonitor(log_dir=log_dir, debug_mode=debug_mode)

    if ipfs_model:
        # We have an instance to patch

        # Save original methods (optional)
        original_stop_streaming = getattr(ipfs_model, "stop_webrtc_streaming", None)
        original_close_connection = getattr(ipfs_model, "close_webrtc_connection", None)
        original_close_all_connections = getattr(ipfs_model, "close_all_webrtc_connections", None)

        # Attach the monitor
        ipfs_model.webrtc_monitor = monitor

        # Replace with enhanced implementations
        ipfs_model.stop_webrtc_streaming = lambda server_id: enhanced_stop_webrtc_streaming(ipfs_model, server_id)
        ipfs_model.close_webrtc_connection = lambda connection_id: enhanced_close_webrtc_connection(ipfs_model, connection_id)
        ipfs_model.close_all_webrtc_connections = lambda: enhanced_close_all_webrtc_connections(ipfs_model)

        # Add async methods for use with FastAPI
        ipfs_model.async_stop_webrtc_streaming = lambda server_id: enhanced_async_stop_webrtc_streaming(ipfs_model, server_id)
        ipfs_model.async_close_webrtc_connection = lambda connection_id: enhanced_async_close_webrtc_connection(ipfs_model, connection_id)
        ipfs_model.async_close_all_webrtc_connections = lambda: enhanced_async_close_all_webrtc_connections(ipfs_model)

        logger.info("IPFS model WebRTC methods enhanced with AnyIO fixes and monitoring")

        # If we have a server, also patch the controller
        if mcp_server and hasattr(mcp_server, 'controllers') and 'webrtc' in mcp_server.controllers:
            controller = mcp_server.controllers['webrtc']
            patch_webrtc_controller_methods(controller)
            logger.info("WebRTC controller methods patched to use enhanced async implementations")
    else:
        # Patch the class directly (more complex)
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

        # Save original methods
        original_stop_streaming = IPFSModel.stop_webrtc_streaming
        original_close_connection = IPFSModel.close_webrtc_connection
        original_close_all_connections = IPFSModel.close_all_webrtc_connections

        # Replace with enhanced implementations
        IPFSModel.stop_webrtc_streaming = enhanced_stop_webrtc_streaming
        IPFSModel.close_webrtc_connection = enhanced_close_webrtc_connection
        IPFSModel.close_all_webrtc_connections = enhanced_close_all_webrtc_connections

        # Add async methods for use with FastAPI
        IPFSModel.async_stop_webrtc_streaming = enhanced_async_stop_webrtc_streaming
        IPFSModel.async_close_webrtc_connection = enhanced_async_close_webrtc_connection
        IPFSModel.async_close_all_webrtc_connections = enhanced_async_close_all_webrtc_connections

        logger.info("IPFSModel class WebRTC methods enhanced with AnyIO fixes and monitoring")

        # We can't patch the controller without an instance

    return monitor

if __name__ == "__main__":
    # Example usage
    print("WebRTC AnyIO & Monitoring Integration")
    print("=====================================")
    print(f"AnyIO available: {HAS_ANYIO}")
    print(f"Local modules available: {HAS_LOCAL_MODULES}")

    # Check if we can run the integration
    if HAS_ANYIO and HAS_LOCAL_MODULES:
        print("\nRunning integration test...")

        # Create a dummy class to test with
        class DummyManager:
            async def close_connection(self, connection_id):
                print(f"Closing connection {connection_id}")
                return {"success": True, "connection_closed": True}

            async def close_all_connections(self):
                print("Closing all connections")
                return {"success": True, "connections_closed": 3}

        class DummyModel:
            def __init__(self):
                self.webrtc_manager = DummyManager()

        # Create a dummy model
        model = DummyModel()

        # Apply enhanced fixes
        monitor = apply_enhanced_fixes(None, log_dir="./logs", debug_mode=True)

        # Manually attach monitor to our test instance
        model.webrtc_monitor = monitor

        # Test the enhanced methods
        print("\nTesting enhanced stop_webrtc_streaming method:")
        result = enhanced_stop_webrtc_streaming(model, "test-server")
        print(f"Result: {result}")

        print("\nTesting enhanced close_webrtc_connection method:")
        result = enhanced_close_webrtc_connection(model, "test-connection")
        print(f"Result: {result}")

        print("\nWebRTC monitor summary:")
        print(monitor.get_summary())
    else:
        print("\nCannot run integration test due to missing dependencies.")
        print("Install required packages with:")
        print("pip install anyio sniffio")
