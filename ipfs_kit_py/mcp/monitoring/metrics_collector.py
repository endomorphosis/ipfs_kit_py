"""
Metrics Collector for MCP Server.

This module provides a central collector for various metrics throughout the system,
integrating with Prometheus for exporting metrics and providing APIs for components
to report their metrics.
"""

import logging
import time
import threading
import os
import psutil
from typing import Dict, List, Any, Optional, Callable, Set, Union

# Import local modules
from ipfs_kit_py.mcp.monitoring.prometheus_exporter import get_exporter, PrometheusExporter
from ipfs_kit_py.mcp.monitoring.health_checker import get_health_checker, HealthStatus

# Configure logger
logger = logging.getLogger(__name__)

class MetricsCollector:
    """
    Central collector for MCP metrics.
    
    Provides a unified API for reporting metrics from various components,
    integrates with Prometheus for metrics export, and includes default
    collectors for system-level metrics.
    """
    
    def __init__(
        self,
        prometheus_exporter: Optional[PrometheusExporter] = None,
        enable_default_collectors: bool = True,
        collection_interval: int = 60,
    ):
        """
        Initialize the metrics collector.
        
        Args:
            prometheus_exporter: Prometheus exporter to use
            enable_default_collectors: Whether to enable default system metrics collectors
            collection_interval: Interval in seconds for automatic metrics collection
        """
        self.prometheus_exporter = prometheus_exporter or get_exporter()
        self.health_checker = get_health_checker()
        self.collection_interval = collection_interval
        self._collectors: Dict[str, Callable] = {}
        self._collection_lock = threading.RLock()
        self._collection_thread = None
        self._shutdown_event = threading.Event()
        
        # Initialize metric values cache
        self._metric_values: Dict[str, Any] = {}
        
        # Register default collectors if enabled
        if enable_default_collectors:
            self._register_default_collectors()
    
    def _register_default_collectors(self) -> None:
        """Register default system metrics collectors."""
        # CPU usage collector
        self.register_collector("cpu", self._collect_cpu_metrics)
        
        # Memory usage collector
        self.register_collector("memory", self._collect_memory_metrics)
        
        # Disk usage collector
        self.register_collector("disk", self._collect_disk_metrics)
        
        # Network I/O collector
        self.register_collector("network", self._collect_network_metrics)
        
        # File descriptor usage collector
        self.register_collector("file_descriptors", self._collect_file_descriptor_metrics)
        
        # Thread count collector
        self.register_collector("threads", self._collect_thread_metrics)
        
        logger.debug("Registered default system metrics collectors")
    
    def _collect_cpu_metrics(self) -> Dict[str, Any]:
        """
        Collect CPU usage metrics.
        
        Returns:
            Dictionary of CPU metrics
        """
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            cpu_times = psutil.cpu_times_percent(interval=0.1)
            
            metrics = {
                "cpu_usage_percent": cpu_percent,
                "cpu_count": cpu_count,
                "cpu_user_percent": cpu_times.user,
                "cpu_system_percent": cpu_times.system,
                "cpu_idle_percent": cpu_times.idle,
            }
            
            # Report CPU usage to Prometheus
            self.prometheus_exporter.set_resource_gauge(
                "cpu_usage_percent",
                cpu_percent,
            )
            
            # Update health status based on CPU usage
            if cpu_percent > 90:
                self.health_checker.update_component_health(
                    component="cpu",
                    status=HealthStatus.DEGRADED,
                    details=f"High CPU usage: {cpu_percent}%",
                )
            else:
                self.health_checker.update_component_health(
                    component="cpu",
                    status=HealthStatus.OK,
                    details=f"CPU usage: {cpu_percent}%",
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting CPU metrics: {str(e)}", exc_info=True)
            
            self.health_checker.update_component_health(
                component="cpu",
                status=HealthStatus.UNKNOWN,
                details=f"Error collecting CPU metrics: {str(e)}",
            )
            
            return {"error": str(e)}
    
    def _collect_memory_metrics(self) -> Dict[str, Any]:
        """
        Collect memory usage metrics.
        
        Returns:
            Dictionary of memory metrics
        """
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            metrics = {
                "memory_total_bytes": memory.total,
                "memory_available_bytes": memory.available,
                "memory_used_bytes": memory.used,
                "memory_used_percent": memory.percent,
                "swap_total_bytes": swap.total,
                "swap_used_bytes": swap.used,
                "swap_used_percent": swap.percent,
            }
            
            # Report memory usage to Prometheus
            self.prometheus_exporter.set_resource_gauge(
                "memory_used_percent",
                memory.percent,
            )
            
            self.prometheus_exporter.set_resource_gauge(
                "memory_used_bytes",
                memory.used,
            )
            
            # Update health status based on memory usage
            if memory.percent > 90:
                self.health_checker.update_component_health(
                    component="memory",
                    status=HealthStatus.DEGRADED,
                    details=f"High memory usage: {memory.percent}%",
                )
            else:
                self.health_checker.update_component_health(
                    component="memory",
                    status=HealthStatus.OK,
                    details=f"Memory usage: {memory.percent}%",
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting memory metrics: {str(e)}", exc_info=True)
            
            self.health_checker.update_component_health(
                component="memory",
                status=HealthStatus.UNKNOWN,
                details=f"Error collecting memory metrics: {str(e)}",
            )
            
            return {"error": str(e)}
    
    def _collect_disk_metrics(self) -> Dict[str, Any]:
        """
        Collect disk usage metrics.
        
        Returns:
            Dictionary of disk metrics
        """
        try:
            disk_usage = psutil.disk_usage(os.getcwd())
            disk_io = psutil.disk_io_counters()
            
            metrics = {
                "disk_total_bytes": disk_usage.total,
                "disk_used_bytes": disk_usage.used,
                "disk_free_bytes": disk_usage.free,
                "disk_used_percent": disk_usage.percent,
                "disk_read_bytes": disk_io.read_bytes if disk_io else 0,
                "disk_write_bytes": disk_io.write_bytes if disk_io else 0,
                "disk_read_count": disk_io.read_count if disk_io else 0,
                "disk_write_count": disk_io.write_count if disk_io else 0,
            }
            
            # Report disk usage to Prometheus
            self.prometheus_exporter.set_resource_gauge(
                "disk_used_percent",
                disk_usage.percent,
            )
            
            # Update health status based on disk usage
            if disk_usage.percent > 90:
                self.health_checker.update_component_health(
                    component="disk",
                    status=HealthStatus.DEGRADED,
                    details=f"High disk usage: {disk_usage.percent}%",
                )
            else:
                self.health_checker.update_component_health(
                    component="disk",
                    status=HealthStatus.OK,
                    details=f"Disk usage: {disk_usage.percent}%",
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting disk metrics: {str(e)}", exc_info=True)
            
            self.health_checker.update_component_health(
                component="disk",
                status=HealthStatus.UNKNOWN,
                details=f"Error collecting disk metrics: {str(e)}",
            )
            
            return {"error": str(e)}
    
    def _collect_network_metrics(self) -> Dict[str, Any]:
        """
        Collect network I/O metrics.
        
        Returns:
            Dictionary of network metrics
        """
        try:
            net_io = psutil.net_io_counters()
            
            metrics = {
                "network_bytes_sent": net_io.bytes_sent,
                "network_bytes_recv": net_io.bytes_recv,
                "network_packets_sent": net_io.packets_sent,
                "network_packets_recv": net_io.packets_recv,
                "network_errin": net_io.errin,
                "network_errout": net_io.errout,
                "network_dropin": net_io.dropin,
                "network_dropout": net_io.dropout,
            }
            
            # Report network I/O to Prometheus
            self.prometheus_exporter.set_resource_gauge(
                "network_bytes_sent",
                net_io.bytes_sent,
            )
            
            self.prometheus_exporter.set_resource_gauge(
                "network_bytes_recv",
                net_io.bytes_recv,
            )
            
            # Update health status based on network errors
            if net_io.errin + net_io.errout > 100:
                self.health_checker.update_component_health(
                    component="network",
                    status=HealthStatus.DEGRADED,
                    details=f"High network errors: {net_io.errin} in, {net_io.errout} out",
                )
            else:
                self.health_checker.update_component_health(
                    component="network",
                    status=HealthStatus.OK,
                    details="Network functioning normally",
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting network metrics: {str(e)}", exc_info=True)
            
            self.health_checker.update_component_health(
                component="network",
                status=HealthStatus.UNKNOWN,
                details=f"Error collecting network metrics: {str(e)}",
            )
            
            return {"error": str(e)}
    
    def _collect_file_descriptor_metrics(self) -> Dict[str, Any]:
        """
        Collect file descriptor usage metrics.
        
        Returns:
            Dictionary of file descriptor metrics
        """
        try:
            # This is platform-dependent and may not work on Windows
            if not hasattr(os, 'getpid'):
                return {"error": "File descriptor metrics not available on this platform"}
            
            proc = psutil.Process(os.getpid())
            
            # Get open file descriptors (platform-dependent)
            try:
                open_files = proc.open_files()
                open_fd_count = len(open_files)
            except (AttributeError, psutil.AccessDenied):
                # Fall back to a simpler method on platforms where open_files() is not available
                if hasattr(proc, 'num_fds'):
                    open_fd_count = proc.num_fds()
                else:
                    return {"error": "File descriptor metrics not available on this platform"}
            
            # Get soft and hard limits (Linux/Unix only)
            if hasattr(proc, 'rlimit'):
                try:
                    soft_limit, hard_limit = proc.rlimit(psutil.RLIMIT_NOFILE)
                except (AttributeError, psutil.AccessDenied):
                    soft_limit = hard_limit = None
            else:
                soft_limit = hard_limit = None
            
            metrics = {
                "fd_open_count": open_fd_count,
            }
            
            if soft_limit is not None:
                metrics["fd_soft_limit"] = soft_limit
                metrics["fd_hard_limit"] = hard_limit
                metrics["fd_usage_percent"] = (open_fd_count / soft_limit) * 100 if soft_limit > 0 else 0
            
            # Report file descriptor usage to Prometheus
            self.prometheus_exporter.set_resource_gauge(
                "fd_open_count",
                open_fd_count,
            )
            
            if soft_limit is not None and soft_limit > 0:
                self.prometheus_exporter.set_resource_gauge(
                    "fd_usage_percent",
                    (open_fd_count / soft_limit) * 100,
                )
            
            # Update health status based on file descriptor usage
            if soft_limit is not None and soft_limit > 0:
                usage_percent = (open_fd_count / soft_limit) * 100
                if usage_percent > 80:
                    self.health_checker.update_component_health(
                        component="file_descriptors",
                        status=HealthStatus.DEGRADED,
                        details=f"High file descriptor usage: {usage_percent:.1f}%",
                    )
                else:
                    self.health_checker.update_component_health(
                        component="file_descriptors",
                        status=HealthStatus.OK,
                        details=f"File descriptor usage: {usage_percent:.1f}%",
                    )
            else:
                self.health_checker.update_component_health(
                    component="file_descriptors",
                    status=HealthStatus.OK,
                    details=f"Open file descriptors: {open_fd_count}",
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting file descriptor metrics: {str(e)}", exc_info=True)
            
            self.health_checker.update_component_health(
                component="file_descriptors",
                status=HealthStatus.UNKNOWN,
                details=f"Error collecting file descriptor metrics: {str(e)}",
            )
            
            return {"error": str(e)}
    
    def _collect_thread_metrics(self) -> Dict[str, Any]:
        """
        Collect thread count metrics.
        
        Returns:
            Dictionary of thread metrics
        """
        try:
            # Get current process
            proc = psutil.Process(os.getpid())
            
            # Get thread count
            threads = proc.threads()
            thread_count = len(threads)
            
            metrics = {
                "thread_count": thread_count,
            }
            
            # Report thread count to Prometheus
            self.prometheus_exporter.set_resource_gauge(
                "thread_count",
                thread_count,
            )
            
            # Update health status based on thread count
            if thread_count > 200:
                self.health_checker.update_component_health(
                    component="threads",
                    status=HealthStatus.DEGRADED,
                    details=f"High thread count: {thread_count}",
                )
            else:
                self.health_checker.update_component_health(
                    component="threads",
                    status=HealthStatus.OK,
                    details=f"Thread count: {thread_count}",
                )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting thread metrics: {str(e)}", exc_info=True)
            
            self.health_checker.update_component_health(
                component="threads",
                status=HealthStatus.UNKNOWN,
                details=f"Error collecting thread metrics: {str(e)}",
            )
            
            return {"error": str(e)}
    
    def register_collector(self, name: str, collector_func: Callable) -> None:
        """
        Register a metrics collector function.
        
        Args:
            name: Name of the collector
            collector_func: Function that collects metrics and returns a dictionary
        """
        with self._collection_lock:
            self._collectors[name] = collector_func
            logger.debug(f"Registered metrics collector: {name}")
    
    def unregister_collector(self, name: str) -> None:
        """
        Unregister a metrics collector function.
        
        Args:
            name: Name of the collector to unregister
        """
        with self._collection_lock:
            if name in self._collectors:
                del self._collectors[name]
                logger.debug(f"Unregistered metrics collector: {name}")
    
    def collect_metrics(self, collector_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect metrics from registered collectors.
        
        Args:
            collector_name: Name of the specific collector to run, or None for all
        
        Returns:
            Dictionary of collected metrics
        """
        metrics = {}
        
        with self._collection_lock:
            if collector_name is not None:
                # Run a specific collector
                if collector_name in self._collectors:
                    try:
                        collector_metrics = self._collectors[collector_name]()
                        metrics[collector_name] = collector_metrics
                        
                        # Update metrics cache
                        self._metric_values[collector_name] = collector_metrics
                        
                        logger.debug(f"Collected metrics from {collector_name}")
                    except Exception as e:
                        logger.error(f"Error collecting metrics from {collector_name}: {str(e)}", exc_info=True)
                        metrics[collector_name] = {"error": str(e)}
                else:
                    logger.warning(f"Collector not found: {collector_name}")
                    metrics[collector_name] = {"error": "Collector not found"}
            else:
                # Run all collectors
                for name, collector_func in self._collectors.items():
                    try:
                        collector_metrics = collector_func()
                        metrics[name] = collector_metrics
                        
                        # Update metrics cache
                        self._metric_values[name] = collector_metrics
                        
                        logger.debug(f"Collected metrics from {name}")
                    except Exception as e:
                        logger.error(f"Error collecting metrics from {name}: {str(e)}", exc_info=True)
                        metrics[name] = {"error": str(e)}
        
        # Add timestamp
        metrics["timestamp"] = time.time()
        
        return metrics
    
    def get_metrics(self, collector_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the most recently collected metrics.
        
        Args:
            collector_name: Name of the specific collector to get metrics for, or None for all
        
        Returns:
            Dictionary of metrics
        """
        with self._collection_lock:
            if collector_name is not None:
                # Get metrics for a specific collector
                if collector_name in self._metric_values:
                    return {
                        collector_name: self._metric_values[collector_name],
                        "timestamp": time.time(),
                    }
                else:
                    logger.warning(f"No metrics available for collector: {collector_name}")
                    return {
                        collector_name: {"error": "No metrics available"},
                        "timestamp": time.time(),
                    }
            else:
                # Get all metrics
                return {
                    **self._metric_values,
                    "timestamp": time.time(),
                }
    
    def _auto_collect_loop(self) -> None:
        """Background thread function to periodically collect metrics."""
        logger.info(f"Starting automatic metrics collection every {self.collection_interval} seconds")
        
        while not self._shutdown_event.is_set():
            try:
                self.collect_metrics()
                logger.debug("Completed automatic metrics collection")
            except Exception as e:
                logger.error(f"Error running automatic metrics collection: {str(e)}", exc_info=True)
            
            # Wait for the next collection interval or until shutdown
            self._shutdown_event.wait(self.collection_interval)
    
    def start_auto_collection(self) -> None:
        """Start automatic metrics collection in a background thread."""
        if self._collection_thread is not None and self._collection_thread.is_alive():
            logger.warning("Automatic metrics collection already running")
            return
        
        self._shutdown_event.clear()
        self._collection_thread = threading.Thread(
            target=self._auto_collect_loop,
            daemon=True,
            name="metrics-collector",
        )
        self._collection_thread.start()
        logger.info("Started automatic metrics collection")
    
    def stop_auto_collection(self) -> None:
        """Stop automatic metrics collection."""
        if self._collection_thread is None or not self._collection_thread.is_alive():
            logger.warning("Automatic metrics collection not running")
            return
        
        self._shutdown_event.set()
        self._collection_thread.join(timeout=5.0)
        if self._collection_thread.is_alive():
            logger.warning("Metrics collector thread did not terminate gracefully")
        else:
            logger.info("Stopped automatic metrics collection")
        
        self._collection_thread = None

    def register_with_fastapi(self, app: Any, path: str = "/metrics/collect") -> None:
        """
        Register metrics collection endpoints with a FastAPI application.
        
        Args:
            app: FastAPI application to register with
            path: Base path for metrics collection endpoints
        """
        try:
            from fastapi import FastAPI, APIRouter, Query
            
            # Ensure the app is a FastAPI instance
            if not isinstance(app, FastAPI):
                logger.error(f"Cannot register metrics collection endpoints: app is not a FastAPI instance")
                return
            
            # Create a router for metrics collection endpoints
            router = APIRouter(tags=["Metrics"])
            
            @router.get(path)
            async def collect_metrics(collector: Optional[str] = Query(None, description="Specific collector to run")):
                """Collect and return metrics."""
                return self.collect_metrics(collector_name=collector)
            
            @router.get(f"{path}/get")
            async def get_metrics(collector: Optional[str] = Query(None, description="Specific collector to get metrics for")):
                """Get the most recently collected metrics."""
                return self.get_metrics(collector_name=collector)
            
            @router.get(f"{path}/info")
            async def get_collectors_info():
                """Get information about registered collectors."""
                return {
                    "collectors": list(self._collectors.keys()),
                    "collection_interval": self.collection_interval,
                    "auto_collection": self._collection_thread is not None and self._collection_thread.is_alive(),
                }
            
            # Include the router in the app
            app.include_router(router)
            logger.info(f"Registered metrics collection endpoints at {path}")
            
        except ImportError:
            logger.error("Cannot register metrics collection endpoints: fastapi not available")
    
    def register_with_router(self, router: Any, path: str = "") -> None:
        """
        Register metrics collection endpoints with a FastAPI router.
        
        Args:
            router: FastAPI router to register with
            path: Base path for metrics collection endpoints (relative to router prefix)
        """
        try:
            from fastapi import APIRouter, Query
            
            # Ensure the router is an APIRouter instance
            if not isinstance(router, APIRouter):
                logger.error(f"Cannot register metrics collection endpoints with router: not an APIRouter instance")
                return
            
            @router.get(f"{path}")
            async def collect_metrics(collector: Optional[str] = Query(None, description="Specific collector to run")):
                """Collect and return metrics."""
                return self.collect_metrics(collector_name=collector)
            
            @router.get(f"{path}/get")
            async def get_metrics(collector: Optional[str] = Query(None, description="Specific collector to get metrics for")):
                """Get the most recently collected metrics."""
                return self.get_metrics(collector_name=collector)
            
            @router.get(f"{path}/info")
            async def get_collectors_info():
                """Get information about registered collectors."""
                return {
                    "collectors": list(self._collectors.keys()),
                    "collection_interval": self.collection_interval,
                    "auto_collection": self._collection_thread is not None and self._collection_thread.is_alive(),
                }
            
            logger.info(f"Registered metrics collection endpoints with router at {path}")
            
        except ImportError:
            logger.error("Cannot register metrics collection endpoints with router: fastapi not available")

# Singleton instance for global access
_default_collector = None

def get_metrics_collector(
    prometheus_exporter: Optional[PrometheusExporter] = None,
    enable_default_collectors: bool = True,
    collection_interval: int = 60,
) -> MetricsCollector:
    """
    Get or create the default metrics collector.
    
    Args:
        prometheus_exporter: Prometheus exporter to use
        enable_default_collectors: Whether to enable default system metrics collectors
        collection_interval: Interval in seconds for automatic metrics collection
    
    Returns:
        MetricsCollector instance
    """
    global _default_collector
    
    if _default_collector is None:
        _default_collector = MetricsCollector(
            prometheus_exporter=prometheus_exporter,
            enable_default_collectors=enable_default_collectors,
            collection_interval=collection_interval,
        )
    
    return _default_collector

def collect_metrics(collector_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Collect metrics using the default metrics collector.
    
    Args:
        collector_name: Name of the specific collector to run, or None for all
    
    Returns:
        Dictionary of collected metrics
    """
    collector = get_metrics_collector()
    return collector.collect_metrics(collector_name=collector_name)

def register_collector(name: str, collector_func: Callable) -> None:
    """
    Register a metrics collector function with the default metrics collector.
    
    Args:
        name: Name of the collector
        collector_func: Function that collects metrics and returns a dictionary
    """
    collector = get_metrics_collector()
    collector.register_collector(name=name, collector_func=collector_func)
