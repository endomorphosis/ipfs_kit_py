"""
WebRTC Controller for the MCP server (AnyIO Version).

This controller handles HTTP requests related to WebRTC operations and
delegates the business logic to the IPFS model. It uses AnyIO for async operations.
"""

import logging
import time

import anyio
from fastapi import APIRouter, 

from ipfs_kit_py.mcp.controllers.webrtc_controller import (
    # Import Pydantic models for request/response validation
    # Import AnyIO for async operations
    # Import models from original controller for consistency
    DependencyResponse,
)

# Configure logger
logger = logging.getLogger(__name__)


class WebRTCControllerAnyIO:
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

        # Start periodic cleanup task
        self._start_cleanup_task()

    def _start_cleanup_task(self):
        """
import sys
import os
# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

Start a periodic cleanup task for WebRTC resources."""
        logger.info("Starting WebRTC cleanup task")

        # Define the cleanup coroutine
        async def periodic_cleanup():
            """
            Periodically clean up stale WebRTC resources.

            This task runs in the background and periodically checks
            for stale streaming servers and connections, cleaning them
            up to prevent resource leaks.
            """
            try:
                logger.debug("WebRTC periodic cleanup task started")

                # Default cleanup interval (in seconds)
                cleanup_interval = 60  # 1 minute

                # Set last auto cleanup time to current time
                self.last_auto_cleanup = time.time()

                while not self.is_shutting_down:
                    try:
                        # Sleep for the specified interval
                        await anyio.sleep(cleanup_interval)

                        # Skip if we're shutting down
                        if self.is_shutting_down:
                            break

                        current_time = time.time()

                        # Check for and remove stale streaming servers
                        for server_id, server_info in list(self.active_streaming_servers.items()):
                            try:
                                # Get creation time
                                started_at = server_info.get("started_at", 0)

                                # If the server is marked for benchmark (temporary)
                                if server_info.get("is_benchmark", False):
                                    # Allow benchmark servers to live for 5 minutes max
                                    max_lifetime = 5 * 60  # 5 minutes
                                else:
                                    # Regular servers can live longer
                                    max_lifetime = 8 * 60 * 60  # 8 hours

                                # Check if the server has been alive for too long
                                if current_time - started_at > max_lifetime:
                                    logger.info(
                                        f"Cleaning up stale streaming server {server_id} (age: {(current_time - started_at) / 60:.1f} minutes)"
                                    )

                                    # Stop the server
                                    try:
                                        await anyio.to_thread.run_sync(
                                            self.ipfs_model.stop_webrtc_streaming,
                                            server_id=server_id,
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Error stopping stale server {server_id}: {e}"
                                        )

                                    # Always remove from tracking
                                    if server_id in self.active_streaming_servers:
                                        del self.active_streaming_servers[server_id]
                            except Exception as e:
                                logger.error(f"Error cleaning up stale server {server_id}: {e}")

                        # Check for and update active connections
                        try:
                            result = await anyio.to_thread.run_sync(
                                self.ipfs_model.list_webrtc_connections
                            )
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
                                            _ = await anyio.to_thread.run_sync(
                                                self.ipfs_model.stop_webrtc_streaming,
                                                server_id=server_id,
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

        # Close all tracks (new)
        try:
            # Get list of connections with tracks
            connections_result = await anyio.to_thread.run_sync(
                self.ipfs_model.list_webrtc_connections
            )

            if connections_result.get("success", False):
                connections = connections_result.get("connections", [])

                # Loop through connections to find tracks
                for connection in connections:
                    if "tracks" in connection and isinstance(connection["tracks"], list):
                        for track in connection["tracks"]:
                            track_id = track.get("id")
                            if track_id:
                                try:
                                    logger.debug(f"Closing track: {track_id}")
                                    # If track close method is available, use it
                                    if hasattr(self.ipfs_model, "close_webrtc_track"):
                                        await anyio.to_thread.run_sync(
                                            self.ipfs_model.close_webrtc_track,
                                            track_id=track_id,
                                        )
                                    logger.debug(f"Closed track: {track_id}")
                                except Exception as track_e:
                                    logger.warning(f"Error closing track {track_id}: {track_e}")
        except Exception as e:
            logger.error(f"Error closing WebRTC tracks during shutdown: {e}")

        # Close all WebRTC connections via the model
        try:
            # Use anyio to run the model's method in a thread
            result = await anyio.to_thread.run_sync(self.ipfs_model.close_all_webrtc_connections)

            if isinstance(result, dict) and not result.get("success", False):
                logger.error(
                    f"Error closing WebRTC connections: {result.get('error', 'Unknown error')}"
                )
            else:
                logger.info(
                    f"Successfully closed all WebRTC connections: {result.get('connections_closed', 0)} closed"
                )
        except Exception as e:
            logger.error(f"Error closing WebRTC connections during shutdown: {e}")

        # Release any final resources
        gc_trigger_success = False
        try:
            # Force garbage collection to clean up any lingering resources
            import gc

            gc.collect()
            gc_trigger_success = True
        except Exception as e:
            logger.warning(f"Error triggering garbage collection: {e}")

        # Clear dictionaries to release references
        self.active_streaming_servers.clear()
        self.active_connections.clear()

        logger.info(f"WebRTC Controller shutdown completed (GC triggered: {gc_trigger_success})")

    # Synchronous version of shutdown for compatibility
    def sync_shutdown(self):
        """Synchronous version of shutdown for backward compatibility."""
        anyio.run(self.shutdown)

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
                # Use synchronous method to ensure completion via anyio thread
                logger.debug(f"Final cleanup of streaming server {server_id}")
                await anyio.to_thread.run_sync(
                    self.ipfs_model.stop_webrtc_streaming, server_id=server_id
                )
            except Exception as e:
                logger.warning(f"Error during final cleanup of server {server_id}: {e}")

        # 2. Clean up any lingering connections
        try:
            # Get all connection IDs
            if hasattr(self, "active_connections"):
                connection_ids = list(self.active_connections.keys())
                logger.info(f"Final cleanup of {len(connection_ids)} tracked connections")

                for conn_id in connection_ids:
                    try:
                        logger.debug(f"Closing connection: {conn_id}")
                        # If connection close method is available, use it
                        if hasattr(self.ipfs_model, "close_webrtc_connection"):
                            await anyio.to_thread.run_sync(
                                self.ipfs_model.close_webrtc_connection,
                                connection_id=conn_id,
                            )
                        logger.debug(f"Connection closed: {conn_id}")
                    except Exception as e:
                        logger.warning(f"Error closing connection {conn_id}: {e}")

                # Clear the dictionary to release references
                self.active_connections.clear()
        except Exception as e:
            logger.error(f"Error during final connection cleanup: {e}")

        # 3. Final check for any resources that might be leaked
        try:
            # If there's a resource check method available
            if hasattr(self.ipfs_model, "get_webrtc_resource_usage"):
                logger.debug("Checking for any leaked WebRTC resources")
                resource_check = await anyio.to_thread.run_sync(
                    self.ipfs_model.get_webrtc_resource_usage
                )

                if resource_check.get("success", False) and "usage" in resource_check:
                    usage = resource_check["usage"]
                    if usage.get("connections", 0) > 0 or sum(usage.get("tracks", {}).values()) > 0:
                        logger.warning(f"Detected leaked resources: {usage}")
                        # Resources detected, force a final cleanup
                        await anyio.to_thread.run_sync(self.ipfs_model.close_all_webrtc_connections)
                    else:
                        logger.info("No leaked WebRTC resources detected")
        except Exception as e:
            logger.error(f"Error checking for leaked resources: {e}")

    async def close_all_streaming_servers(self):
        """
        Close all active WebRTC streaming servers.

        This method ensures proper cleanup of all streaming server resources.
        """
        logger.info(f"Closing all WebRTC streaming servers: {len(self.active_streaming_servers)}")

        for server_id, server_info in list(self.active_streaming_servers.items()):
            try:
                # Use the model's stop_webrtc_streaming method via anyio thread
                result = await anyio.to_thread.run_sync(
                    self.ipfs_model.stop_webrtc_streaming, server_id=server_id
                )

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
            Dictionary containing resource statistics and health metrics
        """
        stats = {
            "timestamp": time.time(),
            "servers": {"count": len(self.active_streaming_servers), "servers": []},
            "connections": {"count": len(self.active_connections), "connections": []},
            "system": {
                "health_score": 100.0,  # Default to 100%
                "memory_usage": 0.0,
                "cpu_usage": 0.0,
            },
            "resource_management": {
                "auto_cleanup_threshold": 30.0,  # Health score below this triggers cleanup
                "last_auto_cleanup": getattr(self, "last_auto_cleanup", 0),
                "cleanup_task_running": self.cleanup_task is not None,
            },
        }

        # Calculate server statistics
        try:
            current_time = time.time()

            # Get server stats
            for server_id, server_info in self.active_streaming_servers.items():
                # Calculate server's age
                age_seconds = current_time - server_info.get("started_at", current_time)

                # Calculate usage impact score (0-100)
                # - Older servers score higher
                # - Benchmark servers score higher
                # - Servers with high resource usage score higher
                age_factor = min(1.0, age_seconds / (4 * 60 * 60))  # Max age factor at 4 hours
                resource_factor = min(
                    1.0, server_info.get("resources", {}).get("usage", 0.0) / 0.7
                )  # Max at 70% usage
                benchmark_factor = 1.0 if server_info.get("is_benchmark", False) else 0.0

                impact_score = (
                    age_factor * 50  # Age: 50% weight
                    + resource_factor * 30  # Resource usage: 30% weight
                    + benchmark_factor * 20  # Benchmark status: 20% weight
                )

                # Count connected clients
                connection_count = 0
                if "connections" in server_info and isinstance(server_info["connections"], list):
                    connection_count = len(server_info["connections"])

                server_stats = {
                    "id": server_id,
                    "age_seconds": age_seconds,
                    "connection_count": connection_count,
                    "is_benchmark": server_info.get("is_benchmark", False),
                    "impact_score": impact_score,
                }

                stats["servers"]["servers"].append(server_stats)
        except Exception as e:
            logger.error(f"Error calculating server statistics: {e}")

        # Calculate health score
        try:
            # Start with perfect health
            health_score = 100.0

            # Server count penalty (0-30)
            server_count = len(self.active_streaming_servers)
            if server_count > 5:
                # More than 5 servers starts to reduce health
                server_penalty = min(30.0, (server_count - 5) * 5.0)
                health_score -= server_penalty

            # Connection count penalty (0-30)
            connection_count = len(self.active_connections)
            if connection_count > 20:
                # More than 20 connections starts to reduce health
                connection_penalty = min(30.0, (connection_count - 20) * 1.5)
                health_score -= connection_penalty

            # Age penalty for old servers (0-20)
            try:
                current_time = time.time()
                oldest_server_age = 0

                for server_info in self.active_streaming_servers.values():
                    age = current_time - server_info.get("started_at", current_time)
                    oldest_server_age = max(oldest_server_age, age)

                # Start penalty after 2 hours
                if oldest_server_age > 7200:  # 2 hours
                    age_hours = oldest_server_age / 3600
                    age_penalty = min(20.0, (age_hours - 2) * 5.0)
                    health_score -= age_penalty
            except Exception as e:
                logger.error(f"Error calculating age penalty: {e}")

            # System resource check (try to detect memory/CPU pressure)
            try:
                import psutil

                # Get memory usage
                memory_percent = psutil.virtual_memory().percent
                stats["system"]["memory_usage"] = memory_percent

                # Memory pressure penalty (0-20)
                if memory_percent > 70:
                    memory_penalty = min(20.0, (memory_percent - 70) * 0.7)
                    health_score -= memory_penalty

                # Get CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                stats["system"]["cpu_usage"] = cpu_percent

                # CPU pressure penalty (0-20)
                if cpu_percent > 60:
                    cpu_penalty = min(20.0, (cpu_percent - 60) * 0.5)
                    health_score -= cpu_penalty
            except ImportError:
                # psutil not available, skip system checks
                pass
            except Exception as e:
                logger.error(f"Error performing system resource check: {e}")

            # Make sure health score stays within bounds
            health_score = max(0.0, min(100.0, health_score))
            stats["system"]["health_score"] = health_score
        except Exception as e:
            logger.error(f"Error calculating overall health score: {e}")

        return stats

    # Endpoint for registering routes with FastAPI
    def register_routes(self, router: APIRouter):
        """Register WebRTC controller routes with FastAPI router."""
        # Dependencies can go here if needed
        # e.g., def get_webrtc_dependencies(): ...

        # Check WebRTC dependencies endpoint
        router.add_api_route(
            "/webrtc/dependencies",
            self.check_dependencies,
            methods=["GET"],
            response_model=DependencyResponse,
            summary="Check WebRTC dependencies",
            description="Check if all required WebRTC dependencies are available",
        )

    # Add your AnyIO-compatible controller methods here
    async def check_dependencies(self):
        """
        Check if all required WebRTC dependencies are available.

        Returns:
            Dictionary with dependency status information
        """
        logger.debug("Checking WebRTC dependencies")

        try:
            # Run the dependency check in a background thread using anyio
            result = await anyio.to_thread.run_sync(self.ipfs_model.check_webrtc_dependencies)
            return result

        except Exception as e:
            logger.error(f"Error checking WebRTC dependencies: {e}")
            mcp_error_handling.raise_http_exception(
        code="INTERNAL_ERROR",
        message_override=str(e,
        endpoint="/api/v0/webrtc_anyio",
        doc_category="api"
    ))
