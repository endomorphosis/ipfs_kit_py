"""
IPFS Monitoring Integration.

This module integrates the advanced IPFS operations with Prometheus metrics
and provides health check endpoints for monitoring system status.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Union
import threading
import asyncio

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

# Import our metrics system
from ipfs_kit_py.mcp.monitoring.ipfs_prometheus import (
    get_metrics_instance,
    get_exporter_instance,
    IPFSMetrics,
    PrometheusExporter
)

# Import the advanced IPFS operations
from ipfs_kit_py.mcp.extensions.advanced_ipfs_operations import get_instance as get_advanced_ipfs

# Set up logging
logger = logging.getLogger("ipfs_monitoring_integration")

# Models for API responses
class HealthCheckResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str = Field(..., description="Health status (healthy, degraded, critical)")
    version: str = Field(..., description="IPFS version")
    services: Dict[str, Dict[str, Any]] = Field(..., description="Status of individual services")
    timestamp: float = Field(..., description="Timestamp of health check")
    uptime: float = Field(..., description="Server uptime in seconds")


class MetricsResponse(BaseModel):
    """Response model for metrics endpoint."""
    success: bool = Field(..., description="Whether the metrics request was successful")
    metrics: Dict[str, Any] = Field(..., description="Current metrics values")
    timestamp: float = Field(..., description="Timestamp of metrics snapshot")


class IPFSMonitoringIntegration:
    """
    Integration of IPFS operations with monitoring systems.
    
    This class connects the advanced IPFS operations with Prometheus metrics
    and provides methods for health checking and monitoring.
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        start_metrics_server: bool = True,
        metrics_host: str = "localhost",
        metrics_port: int = 9090
    ):
        """
        Initialize the monitoring integration.
        
        Args:
            config: Configuration options
            start_metrics_server: Whether to start the Prometheus metrics server
            metrics_host: Host to bind the metrics server to
            metrics_port: Port to bind the metrics server to
        """
        self.config = config or {}
        self.start_time = time.time()
        
        # Get the monitoring components
        self.metrics = get_metrics_instance()
        self.exporter = get_exporter_instance(metrics_host, metrics_port)
        
        # Get the advanced IPFS operations
        self.advanced_ipfs = get_advanced_ipfs(self.config)
        
        # Start metrics server if requested
        if start_metrics_server:
            self.exporter.start()
        
        # Start background collection of metrics
        self.should_stop = False
        self.collection_thread = threading.Thread(target=self._collect_metrics_loop, daemon=True)
        self.collection_thread.start()
        
        logger.info("IPFS Monitoring Integration initialized")
    
    def _collect_metrics_loop(self):
        """Background loop for collecting metrics."""
        logger.info("Starting background metrics collection")
        
        # How often to update metrics (in seconds)
        update_interval = self.config.get("metrics_update_interval", 30)
        
        try:
            while not self.should_stop:
                try:
                    # Collect and update metrics
                    self._update_ipfs_metrics()
                    
                    # Sleep until next update
                    time.sleep(update_interval)
                except Exception as e:
                    logger.error(f"Error in metrics collection: {e}")
                    time.sleep(5)  # Sleep shorter time on error
        except Exception as e:
            logger.error(f"Metrics collection thread terminated with error: {e}")
    
    def _update_ipfs_metrics(self):
        """Update IPFS metrics from various sources."""
        try:
            # Update node information
            self._update_node_info()
            
            # Update connection pool metrics
            self._update_connection_pool_metrics()
            
            # Update pin count
            self._update_pin_count()
            
            # Update IPNS key count
            self._update_ipns_key_count()
            
            logger.debug("IPFS metrics updated successfully")
        except Exception as e:
            logger.error(f"Error updating IPFS metrics: {e}")
    
    def _update_node_info(self):
        """Update IPFS node information."""
        try:
            # Get node information using our advanced IPFS operations
            node_id_result = None
            version_result = None
            
            # Try to access the connected IPFS node
            try:
                # Get IPFS node ID
                node_id_result = self.advanced_ipfs.connection_pool.post("id")
                if node_id_result.status_code == 200:
                    node_id_data = node_id_result.json()
                    
                    # Get version information
                    version_result = self.advanced_ipfs.connection_pool.post("version")
                    if version_result.status_code == 200:
                        version_data = version_result.json()
                        
                        # Update metrics with node information
                        self.metrics.update_node_info(
                            node_id=node_id_data.get("ID", "unknown"),
                            version=version_data.get("Version", "unknown"),
                            addresses=node_id_data.get("Addresses", [])
                        )
                    else:
                        logger.warning(f"Failed to get IPFS version: {version_result.status_code}")
                else:
                    logger.warning(f"Failed to get IPFS node ID: {node_id_result.status_code}")
            except Exception as e:
                logger.error(f"Error getting IPFS node information: {e}")
        except Exception as e:
            logger.error(f"Error updating node info metrics: {e}")
    
    def _update_connection_pool_metrics(self):
        """Update connection pool metrics."""
        try:
            # Get connection pool metrics from our advanced IPFS operations
            if hasattr(self.advanced_ipfs, "connection_pool"):
                pool = self.advanced_ipfs.connection_pool
                
                if hasattr(pool, "_connections") and hasattr(pool, "_lock"):
                    with pool._lock:
                        total = len(pool._connections)
                        active = sum(1 for conn in pool._connections if conn.in_use)
                        idle = total - active
                        
                        # Update metrics
                        self.metrics.track_connection_pool(
                            total=total,
                            active=active,
                            idle=idle
                        )
        except Exception as e:
            logger.error(f"Error updating connection pool metrics: {e}")
    
    def _update_pin_count(self):
        """Update pin count metrics."""
        try:
            # Get pin count using our advanced IPFS operations
            list_pins_result = self.advanced_ipfs.connection_pool.post("pin/ls")
            
            if list_pins_result.status_code == 200:
                pin_data = list_pins_result.json()
                
                # Count the number of pins
                pin_count = 0
                
                # Handle different response formats
                if "Keys" in pin_data and isinstance(pin_data["Keys"], dict):
                    pin_count = len(pin_data["Keys"])
                elif "Pins" in pin_data and isinstance(pin_data["Pins"], list):
                    pin_count = len(pin_data["Pins"])
                elif "pins" in pin_data and isinstance(pin_data["pins"], list):
                    pin_count = len(pin_data["pins"])
                
                # Update metrics
                self.metrics.set_pins_count(pin_count)
        except Exception as e:
            logger.error(f"Error updating pin count metrics: {e}")
    
    def _update_ipns_key_count(self):
        """Update IPNS key count metrics."""
        try:
            # Get IPNS key count using our advanced IPFS operations
            list_keys_result = self.advanced_ipfs.list_keys()
            
            if list_keys_result.get("success", False):
                keys = list_keys_result.get("keys", [])
                
                # Update metrics
                self.metrics.set_ipns_keys_count(len(keys))
        except Exception as e:
            logger.error(f"Error updating IPNS key count metrics: {e}")
    
    def track_api_request(
        self, method: str, endpoint: str, duration: float, error: Optional[str] = None
    ):
        """
        Track an IPFS API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint called
            duration: Request duration in seconds
            error: Optional error type if request failed
        """
        self.metrics.track_api_request(method, endpoint, duration, error)
    
    def track_dht_operation(
        self, operation: str, duration: float, success: bool, peers_found: Optional[int] = None, error: Optional[str] = None
    ):
        """
        Track a DHT operation.
        
        Args:
            operation: DHT operation name
            duration: Operation duration in seconds
            success: Whether operation was successful
            peers_found: Optional number of peers found
            error: Optional error type if operation failed
        """
        self.metrics.track_dht_operation(operation, duration, success, peers_found, error)
    
    def track_ipns_operation(
        self, operation: str, duration: float, success: bool, error: Optional[str] = None
    ):
        """
        Track an IPNS operation.
        
        Args:
            operation: IPNS operation name
            duration: Operation duration in seconds
            success: Whether operation was successful
            error: Optional error type if operation failed
        """
        self.metrics.track_ipns_operation(operation, duration, success, error)
    
    def track_dag_operation(
        self, operation: str, duration: float, success: bool, node_size: Optional[int] = None, error: Optional[str] = None
    ):
        """
        Track a DAG operation.
        
        Args:
            operation: DAG operation name
            duration: Operation duration in seconds
            success: Whether operation was successful
            node_size: Optional size of the DAG node in bytes
            error: Optional error type if operation failed
        """
        self.metrics.track_dag_operation(operation, duration, success, node_size, error)
    
    def track_content_add(self, size: int, duration: float):
        """
        Track content addition to IPFS.
        
        Args:
            size: Content size in bytes
            duration: Operation duration in seconds
        """
        self.metrics.track_content_add(size, duration)
    
    def track_content_get(self, size: int, duration: float):
        """
        Track content retrieval from IPFS.
        
        Args:
            size: Content size in bytes
            duration: Operation duration in seconds
        """
        self.metrics.track_content_get(size, duration)
    
    def track_integration_usage(self, operation: str, source: str):
        """
        Track usage of the advanced IPFS integration.
        
        Args:
            operation: Operation being used
            source: Source/component using the integration
        """
        self.metrics.track_integration_usage(operation, source)
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the IPFS system.
        
        Returns:
            Health check results
        """
        health_result = {
            "status": "unknown",
            "version": "unknown",
            "services": {},
            "timestamp": time.time(),
            "uptime": time.time() - self.start_time
        }
        
        try:
            # Check IPFS daemon status
            ipfs_status = {"status": "unknown", "details": {}}
            try:
                daemon_response = self.advanced_ipfs.connection_pool.post("id")
                if daemon_response.status_code == 200:
                    daemon_data = daemon_response.json()
                    ipfs_status = {
                        "status": "healthy",
                        "details": {
                            "id": daemon_data.get("ID", "unknown"),
                            "version": daemon_data.get("AgentVersion", "unknown"),
                            "addresses": daemon_data.get("Addresses", []),
                            "protocols": daemon_data.get("Protocols", []),
                        }
                    }
                    
                    # Set overall version
                    health_result["version"] = daemon_data.get("AgentVersion", "unknown")
                else:
                    ipfs_status = {
                        "status": "critical",
                        "details": {
                            "error": f"IPFS daemon returned status code {daemon_response.status_code}",
                            "response": daemon_response.text
                        }
                    }
            except Exception as e:
                ipfs_status = {
                    "status": "critical",
                    "details": {
                        "error": f"Error connecting to IPFS daemon: {str(e)}"
                    }
                }
            
            health_result["services"]["ipfs_daemon"] = ipfs_status
            
            # Check DHT status
            dht_status = {"status": "unknown", "details": {}}
            try:
                # Try to get the DHT routing table
                routing_result = self.advanced_ipfs.dht_get_routing_table()
                if routing_result.get("success", False):
                    peer_count = routing_result.get("count", 0)
                    if peer_count > 0:
                        dht_status = {
                            "status": "healthy",
                            "details": {
                                "peers_in_routing_table": peer_count
                            }
                        }
                    else:
                        dht_status = {
                            "status": "degraded",
                            "details": {
                                "peers_in_routing_table": 0,
                                "warning": "No peers in DHT routing table"
                            }
                        }
                else:
                    dht_status = {
                        "status": "degraded",
                        "details": {
                            "error": routing_result.get("error", "Unknown error getting DHT routing table")
                        }
                    }
            except Exception as e:
                dht_status = {
                    "status": "degraded",
                    "details": {
                        "error": f"Error checking DHT status: {str(e)}"
                    }
                }
            
            health_result["services"]["dht"] = dht_status
            
            # Check connection pool status
            pool_status = {"status": "unknown", "details": {}}
            try:
                if hasattr(self.advanced_ipfs, "connection_pool"):
                    pool = self.advanced_ipfs.connection_pool
                    
                    if hasattr(pool, "_connections") and hasattr(pool, "_lock"):
                        with pool._lock:
                            total = len(pool._connections)
                            active = sum(1 for conn in pool._connections if conn.in_use)
                            idle = total - active
                            
                            if active < total:
                                pool_status = {
                                    "status": "healthy",
                                    "details": {
                                        "total_connections": total,
                                        "active_connections": active,
                                        "idle_connections": idle
                                    }
                                }
                            else:
                                pool_status = {
                                    "status": "degraded",
                                    "details": {
                                        "total_connections": total,
                                        "active_connections": active,
                                        "idle_connections": idle,
                                        "warning": "All connections are currently in use"
                                    }
                                }
            except Exception as e:
                pool_status = {
                    "status": "degraded",
                    "details": {
                        "error": f"Error checking connection pool status: {str(e)}"
                    }
                }
            
            health_result["services"]["connection_pool"] = pool_status
            
            # Determine overall status
            statuses = [service["status"] for service in health_result["services"].values()]
            if "critical" in statuses:
                health_result["status"] = "critical"
            elif "degraded" in statuses:
                health_result["status"] = "degraded"
            elif "healthy" in statuses:
                health_result["status"] = "healthy"
            
            return health_result
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return {
                "status": "critical",
                "version": "unknown",
                "services": {
                    "health_check": {
                        "status": "critical",
                        "details": {
                            "error": f"Error performing health check: {str(e)}"
                        }
                    }
                },
                "timestamp": time.time(),
                "uptime": time.time() - self.start_time
            }
    
    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """
        Get a snapshot of current metrics.
        
        Returns:
            Metrics snapshot
        """
        try:
            # This is a simplified representation since Prometheus metrics
            # aren't directly accessible in this way. In a real implementation,
            # you would want to build this from the actual metric values.
            
            # Get some key metrics if available
            metrics_snapshot = {
                "api_requests": {},
                "dht_operations": {},
                "ipns_operations": {},
                "dag_operations": {},
                "content": {
                    "pins_count": 0
                },
                "connection_pool": {
                    "total": 0,
                    "active": 0,
                    "idle": 0
                }
            }
            
            # Add connection pool metrics
            if hasattr(self.advanced_ipfs, "connection_pool"):
                pool = self.advanced_ipfs.connection_pool
                
                if hasattr(pool, "_connections") and hasattr(pool, "_lock"):
                    with pool._lock:
                        total = len(pool._connections)
                        active = sum(1 for conn in pool._connections if conn.in_use)
                        idle = total - active
                        
                        metrics_snapshot["connection_pool"] = {
                            "total": total,
                            "active": active,
                            "idle": idle
                        }
            
            # Get performance metrics from advanced IPFS operations
            metrics_result = self.advanced_ipfs.get_metrics()
            if metrics_result.get("success", False):
                metrics_data = metrics_result.get("metrics", {})
                
                # Add DHT metrics
                if "dht" in metrics_data:
                    metrics_snapshot["dht_operations"] = metrics_data["dht"]
                
                # Add IPNS metrics
                if "ipns" in metrics_data:
                    metrics_snapshot["ipns_operations"] = metrics_data["ipns"]
                
                # Add DAG metrics
                if "dag" in metrics_data:
                    metrics_snapshot["dag_operations"] = metrics_data["dag"]
            
            return {
                "success": True,
                "metrics": metrics_snapshot,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error getting metrics snapshot: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": time.time()
            }
    
    def shutdown(self):
        """Perform cleanup and shutdown."""
        logger.info("Shutting down IPFS monitoring integration")
        
        # Stop metrics collection
        self.should_stop = True
        if self.collection_thread.is_alive():
            self.collection_thread.join(timeout=2.0)
        
        logger.info("IPFS monitoring integration shut down")


class IPFSMonitoringRouter:
    """
    FastAPI router for IPFS monitoring endpoints.
    
    This class provides API endpoints for health checking and metrics.
    """
    
    def __init__(self, monitoring_integration: IPFSMonitoringIntegration):
        """
        Initialize the monitoring router.
        
        Args:
            monitoring_integration: IPFS monitoring integration instance
        """
        self.monitoring = monitoring_integration
        logger.info("IPFS Monitoring Router initialized")
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Health check endpoint
        router.add_api_route(
            "/ipfs/health",
            self.health_check,
            methods=["GET"],
            response_model=HealthCheckResponse,
            summary="Check IPFS health",
            description="Check the health of the IPFS system",
        )
        
        # Plain text health check for simple monitoring
        router.add_api_route(
            "/ipfs/health/plain",
            self.health_check_plain,
            methods=["GET"],
            response_class=Response,
            summary="Check IPFS health (plain text)",
            description="Check the health of the IPFS system (returns plain text)",
        )
        
        # Metrics snapshot endpoint
        router.add_api_route(
            "/ipfs/metrics",
            self.get_metrics,
            methods=["GET"],
            response_model=MetricsResponse,
            summary="Get IPFS metrics",
            description="Get a snapshot of current IPFS metrics",
        )
        
        logger.info("IPFS Monitoring Router routes registered")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Health check endpoint.
        
        Returns:
            Health check results
        """
        return await self.monitoring.check_health()
    
    async def health_check_plain(self) -> Response:
        """
        Plain text health check endpoint.
        
        Returns:
            Plain text response with health status
        """
        health_result = await self.monitoring.check_health()
        
        # Create a simple plain text response
        status = health_result["status"]
        version = health_result["version"]
        uptime = health_result["uptime"]
        
        # Return appropriate status code based on health
        status_code = 200
        if status == "degraded":
            status_code = 429  # Too Many Requests
        elif status == "critical":
            status_code = 503  # Service Unavailable
        
        # Build plain text response
        text = f"status={status}\nversion={version}\nuptime={uptime:.2f}s\n"
        
        # Add service statuses
        for service_name, service_info in health_result["services"].items():
            text += f"{service_name}={service_info['status']}\n"
        
        return Response(
            content=text,
            media_type="text/plain",
            status_code=status_code
        )
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get metrics endpoint.
        
        Returns:
            Metrics snapshot
        """
        return self.monitoring.get_metrics_snapshot()


# Function to create router with IPFS monitoring
def create_monitoring_router(
    config: Optional[Dict[str, Any]] = None,
    start_metrics_server: bool = True,
    metrics_host: str = "localhost",
    metrics_port: int = 9090
) -> tuple[APIRouter, IPFSMonitoringIntegration]:
    """
    Create a FastAPI router with IPFS monitoring endpoints.
    
    Args:
        config: Configuration options
        start_metrics_server: Whether to start the Prometheus metrics server
        metrics_host: Host to bind the metrics server to
        metrics_port: Port to bind the metrics server to
        
    Returns:
        Tuple of (router, monitoring_integration)
    """
    # Create monitoring integration
    monitoring = IPFSMonitoringIntegration(
        config=config,
        start_metrics_server=start_metrics_server,
        metrics_host=metrics_host,
        metrics_port=metrics_port
    )
    
    # Create router
    router = APIRouter(tags=["IPFS Monitoring"])
    router_handler = IPFSMonitoringRouter(monitoring)
    router_handler.register_routes(router)
    
    return router, monitoring


# Middleware for tracking IPFS API requests
async def ipfs_monitoring_middleware(request: Request, call_next):
    """
    Middleware for tracking IPFS API requests.
    
    Args:
        request: FastAPI request
        call_next: Next middleware or endpoint
        
    Returns:
        Response from the next middleware or endpoint
    """
    # Only track IPFS-related endpoints
    if "/ipfs/" in request.url.path:
        method = request.method
        endpoint = request.url.path
        
        # Get monitoring integration if available
        monitoring = None
        if hasattr(request.app.state, "ipfs_monitoring"):
            monitoring = request.app.state.ipfs_monitoring
        
        # Track request timing
        start_time = time.time()
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Track successful request
            if monitoring:
                error = None
                if response.status_code >= 400:
                    error = f"http_{response.status_code}"
                monitoring.track_api_request(method, endpoint, duration, error)
            
            return response
        except Exception as e:
            # Track failed request
            duration = time.time() - start_time
            if monitoring:
                monitoring.track_api_request(
                    method, endpoint, duration, error=type(e).__name__
                )
            raise
    else:
        # Pass through for non-IPFS endpoints
        return await call_next(request)


# Define a function to initialize everything for a FastAPI app
def init_ipfs_monitoring(
    app,
    config: Optional[Dict[str, Any]] = None,
    start_metrics_server: bool = True,
    metrics_host: str = "localhost",
    metrics_port: int = 9090,
    add_middleware: bool = True
) -> IPFSMonitoringIntegration:
    """
    Initialize IPFS monitoring for a FastAPI app.
    
    Args:
        app: FastAPI app
        config: Configuration options
        start_metrics_server: Whether to start the Prometheus metrics server
        metrics_host: Host to bind the metrics server to
        metrics_port: Port to bind the metrics server to
        add_middleware: Whether to add the monitoring middleware
        
    Returns:
        IPFS monitoring integration
    """
    # Create router and monitoring integration
    router, monitoring = create_monitoring_router(
        config, start_metrics_server, metrics_host, metrics_port
    )
    
    # Add router to app
    app.include_router(router)
    
    # Store monitoring integration in app state
    app.state.ipfs_monitoring = monitoring
    
    # Add middleware if requested
    if add_middleware:
        # FastAPI doesn't support middleware functions directly, we need to use middleware decorator
        from starlette.middleware.base import BaseHTTPMiddleware
        
        class IPFSMonitoringMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                return await ipfs_monitoring_middleware(request, call_next)
        
        app.add_middleware(IPFSMonitoringMiddleware)
    
    # Add shutdown event handler
    @app.on_event("shutdown")
    async def shutdown_monitoring():
        monitoring.shutdown()
    
    return monitoring