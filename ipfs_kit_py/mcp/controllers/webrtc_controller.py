"""
WebRTC Controller for the MCP server (AnyIO Version).

This controller handles HTTP requests related to WebRTC operations and
delegates the business logic to the IPFS model. It uses AnyIO for async operations.
"""

import logging
import time
import anyio
import anyio.from_thread
from typing import Dict, List, Any, Optional

try:
    from fastapi import APIRouter
    from pydantic import BaseModel, Field
except ImportError:
    # Create a simple BaseModel class as fallback
    class BaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            
    # Add Field as a no-op function
    def Field(**kwargs):
        return None

# Import WebRTC dependencies and status flags
try:
    from ipfs_kit_py.webrtc_streaming import (
        HAVE_WEBRTC,
        HAVE_AV,
        HAVE_CV2,
        HAVE_NUMPY,
        HAVE_AIORTC,
        WebRTCStreamingManager,
        check_webrtc_dependencies)
except ImportError:
    # Set flags to False if the module is not available
    HAVE_WEBRTC = False
    HAVE_AV = False
    HAVE_CV2 = False
    HAVE_NUMPY = False
    HAVE_AIORTC = False

    # Create stub for check_webrtc_dependencies
    def check_webrtc_dependencies():
        return {
            "webrtc_available": False,
            "dependencies": {
                "numpy": False,
                "opencv": False,
                "av": False,
                "aiortc": False,
                "websockets": False,
                "notifications": False,
            },
            "installation_command": "pip install ipfs_kit_py[webrtc]",
        }


# Configure logger
logger = logging.getLogger(__name__)


