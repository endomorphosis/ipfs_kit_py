"""
Dashboard routes for web interface.
"""

from fastapi import Request
from fastapi.responses import HTMLResponse
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class DashboardRoutes:
    """Dashboard route handlers."""
    
    def __init__(self, templates, backend_monitor):
        self.templates = templates
        self.backend_monitor = backend_monitor
    
    async def dashboard(self, request: Request) -> HTMLResponse:
        """Main dashboard route."""
        return self.templates.TemplateResponse("index.html", {"request": request})
