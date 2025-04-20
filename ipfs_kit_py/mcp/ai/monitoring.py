"""
AI/ML Monitoring Module for MCP Server

This module provides monitoring capabilities for AI/ML components, including:
1. Performance metrics collection
2. Health check management
3. Prometheus integration
4. Custom metrics dashboards

Part of the MCP Roadmap Phase 2: AI/ML Integration (Q4 2025).
"""

import time
import logging
import threading
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Set, Union
from dataclasses import dataclass, field
import datetime
import contextlib

# Configure logger
logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects metrics from AI/ML components.
    
    This class provides methods for collecting and storing metrics
    from various AI/ML components and operations.
    """
    
    def __init__(self):
        """Initialize the metrics collector."""
        self.counters = {}
        self.gauges = {}
        self.histograms = {}
        self.lock = threading.RLock()
        
        # Prometheus registry (if available)
        self.prom_registry = None
        try:
            import prometheus_client
            self.prom_registry = prometheus_client.CollectorRegistry()
            self.prom_counters = {}
            self.prom_gauges = {}
            self.prom_histograms = {}
            logger.info("Prometheus integration enabled")
        except ImportError:
            logger.info("Prometheus client not available, using internal metrics only")
    
    def counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: int = 1) -> int:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            labels: Optional labels for the metric
            value: Value to increment by
            
        Returns:
            Current counter value
        """
        with self.lock:
            # Get label string for key
            label_str = self._labels_to_str(labels or {})
            key = f"{name}{label_str}"
            
            # Update internal counter
            if key not in self.counters:
                self.counters[key] = 0
            self.counters[key] += value
            
            # Update Prometheus counter if available
            if self.prom_registry:
                try:
                    if name not in self.prom_counters:
                        # Create counter with label names
                        label_names = list(labels.keys()) if labels else []
                        self.prom_counters[name] = self._create_prom_counter(name, label_names)
                    
                    if labels:
                        self.prom_counters[name].labels(**labels).inc(value)
                    else:
                        self.prom_counters[name].inc(value)
                        
                except Exception as e:
                    logger.warning(f"Error incrementing Prometheus counter {name}: {e}")
            
            return self.counters[key]
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> float:
        """
        Set a gauge metric.
        
        Args:
            name: Metric name
            value: Gauge value
            labels: Optional labels for the metric
            
        Returns:
            Current gauge value
        """
        with self.lock:
            # Get label string for key
            label_str = self._labels_to_str(labels or {})
            key = f"{name}{label_str}"
            
            # Update internal gauge
            self.gauges[key] = value
            
            # Update Prometheus gauge if available
            if self.prom_registry:
                if name not in self.prom_gauges:
                    self.prom_gauges[name] = self._create_prom_gauge(name)
                
                if labels:
                    self.prom_gauges[name].labels(**labels).set(value)
                else:
                    self.prom_gauges[name].set(value)
            
            return value
    
    def histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Record a histogram observation.
        
        Args:
            name: Metric name
            value: Observation value
            labels: Optional labels for the metric
        """
        with self.lock:
            # Get label string for key
            label_str = self._labels_to_str(labels or {})
            key = f"{name}{label_str}"
            
            # Update internal histogram
            if key not in self.histograms:
                self.histograms[key] = []
            self.histograms[key].append(value)
            
            # Update Prometheus histogram if available
            if self.prom_registry:
                if name not in self.prom_histograms:
                    self.prom_histograms[name] = self._create_prom_histogram(name)
                
                if labels:
                    self.prom_histograms[name].labels(**labels).observe(value)
                else:
                    self.prom_histograms[name].observe(value)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.
        
        Returns:
            Dictionary of all metrics
        """
        with self.lock:
            return {
                "counters": self.counters.copy(),
                "gauges": self.gauges.copy(),
                "histograms": {k: len(v) for k, v in self.histograms.items()}
            }
    
    def get_prometheus_registry(self):
        """
        Get the Prometheus registry.
        
        Returns:
            Prometheus registry or None if not available
        """
        return self.prom_registry
    
    def _labels_to_str(self, labels: Dict[str, str]) -> str:
        """Convert labels to string for dictionary key."""
        if not labels:
            return ""
        
        items = [f"{k}={v}" for k, v in sorted(labels.items())]
        return "{" + ",".join(items) + "}"
    
    def _create_prom_counter(self, name: str, label_names: Optional[List[str]] = None):
        """Create a Prometheus counter."""
        if not self.prom_registry:
            return None
        
        import prometheus_client
        return prometheus_client.Counter(
            name.replace(".", "_"),
            name.replace(".", " ").replace("_", " "),
            labelnames=[] if label_names is None else label_names,
            registry=self.prom_registry
        )
    
    def _create_prom_gauge(self, name: str):
        """Create a Prometheus gauge."""
        if not self.prom_registry:
            return None
        
        import prometheus_client
        return prometheus_client.Gauge(
            name.replace(".", "_"),
            name.replace(".", " ").replace("_", " "),
            registry=self.prom_registry
        )
    
    def _create_prom_histogram(self, name: str):
        """Create a Prometheus histogram."""
        if not self.prom_registry:
            return None
        
        import prometheus_client
        return prometheus_client.Histogram(
            name.replace(".", "_"),
            name.replace(".", " ").replace("_", " "),
            registry=self.prom_registry
        )


