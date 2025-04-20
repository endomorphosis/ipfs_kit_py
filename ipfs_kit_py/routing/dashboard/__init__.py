"""
Routing Dashboard Entry Point

This module provides a simplified interface for creating and running
the routing dashboard as a standalone application.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

class DashboardSettings:
    """Settings for the routing dashboard."""
    
    def __init__(
        self,
        title: str = "IPFS Kit Routing Dashboard",
        theme: str = "darkly",
        debug: bool = False,
        host: str = "127.0.0.1",
        port: int = 8050,
        routing_data_dir: Optional[Union[str, Path]] = None,
        metrics_retention_days: int = 7,
        refresh_interval: int = 10,
        enable_simulator: bool = True,
        enable_config_editing: bool = True,
        **kwargs
    ):
        """
        Initialize dashboard settings.
        
        Args:
            title: Dashboard title
            theme: Dashboard theme (darkly, flatly, etc.)
            debug: Enable debug mode
            host: Host to bind to
            port: Port to bind to
            routing_data_dir: Directory for routing data
            metrics_retention_days: Number of days to retain metrics
            refresh_interval: Interval in seconds for data refresh
            enable_simulator: Enable routing simulator
            enable_config_editing: Enable configuration editing
            **kwargs: Additional settings
        """
        self.title = title
        self.theme = theme
        self.debug = debug
        self.host = host
        self.port = port
        self.routing_data_dir = routing_data_dir
        self.metrics_retention_days = metrics_retention_days
        self.refresh_interval = refresh_interval
        self.enable_simulator = enable_simulator
        self.enable_config_editing = enable_config_editing
        
        # Add any additional settings
        for key, value in kwargs.items():
            setattr(self, key, value)


def create_dashboard_app(settings: Optional[DashboardSettings] = None) -> "FastAPI":
    """
    Create the routing dashboard FastAPI application.
    
    Args:
        settings: Optional dashboard settings
        
    Returns:
        FastAPI application
    """
    settings = settings or DashboardSettings()
    
    try:
        from .dashboard.routing_dashboard import RoutingDashboard
        from fastapi import FastAPI
        
        # Create FastAPI app
        app = FastAPI(
            title=settings.title,
            description="Dashboard for optimized data routing",
            version="1.0.0",
            debug=settings.debug
        )
        
        # Create and mount dashboard
        dashboard = RoutingDashboard(settings)
        dashboard.mount_to_app(app)
        
        return app
    except ImportError as e:
        logger.error(f"Error creating dashboard app: {e}", exc_info=True)
        raise


async def start_dashboard_server(
    settings: Optional[DashboardSettings] = None
) -> None:
    """
    Start the routing dashboard server.
    
    Args:
        settings: Optional dashboard settings
    """
    settings = settings or DashboardSettings()
    
    try:
        import uvicorn
        
        app = create_dashboard_app(settings)
        
        config = uvicorn.Config(
            app=app,
            host=settings.host,
            port=settings.port,
            log_level="debug" if settings.debug else "info",
            reload=settings.debug
        )
        
        server = uvicorn.Server(config)
        logger.info(f"Starting routing dashboard on http://{settings.host}:{settings.port}")
        await server.serve()
        
    except ImportError as e:
        logger.error(f"Error starting dashboard server: {e}", exc_info=True)
        raise


def run_dashboard(settings: Optional[Dict[str, Any]] = None) -> None:
    """
    Run the routing dashboard (blocking).
    
    This is a convenience function for running the dashboard from scripts.
    
    Args:
        settings: Optional dashboard settings as dictionary
    """
    try:
        # Convert dictionary to settings object if provided
        settings_obj = None
        if settings is not None:
            settings_obj = DashboardSettings(**settings)
        
        # Run the dashboard
        asyncio.run(start_dashboard_server(settings_obj))
        
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise