"""
Prometheus metrics exporter for MCP server monitoring.

This module provides Prometheus metrics integration for the MCP server,
allowing collection and exposure of performance, health, and usage metrics.
"""

import os
import time
import logging
import threading
import json
from typing import Dict, Any, Optional, List, Callable, Set

# Configure logger
logger = logging.getLogger(__name__)

try:
    import prometheus_client
    from prometheus_client import Counter, Gauge, Histogram, Summary, Info, Enum
    from prometheus_client.exposition import start_http_server
    PROMETHEUS_AVAILABLE = True
    logger.info("Prometheus client library available")
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client library not available. Install with: pip install prometheus-client")


class PrometheusExporter:
    """
    Prometheus metrics exporter for MCP server.
    
    This class provides methods to expose various metrics from the MCP server
    to a Prometheus monitoring system.
    """
    
    def __init__(self, options: Optional[Dict[str, Any]] = None):
        """
        Initialize the Prometheus exporter.
        
        Args:
            options: Configuration options
        """
        if not PROMETHEUS_AVAILABLE:
            raise ImportError("Prometheus client library not available")
            
        self.options = options or {}
        
        # Configure metrics port and path
        self.metrics_port = self.options.get("metrics_port", 9090)
        self.metrics_path = self.options.get("metrics_path", "/metrics")
        
        # Metric Registry
        self.registry = prometheus_client.CollectorRegistry()
        
        # Internal state
        self._server_thread = None
        self._running = False
        self._server_lock = threading.Lock()
        self._storage_manager = None 
        self._monitoring_system = None
        
        # Initialize metrics
        self._initialize_metrics()
        
    def _initialize_metrics(self):
        """Initialize Prometheus metrics."""
        # System metrics
        self.system_info = Info(
            'mcp_system_info', 
            'MCP server system information',
            registry=self.registry
        )
        
        self.system_uptime = Gauge(
            'mcp_system_uptime_seconds',
            'MCP server uptime in seconds',
            registry=self.registry
        )
        
        # API metrics
        self.api_requests_total = Counter(
            'mcp_api_requests_total',
            'Total API requests processed',
            ['endpoint', 'method', 'status'],
            registry=self.registry
        )
        
        self.api_request_duration = Histogram(
            'mcp_api_request_duration_seconds',
            'API request duration in seconds',
            ['endpoint', 'method'],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')),
            registry=self.registry
        )
        
        # Storage backend metrics
        self.backend_status = Enum(
            'mcp_backend_status',
            'Storage backend health status',
            ['backend'],
            states=['healthy', 'degraded', 'unhealthy', 'unknown'],
            registry=self.registry
        )
        
        self.backend_operations_total = Counter(
            'mcp_backend_operations_total',
            'Total operations performed on storage backends',
            ['backend', 'operation', 'status'],
            registry=self.registry
        )
        
        self.backend_operation_duration = Histogram(
            'mcp_backend_operation_duration_seconds',
            'Storage operation duration in seconds',
            ['backend', 'operation'],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float('inf')),
            registry=self.registry
        )
        
        self.backend_capacity_bytes = Gauge(
            'mcp_backend_capacity_bytes',
            'Storage backend capacity in bytes',
            ['backend', 'type'],  # type can be 'total', 'used', 'available'
            registry=self.registry
        )
        
        # Content metrics
        self.content_count = Gauge(
            'mcp_content_count',
            'Number of content items tracked by MCP',
            ['backend'],
            registry=self.registry
        )
        
        self.content_size_bytes = Gauge(
            'mcp_content_size_bytes',
            'Total size of content tracked by MCP in bytes',
            ['backend'],
            registry=self.registry
        )
        
    def start(self, storage_manager=None, monitoring_system=None):
        """
        Start the Prometheus metrics server.
        
        Args:
            storage_manager: Optional UnifiedStorageManager instance
            monitoring_system: Optional MonitoringSystem instance
            
        Returns:
            True if server was started successfully
        """
        with self._server_lock:
            if self._running:
                logger.info("Prometheus metrics server already running")
                return False
            
            # Store references to storage manager and monitoring system
            self._storage_manager = storage_manager
            self._monitoring_system = monitoring_system
            
            # Update system info
            self._update_system_info()
            
            try:
                # Start the metrics server
                start_http_server(
                    port=self.metrics_port,
                    addr='0.0.0.0',
                    registry=self.registry
                )
                
                self._running = True
                self._start_time = time.time()
                
                # Start background metrics update thread
                self._server_thread = threading.Thread(
                    target=self._metrics_update_loop,
                    name="PrometheusMetricsUpdater",
                    daemon=True
                )
                self._server_thread.start()
                
                logger.info(f"Started Prometheus metrics server on port {self.metrics_port}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {e}")
                return False
            
    def stop(self):
        """
        Stop the Prometheus metrics server.
        
        Returns:
            True if server was stopped successfully
        """
        with self._server_lock:
            if not self._running:
                return False
            
            self._running = False
            
            # The HTTP server runs in the background and cannot be stopped directly
            # We can only stop our update thread
            if self._server_thread:
                self._server_thread.join(timeout=5)
                
            logger.info("Stopped Prometheus metrics updater")
            return True
            
    def _metrics_update_loop(self):
        """Background thread for updating metrics regularly."""
        logger.info("Metrics update thread started")
        
        try:
            while self._running:
                try:
                    # Update uptime
                    self.system_uptime.set(time.time() - self._start_time)
                    
                    # Update backend metrics if monitoring system available
                    if self._monitoring_system:
                        self._update_backend_metrics()
                        
                    # Update content metrics if storage manager available
                    if self._storage_manager:
                        self._update_content_metrics()
                    
                    # Sleep for a bit (update frequency)
                    time.sleep(15)  # 15 seconds between updates
                    
                except Exception as e:
                    logger.error(f"Error in metrics update loop: {e}")
                    time.sleep(60)  # Longer sleep on error
                    
        except Exception as e:
            logger.exception(f"Fatal error in metrics update thread: {e}")
        finally:
            logger.info("Metrics update thread stopped")
            
    def _update_system_info(self):
        """Update system information metrics."""
        try:
            # Get system info
            info = {
                'version': os.environ.get('MCP_VERSION', 'unknown'),
                'hostname': os.environ.get('HOSTNAME', 'unknown'),
                'python_version': os.environ.get('PYTHON_VERSION', 'unknown'),
                'start_time': str(int(time.time())),
            }
            
            # Update info metric
            self.system_info.info(info)
            
        except Exception as e:
            logger.error(f"Error updating system info metrics: {e}")
            
    def _update_backend_metrics(self):
        """Update backend metrics from monitoring system."""
        try:
            # Get all metrics from monitoring system
            all_metrics = self._monitoring_system.get_all_metrics()
            
            # Update backend status
            for backend, status_info in all_metrics["backend_status"]["backends"].items():
                self.backend_status.labels(backend=backend).state(status_info["status"])
                
            # Update backend capacity metrics
            for backend, capacity in all_metrics["capacity_metrics"]["backends"].items():
                if "total" in capacity:
                    self.backend_capacity_bytes.labels(backend=backend, type="total").set(capacity["total"])
                
                if "used" in capacity:
                    self.backend_capacity_bytes.labels(backend=backend, type="used").set(capacity["used"])
                
                if "available" in capacity:
                    self.backend_capacity_bytes.labels(backend=backend, type="available").set(capacity["available"])
                elif "total" in capacity and "used" in capacity:
                    # Calculate available if not provided directly
                    available = capacity["total"] - capacity["used"]
                    self.backend_capacity_bytes.labels(backend=backend, type="available").set(available)
                
            # Update performance metrics
            for backend, ops in all_metrics["performance_metrics"]["performance_metrics"].items():
                for op_type, metrics in ops.items():
                    # Record average operation duration
                    if metrics["count"] > 0:
                        self.backend_operation_duration.labels(
                            backend=backend, 
                            operation=op_type
                        ).observe(metrics["avg_time"])
                        
                        # Calculate success/error counts based on rates
                        success_count = int(metrics["count"] * metrics["success_rate"])
                        error_count = metrics["count"] - success_count
                        
                        # Only increment if we detected new operations
                        # This avoids duplicating counts on restart
                        if hasattr(self, '_last_counts'):
                            last_key = f"{backend}:{op_type}"
                            
                            if last_key in self._last_counts:
                                last_count = self._last_counts[last_key]
                                if metrics["count"] > last_count:
                                    # Only count the difference since last check
                                    new_ops = metrics["count"] - last_count
                                    new_success = int(new_ops * metrics["success_rate"])
                                    new_error = new_ops - new_success
                                    
                                    # Update counters
                                    self.backend_operations_total.labels(
                                        backend=backend, 
                                        operation=op_type,
                                        status="success"
                                    ).inc(new_success)
                                    
                                    self.backend_operations_total.labels(
                                        backend=backend, 
                                        operation=op_type,
                                        status="error"
                                    ).inc(new_error)
                            
                            # Update last count
                            self._last_counts[last_key] = metrics["count"]
                        else:
                            # Initialize last counts dictionary
                            self._last_counts = {f"{backend}:{op_type}": metrics["count"]}
                        
        except Exception as e:
            logger.error(f"Error updating backend metrics: {e}")
            
    def _update_content_metrics(self):
        """Update content metrics from storage manager."""
        try:
            # Get content statistics by backend
            backend_counts = {}
            backend_sizes = {}
            
            # Initialize with zeros to ensure all backends are represented
            for backend_type in self._storage_manager.backends:
                backend_counts[backend_type.value] = 0
                backend_sizes[backend_type.value] = 0
            
            # Aggregate counts and sizes
            for content_id, content_ref in self._storage_manager.content_registry.items():
                size = content_ref.metadata.get("size", 0) or 0
                
                for backend_type in content_ref.backend_locations:
                    backend_name = backend_type.value
                    backend_counts[backend_name] = backend_counts.get(backend_name, 0) + 1
                    backend_sizes[backend_name] = backend_sizes.get(backend_name, 0) + size
            
            # Update metrics
            for backend, count in backend_counts.items():
                self.content_count.labels(backend=backend).set(count)
                
            for backend, size in backend_sizes.items():
                self.content_size_bytes.labels(backend=backend).set(size)
                
        except Exception as e:
            logger.error(f"Error updating content metrics: {e}")
    
    def record_api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """
        Record an API request for metrics.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            status_code: HTTP status code
            duration: Request duration in seconds
        """
        try:
            # Normalize the endpoint to avoid high cardinality
            # E.g., "/api/v0/content/123" becomes "/api/v0/content/{id}"
            normalized_endpoint = self._normalize_endpoint(endpoint)
            
            # Normalize the status code to a category
            status = self._normalize_status_code(status_code)
            
            # Increment request counter
            self.api_requests_total.labels(
                endpoint=normalized_endpoint,
                method=method,
                status=status
            ).inc()
            
            # Record request duration
            self.api_request_duration.labels(
                endpoint=normalized_endpoint,
                method=method
            ).observe(duration)
            
        except Exception as e:
            logger.error(f"Error recording API request metric: {e}")
            
    def _normalize_endpoint(self, endpoint: str) -> str:
        """
        Normalize an endpoint path to reduce cardinality.
        
        Args:
            endpoint: Raw endpoint path
            
        Returns:
            Normalized endpoint path
        """
        # Simple replacement of numeric IDs
        parts = endpoint.split('/')
        normalized_parts = []
        
        for part in parts:
            # Replace numeric IDs and UUIDs with placeholders
            if part.isdigit():
                normalized_parts.append("{id}")
            elif len(part) >= 32 and all(c in "0123456789abcdef-" for c in part.lower()):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)
                
        return '/'.join(normalized_parts)
        
    def _normalize_status_code(self, status_code: int) -> str:
        """
        Normalize HTTP status code to a category.
        
        Args:
            status_code: HTTP status code
            
        Returns:
            Status category
        """
        if 200 <= status_code < 300:
            return "success"
        elif 300 <= status_code < 400:
            return "redirect"
        elif 400 <= status_code < 500:
            return "client_error"
        elif 500 <= status_code < 600:
            return "server_error"
        else:
            return "unknown"
            
    def record_backend_operation(
        self,
        backend_type: str,
        operation: str,
        success: bool,
        duration: float
    ):
        """
        Record a backend operation for metrics.
        
        Args:
            backend_type: Backend type
            operation: Operation type
            success: Whether operation was successful
            duration: Operation duration in seconds
        """
        try:
            # Increment operation counter
            self.backend_operations_total.labels(
                backend=backend_type,
                operation=operation,
                status="success" if success else "error"
            ).inc()
            
            # Record operation duration
            self.backend_operation_duration.labels(
                backend=backend_type,
                operation=operation
            ).observe(duration)
            
        except Exception as e:
            logger.error(f"Error recording backend operation metric: {e}")
            
    def update_backend_capacity(self, backend_type: str, total: int, used: int, available: int):
        """
        Update backend capacity metrics.
        
        Args:
            backend_type: Backend type
            total: Total capacity in bytes
            used: Used capacity in bytes
            available: Available capacity in bytes
        """
        try:
            self.backend_capacity_bytes.labels(backend=backend_type, type="total").set(total)
            self.backend_capacity_bytes.labels(backend=backend_type, type="used").set(used)
            self.backend_capacity_bytes.labels(backend=backend_type, type="available").set(available)
            
        except Exception as e:
            logger.error(f"Error updating backend capacity metric: {e}")
            
    def update_backend_status(self, backend_type: str, status: str):
        """
        Update backend status metric.
        
        Args:
            backend_type: Backend type
            status: Status value
        """
        try:
            self.backend_status.labels(backend=backend_type).state(status)
            
        except Exception as e:
            logger.error(f"Error updating backend status metric: {e}")