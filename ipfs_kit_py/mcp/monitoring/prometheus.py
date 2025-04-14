"""
Prometheus metrics exporter for MCP server.

This module implements the Prometheus metrics integration
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).
"""

import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Set, Callable
from fastapi import FastAPI, Request, Response
from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    REGISTRY, CONTENT_TYPE_LATEST, generate_latest,
    CollectorRegistry, multiprocess
)
import os
import psutil
import platform
from datetime import datetime

logger = logging.getLogger(__name__)

class PrometheusMetrics:
    """
    Prometheus metrics exporter for MCP server.
    
    This class handles metrics collection and exposure for monitoring
    the MCP server's performance and health.
    """
    
    def __init__(self, app: FastAPI = None, 
                 enable_default_metrics: bool = True,
                 metrics_path: str = "/metrics",
                 multiprocess_mode: bool = False):
        """
        Initialize the Prometheus metrics exporter.
        
        Args:
            app: FastAPI application
            enable_default_metrics: Whether to enable default system metrics
            metrics_path: Path for the metrics endpoint
            multiprocess_mode: Whether to use multiprocess mode
        """
        self.app = app
        self.enable_default_metrics = enable_default_metrics
        self.metrics_path = metrics_path
        self.multiprocess_mode = multiprocess_mode
        
        # Custom registry for metrics
        if self.multiprocess_mode:
            self.registry = CollectorRegistry()
            multiprocess.MultiProcessCollector(self.registry)
        else:
            self.registry = REGISTRY
        
        # HTTP metrics
        self.http_requests_total = Counter(
            "mcp_http_requests_total",
            "Total number of HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry
        )
        
        self.http_request_duration_seconds = Histogram(
            "mcp_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, 60.0, float("inf")),
            registry=self.registry
        )
        
        self.http_requests_in_flight = Gauge(
            "mcp_http_requests_in_flight",
            "Number of HTTP requests currently being processed",
            ["method"],
            registry=self.registry
        )
        
        # API metrics
        self.api_operations_total = Counter(
            "mcp_api_operations_total",
            "Total number of API operations",
            ["operation", "backend", "status"],
            registry=self.registry
        )
        
        self.api_operation_duration_seconds = Histogram(
            "mcp_api_operation_duration_seconds",
            "API operation duration in seconds",
            ["operation", "backend"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf")),
            registry=self.registry
        )
        
        # Storage backend metrics
        self.backend_status = Gauge(
            "mcp_backend_status",
            "Storage backend status (1=up, 0=down)",
            ["backend"],
            registry=self.registry
        )
        
        self.backend_operations_total = Counter(
            "mcp_backend_operations_total",
            "Total number of storage backend operations",
            ["backend", "operation", "status"],
            registry=self.registry
        )
        
        self.backend_operation_duration_seconds = Histogram(
            "mcp_backend_operation_duration_seconds",
            "Storage backend operation duration in seconds",
            ["backend", "operation"],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, float("inf")),
            registry=self.registry
        )
        
        self.backend_items_count = Gauge(
            "mcp_backend_items_count",
            "Number of items in storage backend",
            ["backend"],
            registry=self.registry
        )
        
        self.backend_bytes_stored = Gauge(
            "mcp_backend_bytes_stored",
            "Number of bytes stored in storage backend",
            ["backend"],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_hit_total = Counter(
            "mcp_cache_hit_total",
            "Total number of cache hits",
            ["cache_type"],
            registry=self.registry
        )
        
        self.cache_miss_total = Counter(
            "mcp_cache_miss_total",
            "Total number of cache misses",
            ["cache_type"],
            registry=self.registry
        )
        
        self.cache_size = Gauge(
            "mcp_cache_size",
            "Current size of cache in items",
            ["cache_type"],
            registry=self.registry
        )
        
        self.cache_bytes = Gauge(
            "mcp_cache_bytes",
            "Current size of cache in bytes",
            ["cache_type"],
            registry=self.registry
        )
        
        # Auth metrics
        self.auth_login_total = Counter(
            "mcp_auth_login_total",
            "Total number of login attempts",
            ["status"],
            registry=self.registry
        )
        
        self.auth_active_sessions = Gauge(
            "mcp_auth_active_sessions",
            "Number of active user sessions",
            registry=self.registry
        )
        
        self.auth_api_keys_total = Counter(
            "mcp_auth_api_keys_total",
            "Total number of API key operations",
            ["operation"],
            registry=self.registry
        )
        
        # Migration metrics
        self.migration_operations_total = Counter(
            "mcp_migration_operations_total",
            "Total number of migration operations",
            ["operation", "source", "target", "status"],
            registry=self.registry
        )
        
        self.migration_in_progress = Gauge(
            "mcp_migration_in_progress",
            "Number of migrations currently in progress",
            registry=self.registry
        )
        
        self.migration_bytes_total = Counter(
            "mcp_migration_bytes_total",
            "Total number of bytes migrated",
            ["source", "target"],
            registry=self.registry
        )
        
        self.migration_duration_seconds = Histogram(
            "mcp_migration_duration_seconds",
            "Migration operation duration in seconds",
            ["source", "target"],
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0, float("inf")),
            registry=self.registry
        )
        
        # System metrics
        if enable_default_metrics:
            self._setup_system_metrics()
        
        # Build info
        self.build_info = Info(
            "mcp_build_info",
            "MCP server build information",
            registry=self.registry
        )
        
        # If app is provided, set up metrics endpoints
        if app:
            self.setup_app(app)
    
    def _setup_system_metrics(self):
        """Set up system-level metrics."""
        # CPU metrics
        self.cpu_usage_percent = Gauge(
            "mcp_cpu_usage_percent",
            "CPU usage in percent",
            registry=self.registry
        )
        
        self.cpu_cores = Gauge(
            "mcp_cpu_cores",
            "Number of CPU cores",
            registry=self.registry
        )
        self.cpu_cores.set(psutil.cpu_count(logical=True))
        
        # Memory metrics
        self.memory_usage_bytes = Gauge(
            "mcp_memory_usage_bytes",
            "Memory usage in bytes",
            registry=self.registry
        )
        
        self.memory_total_bytes = Gauge(
            "mcp_memory_total_bytes",
            "Total memory in bytes",
            registry=self.registry
        )
        self.memory_total_bytes.set(psutil.virtual_memory().total)
        
        # Disk metrics
        self.disk_usage_bytes = Gauge(
            "mcp_disk_usage_bytes",
            "Disk usage in bytes",
            ["mountpoint"],
            registry=self.registry
        )
        
        self.disk_total_bytes = Gauge(
            "mcp_disk_total_bytes",
            "Total disk space in bytes",
            ["mountpoint"],
            registry=self.registry
        )
        
        # Initialize disk metrics for root partition
        root_disk = psutil.disk_usage("/")
        self.disk_total_bytes.labels(mountpoint="/").set(root_disk.total)
        
        # Process metrics
        self.process_cpu_seconds_total = Counter(
            "mcp_process_cpu_seconds_total",
            "Total user and system CPU time spent in seconds",
            registry=self.registry
        )
        
        self.process_memory_bytes = Gauge(
            "mcp_process_memory_bytes",
            "Process memory usage in bytes",
            registry=self.registry
        )
        
        self.process_open_fds = Gauge(
            "mcp_process_open_fds",
            "Number of open file descriptors",
            registry=self.registry
        )
        
        self.process_start_time_seconds = Gauge(
            "mcp_process_start_time_seconds",
            "Start time of the process since Unix epoch in seconds",
            registry=self.registry
        )
        self.process_start_time_seconds.set(psutil.Process().create_time())
        
        # Start background task to update system metrics
        self._start_system_metrics_updater()
    
    async def _update_system_metrics(self):
        """Update system metrics in the background."""
        while True:
            try:
                # Update CPU metrics
                self.cpu_usage_percent.set(psutil.cpu_percent(interval=None))
                
                # Update memory metrics
                memory = psutil.virtual_memory()
                self.memory_usage_bytes.set(memory.used)
                
                # Update disk metrics
                disk = psutil.disk_usage("/")
                self.disk_usage_bytes.labels(mountpoint="/").set(disk.used)
                
                # Update process metrics
                process = psutil.Process()
                self.process_cpu_seconds_total.inc(
                    process.cpu_times().user + process.cpu_times().system
                )
                self.process_memory_bytes.set(process.memory_info().rss)
                self.process_open_fds.set(process.num_fds() if hasattr(process, 'num_fds') else 0)
            except Exception as e:
                logger.error(f"Error updating system metrics: {e}")
            
            # Sleep for 15 seconds before updating again
            await asyncio.sleep(15)
    
    def _start_system_metrics_updater(self):
        """Start the background task for updating system metrics."""
        asyncio.create_task(self._update_system_metrics())
    
    def setup_app(self, app: FastAPI):
        """
        Set up metrics endpoints and middleware for a FastAPI application.
        
        Args:
            app: FastAPI application
        """
        self.app = app
        
        # Add metrics endpoint
        @app.get(self.metrics_path)
        async def metrics():
            return Response(
                content=generate_latest(self.registry),
                media_type=CONTENT_TYPE_LATEST
            )
        
        # Add middleware for tracking HTTP metrics
        @app.middleware("http")
        async def metrics_middleware(request: Request, call_next):
            # Track in-flight requests
            method = request.method
            endpoint = request.url.path
            
            # Exclude metrics endpoint from metrics to avoid recursion
            if endpoint == self.metrics_path:
                return await call_next(request)
            
            # Increment in-flight requests
            self.http_requests_in_flight.labels(method=method).inc()
            
            # Track request duration
            start_time = time.time()
            
            try:
                response = await call_next(request)
                
                # Record request metrics
                status_code = response.status_code
                duration = time.time() - start_time
                
                self.http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code
                ).inc()
                
                self.http_request_duration_seconds.labels(
                    method=method,
                    endpoint=endpoint
                ).observe(duration)
                
                return response
            except Exception as e:
                # Record error metrics
                self.http_requests_total.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=500
                ).inc()
                
                # Re-raise the exception
                raise e
            finally:
                # Decrement in-flight requests
                self.http_requests_in_flight.labels(method=method).dec()
    
    def record_api_operation(self, operation: str, backend: str, start_time: float, 
                            status: str = "success"):
        """
        Record API operation metrics.
        
        Args:
            operation: Operation name
            backend: Backend name
            start_time: Start time of the operation
            status: Operation status
        """
        duration = time.time() - start_time
        
        self.api_operations_total.labels(
            operation=operation,
            backend=backend,
            status=status
        ).inc()
        
        self.api_operation_duration_seconds.labels(
            operation=operation,
            backend=backend
        ).observe(duration)
    
    def record_backend_operation(self, backend: str, operation: str, start_time: float,
                               status: str = "success"):
        """
        Record storage backend operation metrics.
        
        Args:
            backend: Backend name
            operation: Operation name
            start_time: Start time of the operation
            status: Operation status
        """
        duration = time.time() - start_time
        
        self.backend_operations_total.labels(
            backend=backend,
            operation=operation,
            status=status
        ).inc()
        
        self.backend_operation_duration_seconds.labels(
            backend=backend,
            operation=operation
        ).observe(duration)
    
    def set_backend_status(self, backend: str, available: bool):
        """
        Set storage backend status.
        
        Args:
            backend: Backend name
            available: Whether the backend is available
        """
        self.backend_status.labels(backend=backend).set(1 if available else 0)
    
    def set_backend_items_count(self, backend: str, count: int):
        """
        Set storage backend items count.
        
        Args:
            backend: Backend name
            count: Number of items
        """
        self.backend_items_count.labels(backend=backend).set(count)
    
    def set_backend_bytes_stored(self, backend: str, bytes_count: int):
        """
        Set storage backend bytes stored.
        
        Args:
            backend: Backend name
            bytes_count: Number of bytes
        """
        self.backend_bytes_stored.labels(backend=backend).set(bytes_count)
    
    def record_cache_operation(self, cache_type: str, hit: bool):
        """
        Record cache operation metrics.
        
        Args:
            cache_type: Type of cache
            hit: Whether the operation was a hit
        """
        if hit:
            self.cache_hit_total.labels(cache_type=cache_type).inc()
        else:
            self.cache_miss_total.labels(cache_type=cache_type).inc()
    
    def set_cache_size(self, cache_type: str, size: int):
        """
        Set cache size metrics.
        
        Args:
            cache_type: Type of cache
            size: Number of items in cache
        """
        self.cache_size.labels(cache_type=cache_type).set(size)
    
    def set_cache_bytes(self, cache_type: str, bytes_count: int):
        """
        Set cache bytes metrics.
        
        Args:
            cache_type: Type of cache
            bytes_count: Number of bytes in cache
        """
        self.cache_bytes.labels(cache_type=cache_type).set(bytes_count)
    
    def record_auth_login(self, success: bool):
        """
        Record authentication login metrics.
        
        Args:
            success: Whether the login was successful
        """
        self.auth_login_total.labels(status="success" if success else "failure").inc()
    
    def set_auth_active_sessions(self, count: int):
        """
        Set active sessions metrics.
        
        Args:
            count: Number of active sessions
        """
        self.auth_active_sessions.set(count)
    
    def record_auth_api_key_operation(self, operation: str):
        """
        Record API key operation metrics.
        
        Args:
            operation: Operation name
        """
        self.auth_api_keys_total.labels(operation=operation).inc()
    
    def record_migration_operation(self, operation: str, source: str, target: str,
                                 status: str = "success"):
        """
        Record migration operation metrics.
        
        Args:
            operation: Operation name
            source: Source backend
            target: Target backend
            status: Operation status
        """
        self.migration_operations_total.labels(
            operation=operation,
            source=source,
            target=target,
            status=status
        ).inc()
    
    def record_migration_bytes(self, source: str, target: str, bytes_count: int):
        """
        Record migration bytes metrics.
        
        Args:
            source: Source backend
            target: Target backend
            bytes_count: Number of bytes migrated
        """
        self.migration_bytes_total.labels(
            source=source,
            target=target
        ).inc(bytes_count)
    
    def record_migration_duration(self, source: str, target: str, start_time: float):
        """
        Record migration duration metrics.
        
        Args:
            source: Source backend
            target: Target backend
            start_time: Start time of the migration
        """
        duration = time.time() - start_time
        
        self.migration_duration_seconds.labels(
            source=source,
            target=target
        ).observe(duration)
    
    def set_migration_in_progress(self, count: int):
        """
        Set migrations in progress metrics.
        
        Args:
            count: Number of migrations in progress
        """
        self.migration_in_progress.set(count)
    
    def set_build_info(self, version: str, git_commit: str = None, 
                      build_date: str = None, python_version: str = None):
        """
        Set build information metrics.
        
        Args:
            version: MCP server version
            git_commit: Git commit hash
            build_date: Build date
            python_version: Python version
        """
        info = {
            "version": version,
            "python_version": python_version or platform.python_version(),
            "platform": platform.platform()
        }
        
        if git_commit:
            info["git_commit"] = git_commit
        
        if build_date:
            info["build_date"] = build_date
        else:
            info["build_date"] = datetime.now().isoformat()
        
        self.build_info.info(info)


