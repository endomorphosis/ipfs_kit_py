"""
Optimized Metrics Collector for MCP Server.

This module provides an optimized version of the metrics collector that
addresses high memory usage when tracking many metrics. It extends the
functionality of the standard metrics collector with memory efficiency features.
"""

import logging
import time
import threading
import os
import psutil
from typing import Dict, List, Any, Optional, Callable, Set, Union, Deque
from collections import deque
import weakref
from datetime import datetime, timedelta

# Import local modules
from ipfs_kit_py.mcp.monitoring.prometheus_exporter import get_exporter, PrometheusExporter
from ipfs_kit_py.mcp.monitoring.health_checker import get_health_checker, HealthStatus
from ipfs_kit_py.mcp.monitoring.metrics_collector import MetricsCollector, get_metrics_collector

# Configure logger
logger = logging.getLogger(__name__)

class OptimizedMetricsCollector(MetricsCollector):
    """
    Optimized version of the MetricsCollector with memory usage improvements.
    
    Extends the standard MetricsCollector with features to reduce memory usage:
    1. Time-based retention policy for cached metrics
    2. Memory-aware collection that adapts based on system memory pressure
    3. Selective collection during high memory conditions
    4. Configurable maximum size for metric history
    """
    
    def __init__(
        self,
        prometheus_exporter: Optional[PrometheusExporter] = None,
        enable_default_collectors: bool = True,
        collection_interval: int = 60,
        # New parameters for optimization
        retention_minutes: int = 60,
        max_entries_per_collector: int = 100,
        memory_pressure_threshold: float = 85.0,
        enable_memory_adaptive_collection: bool = True,
    ):
        """
        Initialize the optimized metrics collector.
        
        Args:
            prometheus_exporter: Prometheus exporter to use
            enable_default_collectors: Whether to enable default system metrics collectors
            collection_interval: Interval in seconds for automatic metrics collection
            retention_minutes: Maximum retention time in minutes for cached metrics
            max_entries_per_collector: Maximum number of historical entries to keep per collector
            memory_pressure_threshold: Memory usage percentage above which to enable low-memory mode
            enable_memory_adaptive_collection: Whether to adapt collection based on memory pressure
        """
        # Call parent constructor
        super().__init__(
            prometheus_exporter=prometheus_exporter,
            enable_default_collectors=enable_default_collectors,
            collection_interval=collection_interval,
        )
        
        # Optimization settings
        self.retention_minutes = retention_minutes
        self.max_entries_per_collector = max_entries_per_collector
        self.memory_pressure_threshold = memory_pressure_threshold
        self.enable_memory_adaptive_collection = enable_memory_adaptive_collection
        
        # Replace the simple dict cache with a time-limited cache for each collector
        self._metric_history: Dict[str, Deque[Dict[str, Any]]] = {}
        self._metric_timestamps: Dict[str, Deque[float]] = {}
        
        # Time of last cleanup
        self._last_cleanup = time.time()
        
        # Memory pressure status
        self._under_memory_pressure = False
        self._last_memory_check = time.time()
        self._memory_check_interval = 60  # seconds
        
        # Critical collectors that should always run
        self._critical_collectors = {"cpu", "memory"}
        
        logger.info("Initialized optimized metrics collector with memory efficiency features")
    
    def _check_memory_pressure(self) -> bool:
        """
        Check if the system is under memory pressure.
        
        Returns:
            True if system is under memory pressure, False otherwise
        """
        # Only check periodically to avoid constant overhead
        now = time.time()
        if now - self._last_memory_check < self._memory_check_interval:
            return self._under_memory_pressure
        
        self._last_memory_check = now
        
        try:
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Update memory pressure status
            previous_status = self._under_memory_pressure
            self._under_memory_pressure = memory_percent > self.memory_pressure_threshold
            
            # Log change in memory pressure status
            if previous_status != self._under_memory_pressure:
                if self._under_memory_pressure:
                    logger.warning(
                        f"System under memory pressure ({memory_percent:.1f}% used). "
                        "Switching to selective metrics collection."
                    )
                else:
                    logger.info(
                        f"Memory pressure relieved ({memory_percent:.1f}% used). "
                        "Resuming normal metrics collection."
                    )
            
            return self._under_memory_pressure
            
        except Exception as e:
            logger.error(f"Error checking memory pressure: {str(e)}", exc_info=True)
            return False
    
    def _cleanup_old_metrics(self, force: bool = False) -> None:
        """
        Clean up old metrics that exceed retention period or count limits.
        
        Args:
            force: Whether to force cleanup regardless of timing
        """
        # Only clean up periodically (every 5 minutes) unless forced
        now = time.time()
        if not force and now - self._last_cleanup < 300:  # 5 minutes
            return
        
        self._last_cleanup = now
        retention_seconds = self.retention_minutes * 60
        oldest_allowed = now - retention_seconds
        
        with self._collection_lock:
            collectors_to_check = list(self._metric_history.keys())
            
            for collector in collectors_to_check:
                # Skip if no history for this collector
                if collector not in self._metric_history or collector not in self._metric_timestamps:
                    continue
                
                history = self._metric_history[collector]
                timestamps = self._metric_timestamps[collector]
                
                # First remove by age
                while timestamps and timestamps[0] < oldest_allowed:
                    history.popleft()
                    timestamps.popleft()
                
                # Then enforce maximum entries limit
                while len(history) > self.max_entries_per_collector:
                    history.popleft()
                    timestamps.popleft()
        
        logger.debug(f"Cleaned up metrics older than {self.retention_minutes} minutes")
    
    def collect_metrics(self, collector_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect metrics from registered collectors with memory efficiency.
        
        Overrides the parent method to add memory-aware collection logic.
        
        Args:
            collector_name: Name of the specific collector to run, or None for all
        
        Returns:
            Dictionary of collected metrics
        """
        # Check memory pressure if adaptive collection is enabled
        under_pressure = False
        if self.enable_memory_adaptive_collection:
            under_pressure = self._check_memory_pressure()
        
        metrics = {}
        
        with self._collection_lock:
            if collector_name is not None:
                # Run a specific collector
                if collector_name in self._collectors:
                    try:
                        collector_metrics = self._collectors[collector_name]()
                        metrics[collector_name] = collector_metrics
                        
                        # Update metrics history
                        self._update_metric_history(collector_name, collector_metrics)
                        
                        logger.debug(f"Collected metrics from {collector_name}")
                    except Exception as e:
                        logger.error(f"Error collecting metrics from {collector_name}: {str(e)}", exc_info=True)
                        metrics[collector_name] = {"error": str(e)}
                else:
                    logger.warning(f"Collector not found: {collector_name}")
                    metrics[collector_name] = {"error": "Collector not found"}
            else:
                # Run all collectors (or a subset if under memory pressure)
                for name, collector_func in self._collectors.items():
                    # Skip non-critical collectors when under memory pressure
                    if under_pressure and name not in self._critical_collectors:
                        logger.debug(f"Skipping non-critical collector {name} due to memory pressure")
                        continue
                    
                    try:
                        collector_metrics = collector_func()
                        metrics[name] = collector_metrics
                        
                        # Update metrics history
                        self._update_metric_history(name, collector_metrics)
                        
                        logger.debug(f"Collected metrics from {name}")
                    except Exception as e:
                        logger.error(f"Error collecting metrics from {name}: {str(e)}", exc_info=True)
                        metrics[name] = {"error": str(e)}
        
        # Add timestamp
        metrics["timestamp"] = time.time()
        
        # Clean up old metrics
        self._cleanup_old_metrics()
        
        return metrics
    
    def _update_metric_history(self, collector_name: str, metrics: Dict[str, Any]) -> None:
        """
        Update the metrics history for a collector.
        
        Args:
            collector_name: Name of the collector
            metrics: Collected metrics
        """
        # Initialize history and timestamps deques if not already present
        if collector_name not in self._metric_history:
            self._metric_history[collector_name] = deque(maxlen=self.max_entries_per_collector)
            self._metric_timestamps[collector_name] = deque(maxlen=self.max_entries_per_collector)
        
        # Add new metrics and timestamp
        self._metric_history[collector_name].append(metrics)
        self._metric_timestamps[collector_name].append(time.time())
    
    def get_metrics(self, collector_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the most recently collected metrics with memory efficiency.
        
        Args:
            collector_name: Name of the specific collector to get metrics for, or None for all
        
        Returns:
            Dictionary of metrics
        """
        with self._collection_lock:
            if collector_name is not None:
                # Get metrics for a specific collector
                if collector_name in self._metric_history and self._metric_history[collector_name]:
                    return {
                        collector_name: self._metric_history[collector_name][-1],
                        "timestamp": time.time(),
                    }
                else:
                    logger.warning(f"No metrics available for collector: {collector_name}")
                    return {
                        collector_name: {"error": "No metrics available"},
                        "timestamp": time.time(),
                    }
            else:
                # Get all metrics (most recent entry for each collector)
                result = {"timestamp": time.time()}
                
                for name, history in self._metric_history.items():
                    if history:  # Check if the deque is not empty
                        result[name] = history[-1]
                
                return result
    
    def get_metrics_history(
        self,
        collector_name: str,
        minutes: Optional[int] = None,
        max_entries: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get historical metrics for a specific collector.
        
        Args:
            collector_name: Name of the collector to get metrics for
            minutes: Number of minutes of history to return, or None for all available
            max_entries: Maximum number of entries to return, or None for all available
        
        Returns:
            List of metrics dictionaries with timestamps
        """
        with self._collection_lock:
            if collector_name not in self._metric_history:
                logger.warning(f"No metrics history available for collector: {collector_name}")
                return []
            
            history = list(self._metric_history[collector_name])
            timestamps = list(self._metric_timestamps[collector_name])
            
            # Filter by time if specified
            if minutes is not None:
                oldest_allowed = time.time() - (minutes * 60)
                filtered_metrics = []
                
                for i, timestamp in enumerate(timestamps):
                    if timestamp >= oldest_allowed:
                        filtered_metrics.append({
                            "timestamp": timestamp,
                            "metrics": history[i],
                        })
                
                history_with_timestamps = filtered_metrics
            else:
                # Combine metrics with timestamps
                history_with_timestamps = [
                    {"timestamp": timestamp, "metrics": metrics}
                    for timestamp, metrics in zip(timestamps, history)
                ]
            
            # Limit number of entries if specified
            if max_entries is not None and max_entries > 0:
                history_with_timestamps = history_with_timestamps[-max_entries:]
            
            return history_with_timestamps
    
    def register_with_fastapi(self, app: Any, path: str = "/metrics/collect") -> None:
        """
        Register metrics collection endpoints with a FastAPI application.
        
        Extended to add history endpoint.
        
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
            
            # Call parent method to register basic endpoints
            super().register_with_fastapi(app, path)
            
            # Add history endpoint
            @router.get(f"{path}/history")
            async def get_metrics_history(
                collector: str = Query(..., description="Collector to get history for"),
                minutes: Optional[int] = Query(None, description="Number of minutes of history to return"),
                max_entries: Optional[int] = Query(None, description="Maximum number of entries to return"),
            ):
                """Get historical metrics for a specific collector."""
                return self.get_metrics_history(
                    collector_name=collector,
                    minutes=minutes,
                    max_entries=max_entries,
                )
            
            # Add info endpoint with extended information
            @router.get(f"{path}/settings")
            async def get_collector_settings():
                """Get information about collector settings."""
                return {
                    "collectors": list(self._collectors.keys()),
                    "critical_collectors": list(self._critical_collectors),
                    "collection_interval": self.collection_interval,
                    "retention_minutes": self.retention_minutes,
                    "max_entries_per_collector": self.max_entries_per_collector,
                    "memory_pressure_threshold": self.memory_pressure_threshold,
                    "enable_memory_adaptive_collection": self.enable_memory_adaptive_collection,
                    "under_memory_pressure": self._under_memory_pressure,
                    "auto_collection": self._collection_thread is not None and self._collection_thread.is_alive(),
                }
            
            # Add cleanup endpoint
            @router.post(f"{path}/cleanup")
            async def force_metrics_cleanup():
                """Force cleanup of old metrics."""
                self._cleanup_old_metrics(force=True)
                return {"message": "Metrics cleanup completed"}
            
            # Include the router in the app
            app.include_router(router)
            logger.info(f"Registered optimized metrics collection endpoints at {path}")
            
        except ImportError:
            logger.error("Cannot register metrics collection endpoints: fastapi not available")
    
    def register_critical_collector(self, collector_name: str) -> None:
        """
        Register a collector as critical, ensuring it runs even under memory pressure.
        
        Args:
            collector_name: Name of the collector to mark as critical
        """
        self._critical_collectors.add(collector_name)
        logger.debug(f"Registered {collector_name} as a critical collector")
    
    def unregister_critical_collector(self, collector_name: str) -> None:
        """
        Unregister a collector as critical.
        
        Args:
            collector_name: Name of the collector to unmark as critical
        """
        if collector_name in self._critical_collectors:
            self._critical_collectors.remove(collector_name)
            logger.debug(f"Unregistered {collector_name} as a critical collector")
    
    def _register_default_collectors(self) -> None:
        """Register default system metrics collectors."""
        # Call parent method to register the collectors
        super()._register_default_collectors()
        
        # Mark CPU and memory collectors as critical
        self._critical_collectors.add("cpu")
        self._critical_collectors.add("memory")

# Singleton instance for global access
_default_optimized_collector = None

def get_optimized_metrics_collector(
    prometheus_exporter: Optional[PrometheusExporter] = None,
    enable_default_collectors: bool = True,
    collection_interval: int = 60,
    retention_minutes: int = 60,
    max_entries_per_collector: int = 100,
    memory_pressure_threshold: float = 85.0,
    enable_memory_adaptive_collection: bool = True,
) -> OptimizedMetricsCollector:
    """
    Get or create the default optimized metrics collector.
    
    Args:
        prometheus_exporter: Prometheus exporter to use
        enable_default_collectors: Whether to enable default system metrics collectors
        collection_interval: Interval in seconds for automatic metrics collection
        retention_minutes: Maximum retention time in minutes for cached metrics
        max_entries_per_collector: Maximum number of historical entries to keep per collector
        memory_pressure_threshold: Memory usage percentage above which to enable low-memory mode
        enable_memory_adaptive_collection: Whether to adapt collection based on memory pressure
    
    Returns:
        OptimizedMetricsCollector instance
    """
    global _default_optimized_collector
    
    if _default_optimized_collector is None:
        _default_optimized_collector = OptimizedMetricsCollector(
            prometheus_exporter=prometheus_exporter,
            enable_default_collectors=enable_default_collectors,
            collection_interval=collection_interval,
            retention_minutes=retention_minutes,
            max_entries_per_collector=max_entries_per_collector,
            memory_pressure_threshold=memory_pressure_threshold,
            enable_memory_adaptive_collection=enable_memory_adaptive_collection,
        )
    
    return _default_optimized_collector

def replace_default_collector_with_optimized():
    """
    Replace the default metrics collector with the optimized version.
    
    This function is used to seamlessly upgrade to the optimized collector
    without requiring changes to existing code that uses the standard collector.
    """
    from ipfs_kit_py.mcp.monitoring.metrics_collector import _default_collector
    
    # Create optimized collector
    optimized = get_optimized_metrics_collector()
    
    # If the default collector exists, copy its state
    if _default_collector is not None:
        # Transfer registered collectors
        for name, func in _default_collector._collectors.items():
            if name not in optimized._collectors:
                optimized.register_collector(name, func)
        
        # Stop existing auto-collection if running
        if (_default_collector._collection_thread is not None and 
            _default_collector._collection_thread.is_alive()):
            _default_collector.stop_auto_collection()
            # Start auto-collection on the optimized collector
            optimized.start_auto_collection()
    
    # Replace the default collector
    import ipfs_kit_py.mcp.monitoring.metrics_collector
    ipfs_kit_py.mcp.monitoring.metrics_collector._default_collector = optimized
    
    logger.info("Replaced default metrics collector with optimized version")
    
    return optimized
