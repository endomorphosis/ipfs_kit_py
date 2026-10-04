"""
Dashboard module for IPFS Kit MCP Server.

This module provides the web dashboard interface for monitoring and configuring
all IPFS Kit backends and services.
"""

from .template_manager import DashboardTemplateManager
from .routes import DashboardRoutes
from .websocket_manager import WebSocketManager

__all__ = [
    'DashboardTemplateManager',
    'DashboardRoutes', 
    'WebSocketManager'
]