class MetricsService:
    """
    Service for managing metrics and monitoring.
    
    This service provides a unified interface for collecting and
    reporting metrics from various components of the MCP server.
    """
    
    def __init__(self, app: FastAPI = None):
        """
        Initialize the metrics service.
        
        Args:
            app: FastAPI application
        """
        self.prometheus = PrometheusMetrics(app=app)
        self.metrics_callbacks = []
        
        # Metrics collector task
        self.collector_task = None
    
    async def start(self):
        """Start the metrics service."""
        logger.info("Starting metrics service")
        
        # Set build info
        self.prometheus.set_build_info(
            version="0.1.0",  # Replace with actual version
            python_version=platform.python_version(),
            build_date=datetime.now().isoformat()
        )
        
        # Start metrics collector task
        self.collector_task = asyncio.create_task(self._collect_metrics())
        
        logger.info("Metrics service started")
    
    async def stop(self):
        """Stop the metrics service."""
        logger.info("Stopping metrics service")
        
        # Cancel metrics collector task
        if self.collector_task:
            self.collector_task.cancel()
            try:
                await self.collector_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Metrics service stopped")
    
    def register_metrics_callback(self, callback: Callable[[], Dict[str, Any]]):
        """
        Register a callback for collecting metrics.
        
        Args:
            callback: Function that returns a dictionary of metrics
        """
        self.metrics_callbacks.append(callback)
    
    async def _collect_metrics(self):
        """Collect metrics from registered callbacks."""
        while True:
            try:
                # Collect metrics from all registered callbacks
                for callback in self.metrics_callbacks:
                    try:
                        metrics = callback()
                        self._process_metrics(metrics)
                    except Exception as e:
                        logger.error(f"Error collecting metrics from callback: {e}")
            except Exception as e:
                logger.error(f"Error in metrics collector: {e}")
            
            # Sleep for 15 seconds before collecting again
            await asyncio.sleep(15)
    
    def _process_metrics(self, metrics: Dict[str, Any]):
        """
        Process metrics from a callback.
        
        Args:
            metrics: Dictionary of metrics
        """
        # Process backend metrics
        if "backends" in metrics:
            for backend, backend_metrics in metrics["backends"].items():
                # Update backend status
                if "available" in backend_metrics:
                    self.prometheus.set_backend_status(backend, backend_metrics["available"])
                
                # Update backend items count
                if "items_count" in backend_metrics:
                    self.prometheus.set_backend_items_count(backend, backend_metrics["items_count"])
                
                # Update backend bytes stored
                if "bytes_stored" in backend_metrics:
                    self.prometheus.set_backend_bytes_stored(backend, backend_metrics["bytes_stored"])
        
        # Process cache metrics
        if "caches" in metrics:
            for cache_type, cache_metrics in metrics["caches"].items():
                # Update cache size
                if "size" in cache_metrics:
                    self.prometheus.set_cache_size(cache_type, cache_metrics["size"])
                
                # Update cache bytes
                if "bytes" in cache_metrics:
                    self.prometheus.set_cache_bytes(cache_type, cache_metrics["bytes"])
        
        # Process auth metrics
        if "auth" in metrics:
            auth_metrics = metrics["auth"]
            
            # Update active sessions
            if "active_sessions" in auth_metrics:
                self.prometheus.set_auth_active_sessions(auth_metrics["active_sessions"])
        
        # Process migration metrics
        if "migrations" in metrics:
            migration_metrics = metrics["migrations"]
            
            # Update migrations in progress
            if "in_progress" in migration_metrics:
                self.prometheus.set_migration_in_progress(migration_metrics["in_progress"])
    
    def instrument_api_operation(self, operation: str, backend: str):
        """
        Create a decorator for instrumenting API operations.
        
        Args:
            operation: Operation name
            backend: Backend name
            
        Returns:
            Decorator function
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    self.prometheus.record_api_operation(operation, backend, start_time, "success")
                    return result
                except Exception as e:
                    self.prometheus.record_api_operation(operation, backend, start_time, "error")
                    raise e
            return wrapper
        return decorator
    
    def instrument_backend_operation(self, backend: str, operation: str):
        """
        Create a decorator for instrumenting backend operations.
        
        Args:
            backend: Backend name
            operation: Operation name
            
        Returns:
            Decorator function
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    self.prometheus.record_backend_operation(backend, operation, start_time, "success")
                    return result
                except Exception as e:
                    self.prometheus.record_backend_operation(backend, operation, start_time, "error")
                    raise e
            return wrapper
        return decorator
    
    def instrument_migration_operation(self, operation: str, source: str, target: str):
        """
        Create a decorator for instrumenting migration operations.
        
        Args:
            operation: Operation name
            source: Source backend
            target: Target backend
            
        Returns:
            Decorator function
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    self.prometheus.record_migration_operation(operation, source, target, "success")
                    self.prometheus.record_migration_duration(source, target, start_time)
                    
                    # Record migrated bytes if available
                    if hasattr(result, "size_bytes"):
                        self.prometheus.record_migration_bytes(source, target, result.size_bytes)
                    elif isinstance(result, dict) and "size_bytes" in result:
                        self.prometheus.record_migration_bytes(source, target, result["size_bytes"])
                    
                    return result
                except Exception as e:
                    self.prometheus.record_migration_operation(operation, source, target, "error")
                    raise e
            return wrapper
        return decorator