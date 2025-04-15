"""
Monitoring Integration Module

This module provides a unified interface for integrating all monitoring components:
- Metrics collection and management
- Prometheus integration
- Alerting system
- Dashboard configurations
- Health checks and status endpoints

Part of the MCP Roadmap Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
import time

from ipfs_kit_py.mcp.monitoring import (
    MetricsRegistry, MetricType, MetricUnit, MetricTag, 
    MonitoringManager, SystemMonitor, BackendMonitor, 
    APIMonitor, MigrationMonitor, StreamingMonitor, SearchMonitor
)
from ipfs_kit_py.mcp.monitoring.prometheus import setup_prometheus, PrometheusExporter
from ipfs_kit_py.mcp.monitoring.alerts import setup_alert_manager, AlertManager

# Configure logging
logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Central monitoring service that integrates all monitoring components.
    
    This service initializes and coordinates:
    - Metrics collection and storage
    - Prometheus integration
    - Alerting system
    - Dashboard configurations
    """
    
    def __init__(self, app: FastAPI, backend_registry: Optional[Dict[str, Any]] = None):
        """
        Initialize the monitoring service.
        
        Args:
            app: FastAPI application
            backend_registry: Optional dictionary mapping backend names to instances
        """
        self.app = app
        self.backend_registry = backend_registry or {}
        
        # Create monitoring components
        self.metrics_registry = MetricsRegistry()
        self.monitoring_manager = MonitoringManager(self.backend_registry)
        
        # Prometheus and alerts are initialized later
        self.prometheus_exporter = None
        self.alert_manager = None
        
        # Set up middleware for request timing
        self._setup_timing_middleware()
        
        logger.info("Monitoring service initialized")
    
    def start(self) -> None:
        """Start all monitoring components."""
        # Start monitoring manager
        self.monitoring_manager.start()
        
        # Set up Prometheus integration
        self.prometheus_exporter = setup_prometheus(self.app, self.metrics_registry)
        
        # Set up alerting system
        self.alert_manager = setup_alert_manager(self.app, self.metrics_registry, self.backend_registry)
        
        # Set up health check endpoints
        self._setup_health_endpoints()
        
        logger.info("Monitoring service started")
    
    def stop(self) -> None:
        """Stop all monitoring components."""
        # Stop monitoring manager
        self.monitoring_manager.stop()
        
        # Stop Prometheus push gateway if started
        if self.prometheus_exporter:
            self.prometheus_exporter.stop_push_loop()
        
        # Stop alert manager
        if self.alert_manager:
            self.alert_manager.stop()
        
        logger.info("Monitoring service stopped")
    
    def _setup_timing_middleware(self) -> None:
        """Set up middleware for timing requests."""
        @self.app.middleware("http")
        async def add_timing_middleware(request: Request, call_next):
            # Start timer
            start_time = time.time()
            
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Record metrics (skip for metrics endpoint itself)
            if not request.url.path.startswith("/metrics"):
                # Normalize endpoint for metrics
                endpoint = self._normalize_endpoint(request.url.path)
                
                # Record API request
                self.monitoring_manager.record_api_request(
                    endpoint=endpoint,
                    method=request.method,
                    duration_ms=duration_ms,
                    status=response.status_code
                )
            
            return response
    
    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize API endpoint for metrics to avoid cardinality explosion.
        
        Args:
            path: Request path
            
        Returns:
            Normalized endpoint string
        """
        parts = path.split('/')
        normalized_parts = []
        
        for part in parts:
            # Check if part looks like an ID (uuid, hash, etc)
            if len(part) > 8 and any(c.isdigit() for c in part) and any(c.isalpha() for c in part):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)
        
        return '/'.join(normalized_parts)
    
    def _setup_health_endpoints(self) -> None:
        """Set up health check and monitoring endpoints."""
        @self.app.get("/api/v0/monitoring/status")
        async def get_monitoring_status():
            """Get monitoring system status."""
            return {
                "status": "operational",
                "components": {
                    "metrics": True,
                    "prometheus": self.prometheus_exporter is not None,
                    "alerts": self.alert_manager is not None
                },
                "metrics_count": len(self.metrics_registry.metrics),
                "timestamp": time.time()
            }
        
        @self.app.get("/api/v0/monitoring/metrics")
        async def get_metrics():
            """Get all metrics in JSON format."""
            return self.metrics_registry.get_metrics()
        
        @self.app.get("/api/v0/monitoring/system")
        async def get_system_metrics():
            """Get system metrics."""
            return self.monitoring_manager.get_system_metrics()
        
        @self.app.get("/api/v0/monitoring/backends")
        async def get_backend_metrics():
            """Get storage backend metrics."""
            return self.monitoring_manager.get_backend_metrics()
        
        @self.app.get("/api/v0/monitoring/dashboards")
        async def get_dashboards():
            """Get available Grafana dashboard configurations."""
            dashboards_dir = os.path.join(os.path.dirname(__file__), "dashboards")
            dashboards = []
            
            if os.path.exists(dashboards_dir):
                for filename in os.listdir(dashboards_dir):
                    if filename.endswith(".json"):
                        dashboard_path = os.path.join(dashboards_dir, filename)
                        try:
                            with open(dashboard_path, 'r') as f:
                                dashboard = json.load(f)
                            
                            dashboards.append({
                                "id": dashboard.get("uid", filename),
                                "title": dashboard.get("title", filename),
                                "filename": filename,
                                "tags": dashboard.get("tags", [])
                            })
                        except Exception as e:
                            logger.error(f"Error loading dashboard {filename}: {e}")
            
            return {"dashboards": dashboards}
        
        @self.app.get("/api/v0/monitoring/dashboards/{dashboard_id}")
        async def get_dashboard(dashboard_id: str):
            """Get a specific Grafana dashboard configuration."""
            dashboards_dir = os.path.join(os.path.dirname(__file__), "dashboards")
            
            # Try to find dashboard by ID or filename
            if os.path.exists(dashboards_dir):
                for filename in os.listdir(dashboards_dir):
                    if filename.endswith(".json"):
                        dashboard_path = os.path.join(dashboards_dir, filename)
                        try:
                            with open(dashboard_path, 'r') as f:
                                dashboard = json.load(f)
                            
                            # Check if this is the requested dashboard
                            if dashboard.get("uid") == dashboard_id or filename == f"{dashboard_id}.json":
                                return dashboard
                        except Exception as e:
                            logger.error(f"Error loading dashboard {filename}: {e}")
            
            # Dashboard not found
            return JSONResponse(
                status_code=404,
                content={"detail": f"Dashboard {dashboard_id} not found"}
            )
    
    def record_backend_operation(self, backend_name: str, operation: str,
                             duration_ms: float, success: bool = True,
                             bytes_processed: Optional[float] = None) -> None:
        """
        Record a backend operation.
        
        Args:
            backend_name: Name of the backend
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether the operation was successful
            bytes_processed: Optional bytes processed
        """
        self.monitoring_manager.record_backend_operation(
            backend_name, operation, duration_ms, success, bytes_processed
        )
    
    def record_migration(self, source_backend: str, target_backend: str,
                     status: str, bytes_transferred: Optional[float] = None) -> None:
        """
        Record a migration operation.
        
        Args:
            source_backend: Source backend name
            target_backend: Target backend name
            status: Migration status
            bytes_transferred: Optional bytes transferred
        """
        self.monitoring_manager.record_migration(
            source_backend, target_backend, status, bytes_transferred
        )
    
    def record_streaming(self, direction: str, status: str,
                     bytes_transferred: Optional[float] = None) -> None:
        """
        Record a streaming operation.
        
        Args:
            direction: Streaming direction (upload/download)
            status: Operation status
            bytes_transferred: Optional bytes transferred
        """
        self.monitoring_manager.record_streaming(
            direction, status, bytes_transferred
        )
    
    def record_search(self, index_type: str, duration_ms: float,
                  status: str = "success") -> None:
        """
        Record a search operation.
        
        Args:
            index_type: Type of search index
            duration_ms: Operation duration in milliseconds
            status: Operation status
        """
        self.monitoring_manager.record_search(
            index_type, duration_ms, status
        )


def setup_monitoring(app: FastAPI, backend_registry: Optional[Dict[str, Any]] = None) -> MonitoringService:
    """
    Set up the monitoring system for MCP.
    
    Args:
        app: FastAPI application
        backend_registry: Optional dictionary mapping backend names to instances
        
    Returns:
        Monitoring service instance
    """
    # Create and start monitoring service
    monitoring_service = MonitoringService(app, backend_registry)
    monitoring_service.start()
    
    # Set up shutdown handler
    @app.on_event("shutdown")
    async def shutdown_monitoring():
        monitoring_service.stop()
    
    logger.info("Monitoring system set up for MCP")
    return monitoring_service