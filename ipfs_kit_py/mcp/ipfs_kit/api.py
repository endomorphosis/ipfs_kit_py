"""
API Routes for the Modular Enhanced MCP Server.
"""
import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .backends import BackendHealthMonitor

logger = logging.getLogger(__name__)


class APIRoutes:
    """Sets up API routes for the server."""

    def __init__(self, app: FastAPI, backend_monitor: BackendHealthMonitor,
                 templates: Jinja2Templates, websocket_manager=None):
        self.app = app
        self.backend_monitor = backend_monitor
        self.templates = templates
        self.websocket_manager = websocket_manager
        self.start_time = time.time()

        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Serves the main dashboard page."""
            # Get backend status data from the monitor
            backend_status_data = self.backend_monitor.get_backend_health()

            context = {
                "request": request,
                "backend_status": backend_status_data,
            }
            return self.templates.TemplateResponse("dashboard.html", context)

        @self.app.get("/health")
        async def health_check():
            """Comprehensive health check with filesystem status from parquet files."""
            try:
                # Get comprehensive health status including filesystem data
                health_status = await self.backend_monitor.get_comprehensive_health_status()
                return health_status
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time(),
                    "system_healthy": False
                }

        @self.app.get("/health/backends")
        async def backend_health_check():
            """Get detailed backend health status."""
            try:
                return await self.backend_monitor.check_all_backends_health()
            except Exception as e:
                logger.error(f"Backend health check failed: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time()
                }

        @self.app.get("/health/filesystem")
        async def filesystem_health_check():
            """Get filesystem status from parquet files."""
            try:
                return await self.backend_monitor.get_filesystem_status_from_parquet()
            except Exception as e:
                logger.error(f"Filesystem health check failed: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": time.time()
                }