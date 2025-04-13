"""
WebRTC Dashboard Controller for the MCP Server with AnyIO support.

This module provides API endpoints for the WebRTC monitoring dashboard,
along with the dashboard UI itself. This implementation uses AnyIO for
backend-agnostic async operations.
"""

import os
import json
import time
import uuid
import anyio
import sniffio
import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Set up logging
logger = logging.getLogger(__name__)

# Import WebRTC monitor if available
try:
    from fixes.webrtc_monitor import WebRTCMonitor
    WEBRTC_MONITOR_AVAILABLE = True
except ImportError:
    WEBRTC_MONITOR_AVAILABLE = False
    
# Try to import enhanced WebRTC monitor integration
try:
    from fixes.webrtc_anyio_monitor_integration import WebRTCMonitor as EnhancedWebRTCMonitor
    ENHANCED_MONITOR_AVAILABLE = True
except ImportError:
    ENHANCED_MONITOR_AVAILABLE = False


class WebRTCDashboardControllerAnyIO:
    """
    Controller for the WebRTC monitoring dashboard using AnyIO.
    
    This implementation uses AnyIO for backend-agnostic async operations,
    supporting both asyncio and trio.
    """
    
    def __init__(self, webrtc_model=None, webrtc_monitor=None):
        """Initialize the WebRTC dashboard controller.
        
        Args:
            webrtc_model: The IPFS model instance with WebRTC methods
            webrtc_monitor: Optional WebRTCMonitor instance
        """
        self.webrtc_model = webrtc_model
        self.webrtc_monitor = webrtc_monitor
        
        # Check for enhanced monitor features
        self.has_enhanced_monitor = ENHANCED_MONITOR_AVAILABLE and hasattr(self.webrtc_monitor, 'get_summary')
        if self.has_enhanced_monitor:
            logger.info("Enhanced WebRTC monitor detected")
        else:
            logger.info("Using standard WebRTC monitor")
            
        self.static_dir = self._get_static_dir()
        
    @staticmethod
    def get_backend():
        """Get the current async backend being used."""
        try:
            return sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            return None
    
    def _get_static_dir(self) -> str:
        """Get the path to the static directory."""
        # Try to find the static directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
        static_dir = os.path.join(root_dir, "static")
        
        # Create the directory if it doesn't exist
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)
            
        return static_dir
    
    def register_routes(self, router: APIRouter):
        """Register the WebRTC dashboard routes with the API router.
        
        Args:
            router: The FastAPI router to register routes with
        """
        # Mount static files
        try:
            router.app.mount("/static", StaticFiles(directory=self.static_dir), name="static")
        except (AttributeError, RuntimeError):
            # Already mounted or not a FastAPI app
            pass
        
        # Dashboard UI route
        @router.get("/dashboard", response_class=HTMLResponse)
        async def get_dashboard():
            dashboard_path = os.path.join(self.static_dir, "webrtc_dashboard.html")
            
            if os.path.exists(dashboard_path):
                async with await anyio.open_file(dashboard_path, "r") as f:
                    content = await f.read()
                    return content
            else:
                return "<html><body><h1>WebRTC Dashboard</h1><p>Dashboard HTML file not found.</p></body></html>"
                
        # Monitor summary endpoint (only available with enhanced monitor)
        @router.get("/summary", response_class=JSONResponse)
        async def get_monitor_summary():
            if not self.webrtc_monitor:
                return {
                    "success": False,
                    "error": "WebRTC monitor not available",
                    "timestamp": time.time()
                }
                
            if not self.has_enhanced_monitor:
                return {
                    "success": False,
                    "error": "Enhanced WebRTC monitor not available",
                    "backend": self.get_backend(),
                    "timestamp": time.time()
                }
                
            try:
                # Check if method is async
                if hasattr(self.webrtc_monitor.get_summary, "__await__"):
                    summary_data = await self.webrtc_monitor.get_summary()
                else:
                    summary_data = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_monitor.get_summary()
                    )
                    
                return {
                    "success": True,
                    "summary": summary_data,
                    "backend": self.get_backend(),
                    "timestamp": time.time()
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error getting monitor summary: {str(e)}",
                    "backend": self.get_backend(),
                    "timestamp": time.time()
                }
        
        # WebRTC connections endpoint
        @router.get("/connections", response_class=JSONResponse)
        async def get_connections():
            if not self.webrtc_monitor:
                return {"connections": [], "timestamp": time.time()}
            
            # Use enhanced monitor features if available
            if self.has_enhanced_monitor:
                # Use enhanced monitor's get_connection_stats method
                try:
                    # Check if method is async
                    if hasattr(self.webrtc_monitor.get_connection_stats, "__await__"):
                        return await self.webrtc_monitor.get_connection_stats()
                    else:
                        return await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.get_connection_stats()
                        )
                except Exception as e:
                    logger.error(f"Error using enhanced monitor: {e}")
                    # Fall back to standard access method
            
            # Standard monitor access
            # Check if the connections property access might be blocking
            if hasattr(self.webrtc_monitor, "__await__"):
                connections_data = await self.webrtc_monitor.connections
            else:
                connections_data = await anyio.to_thread.run_sync(
                    lambda: self.webrtc_monitor.connections
                )
                
            connections = []
            for conn_id, conn_data in connections_data.items():
                # Convert to consistent format
                if isinstance(conn_data, dict):
                    # Simple dictionary format
                    connections.append({
                        "connection_id": conn_id,
                        "content_cid": conn_data.get("content_cid", "N/A"),
                        "status": conn_data.get("status", "unknown"),
                        "start_time": conn_data.get("start_time"),
                        "end_time": conn_data.get("end_time"),
                        "quality": conn_data.get("quality", 80),
                        "peer_id": conn_data.get("peer_id", "N/A")
                    })
                else:
                    # Possibly a WebRTCConnectionStats object, call to_dict if available
                    if hasattr(conn_data, "to_dict"):
                        connections.append(conn_data.to_dict())
                    else:
                        # Fallback for unknown format
                        connections.append({
                            "connection_id": conn_id,
                            "status": "unknown_format"
                        })
                
            return {
                "connections": connections,
                "count": len(connections),
                "timestamp": time.time()
            }
        
        # WebRTC operations endpoint
        @router.get("/operations", response_class=JSONResponse)
        async def get_operations():
            if not self.webrtc_monitor:
                return {"operations": [], "timestamp": time.time()}
            
            # Use enhanced monitor features if available
            if self.has_enhanced_monitor:
                # Use enhanced monitor's get_active_operations method
                try:
                    # Check if method is async
                    if hasattr(self.webrtc_monitor.get_active_operations, "__await__"):
                        return await self.webrtc_monitor.get_active_operations()
                    else:
                        return await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.get_active_operations()
                        )
                except Exception as e:
                    logger.error(f"Error using enhanced monitor for operations: {e}")
                    # Fall back to standard access method
            
            # Standard monitor access
            # Check if the operations property access might be blocking
            if hasattr(self.webrtc_monitor, "__await__"):
                operations_data = await self.webrtc_monitor.operations
            else:
                operations_data = await anyio.to_thread.run_sync(
                    lambda: self.webrtc_monitor.operations
                )
                
            # Convert operations data to list if it's a dictionary
            operations_list = []
            if isinstance(operations_data, dict):
                operations_list = list(operations_data.values())
            elif isinstance(operations_data, list):
                operations_list = operations_data
                
            operations = []
            for op_data in operations_list:
                operations.append({
                    "operation": op_data.get("operation_type", op_data.get("operation", "N/A")),
                    "operation_id": op_data.get("operation_id", "unknown"),
                    "connection_id": op_data.get("connection_id", op_data.get("details", {}).get("connection_id", "N/A")),
                    "timestamp": op_data.get("timestamp", op_data.get("start_time")),
                    "success": op_data.get("success", False),
                    "error": op_data.get("error", op_data.get("result", {}).get("error")),
                    "start_time": op_data.get("start_time"),
                    "end_time": op_data.get("end_time"),
                    "status": op_data.get("status", "unknown"),
                    "duration": op_data.get("duration")
                })
                
            return {
                "operations": operations,
                "count": len(operations),
                "timestamp": time.time()
            }
        
        # WebRTC tasks endpoint
        @router.get("/tasks", response_class=JSONResponse)
        async def get_tasks():
            if not self.webrtc_monitor:
                return {"tasks": [], "timestamp": time.time()}
            
            # Use enhanced monitor features if available
            if self.has_enhanced_monitor:
                # Use enhanced monitor's get_pending_tasks method
                try:
                    # Check if method is async
                    if hasattr(self.webrtc_monitor.get_pending_tasks, "__await__"):
                        return await self.webrtc_monitor.get_pending_tasks()
                    else:
                        return await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.get_pending_tasks()
                        )
                except Exception as e:
                    logger.error(f"Error using enhanced monitor for tasks: {e}")
                    # Fall back to standard access method
            
            # Check if task_tracker attribute exists    
            if not hasattr(self.webrtc_monitor, "task_tracker"):
                return {"tasks": [], "count": 0, "timestamp": time.time()}
                
            # Check if task access might be blocking
            task_data = {}
            try:
                if hasattr(self.webrtc_monitor.task_tracker, "__await__"):
                    tasks_data = await self.webrtc_monitor.task_tracker.tasks
                else:
                    tasks_data = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_monitor.task_tracker.tasks
                    )
                    
                task_data = tasks_data
            except AttributeError:
                # Handle case where tasks is a property not a method
                if hasattr(self.webrtc_monitor.task_tracker, "tasks"):
                    task_data = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_monitor.task_tracker.tasks
                    )
                    
            # Process task data which might be in different formats
            formatted_tasks = []
            
            # Check if it's a dictionary mapping connection IDs to tasks
            if isinstance(task_data, dict):
                # If values are lists, it's connection -> [task_ids]
                for conn_id, tasks in task_data.items():
                    if isinstance(tasks, list):
                        for task_id in tasks:
                            formatted_tasks.append({
                                "task_id": task_id,
                                "connection_id": conn_id,
                                "name": f"Task for {conn_id}",
                                "created_at": time.time(),  # Approximate
                                "status": "pending"
                            })
                    # If values are dicts, it's task_id -> task_data
                    else:
                        for task_id, task_info in tasks.items():
                            formatted_tasks.append({
                                "task_id": task_id,
                                "name": task_info.get("name", "Unknown task"),
                                "created_at": task_info.get("created_at"),
                                "completed": task_info.get("completed", False),
                                "completed_at": task_info.get("completed_at"),
                                "error": task_info.get("error"),
                                "connection_id": conn_id
                            })
            # Check if it's a direct mapping of task_id -> task_data
            elif isinstance(task_data, dict):
                for task_id, task_info in task_data.items():
                    formatted_tasks.append({
                        "task_id": task_id,
                        "name": task_info.get("name", "Unknown task"),
                        "created_at": task_info.get("created_at"),
                        "completed": task_info.get("completed", False),
                        "completed_at": task_info.get("completed_at"),
                        "error": task_info.get("error")
                    })
                    
            return {
                "tasks": formatted_tasks,
                "count": len(formatted_tasks),
                "timestamp": time.time()
            }
        
        # Test connection endpoint
        @router.post("/test_connection", response_class=JSONResponse)
        async def test_connection():
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}
                
            try:
                # Generate a connection ID
                connection_id = str(uuid.uuid4())
                
                # Record connection start if monitor available
                if self.webrtc_monitor:
                    # Check if record_connection is async
                    if hasattr(self.webrtc_monitor.record_connection, "__await__"):
                        await self.webrtc_monitor.record_connection(
                            connection_id=connection_id,
                            content_cid="test",
                            status="active"
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_connection(
                                connection_id=connection_id,
                                content_cid="test",
                                status="active"
                            )
                        )
                    
                    # Check if record_operation is async
                    if hasattr(self.webrtc_monitor.record_operation, "__await__"):
                        await self.webrtc_monitor.record_operation(
                            operation="test_connection",
                            connection_id=connection_id,
                            success=True
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_operation(
                                operation="test_connection",
                                connection_id=connection_id,
                                success=True
                            )
                        )
                
                return {
                    "success": True,
                    "connection_id": connection_id,
                    "message": "Test connection successful"
                }
            except Exception as e:
                if self.webrtc_monitor:
                    # Check if record_operation is async
                    if hasattr(self.webrtc_monitor.record_operation, "__await__"):
                        await self.webrtc_monitor.record_operation(
                            operation="test_connection",
                            connection_id="N/A",
                            success=False,
                            error=str(e)
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_operation(
                                operation="test_connection",
                                connection_id="N/A",
                                success=False,
                                error=str(e)
                            )
                        )
                
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Stream test content endpoint
        @router.post("/stream_test_content", response_class=JSONResponse)
        async def stream_test_content():
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}
                
            try:
                # Use test CID
                test_cid = "QmTest123"
                
                # Check if stream_content_webrtc is async
                if hasattr(self.webrtc_model.stream_content_webrtc, "__await__"):
                    # Method is already async
                    result = await self.webrtc_model.stream_content_webrtc(test_cid)
                else:
                    # Method is sync, run in a thread
                    result = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_model.stream_content_webrtc(test_cid)
                    )
                
                if result.get("success"):
                    return {
                        "success": True,
                        "connection_id": result.get("connection_id", "unknown"),
                        "message": "Streaming started successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    # Check if record_operation is async
                    if hasattr(self.webrtc_monitor.record_operation, "__await__"):
                        await self.webrtc_monitor.record_operation(
                            operation="stream_test_content",
                            connection_id="N/A",
                            success=False,
                            error=str(e)
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_operation(
                                operation="stream_test_content",
                                connection_id="N/A",
                                success=False,
                                error=str(e)
                            )
                        )
                
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Stream content endpoint
        @router.post("/stream", response_class=JSONResponse)
        async def stream_content(request: Request):
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}
                
            try:
                # Get request body
                body = await request.json()
                content_cid = body.get("cid")
                quality = body.get("quality", 80)
                
                if not content_cid:
                    return {"success": False, "error": "Content CID is required"}
                
                # Check if stream_content_webrtc is async
                if hasattr(self.webrtc_model.stream_content_webrtc, "__await__"):
                    # Method is already async
                    result = await self.webrtc_model.stream_content_webrtc(content_cid, quality=quality)
                else:
                    # Method is sync, run in a thread
                    result = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_model.stream_content_webrtc(content_cid, quality=quality)
                    )
                
                if result.get("success"):
                    return {
                        "success": True,
                        "connection_id": result.get("connection_id", "unknown"),
                        "message": "Streaming started successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    # Check if record_operation is async
                    if hasattr(self.webrtc_monitor.record_operation, "__await__"):
                        await self.webrtc_monitor.record_operation(
                            operation="stream_content",
                            connection_id="N/A",
                            success=False,
                            error=str(e)
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_operation(
                                operation="stream_content",
                                connection_id="N/A",
                                success=False,
                                error=str(e)
                            )
                        )
                
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Close connection endpoint
        @router.post("/close/{connection_id}", response_class=JSONResponse)
        async def close_connection(connection_id: str):
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}
                
            try:
                # Check if close_webrtc_connection is async
                if hasattr(self.webrtc_model.close_webrtc_connection, "__await__"):
                    # Method is already async
                    result = await self.webrtc_model.close_webrtc_connection(connection_id)
                else:
                    # Method is sync, run in a thread
                    result = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_model.close_webrtc_connection(connection_id)
                    )
                
                if result.get("success"):
                    return {
                        "success": True,
                        "message": f"Connection {connection_id} closed successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    # Check if record_operation is async
                    if hasattr(self.webrtc_monitor.record_operation, "__await__"):
                        await self.webrtc_monitor.record_operation(
                            operation="close_connection",
                            connection_id=connection_id,
                            success=False,
                            error=str(e)
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_operation(
                                operation="close_connection",
                                connection_id=connection_id,
                                success=False,
                                error=str(e)
                            )
                        )
                
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Close all connections endpoint
        @router.post("/close_all", response_class=JSONResponse)
        async def close_all_connections():
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}
                
            try:
                # Check if close_all_webrtc_connections is async
                if hasattr(self.webrtc_model.close_all_webrtc_connections, "__await__"):
                    # Method is already async
                    result = await self.webrtc_model.close_all_webrtc_connections()
                else:
                    # Method is sync, run in a thread
                    result = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_model.close_all_webrtc_connections()
                    )
                
                if result.get("success"):
                    return {
                        "success": True,
                        "message": "All connections closed successfully"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    # Check if record_operation is async
                    if hasattr(self.webrtc_monitor.record_operation, "__await__"):
                        await self.webrtc_monitor.record_operation(
                            operation="close_all_connections",
                            connection_id="N/A",
                            success=False,
                            error=str(e)
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_operation(
                                operation="close_all_connections",
                                connection_id="N/A",
                                success=False,
                                error=str(e)
                            )
                        )
                
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Set WebRTC quality endpoint
        @router.post("/quality/{connection_id}", response_class=JSONResponse)
        async def set_webrtc_quality(connection_id: str, request: Request):
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}
                
            try:
                # Get request body
                body = await request.json()
                quality = body.get("quality", 80)
                
                # Check if set_webrtc_quality is async
                if hasattr(self.webrtc_model.set_webrtc_quality, "__await__"):
                    # Method is already async
                    result = await self.webrtc_model.set_webrtc_quality(connection_id, quality)
                else:
                    # Method is sync, run in a thread
                    result = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_model.set_webrtc_quality(connection_id, quality)
                    )
                
                if result.get("success"):
                    return {
                        "success": True,
                        "message": f"Quality set to {quality} for connection {connection_id}"
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error")
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    # Check if record_operation is async
                    if hasattr(self.webrtc_monitor.record_operation, "__await__"):
                        await self.webrtc_monitor.record_operation(
                            operation="set_quality",
                            connection_id=connection_id,
                            success=False,
                            error=str(e)
                        )
                    else:
                        await anyio.to_thread.run_sync(
                            lambda: self.webrtc_monitor.record_operation(
                                operation="set_quality",
                                connection_id=connection_id,
                                success=False,
                                error=str(e)
                            )
                        )
                
                return {
                    "success": False,
                    "error": str(e)
                }


def create_webrtc_dashboard_router_anyio(
    webrtc_model=None, 
    webrtc_monitor=None,
    use_enhanced_monitor=True
) -> APIRouter:
    """Create a FastAPI router with WebRTC dashboard endpoints using AnyIO.
    
    Args:
        webrtc_model: The IPFS model instance with WebRTC methods
        webrtc_monitor: Optional WebRTCMonitor instance
        use_enhanced_monitor: Whether to use the enhanced monitor if available
        
    Returns:
        FastAPI router with WebRTC dashboard endpoints
    """
    router = APIRouter(prefix="/api/v0/webrtc", tags=["webrtc"])
    
    # Check for enhanced monitor if requested
    enhanced_monitor = None
    if use_enhanced_monitor and ENHANCED_MONITOR_AVAILABLE and webrtc_monitor is None:
        try:
            # Import and create enhanced monitor
            from fixes.webrtc_anyio_monitor_integration import WebRTCMonitor as EnhancedMonitor
            enhanced_monitor = EnhancedMonitor()
            logger.info("Created enhanced WebRTC monitor")
        except ImportError:
            logger.warning("Enhanced WebRTC monitor not available")
    
    # Use the provided monitor, the enhanced monitor, or none
    monitor_to_use = webrtc_monitor or enhanced_monitor
    
    # Create and register controller
    controller = WebRTCDashboardControllerAnyIO(
        webrtc_model=webrtc_model,
        webrtc_monitor=monitor_to_use
    )
    controller.register_routes(router)
    
    return router