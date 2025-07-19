"""
API Routes for the Modular Enhanced MCP Server.
"""
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .backends import BackendHealthMonitor


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
            return {"status": "ok"}