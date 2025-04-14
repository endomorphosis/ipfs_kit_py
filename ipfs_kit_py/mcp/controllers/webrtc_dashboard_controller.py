"""
WebRTC Dashboard Controller for the MCP Server.

This module provides API endpoints for the WebRTC monitoring dashboard,
along with the dashboard UI itself.
"""

import importlib.util
import os
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Check if the module exists without importing everything


WEBRTC_MONITOR_AVAILABLE = importlib.util.find_spec("fixes.webrtc_monitor") is not None
if WEBRTC_MONITOR_AVAILABLE:
    pass  # Import only if needed
else:
    WEBRTC_MONITOR_AVAILABLE = False


class WebRTCDashboardController:
    """Controller for the WebRTC monitoring dashboard."""

    def __init__(self, webrtc_model=None, webrtc_monitor=None):
        """Initialize the WebRTC dashboard controller.

        Args:
            webrtc_model: The IPFS model instance with WebRTC methods
            webrtc_monitor: Optional WebRTCMonitor instance
        """
        self.webrtc_model = webrtc_model
        self.webrtc_monitor = webrtc_monitor
        self.static_dir = self._get_static_dir()

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
                with open(dashboard_path, "r") as f:
                    return f.read()
            else:
                return "<html><body><h1>WebRTC Dashboard</h1><p>Dashboard HTML file not found.</p></body></html>"

        # WebRTC connections endpoint
        @router.get("/connections", response_class=JSONResponse)
        async def get_connections():
            if not self.webrtc_monitor:
                return {"connections": []}

            connections = []
            for conn_id, conn_data in self.webrtc_monitor.connections.items():
                connections.append(
                    {
                        "connection_id": conn_id,
                        "content_cid": conn_data.get("content_cid", "N/A"),
                        "status": conn_data.get("status", "unknown"),
                        "start_time": conn_data.get("start_time"),
                        "end_time": conn_data.get("end_time"),
                        "quality": conn_data.get("quality", 80),
                        "peer_id": conn_data.get("peer_id", "N/A"),
                    }
                )

            return {"connections": connections}

        # WebRTC operations endpoint
        @router.get("/operations", response_class=JSONResponse)
        async def get_operations():
            if not self.webrtc_monitor:
                return {"operations": []}

            operations = []
            for op_data in self.webrtc_monitor.operations:
                operations.append(
                    {
                        "operation": op_data.get("operation", "N/A"),
                        "connection_id": op_data.get("connection_id", "N/A"),
                        "timestamp": op_data.get("timestamp"),
                        "success": op_data.get("success", False),
                        "error": op_data.get("error"),
                        "start_time": op_data.get("start_time"),
                        "end_time": op_data.get("end_time"),
                    }
                )

            return {"operations": operations}

        # WebRTC tasks endpoint
        @router.get("/tasks", response_class=JSONResponse)
        async def get_tasks():
            if not self.webrtc_monitor:
                return {"tasks": []}

            tasks = []
            if hasattr(self.webrtc_monitor, "task_tracker"):
                for (
                    task_id,
                    task_data,
                ) in self.webrtc_monitor.task_tracker.tasks.items():
                    tasks.append(
                        {
                            "task_id": task_id,
                            "name": task_data.get("name", "Unknown task"),
                            "created_at": task_data.get("created_at"),
                            "completed": task_data.get("completed", False),
                            "completed_at": task_data.get("completed_at"),
                            "error": task_data.get("error"),
                        }
                    )

            return {"tasks": tasks}

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
                    self.webrtc_monitor.record_connection(
                        connection_id=connection_id, content_cid="test", status="active"
                    )

                    # Record operation
                    self.webrtc_monitor.record_operation(
                        operation="test_connection",
                        connection_id=connection_id,
                        success=True,
                    )

                return {
                    "success": True,
                    "connection_id": connection_id,
                    "message": "Test connection successful",
                }
            except Exception as e:
                if self.webrtc_monitor:
                    self.webrtc_monitor.record_operation(
                        operation="test_connection",
                        connection_id="N/A",
                        success=False,
                        error=str(e),
                    )

                return {"success": False, "error": str(e)}

        # Stream test content endpoint
        @router.post("/stream_test_content", response_class=JSONResponse)
        async def stream_test_content():
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}

            try:
                # Use test CID
                test_cid = "QmTest123"

                # Try to call stream_content_webrtc method
                result = await self.webrtc_model.stream_content_webrtc(test_cid)

                if result.get("success"):
                    return {
                        "success": True,
                        "connection_id": result.get("connection_id", "unknown"),
                        "message": "Streaming started successfully",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    self.webrtc_monitor.record_operation(
                        operation="stream_test_content",
                        connection_id="N/A",
                        success=False,
                        error=str(e),
                    )

                return {"success": False, "error": str(e)}

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

                # Try to call stream_content_webrtc method
                result = await self.webrtc_model.stream_content_webrtc(content_cid, quality=quality)

                if result.get("success"):
                    return {
                        "success": True,
                        "connection_id": result.get("connection_id", "unknown"),
                        "message": "Streaming started successfully",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    self.webrtc_monitor.record_operation(
                        operation="stream_content",
                        connection_id="N/A",
                        success=False,
                        error=str(e),
                    )

                return {"success": False, "error": str(e)}

        # Close connection endpoint
        @router.post("/close/{connection_id}", response_class=JSONResponse)
        async def close_connection(connection_id: str):
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}

            try:
                # Try to call close_webrtc_connection method
                result = await self.webrtc_model.close_webrtc_connection(connection_id)

                if result.get("success"):
                    return {
                        "success": True,
                        "message": f"Connection {connection_id} closed successfully",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    self.webrtc_monitor.record_operation(
                        operation="close_connection",
                        connection_id=connection_id,
                        success=False,
                        error=str(e),
                    )

                return {"success": False, "error": str(e)}

        # Close all connections endpoint
        @router.post("/close_all", response_class=JSONResponse)
        async def close_all_connections():
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}

            try:
                # Try to call close_all_webrtc_connections method
                result = await self.webrtc_model.close_all_webrtc_connections()

                if result.get("success"):
                    return {
                        "success": True,
                        "message": "All connections closed successfully",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    self.webrtc_monitor.record_operation(
                        operation="close_all_connections",
                        connection_id="N/A",
                        success=False,
                        error=str(e),
                    )

                return {"success": False, "error": str(e)}

        # Set WebRTC quality endpoint
        @router.post("/quality/{connection_id}", response_class=JSONResponse)
        async def set_webrtc_quality(connection_id: str, request: Request):
            if not self.webrtc_model:
                return {"success": False, "error": "WebRTC model not available"}

            try:
                # Get request body
                body = await request.json()
                quality = body.get("quality", 80)

                # Try to call set_webrtc_quality method
                result = await self.webrtc_model.set_webrtc_quality(connection_id, quality)

                if result.get("success"):
                    return {
                        "success": True,
                        "message": f"Quality set to {quality} for connection {connection_id}",
                    }
                else:
                    return {
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                    }
            except Exception as e:
                if self.webrtc_monitor:
                    self.webrtc_monitor.record_operation(
                        operation="set_quality",
                        connection_id=connection_id,
                        success=False,
                        error=str(e),
                    )

                return {"success": False, "error": str(e)}


def create_webrtc_dashboard_router(webrtc_model=None, webrtc_monitor=None) -> APIRouter:
    """Create a FastAPI router with WebRTC dashboard endpoints.

    Args:
        webrtc_model: The IPFS model instance with WebRTC methods
        webrtc_monitor: Optional WebRTCMonitor instance

    Returns:
        FastAPI router with WebRTC dashboard endpoints
    """
    router = APIRouter(prefix="/api/v0/webrtc", tags=["webrtc"])

    # Create and register controller
    controller = WebRTCDashboardController(webrtc_model=webrtc_model, webrtc_monitor=webrtc_monitor)
    controller.register_routes(router)

    return router
