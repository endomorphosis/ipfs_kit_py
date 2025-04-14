"""
MCP Monitoring System

This module provides a comprehensive monitoring system for the MCP server,
including performance metrics, health checks, and integration with Prometheus.
"""

import os
import time
import json
import logging
import threading
import platform
import psutil
import socket
from typing import Dict, Any, List, Optional, Union, Callable, Tuple # Added Tuple
from datetime import datetime, timedelta
from collections import deque

# Configure logging
logger = logging.getLogger(__name__)

# Try to import prometheus_client
try:
    import prometheus_client as prom
    from prometheus_client import Counter, Gauge, Histogram, Summary
    PROMETHEUS_AVAILABLE = True
    logger.info("Prometheus client library available")
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus client library not available. Install with: pip install prometheus-client")

# Default configuration
DEFAULT_CONFIG = {
    "metrics_enabled": True,
    "prometheus_enabled": True,
    "prometheus_port": 9998,
    "collection_interval": 10,  # seconds
    "history_size": 60,  # number of data points to keep (10 minutes at 10s interval)
    "log_metrics": False,  # whether to log metrics to the logger
    "disk_paths": ["/"],  # paths to monitor disk usage for
    "network_interfaces": ["eth0"],  # network interfaces to monitor
    "enable_process_metrics": True,  # whether to collect process-specific metrics
    "enable_system_metrics": True,  # whether to collect system-wide metrics
    "enable_storage_metrics": True,  # whether to collect storage backend metrics
    "enable_api_metrics": True,  # whether to collect API endpoint metrics
}