class HealthCheck:
    """
    Health check management for AI/ML components.
    
    This class provides methods for registering and executing
    health checks for AI/ML components.
    """
    
    def __init__(self):
        """Initialize the health check manager."""
        self.checks: Dict[str, Callable[[], Dict[str, Any]]] = {}
        self.lock = threading.RLock()
    
    def register_check(self, name: str, check_func: Callable[[], Dict[str, Any]]) -> None:
        """
        Register a health check function.
        
        Args:
            name: Health check name
            check_func: Function that returns health check result
        """
        with self.lock:
            self.checks[name] = check_func
            logger.info(f"Registered health check: {name}")
    
    def check_health(self, name: str) -> Dict[str, Any]:
        """
        Execute a specific health check.
        
        Args:
            name: Health check name
            
        Returns:
            Health check result
        """
        with self.lock:
            check_func = self.checks.get(name)
            if not check_func:
                return {
                    "status": "unknown",
                    "error": f"Health check '{name}' not found",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            
            try:
                result = check_func()
                return result
            except Exception as e:
                logger.error(f"Error executing health check '{name}': {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.datetime.now().isoformat()
                }
    
    def check_overall_health(self) -> Dict[str, Any]:
        """
        Execute all health checks.
        
        Returns:
            Overall health check result
        """
        with self.lock:
            results = {}
            overall_status = "healthy"
            
            for name, check_func in self.checks.items():
                try:
                    result = check_func()
                    results[name] = result
                    
                    # Update overall status
                    status = result.get("status", "unknown")
                    if status == "error":
                        overall_status = "error"
                    elif status == "warning" and overall_status != "error":
                        overall_status = "warning"
                    
                except Exception as e:
                    logger.error(f"Error executing health check '{name}': {e}")
                    results[name] = {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                    overall_status = "error"
            
            return {
                "status": overall_status,
                "components": results,
                "timestamp": datetime.datetime.now().isoformat()
            }


class PerformanceTimer:
    """
    Timer for measuring operation performance.
    
    This class provides a context manager for measuring
    the duration of operations.
    """
    
    def __init__(self, name: str, metrics_collector: Optional[MetricsCollector] = None, 
                 labels: Optional[Dict[str, str]] = None):
        """
        Initialize the performance timer.
        
        Args:
            name: Operation name
            metrics_collector: Optional metrics collector to record duration
            labels: Optional labels for the metric
        """
        self.name = name
        self.metrics_collector = metrics_collector
        self.labels = labels or {}
        self.start_time = 0
        self.duration = 0
    
    def __enter__(self):
        """Enter the context manager."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager."""
        self.duration = time.time() - self.start_time
        
        # Record metric if collector is available
        if self.metrics_collector:
            self.metrics_collector.histogram(
                f"{self.name}.duration", self.duration, self.labels
            )
        
        return False  # Don't suppress exceptions


# Singleton instances
_metrics_collector = None
_health_check = None

def get_metrics_collector(fresh_instance: bool = False) -> MetricsCollector:
    """
    Get the metrics collector instance.
    
    Args:
        fresh_instance: If True, creates a new instance (for testing)
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None or fresh_instance:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

def get_health_check() -> HealthCheck:
    """
    Get the singleton health check instance.
    
    Returns:
        HealthCheck instance
    """
    global _health_check
    if _health_check is None:
        _health_check = HealthCheck()
    return _health_check

def measure_time(name: str, labels: Optional[Dict[str, str]] = None):
    """
    Decorator for measuring function execution time.
    
    Args:
        name: Operation name
        labels: Optional labels for the metric
        
    Returns:
        Decorator function
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            metrics = get_metrics_collector()
            with PerformanceTimer(name, metrics, labels):
                return func(*args, **kwargs)
        return wrapper
    return decorator


@contextlib.contextmanager
def timer(name: str, labels: Optional[Dict[str, str]] = None):
    """
    Context manager for measuring operation execution time.
    
    Args:
        name: Operation name
        labels: Optional labels for the metric
        
    Yields:
        PerformanceTimer instance
    """
    metrics = get_metrics_collector()
    with PerformanceTimer(name, metrics, labels) as t:
        yield t


def log_metrics():
    """Log all collected metrics."""
    metrics = get_metrics_collector().get_metrics()
    logger.info(f"Metrics: {metrics}")


def log_health():
    """Log health check results."""
    health = get_health_check().check_overall_health()
    logger.info(f"Health: {health}")
