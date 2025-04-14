"""
WebRTC Video Player Controller for the MCP Server (AnyIO version).

This module provides endpoints for the WebRTC video player page
which includes random seek functionality.

This version uses AnyIO for backend-agnostic async operations.
"""

import os

import anyio
import sniffio
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse


class WebRTCVideoPlayerControllerAnyIO:
    """Controller for the WebRTC video player (AnyIO version)."""

    def __init__(self, static_dir=None, webrtc_model=None):
        """Initialize the WebRTC video player controller.

        Args:
            static_dir: Optional path to static directory. If None, will attempt to find it.
            webrtc_model: Optional WebRTC model for accessing connection data
        """
        self.static_dir = static_dir or self._get_static_dir()
        self.webrtc_model = webrtc_model

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
        """Register the video player routes with the API router.

        Args:
            router: The FastAPI router to register routes with
        """

        # Video player page
        @router.get("/player", response_class=HTMLResponse)
        async def get_video_player(request: Request):
            # Get connection ID and content CID from query parameters if provided
            connection_id = request.query_params.get("connection_id", "")
            content_cid = request.query_params.get("content_cid", "")

            player_path = os.path.join(self.static_dir, "webrtc_video_player.html")

            if os.path.exists(player_path):
                # Use anyio's file operations instead of synchronous open
                async with await anyio.open_file(player_path, "r") as f:
                    html_content = await f.read()

                # If connection parameters were provided, inject them into the HTML
                if connection_id and content_cid:
                    # Insert a script to auto-populate the form fields
                    html_content = html_content.replace(
                        "</body>",
                        f"""
                        <script>
                            // Auto-populate connection details from URL parameters
                            document.addEventListener('DOMContentLoaded', function() {{
                                // Set connection details from URL parameters
                                document.getElementById('content-cid').value = "{content_cid}";
                                
                                // Add a message about the connection
                                addLogEntry("Connection parameters received from dashboard: Connection ID {connection_id}", "info");
                                
                                // Optionally auto-connect when from dashboard
                                if (confirm("Auto-connect to stream with content CID {content_cid}?")) {{
                                    connectStream();
                                }}
                            }});
                        </script>
                        </body>""",
                    )

                return html_content
            else:
                return "<html><body><h1>WebRTC Video Player</h1><p>Player HTML file not found.</p></body></html>"

        # Connection status endpoint (to retrieve information about a specific connection)
        @router.get("/connection/{connection_id}", response_class=JSONResponse)
        async def get_connection_details(connection_id: str):
            # Return information if webrtc model is available
            if not self.webrtc_model or not hasattr(self.webrtc_model, "get_connection_info"):
                return {
                    "success": False,
                    "error": "Connection information not available",
                }

            try:
                # Check if method is async and call appropriately
                if hasattr(self.webrtc_model.get_connection_info, "__await__"):
                    # Method is already async
                    connection_info = await self.webrtc_model.get_connection_info(connection_id)
                else:
                    # Method is sync, run in a thread
                    connection_info = await anyio.to_thread.run_sync(
                        lambda: self.webrtc_model.get_connection_info(connection_id)
                    )
                return connection_info
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Error retrieving connection info: {str(e)}",
                }

        # Sample video endpoint for testing
        @router.get("/demo_video.mp4", response_class=FileResponse)
        async def get_demo_video():
            # Path to a sample video file - if not exists, return a 404
            video_path = os.path.join(self.static_dir, "demo_video.mp4")

            # Check if file exists using anyio
            exists = await anyio.to_thread.run_sync(lambda: os.path.exists(video_path))

            if not exists:
                return {"error": "Demo video not found"}

            return FileResponse(video_path)


async def create_webrtc_video_player_router_anyio(static_dir=None, webrtc_model=None) -> APIRouter:
    """Create a FastAPI router with WebRTC video player endpoints (AnyIO version).

    Args:
        static_dir: Optional path to static directory
        webrtc_model: Optional WebRTC model for accessing connection data

    Returns:
        FastAPI router with WebRTC video player endpoints
    """
    router = APIRouter(prefix="/api/v0/webrtc", tags=["webrtc"])

    # Create and register controller
    controller = WebRTCVideoPlayerControllerAnyIO(static_dir=static_dir, webrtc_model=webrtc_model)
    controller.register_routes(router)

    return router


def create_webrtc_video_player_router(static_dir=None, webrtc_model=None) -> APIRouter:
    """Create a FastAPI router with WebRTC video player endpoints.

    This function creates the AnyIO-compatible router but provides the same
    API as the original function for backwards compatibility.

    Args:
        static_dir: Optional path to static directory
        webrtc_model: Optional WebRTC model for accessing connection data

    Returns:
        FastAPI router with WebRTC video player endpoints
    """
    router = APIRouter(prefix="/api/v0/webrtc", tags=["webrtc"])

    # Create and register controller
    controller = WebRTCVideoPlayerControllerAnyIO(static_dir=static_dir, webrtc_model=webrtc_model)
    controller.register_routes(router)

    return router
