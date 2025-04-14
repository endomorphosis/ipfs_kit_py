"""
Monitoring system initialization for MCP server.

This module initializes and configures all monitoring components,
including metrics collection, health checks, and alerting.
"""

import logging
import os
import json
from typing import Dict, Any, Optional, List, Union

# Configure logger
logger = logging.getLogger(__name__)

# Import monitoring components
try:
    from .prometheus_exporter import PrometheusExporter, PROMETHEUS_AVAILABLE
except ImportError:
    logger.warning("Prometheus exporter not available")
    PROMETHEUS_AVAILABLE = False
    PrometheusExporter = None

try:
    from .health_check import HealthCheckAPI
except ImportError:
    logger.warning("Health check API not available")
    HealthCheckAPI = None

try:
    from ..storage_manager.monitoring import MonitoringSystem
except ImportError:
    logger.warning("Storage monitoring system not available")
    MonitoringSystem = None


class MonitoringManager:
    """
    Unified monitoring manager for MCP server.
    
    This class initializes and manages all monitoring components:
    - Backend monitoring system
    - Prometheus metrics exporter
    - Health check API
    - (Future) Alerting system
    """
    
    def __init__(
        self,
        app=None,
        storage_manager=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the monitoring manager.
        
        Args:
            app: FastAPI or similar app instance
            storage_manager: UnifiedStorageManager instance
            config: Monitoring configuration options
        """
        self.app = app
        self.storage_manager = storage_manager
        self.config = config or {}
        
        # Components
        self.monitoring_system = None
        self.prometheus_exporter = None
        self.health_check = None
        
        # Flags for enabled components
        self.monitoring_enabled = self.config.get("enable_monitoring", True)
        self.metrics_enabled = self.config.get("enable_metrics", PROMETHEUS_AVAILABLE)
        self.health_check_enabled = self.config.get("enable_health_check", True)
        
        # Initialize components
        if self.monitoring_enabled:
            self._initialize_components()
            
    def _initialize_components(self):
        """Initialize monitoring components."""
        # Get component configurations
        monitoring_config = self.config.get("monitoring", {})
        metrics_config = self.config.get("metrics", {})
        health_config = self.config.get("health_check", {})
        
        # Initialize backend monitoring system
        if MonitoringSystem and self.storage_manager and self.monitoring_enabled:
            try:
                self.monitoring_system = MonitoringSystem(
                    storage_manager=self.storage_manager,
                    options=monitoring_config
                )
                logger.info("Initialized backend monitoring system")
                
                # Start background monitoring if enabled
                if self.config.get("start_monitoring", False):
                    self.monitoring_system.start_monitoring()
                    logger.info("Started background monitoring")
                    
            except Exception as e:
                logger.error(f"Failed to initialize backend monitoring system: {e}")
                
        # Initialize Prometheus exporter
        if PrometheusExporter and self.metrics_enabled:
            try:
                self.prometheus_exporter = PrometheusExporter(options=metrics_config)
                logger.info("Initialized Prometheus metrics exporter")
                
                # Start metrics server if enabled
                if self.config.get("start_metrics_server", False):
                    self.prometheus_exporter.start(
                        storage_manager=self.storage_manager,
                        monitoring_system=self.monitoring_system
                    )
                    logger.info("Started Prometheus metrics server")
                    
            except Exception as e:
                logger.error(f"Failed to initialize Prometheus metrics exporter: {e}")
                
        # Initialize health check API
        if HealthCheckAPI and self.health_check_enabled:
            try:
                self.health_check = HealthCheckAPI(
                    app=self.app,
                    storage_manager=self.storage_manager,
                    monitoring_system=self.monitoring_system
                )
                logger.info("Initialized health check API")
                
                # Start background health checks if enabled
                if self.config.get("start_health_checks", False):
                    interval = health_config.get("check_interval", 60)
                    self.health_check.start_background_checks(interval=interval)
                    logger.info(f"Started background health checks with {interval}s interval")
                    
            except Exception as e:
                logger.error(f"Failed to initialize health check API: {e}")
                
    def start(self):
        """Start all monitoring components."""
        # Start backend monitoring system
        if self.monitoring_system:
            try:
                self.monitoring_system.start_monitoring()
                logger.info("Started backend monitoring system")
            except Exception as e:
                logger.error(f"Failed to start backend monitoring system: {e}")
                
        # Start Prometheus metrics server
        if self.prometheus_exporter:
            try:
                self.prometheus_exporter.start(
                    storage_manager=self.storage_manager,
                    monitoring_system=self.monitoring_system
                )
                logger.info("Started Prometheus metrics server")
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {e}")
                
        # Start health check background checks
        if self.health_check:
            try:
                interval = self.config.get("health_check", {}).get("check_interval", 60)
                self.health_check.start_background_checks(interval=interval)
                logger.info(f"Started background health checks with {interval}s interval")
            except Exception as e:
                logger.error(f"Failed to start background health checks: {e}")
                
    def stop(self):
        """Stop all monitoring components."""
        # Stop backend monitoring system
        if self.monitoring_system:
            try:
                self.monitoring_system.stop_monitoring()
                logger.info("Stopped backend monitoring system")
            except Exception as e:
                logger.error(f"Failed to stop backend monitoring system: {e}")
                
        # Stop Prometheus metrics server
        if self.prometheus_exporter:
            try:
                self.prometheus_exporter.stop()
                logger.info("Stopped Prometheus metrics server")
            except Exception as e:
                logger.error(f"Failed to stop Prometheus metrics server: {e}")
                
    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """
        Record an API request for metrics.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP status code
            duration: Request duration in seconds
        """
        if self.prometheus_exporter:
            try:
                self.prometheus_exporter.record_api_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    duration=duration
                )
            except Exception as e:
                logger.error(f"Failed to record API request metric: {e}")
                
    def record_backend_operation(
        self,
        backend_type: str,
        operation: str,
        success: bool,
        duration: float,
        data_size: Optional[int] = None,
    ):
        """
        Record a backend operation for metrics.
        
        Args:
            backend_type: Backend type
            operation: Operation type
            success: Whether operation was successful
            duration: Operation duration in seconds
            data_size: Size of data in bytes (optional)
        """
        # Record in monitoring system if available
        if self.monitoring_system:
            try:
                self.monitoring_system.record_operation(
                    backend_type=backend_type,
                    operation=operation,
                    duration=duration,
                    success=success,
                    data_size=data_size
                )
            except Exception as e:
                logger.error(f"Failed to record operation in monitoring system: {e}")
                
        # Record in Prometheus metrics if available
        if self.prometheus_exporter:
            try:
                self.prometheus_exporter.record_backend_operation(
                    backend_type=backend_type,
                    operation=operation,
                    success=success,
                    duration=duration
                )
            except Exception as e:
                logger.error(f"Failed to record operation in Prometheus metrics: {e}")
                
    def get_health_status(self):
        """
        Get the current health status of the server.
        
        Returns:
            Dictionary with health status
        """
        if self.health_check:
            try:
                # Use health check API to get status
                return {
                    "status": self.health_check.overall_status,
                    "components": {
                        component: info["status"] 
                        for component, info in self.health_check.components.items()
                    },
                    "uptime": self.health_check.startup_time,
                    "timestamp": self.health_check.components["server"]["last_check"]
                }
            except Exception as e:
                logger.error(f"Failed to get health status: {e}")
                
        elif self.monitoring_system:
            try:
                # Fall back to monitoring system
                backend_status = self.monitoring_system.get_backend_status()
                
                return {
                    "status": backend_status.get("overall_status", "unknown"),
                    "backends": backend_status.get("backends", {}),
                    "timestamp": backend_status.get("timestamp", 0)
                }
            except Exception as e:
                logger.error(f"Failed to get backend status: {e}")
                
        # No health monitoring available
        return {
            "status": "unknown",
            "error": "No health monitoring available",
            "timestamp": 0
        }
        
    def create_middleware(self):
        """
        Create a middleware function for request monitoring.
        
        Returns:
            A middleware function compatible with FastAPI or Starlette
        """
        async def monitoring_middleware(request, call_next):
            """Middleware for monitoring request metrics."""
            # Record start time
            start_time = time.time()
            
            # Process request
            response = await call_next(request)
            
            # Record duration
            duration = time.time() - start_time
            
            # Record metrics
            self.record_api_request(
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration=duration
            )
            
            return response
            
        return monitoring_middleware
        
    def configure_fastapi(self, app):
        """
        Configure FastAPI app with monitoring components.
        
        Args:
            app: FastAPI app instance
        """
        # Store app reference
        self.app = app
        
        # Add middleware for request monitoring
        if hasattr(app, "middleware"):
            try:
                @app.middleware("http")
                async def monitoring_middleware(request, call_next):
                    # Record start time
                    import time
                    start_time = time.time()
                    
                    # Process request
                    response = await call_next(request)
                    
                    # Record duration
                    duration = time.time() - start_time
                    
                    # Record metrics
                    self.record_api_request(
                        endpoint=request.url.path,
                        method=request.method,
                        status_code=response.status_code,
                        duration=duration
                    )
                    
                    return response
                    
                logger.info("Added monitoring middleware to FastAPI app")
                
            except Exception as e:
                logger.error(f"Failed to add monitoring middleware: {e}")
                
        # Register health check routes
        if self.health_check:
            try:
                self.health_check.register_routes(app)
                logger.info("Registered health check routes with FastAPI app")
            except Exception as e:
                logger.error(f"Failed to register health check routes: {e}")
                
        # Add status endpoint
        if hasattr(app, "add_api_route"):
            try:
                @app.get("/api/v0/status")
                async def get_status():
                    # Get comprehensive status
                    status = {
                        "monitoring": {
                            "monitoring_enabled": self.monitoring_enabled,
                            "metrics_enabled": self.metrics_enabled,
                            "health_check_enabled": self.health_check_enabled,
                        }
                    }
                    
                    # Add backend status if available
                    if self.monitoring_system:
                        try:
                            status["backends"] = self.monitoring_system.get_backend_status()
                        except Exception as e:
                            status["backends_error"] = str(e)
                            
                    # Add health status if available
                    if self.health_check:
                        try:
                            status["health"] = self.get_health_status()
                        except Exception as e:
                            status["health_error"] = str(e)
                            
                    return status
                    
                logger.info("Added status endpoint to FastAPI app")
                
            except Exception as e:
                logger.error(f"Failed to add status endpoint: {e}")
                
def create_monitoring_manager(
    app=None,
    storage_manager=None,
    config: Optional[Dict[str, Any]] = None,
):
    """
    Create and initialize a monitoring manager instance.
    
    Args:
        app: FastAPI or similar app instance
        storage_manager: UnifiedStorageManager instance
        config: Monitoring configuration options
        
    Returns:
        Configured MonitoringManager instance
    """
    # Create manager
    manager = MonitoringManager(
        app=app,
        storage_manager=storage_manager,
        config=config
    )
    
    # Configure FastAPI app if provided
    if app and hasattr(app, "middleware"):
        manager.configure_fastapi(app)
    
    # Start components if enabled
    if config and config.get("autostart", False):
        manager.start()
    
    return manager