class MetricsRegistry:
    """Registry for tracking metrics in the application."""
    
    def __init__(self):
        """Initialize the metrics registry."""
        self.metrics = {}
        self.prom_metrics = {}
    
    def register(self, name: str, description: str, metric_type: str = "gauge", labels: Optional[List[str]] = None):
        """
        Register a new metric.
        
        Args:
            name: Metric name
            description: Metric description
            metric_type: Type of metric (gauge, counter, histogram, summary)
            labels: Optional list of label names
        """
        if name in self.metrics:
            logger.warning(f"Metric '{name}' already registered")
            return
        
        self.metrics[name] = {
            "name": name,
            "description": description,
            "type": metric_type,
            "labels": labels or [],
            "values": {},
            "history": {},
            "created_at": time.time()
        }
        
        # Create Prometheus metric if available
        if PROMETHEUS_AVAILABLE:
            prom_name = name.replace(".", "_").replace("-", "_")
            labels = labels or []
            
            if metric_type == "gauge":
                self.prom_metrics[name] = Gauge(prom_name, description, labels)
            elif metric_type == "counter":
                self.prom_metrics[name] = Counter(prom_name, description, labels)
            elif metric_type == "histogram":
                self.prom_metrics[name] = Histogram(prom_name, description, labels)
            elif metric_type == "summary":
                self.prom_metrics[name] = Summary(prom_name, description, labels)
            else:
                logger.warning(f"Unknown metric type: {metric_type}")
    
    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Set a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Optional label values
        """
        if name not in self.metrics:
            logger.warning(f"Metric '{name}' not registered")
            return
        
        labels_key = self._labels_to_key(labels or {})
        metric = self.metrics[name]
        
        # Update current value
        metric["values"][labels_key] = value
        
        # Update history
        if labels_key not in metric["history"]:
            metric["history"][labels_key] = deque(maxlen=DEFAULT_CONFIG["history_size"])
        
        metric["history"][labels_key].append((time.time(), value))
        
        # Update Prometheus metric if available
        if PROMETHEUS_AVAILABLE and name in self.prom_metrics:
            prom_metric = self.prom_metrics[name]
            if metric["type"] == "gauge":
                if labels:
                    prom_metric.labels(**labels).set(value)
                else:
                    prom_metric.set(value)
            elif metric["type"] == "counter":
                # For counters, we need to increment by the delta
                if labels:
                    prom_metric.labels(**labels).inc(value)
                else:
                    prom_metric.inc(value)
    
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Increment value
            labels: Optional label values
        """
        if name not in self.metrics:
            logger.warning(f"Metric '{name}' not registered")
            return
        
        if self.metrics[name]["type"] != "counter":
            logger.warning(f"Metric '{name}' is not a counter")
            return
        
        labels_key = self._labels_to_key(labels or {})
        metric = self.metrics[name]
        
        # Update current value
        if labels_key in metric["values"]:
            metric["values"][labels_key] += value
        else:
            metric["values"][labels_key] = value
        
        # Update history
        if labels_key not in metric["history"]:
            metric["history"][labels_key] = deque(maxlen=DEFAULT_CONFIG["history_size"])
        
        metric["history"][labels_key].append((time.time(), metric["values"][labels_key]))
        
        # Update Prometheus metric if available
        if PROMETHEUS_AVAILABLE and name in self.prom_metrics:
            prom_metric = self.prom_metrics[name]
            if labels:
                prom_metric.labels(**labels).inc(value)
            else:
                prom_metric.inc(value)
    
    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        Observe a value for a histogram or summary metric.
        
        Args:
            name: Metric name
            value: Observed value
            labels: Optional label values
        """
        if name not in self.metrics:
            logger.warning(f"Metric '{name}' not registered")
            return
        
        if self.metrics[name]["type"] not in ["histogram", "summary"]:
            logger.warning(f"Metric '{name}' is not a histogram or summary")
            return
        
        # Update Prometheus metric if available
        if PROMETHEUS_AVAILABLE and name in self.prom_metrics:
            prom_metric = self.prom_metrics[name]
            if labels:
                prom_metric.labels(**labels).observe(value)
            else:
                prom_metric.observe(value)
        
        # We don't track histograms and summaries in our custom registry
        # as they're aggregated differently
    
    def get(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """
        Get current metric value.
        
        Args:
            name: Metric name
            labels: Optional label values
            
        Returns:
            Current metric value or None if not found
        """
        if name not in self.metrics:
            logger.warning(f"Metric '{name}' not registered")
            return None
        
        labels_key = self._labels_to_key(labels or {})
        metric = self.metrics[name]
        
        if labels_key in metric["values"]:
            return metric["values"][labels_key]
        
        return None
    
    def get_history(self, name: str, labels: Optional[Dict[str, str]] = None) -> List[Tuple[float, float]]:
        """
        Get metric history.
        
        Args:
            name: Metric name
            labels: Optional label values
            
        Returns:
            List of (timestamp, value) tuples or empty list if not found
        """
        if name not in self.metrics:
            logger.warning(f"Metric '{name}' not registered")
            return []
        
        labels_key = self._labels_to_key(labels or {})
        metric = self.metrics[name]
        
        if labels_key in metric["history"]:
            return list(metric["history"][labels_key])
        
        return []
    
    def get_metrics_info(self) -> Dict[str, Any]:
        """
        Get information about all registered metrics.
        
        Returns:
            Dict with metric information
        """
        info = {}
        
        for name, metric in self.metrics.items():
            info[name] = {
                "name": metric["name"],
                "description": metric["description"],
                "type": metric["type"],
                "labels": metric["labels"],
                "created_at": metric["created_at"]
            }
        
        return info
    
    def get_metrics_snapshot(self) -> Dict[str, Any]:
        """
        Get a snapshot of all current metric values.
        
        Returns:
            Dict with metric values
        """
        snapshot = {}
        
        for name, metric in self.metrics.items():
            snapshot[name] = {
                "type": metric["type"],
                "values": {},
                "latest_update": time.time()
            }
            
            for labels_key, value in metric["values"].items():
                if labels_key == "()":  # No labels
                    snapshot[name]["values"][""] = value
                else:
                    snapshot[name]["values"][labels_key] = value
        
        return snapshot
    
    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        """Convert labels dict to a string key for internal storage."""
        if not labels:
            return "()"
        
        sorted_items = sorted(labels.items())
        return str(tuple(sorted_items))

class MonitoringSystem:
    """Comprehensive monitoring system for MCP server."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the monitoring system.
        
        Args:
            config: Configuration options
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.registry = MetricsRegistry()
        self.running = False
        self.collection_thread = None
        self.start_time = time.time()
        
        # Initialize storage backend metrics
        self.storage_backends = {}
        
        # Register basic metrics
        self._register_metrics()
        
        # Start metrics collection if enabled
        if self.config["metrics_enabled"]:
            self.start_collection()
            
            # Start Prometheus server if enabled
            if self.config["prometheus_enabled"] and PROMETHEUS_AVAILABLE:
                self._start_prometheus_server()
    
    def _register_metrics(self):
        """Register all metrics."""
        # System metrics
        self.registry.register("system.uptime", "System uptime in seconds", "gauge")
        self.registry.register("system.cpu_usage", "System CPU usage percentage", "gauge")
        self.registry.register("system.memory_usage", "System memory usage percentage", "gauge")
        self.registry.register("system.memory_available", "System memory available in bytes", "gauge")
        self.registry.register("system.memory_total", "System total memory in bytes", "gauge")
        self.registry.register("system.disk_usage", "Disk usage percentage", "gauge", ["path"])
        self.registry.register("system.disk_free", "Disk free space in bytes", "gauge", ["path"])
        self.registry.register("system.disk_total", "Disk total space in bytes", "gauge", ["path"])
        self.registry.register("system.network_sent", "Network bytes sent", "counter", ["interface"])
        self.registry.register("system.network_received", "Network bytes received", "counter", ["interface"])
        
        # Process metrics
        self.registry.register("process.cpu_usage", "Process CPU usage percentage", "gauge")
        self.registry.register("process.memory_usage", "Process memory usage in bytes", "gauge")
        self.registry.register("process.threads", "Number of threads in the process", "gauge")
        self.registry.register("process.open_files", "Number of open files by the process", "gauge")
        self.registry.register("process.connections", "Number of network connections by the process", "gauge")
        
        # API metrics
        self.registry.register("api.requests_total", "Total number of API requests", "counter", ["endpoint", "method", "status"])
        self.registry.register("api.request_duration_seconds", "API request duration in seconds", "histogram", ["endpoint", "method"])
        self.registry.register("api.request_size_bytes", "API request size in bytes", "histogram", ["endpoint", "method"])
        self.registry.register("api.response_size_bytes", "API response size in bytes", "histogram", ["endpoint", "method"])
        self.registry.register("api.errors_total", "Total number of API errors", "counter", ["endpoint", "method", "error_code"])
        
        # Storage metrics
        self.registry.register("storage.operations_total", "Total number of storage operations", "counter", ["backend", "operation"])
        self.registry.register("storage.operation_errors_total", "Total number of storage operation errors", "counter", ["backend", "operation"])
        self.registry.register("storage.operation_duration_seconds", "Storage operation duration in seconds", "histogram", ["backend", "operation"])
        self.registry.register("storage.stored_items", "Number of items stored in backend", "gauge", ["backend"])
        self.registry.register("storage.stored_bytes", "Total bytes stored in backend", "gauge", ["backend"])
        
        # IPFS metrics
        self.registry.register("ipfs.repo_size", "IPFS repository size in bytes", "gauge")
        self.registry.register("ipfs.repo_objects", "Number of objects in IPFS repository", "gauge")
        self.registry.register("ipfs.bandwidth_total_in", "Total incoming bandwidth in bytes", "counter")
        self.registry.register("ipfs.bandwidth_total_out", "Total outgoing bandwidth in bytes", "counter")
        self.registry.register("ipfs.peers", "Number of connected IPFS peers", "gauge")
    
    def start_collection(self):
        """Start the metrics collection thread."""
        if self.running:
            logger.warning("Metrics collection already running")
            return
        
        self.running = True
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self.collection_thread.start()
        logger.info("Started metrics collection thread")
    
    def stop_collection(self):
        """Stop the metrics collection thread."""
        if not self.running:
            logger.warning("Metrics collection not running")
            return
        
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=5.0)
            if self.collection_thread.is_alive():
                logger.warning("Metrics collection thread did not terminate gracefully")
            else:
                logger.info("Stopped metrics collection thread")
    
    def _start_prometheus_server(self):
        """Start the Prometheus metrics server."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client library not available")
            return
        
        try:
            port = self.config["prometheus_port"]
            prom.start_http_server(port)
            logger.info(f"Started Prometheus metrics server on port {port}")
        except Exception as e:
            logger.error(f"Error starting Prometheus metrics server: {e}")
    
    def _collection_loop(self):
        """Main metrics collection loop."""
        while self.running:
            try:
                # Collect system metrics
                if self.config["enable_system_metrics"]:
                    self._collect_system_metrics()
                
                # Collect process metrics
                if self.config["enable_process_metrics"]:
                    self._collect_process_metrics()
                
                # Collect IPFS metrics
                self._collect_ipfs_metrics()
                
                # Log metrics if enabled
                if self.config["log_metrics"]:
                    self._log_metrics()
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
            
            # Sleep until next collection
            time.sleep(self.config["collection_interval"])
    
    def _collect_system_metrics(self):
        """Collect system-wide metrics."""
        # Uptime
        uptime = time.time() - self.start_time
        self.registry.set("system.uptime", uptime)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=None)
        self.registry.set("system.cpu_usage", cpu_percent)
        
        # Memory usage
        memory = psutil.virtual_memory()
        self.registry.set("system.memory_usage", memory.percent)
        self.registry.set("system.memory_available", memory.available)
        self.registry.set("system.memory_total", memory.total)
        
        # Disk usage
        for path in self.config["disk_paths"]:
            try:
                disk = psutil.disk_usage(path)
                self.registry.set("system.disk_usage", disk.percent, {"path": path})
                self.registry.set("system.disk_free", disk.free, {"path": path})
                self.registry.set("system.disk_total", disk.total, {"path": path})
            except Exception as e:
                logger.warning(f"Error collecting disk metrics for {path}: {e}")
        
        # Network usage
        net_io_counters = psutil.net_io_counters(pernic=True)
        for interface in self.config["network_interfaces"]:
            if interface in net_io_counters:
                stats = net_io_counters[interface]
                # These are cumulative counters, so we'd normally calculate the delta
                # but for our registry we'll just set the latest value
                self.registry.set("system.network_sent", stats.bytes_sent, {"interface": interface})
                self.registry.set("system.network_received", stats.bytes_recv, {"interface": interface})
    
    def _collect_process_metrics(self):
        """Collect process-specific metrics."""
        try:
            process = psutil.Process()
            
            # CPU usage
            cpu_percent = process.cpu_percent(interval=None)
            self.registry.set("process.cpu_usage", cpu_percent)
            
            # Memory usage
            memory_info = process.memory_info()
            self.registry.set("process.memory_usage", memory_info.rss)
            
            # Threads count
            threads = process.num_threads()
            self.registry.set("process.threads", threads)
            
            # Open files count
            try:
                open_files = len(process.open_files())
                self.registry.set("process.open_files", open_files)
            except Exception:
                # May require higher privileges
                pass
            
            # Connections count
            try:
                connections = len(process.connections())
                self.registry.set("process.connections", connections)
            except Exception:
                # May require higher privileges
                pass
        except Exception as e:
            logger.warning(f"Error collecting process metrics: {e}")
    
    def _collect_ipfs_metrics(self):
        """Collect IPFS-specific metrics."""
        try:
            # This would typically involve calling the IPFS API
            # For now, we'll just use mock values for demonstration
            import subprocess
            import json
            
            # Get repo stats
            try:
                result = subprocess.run(
                    ["ipfs", "repo", "stat", "--human=false", "--size-only"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    try:
                        stats = json.loads(result.stdout)
                        if "RepoSize" in stats:
                            self.registry.set("ipfs.repo_size", stats["RepoSize"])
                        if "NumObjects" in stats:
                            self.registry.set("ipfs.repo_objects", stats["NumObjects"])
                    except Exception:
                        pass
            except Exception:
                pass
            
            # Get bandwidth stats
            try:
                result = subprocess.run(
                    ["ipfs", "stats", "bw", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    try:
                        stats = json.loads(result.stdout)
                        if "TotalIn" in stats:
                            self.registry.set("ipfs.bandwidth_total_in", stats["TotalIn"])
                        if "TotalOut" in stats:
                            self.registry.set("ipfs.bandwidth_total_out", stats["TotalOut"])
                    except Exception:
                        pass
            except Exception:
                pass
            
            # Get peer count
            try:
                result = subprocess.run(
                    ["ipfs", "swarm", "peers", "--count"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    try:
                        peer_count = int(result.stdout.strip())
                        self.registry.set("ipfs.peers", peer_count)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Error collecting IPFS metrics: {e}")
    
    def _log_metrics(self):
        """Log current metrics."""
        snapshot = self.registry.get_metrics_snapshot()
        logger.info(f"Metrics snapshot: {json.dumps(snapshot)}")
    
    def update_storage_backend_status(self, storage_backends: Dict[str, Any]):
        """
        Update storage backend status.
        
        Args:
            storage_backends: Dictionary of storage backends to track
        """
        self.storage_backends = storage_backends
        
        # Update storage metrics
        for backend_name, backend_info in storage_backends.items():
            if not backend_info.get("available", False):
                continue
            
            # Set stored items and bytes if available
            if "statistics" in backend_info:
                stats = backend_info["statistics"]
                
                if "total_items" in stats:
                    self.registry.set("storage.stored_items", stats["total_items"], {"backend": backend_name})
                
                if "total_bytes" in stats:
                    self.registry.set("storage.stored_bytes", stats["total_bytes"], {"backend": backend_name})
    
    def track_api_request(
        self,
        endpoint: str,
        method: str,
        start_time: float,
        end_time: float,
        status_code: int,
        request_size: int,
        response_size: int,
        error_code: Optional[str] = None
    ):
        """
        Track an API request.
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            start_time: Request start time
            end_time: Request end time
            status_code: HTTP status code
            request_size: Request size in bytes
            response_size: Response size in bytes
            error_code: Optional error code if request failed
        """
        duration = end_time - start_time
        status = str(status_code)
        
        # Increment request counter
        self.registry.increment("api.requests_total", 1, {
            "endpoint": endpoint,
            "method": method,
            "status": status
        })
        
        # Observe request duration
        self.registry.observe("api.request_duration_seconds", duration, {
            "endpoint": endpoint,
            "method": method
        })
        
        # Observe request and response sizes
        self.registry.observe("api.request_size_bytes", request_size, {
            "endpoint": endpoint,
            "method": method
        })
        
        self.registry.observe("api.response_size_bytes", response_size, {
            "endpoint": endpoint,
            "method": method
        })
        
        # Track errors if applicable
        if error_code:
            self.registry.increment("api.errors_total", 1, {
                "endpoint": endpoint,
                "method": method,
                "error_code": error_code
            })
    
    def track_storage_operation(
        self,
        backend: str,
        operation: str,
        start_time: float,
        end_time: float,
        success: bool,
        error_code: Optional[str] = None
    ):
        """
        Track a storage operation.
        
        Args:
            backend: Storage backend name
            operation: Operation name
            start_time: Operation start time
            end_time: Operation end time
            success: Whether the operation succeeded
            error_code: Optional error code if operation failed
        """
        duration = end_time - start_time
        
        # Increment operation counter
        self.registry.increment("storage.operations_total", 1, {
            "backend": backend,
            "operation": operation
        })
        
        # Observe operation duration
        self.registry.observe("storage.operation_duration_seconds", duration, {
            "backend": backend,
            "operation": operation
        })
        
        # Track errors if applicable
        if not success:
            self.registry.increment("storage.operation_errors_total", 1, {
                "backend": backend,
                "operation": operation,
                "error_code": error_code or "unknown"
            })
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information.
        
        Returns:
            Dict with system information
        """
        info = {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "uptime": time.time() - self.start_time,
            "start_time": self.start_time,
            "current_time": time.time(),
            "disk_info": {}
        }
        
        # Add disk info
        for path in self.config["disk_paths"]:
            try:
                disk = psutil.disk_usage(path)
                info["disk_info"][path] = {
                    "total": disk.total,
                    "used": disk.used,
                    "free": disk.free,
                    "percent": disk.percent
                }
            except Exception:
                pass
        
        return info
    
    def get_metrics_data(self) -> Dict[str, Any]:
        """
        Get all metrics data.
        
        Returns:
            Dict with metrics data
        """
        return {
            "system_info": self.get_system_info(),
            "metrics_info": self.registry.get_metrics_info(),
            "metrics_snapshot": self.registry.get_metrics_snapshot(),
            "storage_backends": self.storage_backends,
            "config": self.config,
            "prometheus_enabled": PROMETHEUS_AVAILABLE and self.config["prometheus_enabled"],
            "prometheus_port": self.config["prometheus_port"] if PROMETHEUS_AVAILABLE and self.config["prometheus_enabled"] else None
        }
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for monitoring dashboard.
        
        Returns:
            Dict with dashboard data
        """
        # System metrics
        system_cpu = self.registry.get("system.cpu_usage") or 0
        system_memory = self.registry.get("system.memory_usage") or 0
        system_uptime = self.registry.get("system.uptime") or 0
        
        # Process metrics
        process_cpu = self.registry.get("process.cpu_usage") or 0
        process_memory = self.registry.get("process.memory_usage") or 0
        process_threads = self.registry.get("process.threads") or 0
        
        # API metrics (aggregate across all endpoints)
        api_requests = 0
        api_errors = 0
        
        for name, metric in self.registry.metrics.items():
            if name == "api.requests_total":
                for value in metric["values"].values():
                    api_requests += value
            elif name == "api.errors_total":
                for value in metric["values"].values():
                    api_errors += value
        
        # Storage metrics (aggregate across all backends)
        storage_operations = 0
        storage_errors = 0
        
        for name, metric in self.registry.metrics.items():
            if name == "storage.operations_total":
                for value in metric["values"].values():
                    storage_operations += value
            elif name == "storage.operation_errors_total":
                for value in metric["values"].values():
                    storage_errors += value
        
        # IPFS metrics
        ipfs_repo_size = self.registry.get("ipfs.repo_size") or 0
        ipfs_repo_objects = self.registry.get("ipfs.repo_objects") or 0
        ipfs_peers = self.registry.get("ipfs.peers") or 0
        
        # Format uptime
        uptime_str = str(timedelta(seconds=int(system_uptime)))
        
        return {
            "system": {
                "cpu": system_cpu,
                "memory": system_memory,
                "uptime": uptime_str,
                "uptime_seconds": system_uptime
            },
            "process": {
                "cpu": process_cpu,
                "memory": process_memory,
                "memory_mb": process_memory / (1024 * 1024),
                "threads": process_threads
            },
            "api": {
                "requests": api_requests,
                "errors": api_errors,
                "error_rate": (api_errors / api_requests * 100) if api_requests > 0 else 0
            },
            "storage": {
                "operations": storage_operations,
                "errors": storage_errors,
                "error_rate": (storage_errors / storage_operations * 100) if storage_operations > 0 else 0,
                "backends": len(self.storage_backends),
                "active_backends": sum(1 for backend in self.storage_backends.values() if backend.get("available", False))
            },
            "ipfs": {
                "repo_size": ipfs_repo_size,
                "repo_size_mb": ipfs_repo_size / (1024 * 1024),
                "objects": ipfs_repo_objects,
                "peers": ipfs_peers
            },
            "timestamp": time.time()
        }
    
    def shutdown(self):
        """Shut down the monitoring system."""
        self.stop_collection()
        logger.info("Monitoring system shutdown complete")