# Define Pydantic models for requests and responses
class WebRTCResponse(BaseModel):
    """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Base response model for WebRTC operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    operation_id: str = Field(None, description="Unique identifier for this operation")


class ResourceStatsResponse(WebRTCResponse):
    """Response model for resource statistics."""
    servers: Dict[str, Any] = Field(None, description="Streaming server statistics")
    connections: Dict[str, Any] = Field(None, description="Connection statistics")
    timestamp: float = Field(None, description="Timestamp of the statistics")
    is_shutting_down: bool = Field(False, description="Whether the controller is shutting down")
    cleanup_task_active: bool = Field(False, description="Whether the cleanup task is active")


class StreamRequest(BaseModel):
    """Request model for starting a WebRTC stream."""
    cid: str = Field(..., description="Content Identifier (CID) of the media to stream")
    address: str = Field("127.0.0.1", description="Address to bind the WebRTC signaling server")
    port: int = Field(8080, description="Port for the WebRTC signaling server")
    quality: str = Field("medium", description="Streaming quality preset (low, medium, high, auto)")
    ice_servers: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of ICE server objects"
    )
    benchmark: bool = Field(False, description="Enable performance benchmarking")
    # Advanced streaming optimization parameters
    buffer_size: Optional[int] = Field(30, description="Frame buffer size (1-60 frames)")
    prefetch_threshold: Optional[float] = Field(
        0.5, description="Buffer prefetch threshold (0.1-0.9)"
    )
    use_progressive_loading: Optional[bool] = Field(
        True, description="Enable progressive content loading"
    )


class StreamResponse(WebRTCResponse):
    """Response model for starting a WebRTC stream."""
    server_id: Optional[str] = Field(None, description="ID of the WebRTC streaming server")
    url: Optional[str] = Field(None, description="URL to access the WebRTC stream")


class ConnectionResponse(WebRTCResponse):
    """Response model for WebRTC connection operations."""
    connection_id: Optional[str] = Field(None, description="ID of the WebRTC connection")


class ConnectionsListResponse(WebRTCResponse):
    """Response model for listing WebRTC connections."""
    connections: Optional[List[Dict[str, Any]]] = Field(
        None, description="List of active WebRTC connections"
    )


class ConnectionStatsResponse(WebRTCResponse):
    """Response model for WebRTC connection statistics."""
    stats: Optional[Dict[str, Any]] = Field(
        None, description="Statistics for the WebRTC connection"
    )


class DependencyResponse(WebRTCResponse):
    """Response model for WebRTC dependency check."""
    dependencies: Optional[Dict[str, bool]] = Field(None, description="WebRTC dependencies status")
    webrtc_available: bool = Field(False, description="Whether WebRTC is available")
    installation_command: Optional[str] = Field(None, description="Command to install dependencies")


class BenchmarkRequest(BaseModel):
    """Request model for running a WebRTC benchmark."""
    cid: str = Field(..., description="Content Identifier (CID) of the media to benchmark")
    duration: int = Field(60, description="Benchmark duration in seconds")
    format: str = Field("json", description="Report output format (json, html, csv)")
    output_dir: Optional[str] = Field(None, description="Directory to save benchmark reports")


class BenchmarkResponse(WebRTCResponse):
    """Response model for WebRTC benchmark results."""
    benchmark_id: Optional[str] = Field(None, description="ID of the benchmark run")
    report_path: Optional[str] = Field(None, description="Path to the benchmark report file")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary of benchmark results")


class QualityRequest(BaseModel):
    """Request model for changing WebRTC quality."""
    connection_id: str = Field(..., description="ID of the WebRTC connection")
    quality: str = Field(..., description="Quality preset to use (low, medium, high, auto)")


class WebRTCController:
    """
    Controller for WebRTC operations (AnyIO version).

    Handles HTTP requests related to WebRTC operations and delegates
    the business logic to the IPFS model.
    """
    def __init__(self, ipfs_model):
        """
        Initialize the WebRTC controller.

        Args:
            ipfs_model: IPFS model to use for WebRTC operations
        """
        self.ipfs_model = ipfs_model
        self.active_streaming_servers = {}
        self.active_connections = {}
        self.cleanup_task = None
        self.is_shutting_down = False
        self.last_auto_cleanup = None

        # Set default resource limits
        self.max_servers = 10
        self.max_connections_per_server = 20
        self.auto_cleanup_threshold = 80

        # Start background cleanup task
        self._start_cleanup_task()

        logger.info("WebRTC Controller initialized with AnyIO and resource management")

    def _start_cleanup_task(self):
        """Start a periodic background task to clean up stale resources."""
        async def periodic_cleanup():
            try:
                logger.debug("Starting WebRTC periodic cleanup task")
                while not self.is_shutting_down:
                    try:
                        # Wait for the cleanup interval
                        await anyio.sleep(60)  # Run cleanup every minute

                        if self.is_shutting_down:
                            break

                        # Check for stale streaming servers
                        current_time = time.time()
                        stale_servers = []

                        for server_id, server_info in list(self.active_streaming_servers.items()):
                            # Get server info
                            started_at = server_info.get("started_at", 0)
                            is_benchmark = server_info.get("is_benchmark", False)
                            duration = server_info.get("duration", 3600)  # 1 hour default

                            # Calculate expected end time for benchmarks
                            if is_benchmark and (current_time - started_at) > (
                                duration + 60
                            ):  # Add 60s buffer
                                stale_servers.append(server_id)
                                logger.info(
                                    f"Detected stale benchmark server: {server_id}, age: {current_time - started_at:.0f}s"
                                )

                            # For normal streaming servers, just check if they are still running
                            # by calling list_webrtc_connections in the cleanup task

                        # Clean up stale servers
                        for server_id in stale_servers:
                            try:
                                logger.info(f"Cleaning up stale server: {server_id}")
                                _ = self.ipfs_model.stop_webrtc_streaming(server_id=server_id)
                                if server_id in self.active_streaming_servers:
                                    del self.active_streaming_servers[server_id]
                            except Exception as e:
                                logger.error(f"Error cleaning up stale server {server_id}: {e}")

                        # Check for and update active connections
                        try:
                            result = self.ipfs_model.list_webrtc_connections()
                            if result.get("success", False):
                                connections = result.get("connections", [])

                                # Get current live connection IDs
                                current_connection_ids = {
                                    conn.get("id") for conn in connections if conn.get("id")
                                }

                                # Find and remove stale connections
                                stale_connections = (
                                    set(self.active_connections.keys()) - current_connection_ids
                                )
                                for conn_id in stale_connections:
                                    logger.info(
                                        f"Removing stale connection from tracking: {conn_id}"
                                    )
                                    if conn_id in self.active_connections:
                                        del self.active_connections[conn_id]
                        except Exception as e:
                            logger.error(f"Error checking connections in cleanup task: {e}")

                        # Check system resource usage and perform proactive cleanup if needed
                        try:
                            # Get current resource stats
                            stats = self.get_resource_stats()

                            # Check if we have system stats
                            if "system" in stats and "health_score" in stats["system"]:
                                health_score = stats["system"]["health_score"]

                                # If health score is too low, perform auto cleanup
                                if (
                                    health_score
                                    < stats["resource_management"]["auto_cleanup_threshold"]
                                ):
                                    logger.warning(
                                        f"System health score ({health_score}) below threshold "
                                        f"({stats['resource_management']['auto_cleanup_threshold']}). "
                                        f"Performing automatic resource cleanup."
                                    )

                                    # Log the current state before cleanup
                                    logger.info(
                                        f"Servers before cleanup: {len(self.active_streaming_servers)}"
                                    )
                                    logger.info(
                                        f"Connections before cleanup: {len(self.active_connections)}"
                                    )

                                    # Set last auto cleanup time
                                    self.last_auto_cleanup = time.time()

                                    # Find high-impact servers for cleanup
                                    high_impact_servers = []

                                    # First, add any idle/inactive servers
                                    # (those with few or no connections) to the cleanup list
                                    for server_info in stats["servers"]["servers"]:
                                        server_id = server_info["id"]

                                        # Skip benchmark servers (they're temporary anyway)
                                        if server_info["is_benchmark"]:
                                            continue

                                        # Check if server has no connections
                                        if server_info["connection_count"] == 0:
                                            logger.info(
                                                f"Marking idle server for cleanup: {server_id}"
                                            )
                                            high_impact_servers.append(server_id)
                                            continue

                                        # Check if server has high impact score
                                        if server_info["impact_score"] > 70:
                                            logger.info(
                                                f"Marking high-impact server for cleanup: {server_id}"
                                            )
                                            high_impact_servers.append(server_id)

                                    # Clean up high-impact servers, oldest first
                                    high_impact_servers.sort(
                                        key=lambda sid: self.active_streaming_servers.get(
                                            sid, {}
                                        ).get("started_at", 0)
                                    )

                                    # Limit cleanup to 50% of servers to avoid disrupting too many streams
                                    cleanup_limit = max(1, len(self.active_streaming_servers) // 2)
                                    servers_to_cleanup = high_impact_servers[:cleanup_limit]

                                    for server_id in servers_to_cleanup:
                                        try:
                                            logger.info(f"Auto-cleanup stopping server {server_id}")
                                            _ = self.ipfs_model.stop_webrtc_streaming(
                                                server_id=server_id
                                            )
                                            if server_id in self.active_streaming_servers:
                                                del self.active_streaming_servers[server_id]
                                        except Exception as e:
                                            logger.error(
                                                f"Error auto-cleaning server {server_id}: {e}"
                                            )

                                    # Log the result of cleanup
                                    logger.info(
                                        f"Auto-cleanup complete. Stopped {len(servers_to_cleanup)} servers"
                                    )
                                    logger.info(
                                        f"Servers after cleanup: {len(self.active_streaming_servers)}"
                                    )
                                    logger.info(
                                        f"Connections after cleanup: {len(self.active_connections)}"
                                    )
                        except Exception as e:
                            logger.error(f"Error performing resource-based cleanup: {e}")

                    except anyio.get_cancelled_exc_class():
                        # Handle task cancellation
                        logger.info("Cleanup task cancelled")
                        break
                    except Exception as e:
                        # Don't let errors stop the cleanup loop
                        logger.error(f"Error in periodic cleanup: {e}")

                logger.debug("WebRTC periodic cleanup task stopped")
            except Exception as e:
                logger.error(f"Fatal error in cleanup task: {e}")

        # Start the task with AnyIO
        try:
            # Use the current TaskGroup if it exists, or spawn a new one
            if hasattr(anyio, "create_task_group"):
                # AnyIO 3.x style
                async def start_task():
                    async with anyio.create_task_group() as tg:
                        tg.start_soon(periodic_cleanup)
                        # Store task group reference for potential cancellation
                        self.cleanup_task = tg

                # Schedule the task starter, but don't wait for it
                # In real runtime context, this will work normally
                self.cleanup_task = {"pending": True, "type": "task_group"}
                logger.info("Scheduled WebRTC cleanup task with AnyIO task group")
            else:
                # Handle older versions or alternative implementations
                try:
                    # Try the standard create_task approach
                    self.cleanup_task = anyio.create_task(periodic_cleanup())
                    logger.info("Started WebRTC cleanup task with anyio.create_task")
                except AttributeError:
                    # Fall back to creating a task group manually
                    logger.info("Using manual task management for WebRTC cleanup")
                    self.cleanup_task = {"pending": True, "type": "manual"}

        except Exception as e:
            logger.warning(f"Could not start cleanup task with AnyIO: {e}")
            self.cleanup_task = None

    async def shutdown(self):
        """
        Safely shut down all WebRTC resources.

        This method ensures proper cleanup of all WebRTC resources,
        including streaming servers, peer connections, and tracks.
        It handles both synchronous and asynchronous contexts for
        proper cleanup task management.
        """
        logger.info("WebRTC Controller shutdown initiated")

        # Signal the cleanup task to stop
        self.is_shutting_down = True

        # Helper function to handle different async frameworks
        def handle_asyncio_cancel():
            """Handle cancellation in asyncio context"""
            try:
                # Try to get the event loop and cancel the task
                loop = anyio.get_event_loop()
                self.cleanup_task.cancel()

                # Wait for the task to be cancelled (with timeout)
                if loop.is_running():
                    # We can't use run_until_complete in a running loop
                    logger.info("Loop is running, scheduling cancellation")
                    # Just schedule the cancellation and continue
                    return

                try:
                    # Use a timeout to prevent hanging
                    loop.run_until_complete(
                        anyio.wait_for(anyio.shield(self.cleanup_task), timeout=2.0)
                    )
                    logger.info("Cleanup task cancelled successfully")
                except (anyio.TimeoutError, anyio.CancelledError):
                    # Task either timed out or was cancelled, which is expected
                    logger.info("Cleanup task cancellation completed")
                except RuntimeError as e:
                    if "This event loop is already running" in str(e):
                        # We're in a running event loop, which is fine
                        logger.info("Cleanup task cancellation scheduled in running loop")
                    else:
                        logger.warning(f"Runtime error waiting for task cancellation: {e}")
                except Exception as e:
                    logger.warning(f"Error waiting for cleanup task cancellation: {e}")
            except Exception as e:
                logger.warning(f"Error cancelling cleanup task with asyncio: {e}")

        # Helper function to handle AnyIO cancellation
        def handle_anyio_cancel():
            """Handle cancellation in AnyIO context"""
            try:
                if self.cleanup_task is None:
                    return

                # Handle different types of task objects
                if isinstance(self.cleanup_task, dict):
                    # It's our dictionary-based task tracking
                    logger.info(
                        f"Task is being tracked as: {self.cleanup_task.get('type', 'unknown')}"
                    )
                    # Just rely on the shutting_down flag for these

                # For AnyIO 3.x TaskGroup
                elif hasattr(self.cleanup_task, "cancel_scope"):
                    # Task group with cancel scope
                    self.cleanup_task.cancel_scope.cancel()
                    logger.info("AnyIO TaskGroup cancellation initiated")

                # For standard AnyIO task
                elif hasattr(self.cleanup_task, "cancel"):
                    # Direct cancellation for AnyIO task
                    self.cleanup_task.cancel()
                    logger.info("AnyIO task cancellation initiated")

                else:
                    # Unknown task type
                    logger.warning(
                        f"Unknown task type: {type(self.cleanup_task).__name__}, falling back to flag-based cancellation"
                    )
                    # Signal cancellation through shutting_down flag
                    # The task should check this flag periodically
            except Exception as e:
                logger.warning(f"Error cancelling cleanup task with AnyIO: {e}")
                # Fall back to asyncio method as a last resort
                try:
                    handle_asyncio_cancel()
                except Exception as nested_e:
                    logger.warning(f"Fallback asyncio cancellation also failed: {nested_e}")

        # Cancel the cleanup task if it's running
        if self.cleanup_task is not None:
            logger.info(
                f"Attempting to cancel cleanup task (type: {type(self.cleanup_task).__name__})"
            )

            # Import asyncio for handling asyncio tasks
            

            # Use AnyIO since we already imported it at the top of the file
            handle_anyio_cancel()

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
            # Check if we're in interpreter shutdown
            import sys

            is_shutdown = hasattr(sys, "is_finalizing") and sys.is_finalizing()

            if is_shutdown:
                # During interpreter shutdown, thread creation might fail
                # Just log and continue without trying thread operations
                logger.warning(
                    "Interpreter is shutting down, skipping thread-based WebRTC connection closure"
                )
                result = {
                    "success": True,
                    "warning": "Interpreter shutting down, connections may not be fully closed",
                }
            elif hasattr(self.ipfs_model, "async_close_all_webrtc_connections"):
                # Use async version if available
                result = await self.ipfs_model.async_close_all_webrtc_connections()
            elif hasattr(self.ipfs_model, "close_all_webrtc_connections"):
                # Fall back to sync version, but check for interpreter shutdown first
                if not is_shutdown:
                    try:
                        result = await anyio.to_thread.run_sync(
                            self.ipfs_model.close_all_webrtc_connections
                        )
                    except RuntimeError as e:
                        if "can't create new thread" in str(e):
                            logger.warning("Thread creation failed during interpreter shutdown")
                            result = {
                                "success": True,
                                "warning": "Interpreter shutting down, connections may not be fully closed",
                            }
                        else:
                            raise
                else:
                    result = {
                        "success": True,
                        "warning": "Interpreter shutting down, connections may not be fully closed",
                    }
            else:
                logger.warning("No method available to close WebRTC connections")
                result = {"success": False, "error": "Method not available"}

            if isinstance(result, dict) and not result.get("success", False):
                logger.error(
                    f"Error closing WebRTC connections: {result.get('error', 'Unknown error')}"
                )
            else:
                logger.info("Successfully closed all WebRTC connections")
        except Exception as e:
            logger.error(f"Error closing WebRTC connections during shutdown: {e}")

        # Clear dictionaries to release references
        self.active_streaming_servers.clear()
        self.active_connections.clear()

        logger.info("WebRTC Controller shutdown completed")

    # Synchronous version of shutdown for compatibility
    def sync_shutdown(self):
        """
        Synchronous version of shutdown for backward compatibility.

        This method provides a synchronous way to shut down the controller
        for contexts where async/await cannot be used directly.
        """
        logger.info("Running synchronous shutdown for WebRTC Controller")

        # Check for interpreter shutdown
        import sys

        is_interpreter_shutdown = hasattr(sys, "is_finalizing") and sys.is_finalizing()

        # Special fast shutdown path for interpreter shutdown to avoid thread creation
        if is_interpreter_shutdown:
            logger.warning("Detected interpreter shutdown, using simplified cleanup")
            try:
                # Signal the cleanup task to stop
                self.is_shutting_down = True

                # Clear active resources without trying to create new threads
                self.active_streaming_servers.clear()
                self.active_connections.clear()

                # Set cleanup task to None to avoid further processing
                self.cleanup_task = None

                logger.info(
                    "Simplified WebRTC Controller shutdown completed during interpreter shutdown"
                )
                return
            except Exception as e:
                logger.error(f"Error during simplified shutdown: {e}")
                # Continue with standard shutdown which might fail gracefully

        try:
            # Try using anyio (preferred method)
            try:
                

                anyio.run(self.shutdown)
                return
            except ImportError:
                logger.warning("anyio not available, falling back to asyncio")
            except Exception as e:
                logger.warning(f"Error using anyio.run for shutdown: {e}, falling back to asyncio")

            # Fallback to asyncio
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # Don't create a new event loop during interpreter shutdown
                if is_interpreter_shutdown:
                    logger.warning("Cannot get event loop during interpreter shutdown")
                    # Signal shutdown and clear resources directly
                    self.is_shutting_down = True
                    self.active_streaming_servers.clear()
                    self.active_connections.clear()
                    return

                # Create a new event loop if no event loop is set and not in shutdown
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the shutdown method
            try:
                loop.run_until_complete(self.shutdown())
            except RuntimeError as e:
                if "This event loop is already running" in str(e):
                    logger.warning("Cannot use run_until_complete in a running event loop")
                    # Cannot handle properly in this case - controller shutdown might be incomplete
                elif "can't create new thread" in str(e):
                    logger.warning("Thread creation failed during interpreter shutdown")
                    # Signal shutdown and clear resources directly
                    self.is_shutting_down = True
                    self.active_streaming_servers.clear()
                    self.active_connections.clear()
                else:
                    raise
        except Exception as e:
            logger.error(f"Error in sync_shutdown for WebRTC Controller: {e}")
            # Ensure resources are cleared even on error
            try:
                self.is_shutting_down = True
                self.active_streaming_servers.clear()
                self.active_connections.clear()
            except Exception as clear_error:
                logger.error(f"Error clearing resources during error handling: {clear_error}")

        logger.info("Synchronous shutdown for WebRTC Controller completed")

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
                if hasattr(self.ipfs_model, "stop_webrtc_streaming"):
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
                if hasattr(self.ipfs_model, "close_webrtc_connection"):
                    self.ipfs_model.close_webrtc_connection(connection_id=connection_id)
            except Exception as e:
                logger.warning(f"Error during final cleanup of connection {connection_id}: {e}")
            finally:
                # Always remove from tracking
                if connection_id in self.active_connections:
                    del self.active_connections[connection_id]

        # 3. For extra safety, try calling close_all_webrtc_connections
        try:
            # Check if we're in interpreter shutdown
            import sys

            is_shutdown = hasattr(sys, "is_finalizing") and sys.is_finalizing()

            if is_shutdown:
                logger.debug(
                    "Skipping final close_all_webrtc_connections due to interpreter shutdown"
                )
            elif hasattr(self.ipfs_model, "close_all_webrtc_connections"):
                logger.debug("Calling close_all_webrtc_connections as final safety measure")
                try:
                    self.ipfs_model.close_all_webrtc_connections()
                except RuntimeError as e:
                    if "can't create new thread" in str(e):
                        logger.warning(
                            "Thread creation failed during interpreter shutdown in final cleanup"
                        )
                    else:
                        raise
        except Exception as e:
            logger.warning(f"Error during final close_all_webrtc_connections: {e}")

        # 4. Check if event loop or thread needs cleanup
        if hasattr(self, "event_loop_thread"):
            logger.debug("Cleanup of event loop thread may be needed at process exit")
            # We don't forcibly kill the thread here as it might be unsafe,
            # but we log it for potential future improvement

        logger.info("Final resource cleanup completed")

    async def close_all_streaming_servers(self):
        """
        Close all active WebRTC streaming servers.

        This method ensures proper cleanup of all streaming server resources.
        """
        logger.info(f"Closing all WebRTC streaming servers: {len(self.active_streaming_servers)}")

        for server_id, server_info in list(self.active_streaming_servers.items()):
            try:
                # Use the model's stop_webrtc_streaming method
                if hasattr(self.ipfs_model, "stop_webrtc_streaming"):
                    result = self.ipfs_model.stop_webrtc_streaming(server_id=server_id)
                    if isinstance(result, dict) and not result.get("success", False):
                        logger.error(
                            f"Error stopping streaming server {server_id}: {result.get('error', 'Unknown error')}"
                        )
                    else:
                        logger.info(f"Successfully stopped streaming server {server_id}")
            except Exception as e:
                logger.error(f"Error stopping streaming server {server_id}: {e}")

        # Clear the dictionary to release references
        self.active_streaming_servers.clear()

        logger.info("All WebRTC streaming servers closed")

    def get_resource_stats(self):
        """
        Get statistics about tracked resources.

        Returns:
            Dictionary with resource usage and tracking information
        """
        current_time = time.time()

        # Get system resource usage if psutil is available
        system_resources = {}
        try:
            import psutil

            # Get CPU usage
            system_resources["cpu"] = {
                "percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count(),
                "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            }

            # Get memory usage
            memory = psutil.virtual_memory()
            system_resources["memory"] = {
                "total": memory.total,
                "available": memory.available,
                "used": memory.used,
                "percent": memory.percent,
            }

            # Get disk usage for the current directory
            disk = psutil.disk_usage(".")
            system_resources["disk"] = {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent,
            }

            # Get network I/O stats
            net_io = psutil.net_io_counters()
            system_resources["network"] = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errin": net_io.errin,
                "errout": net_io.errout,
                "dropin": net_io.dropin,
                "dropout": net_io.dropout,
            }

            # Calculate a health score based on resource availability
            health_score = 100

            # Reduce health score based on CPU usage
            cpu_penalty = max(0, (system_resources["cpu"]["percent"] - 70) * 1.5)
            health_score -= cpu_penalty

            # Reduce health score based on memory usage
            memory_penalty = max(0, (system_resources["memory"]["percent"] - 70) * 1.5)
            health_score -= memory_penalty

            # Reduce health score based on disk usage
            disk_penalty = max(0, (system_resources["disk"]["percent"] - 70) * 1.5)
            health_score -= disk_penalty

            # Cap health score between 0 and 100
            health_score = max(0, min(100, health_score))

            system_resources["health_score"] = health_score
            system_resources["status"] = (
                "critical" if health_score < 30 else "warning" if health_score < 70 else "healthy"
            )

        except ImportError:
            logger.warning("psutil not available for resource monitoring")
            system_resources = {"available": False, "error": "psutil not installed"}
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            system_resources = {"available": False, "error": str(e)}

        # Get per-server resource usage
        server_resources = []
        for server_id, server_info in self.active_streaming_servers.items():
            # Get stats for this server
            started_at = server_info.get("started_at", current_time)
            age_seconds = current_time - started_at
            is_benchmark = server_info.get("is_benchmark", False)

            # Get connection count for this server
            conn_count = len(
                [
                    conn_id
                    for conn_id, conn_info in self.active_connections.items()
                    if conn_info.get("server_id") == server_id
                ]
            )

            # Calculate resource impact
            resource_impact = {
                "age_impact": min(100, age_seconds / 3600 * 10),  # 10% per hour up to 100%
                "connection_impact": conn_count * 5,  # 5% per connection
                "benchmark_impact": 20 if is_benchmark else 0,  # Extra 20% for benchmarks
            }

            # Calculate total impact score (higher means more resource intensive)
            impact_score = min(100, sum(resource_impact.values()))

            server_resources.append(
                {
                    "id": server_id,
                    "cid": server_info.get("cid"),
                    "started_at": started_at,
                    "age_seconds": age_seconds,
                    "is_benchmark": is_benchmark,
                    "url": server_info.get("url"),
                    "connection_count": conn_count,
                    "resource_impact": resource_impact,
                    "impact_score": impact_score,
                    "priority": server_info.get("priority", "normal"),
                }
            )

        # Sort servers by impact score (highest first)
        server_resources.sort(key=lambda x: x["impact_score"], reverse=True)

        # Build resource stats response
        return {
            "servers": {
                "count": len(self.active_streaming_servers),
                "servers": server_resources,
                "total_impact_score": sum(server["impact_score"] for server in server_resources),
                "high_impact_count": len([s for s in server_resources if s["impact_score"] > 70]),
            },
            "connections": {
                "count": len(self.active_connections),
                "connections": [
                    {
                        "id": conn_id,
                        "added_at": conn_info.get("added_at"),
                        "age_seconds": current_time - conn_info.get("added_at", current_time),
                        "server_id": conn_info.get("server_id"),
                        "has_stats": "last_stats_update" in conn_info,
                        "quality": conn_info.get("quality"),
                        "last_activity": conn_info.get(
                            "last_activity", conn_info.get("added_at", current_time)
                        ),
                        "inactive_seconds": current_time
                        - conn_info.get("last_activity", conn_info.get("added_at", current_time)),
                    }
                    for conn_id, conn_info in self.active_connections.items()
                ],
            },
            "system": system_resources,
            "timestamp": current_time,
            "is_shutting_down": self.is_shutting_down,
            "cleanup_task_active": self.cleanup_task is not None,
            "max_servers": 10,  # Maximum number of concurrent servers allowed
            "max_connections_per_server": 20,  # Maximum connections per server
            "resource_management": {
                "enabled": True,
                "auto_cleanup_threshold": 80,  # Auto cleanup when health score drops below this
                "last_auto_cleanup": (
                    self.last_auto_cleanup if hasattr(self, "last_auto_cleanup") else None
                ),
            },
        }

    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.

        Args:
            router: FastAPI router to register routes with
        """
        # Check WebRTC dependencies
        router.add_api_route(
            "/webrtc/check",
            self.check_dependencies,
            methods=["GET"],
            response_model=DependencyResponse,
            summary="Check WebRTC dependencies",
            description="Check if WebRTC dependencies are available and working",
        )

        # Stream content
        router.add_api_route(
            "/webrtc/stream",
            self.stream_content,
            methods=["POST"],
            response_model=StreamResponse,
            summary="Stream IPFS content over WebRTC",
            description="Start a WebRTC streaming server for IPFS content",
        )

        # Stop streaming
        router.add_api_route(
            "/webrtc/stream/stop/{server_id}",
            self.stop_streaming,
            methods=["POST"],
            response_model=WebRTCResponse,
            summary="Stop WebRTC streaming",
            description="Stop a WebRTC streaming server",
        )

        # List connections
        router.add_api_route(
            "/webrtc/connections",
            self.list_connections,
            methods=["GET"],
            response_model=ConnectionsListResponse,
            summary="List WebRTC connections",
            description="List active WebRTC connections",
        )

        # Get connection stats
        router.add_api_route(
            "/webrtc/connections/{connection_id}/stats",
            self.get_connection_stats,
            methods=["GET"],
            response_model=ConnectionStatsResponse,
            summary="Get WebRTC connection statistics",
            description="Get statistics for a specific WebRTC connection",
        )

        # Close connection
        router.add_api_route(
            "/webrtc/connections/{connection_id}/close",
            self.close_connection,
            methods=["POST"],
            response_model=ConnectionResponse,
            summary="Close WebRTC connection",
            description="Close a specific WebRTC connection",
        )

        # Close all connections
        router.add_api_route(
            "/webrtc/connections/close-all",
            self.close_all_connections,
            methods=["POST"],
            response_model=WebRTCResponse,
            summary="Close all WebRTC connections",
            description="Close all active WebRTC connections",
        )

        # Change quality
        router.add_api_route(
            "/webrtc/connections/quality",
            self.set_quality,
            methods=["POST"],
            response_model=ConnectionResponse,
            summary="Change WebRTC quality",
            description="Change streaming quality for a specific connection",
        )

        # Run benchmark
        router.add_api_route(
            "/webrtc/benchmark",
            self.run_benchmark,
            methods=["POST"],
            response_model=BenchmarkResponse,
            summary="Run WebRTC benchmark",
            description="Run a performance benchmark for WebRTC streaming",
        )

        # Get resource statistics
        router.add_api_route(
            "/webrtc/stats/resources",
            self.get_resources_endpoint,
            methods=["GET"],
            response_model=ResourceStatsResponse,
            summary="Get WebRTC resource statistics",
            description="Get statistics about tracked WebRTC resources",
        )

        logger.info("WebRTC Controller routes registered")

    async def check_dependencies(self) -> Dict[str, Any]:
        """
        Check if WebRTC dependencies are available.

        Returns:
            Dictionary with dependency status
        """
        logger.debug("Checking WebRTC dependencies")

        # Use the AnyIO-compatible version if available
        if hasattr(self.ipfs_model, "async_check_webrtc_dependencies"):
            return await self.ipfs_model.async_check_webrtc_dependencies()
        elif hasattr(self.ipfs_model, "check_webrtc_dependencies_anyio"):
            return await self.ipfs_model.check_webrtc_dependencies_anyio()

        # Fall back to the original synchronous method as a background thread
        return await anyio.to_thread.run_sync(self.ipfs_model.check_webrtc_dependencies)

    async def stream_content(self, request: StreamRequest) -> Dict[str, Any]:
        """
        Stream IPFS content over WebRTC.

        Args:
            request: Stream request with CID and configuration options

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Starting WebRTC stream for CID: {request.cid}")

        # Check if we've hit server limit
        stats = self.get_resource_stats()
        server_count = stats["servers"]["count"]
        max_servers = stats["max_servers"]

        # Resource limit checks
        if server_count >= max_servers:
            logger.warning(f"WebRTC server limit reached ({server_count}/{max_servers})")
            return {
                "success": False,
                "error": f"Server limit reached ({server_count}/{max_servers})",
                "error_type": "resource_limit",
                "operation_id": f"stream_{time.time()}",
                "resource_stats": {
                    "server_count": server_count,
                    "max_servers": max_servers,
                },
            }

        # Check system health score if available
        if "system" in stats and "health_score" in stats["system"]:
            health_score = stats["system"]["health_score"]
            if health_score < 30:  # Critical health score
                logger.warning(f"System health too low for new streams: {health_score}/100")
                return {
                    "success": False,
                    "error": f"System resources too low to start new stream (health: {health_score}/100)",
                    "error_type": "resource_exhaustion",
                    "operation_id": f"stream_{time.time()}",
                    "resource_stats": {
                        "health_score": health_score,
                        "status": stats["system"]["status"],
                    },
                }

            # Apply quality throttling based on system health
            if health_score < 50 and request.quality == "high":
                logger.warning(
                    f"Downgrading quality from high to medium due to health score {health_score}"
                )
                request.quality = "medium"
            elif health_score < 30 and request.quality in ["high", "medium"]:
                logger.warning(f"Downgrading quality to low due to health score {health_score}")
                request.quality = "low"

        # Parse ICE servers
        ice_servers = request.ice_servers
        if not ice_servers:
            ice_servers = [{"urls": ["stun:stun.l.google.com:19302"]}]

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_stream_content_webrtc"):
                result = await self.ipfs_model.async_stream_content_webrtc(
                    cid=request.cid,
                    listen_address=request.address,
                    port=request.port,
                    quality=request.quality,
                    ice_servers=ice_servers,
                    enable_benchmark=request.benchmark,
                    # Advanced buffering parameters
                    buffer_size=request.buffer_size,
                    prefetch_threshold=request.prefetch_threshold,
                    use_progressive_loading=request.use_progressive_loading,
                )
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(
                    lambda: self.ipfs_model.stream_content_webrtc(
                        cid=request.cid,
                        listen_address=request.address,
                        port=request.port,
                        quality=request.quality,
                        ice_servers=ice_servers,
                        enable_benchmark=request.benchmark,
                        # Advanced buffering parameters
                        buffer_size=request.buffer_size,
                        prefetch_threshold=request.prefetch_threshold,
                        use_progressive_loading=request.use_progressive_loading,
                    )
                )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                if "dependencies" in result:
                    error_msg = "WebRTC dependencies not available"
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Track the streaming server for cleanup
            server_id = result.get("server_id")
            if server_id:
                self.active_streaming_servers[server_id] = {
                    "cid": request.cid,
                    "started_at": time.time(),
                    "address": request.address,
                    "port": request.port,
                    "url": result.get("url"),
                }
                logger.info(f"Tracking streaming server {server_id} for cleanup")

            return result

        except Exception as e:
            logger.error(f"Error streaming content: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )

    async def stop_streaming(self, server_id: str) -> Dict[str, Any]:
        """
        Stop WebRTC streaming.

        Args:
            server_id: ID of the WebRTC streaming server

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Stopping WebRTC streaming for server ID: {server_id}")

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_stop_webrtc_streaming"):
                result = await self.ipfs_model.async_stop_webrtc_streaming(server_id=server_id)
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(
                    lambda: self.ipfs_model.stop_webrtc_streaming(server_id=server_id)
                )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Remove from active servers tracking
            if server_id in self.active_streaming_servers:
                logger.info(f"Removing server {server_id} from tracking")
                del self.active_streaming_servers[server_id]

            return result

        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            # Even in case of errors, try to remove from tracking to avoid leaks
            if server_id in self.active_streaming_servers:
                logger.info(f"Removing server {server_id} from tracking despite error")
                del self.active_streaming_servers[server_id]
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )

    async def list_connections(self) -> Dict[str, Any]:
        """
        List active WebRTC connections.

        Returns:
            Dictionary with connection list
        """
        logger.debug("Listing WebRTC connections")

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_list_webrtc_connections"):
                result = await self.ipfs_model.async_list_webrtc_connections()
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(self.ipfs_model.list_webrtc_connections)

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Update connection tracking
            connections = result.get("connections", [])
            if connections:
                # Update our tracking dict with active connections
                current_connection_ids = set()
                for connection in connections:
                    connection_id = connection.get("id")
                    if connection_id:
                        current_connection_ids.add(connection_id)
                        if connection_id not in self.active_connections:
                            # Add to tracking if not already tracked
                            self.active_connections[connection_id] = {
                                "added_at": time.time(),
                                "server_id": connection.get("server_id"),
                                "peer_id": connection.get("peer_id"),
                            }

                # Remove stale connections from tracking
                stale_connections = set(self.active_connections.keys()) - current_connection_ids
                for stale_id in stale_connections:
                    logger.info(f"Removing stale connection {stale_id} from tracking")
                    del self.active_connections[stale_id]

                logger.debug(f"Tracking {len(self.active_connections)} active connections")

            return result

        except Exception as e:
            logger.error(f"Error listing connections: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )

    async def get_connection_stats(self, connection_id: str) -> Dict[str, Any]:
        """
        Get statistics for a WebRTC connection.

        Args:
            connection_id: ID of the WebRTC connection

        Returns:
            Dictionary with connection statistics
        """
        logger.debug(f"Getting stats for WebRTC connection ID: {connection_id}")

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_get_webrtc_connection_stats"):
                result = await self.ipfs_model.async_get_webrtc_connection_stats(
                    connection_id=connection_id
                )
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(
                    lambda: self.ipfs_model.get_webrtc_connection_stats(connection_id=connection_id)
                )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")

                # Clean up tracking if connection no longer exists
                if "not found" in error_msg.lower() and connection_id in self.active_connections:
                    logger.info(f"Removing non-existent connection {connection_id} from tracking")
                    del self.active_connections[connection_id]

                mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Update our tracking with latest stats
            stats = result.get("stats", {})
            if stats and connection_id in self.active_connections:
                # Only store essential stats to avoid memory bloat
                self.active_connections[connection_id]["last_stats_update"] = time.time()

                # Store key metrics for monitoring
                if "bandwidth" in stats:
                    self.active_connections[connection_id]["bandwidth"] = stats["bandwidth"]
                if "quality_metrics" in stats:
                    self.active_connections[connection_id]["quality_metrics"] = stats[
                        "quality_metrics"
                    ]
                if "latency" in stats:
                    self.active_connections[connection_id]["latency"] = stats["latency"]

                logger.debug(f"Updated tracking stats for connection {connection_id}")
            elif connection_id not in self.active_connections:
                # Connection exists but not in our tracking - add it
                self.active_connections[connection_id] = {
                    "added_at": time.time(),
                    "last_stats_update": time.time(),
                }
                logger.info(f"Added previously unknown connection {connection_id} to tracking")

            return result

        except Exception as e:
            logger.error(f"Error getting connection stats: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )

    async def close_connection(self, connection_id: str) -> Dict[str, Any]:
        """
        Close a WebRTC connection.

        Args:
            connection_id: ID of the WebRTC connection

        Returns:
            Dictionary with operation results
        """
        logger.debug(f"Closing WebRTC connection ID: {connection_id}")

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_close_webrtc_connection"):
                result = await self.ipfs_model.async_close_webrtc_connection(
                    connection_id=connection_id
                )
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(
                    lambda: self.ipfs_model.close_webrtc_connection(connection_id=connection_id)
                )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Remove from active connections tracking
            if connection_id in self.active_connections:
                logger.info(f"Removing connection {connection_id} from tracking")
                del self.active_connections[connection_id]

            return result

        except Exception as e:
            logger.error(f"Error closing connection: {e}")
            # Even in case of errors, try to remove from tracking to avoid leaks
            if connection_id in self.active_connections:
                logger.info(f"Removing connection {connection_id} from tracking despite error")
                del self.active_connections[connection_id]
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )

    async def close_all_connections(self) -> Dict[str, Any]:
        """
        Close all WebRTC connections.

        Returns:
            Dictionary with operation results
        """
        logger.debug("Closing all WebRTC connections")

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_close_all_webrtc_connections"):
                result = await self.ipfs_model.async_close_all_webrtc_connections()
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(
                    self.ipfs_model.close_all_webrtc_connections
                )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Clear all connection tracking
            count = len(self.active_connections)
            if count > 0:
                logger.info(f"Clearing tracking for {count} connections")
                self.active_connections.clear()

            return result

        except Exception as e:
            logger.error(f"Error closing all connections: {e}")
            # Even in case of errors, clear tracking to avoid leaks
            self.active_connections.clear()
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )

    async def set_quality(self, request: QualityRequest) -> Dict[str, Any]:
        """
        Change streaming quality for a WebRTC connection.

        Args:
            request: Quality request with connection ID and quality preset

        Returns:
            Dictionary with operation results
        """
        logger.debug(
            f"Setting quality for connection {request.connection_id} to: {request.quality}"
        )

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_set_webrtc_quality"):
                result = await self.ipfs_model.async_set_webrtc_quality(
                    connection_id=request.connection_id, quality=request.quality
                )
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(
                    lambda: self.ipfs_model.set_webrtc_quality(
                        connection_id=request.connection_id, quality=request.quality
                    )
                )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                mcp_error_handling.raise_http_exception(
        code="CONTENT_NOT_FOUND",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Update connection tracking with new quality setting
            if request.connection_id in self.active_connections:
                self.active_connections[request.connection_id]["quality"] = request.quality
                self.active_connections[request.connection_id]["quality_updated_at"] = time.time()
                logger.debug(f"Updated quality tracking for connection {request.connection_id}")
            else:
                # Connection not in tracking yet, add it
                self.active_connections[request.connection_id] = {
                    "added_at": time.time(),
                    "quality": request.quality,
                    "quality_updated_at": time.time(),
                }
                logger.debug(f"Added quality tracking for connection {request.connection_id}")

            return result

        except Exception as e:
            logger.error(f"Error setting quality: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )

    async def get_resources_endpoint(self) -> Dict[str, Any]:
        """
        Get statistics about tracked WebRTC resources.

        Returns:
            Dictionary with resource usage and tracking information
        """
        logger.debug("Getting WebRTC resource statistics")

        try:
            # Get the resource stats
            stats = self.get_resource_stats()

            # Add success flag for API consistency
            stats["success"] = True
            stats["operation_id"] = f"resource_stats_{time.time()}"

            return stats
        except Exception as e:
            logger.error(f"Error getting resource statistics: {e}")
            return {
                "success": False,
                "error": str(e),
                "servers": {"count": 0, "servers": []},
                "connections": {"count": 0, "connections": []},
                "timestamp": time.time(),
                "is_shutting_down": self.is_shutting_down,
                "cleanup_task_active": False,
            }

    async def run_benchmark(self, request: BenchmarkRequest) -> Dict[str, Any]:
        """
        Run a WebRTC streaming benchmark.

        Args:
            request: Benchmark request with CID and options

        Returns:
            Dictionary with benchmark results
        """
        logger.debug(f"Running WebRTC benchmark for CID: {request.cid}")

        try:
            # Use async version if available
            if hasattr(self.ipfs_model, "async_run_webrtc_benchmark"):
                result = await self.ipfs_model.async_run_webrtc_benchmark(
                    cid=request.cid,
                    duration_seconds=request.duration,
                    report_format=request.format,
                    output_dir=request.output_dir,
                )
            else:
                # Fall back to synchronous version in a background thread
                result = await anyio.to_thread.run_sync(
                    lambda: self.ipfs_model.run_webrtc_benchmark(
                        cid=request.cid,
                        duration_seconds=request.duration,
                        report_format=request.format,
                        output_dir=request.output_dir,
                    )
                )

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=error_msg,
        endpoint="/api/v0/webrtc",
        doc_category="api"
    )

            # Track benchmarks for potential cleanup
            benchmark_id = result.get("benchmark_id")
            if benchmark_id:
                # Track in streaming servers since benchmarks typically create streams
                self.active_streaming_servers[benchmark_id] = {
                    "cid": request.cid,
                    "started_at": time.time(),
                    "is_benchmark": True,
                    "duration": request.duration,
                    "report_path": result.get("report_path"),
                }
                logger.info(f"Tracking benchmark {benchmark_id} for cleanup")

                # Schedule cleanup after benchmark completes
                async def delayed_cleanup():
                    # Add a buffer of 5 seconds to the benchmark duration
                    await anyio.sleep(request.duration + 5)
                    if benchmark_id in self.active_streaming_servers:
                        logger.info(f"Cleaning up benchmark resources for {benchmark_id}")
                        try:
                            # Use async version if available
                            if hasattr(self.ipfs_model, "async_stop_webrtc_streaming"):
                                cleanup_result = await self.ipfs_model.async_stop_webrtc_streaming(
                                    server_id=benchmark_id
                                )
                            else:
                                # Fall back to synchronous version in a background thread
                                cleanup_result = await anyio.to_thread.run_sync(
                                    lambda: self.ipfs_model.stop_webrtc_streaming(
                                        server_id=benchmark_id
                                    )
                                )

                            if cleanup_result and not cleanup_result.get("success", False):
                                logger.warning(
                                    f"Cleanup after benchmark failed: {cleanup_result.get('error', 'Unknown error')}"
                                )
                        except Exception as e:
                            logger.error(f"Error during benchmark cleanup: {e}")
                        finally:
                            # Remove from tracking regardless of cleanup result
                            if benchmark_id in self.active_streaming_servers:
                                del self.active_streaming_servers[benchmark_id]

                # Schedule the cleanup
                anyio.create_task(delayed_cleanup())

            return result

        except Exception as e:
            logger.error(f"Error running benchmark: {e}")
            mcp_error_handling.raise_http_exception(
                code="INTERNAL_ERROR",
                message_override=str(e),
                endpoint="/api/v0/webrtc",
                doc_category="api"
            )
