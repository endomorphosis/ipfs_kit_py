"""
Performance metrics tracking for IPFS operations.

This module provides utilities for tracking performance metrics like latency,
bandwidth usage, and cache hit rates for IPFS operations.
"""

import time
import json
import math
import os
import logging
import statistics
import threading
from typing import Dict, List, Any, Optional, Union
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """
    Tracks performance metrics for IPFS operations.
    
    This class provides tools to measure and analyze performance for IPFS operations,
    including latency tracking, bandwidth monitoring, and cache efficiency metrics.
    """
    
    def __init__(self, max_history: int = 1000, metrics_dir: Optional[str] = None, 
                 collection_interval: int = 300, enable_logging: bool = True):
        """
        Initialize the performance metrics tracker.
        
        Args:
            max_history: Maximum number of data points to keep in history for each metric
            metrics_dir: Directory to store metrics logs
            collection_interval: How often to collect and log metrics (seconds)
            enable_logging: Whether to enable logging of metrics
        """
        self.max_history = max_history
        self.metrics_dir = metrics_dir
        self.collection_interval = collection_interval
        self.enable_logging = enable_logging
        
        # Create metrics directory if provided
        if self.metrics_dir:
            self.metrics_dir = os.path.expanduser(metrics_dir)
            os.makedirs(self.metrics_dir, exist_ok=True)
        
        self.reset()
        
        # Start collection thread if logging is enabled
        if self.enable_logging and self.metrics_dir:
            self.stop_collection = threading.Event()
            self.collection_thread = threading.Thread(
                target=self._collection_loop,
                daemon=True,
                name="metrics-collector"
            )
            self.collection_thread.start()
            logger.info("Started performance metrics collection")
    
    def reset(self):
        """Reset all metrics to their initial state."""
        # Latency metrics for various operations
        self.latency = defaultdict(lambda: deque(maxlen=self.max_history))
        
        # Bandwidth usage metrics
        self.bandwidth = {
            'inbound': [],
            'outbound': []
        }
        
        # Cache usage metrics
        self.cache = {
            'hits': 0,
            'misses': 0,
            'hit_rate': 0.0,
            'operations': [],
            'tiers': defaultdict(lambda: {'hits': 0, 'misses': 0})
        }
        
        # Operation counts
        self.operations = defaultdict(int)
        
        # Start time for session
        self.start_time = time.time()
    
    def _collection_loop(self):
        """Background thread that collects and logs metrics at regular intervals."""
        while not self.stop_collection.is_set():
            try:
                # Collect metrics
                self._collect_metrics()
                
                # Write to log
                self._write_metrics_to_log()
                
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
            
            # Sleep until next collection interval
            time.sleep(self.collection_interval)
    
    def _collect_metrics(self):
        """Collect metrics from various sources for aggregation."""
        # In a more complex implementation, this could pull metrics from
        # different components or subsystems
        logger.debug("Collecting performance metrics")
        
        # Here we're just using the metrics we already have in memory
    
    def _write_metrics_to_log(self):
        """Write current metrics to log file."""
        if not self.metrics_dir:
            return
        
        try:
            # Generate filename based on timestamp
            current_time = time.time()
            date_str = time.strftime("%Y-%m-%d", time.localtime(current_time))
            hour_str = time.strftime("%H", time.localtime(current_time))
            
            # Create date directory if it doesn't exist
            date_dir = os.path.join(self.metrics_dir, date_str)
            os.makedirs(date_dir, exist_ok=True)
            
            # Create metrics snapshot
            metrics_snapshot = {
                "timestamp": current_time,
                "session_duration": current_time - self.start_time,
                "cache": {
                    "hits": self.cache["hits"],
                    "misses": self.cache["misses"],
                    "hit_rate": self.cache["hit_rate"],
                    "tier_stats": {
                        tier: dict(stats) for tier, stats in self.cache["tiers"].items()
                    }
                },
                "operations": dict(self.operations),
                "latency": {
                    op: {
                        "count": len(values),
                        "min": min(values) if values else None,
                        "max": max(values) if values else None,
                        "mean": statistics.mean(values) if values else None,
                        "median": statistics.median(values) if len(values) > 0 else None,
                        "p95": self._percentile(list(values), 95) if values else None
                    }
                    for op, values in self.latency.items() if values
                },
                "bandwidth": {
                    "inbound_total": sum(item["size"] for item in self.bandwidth["inbound"]),
                    "outbound_total": sum(item["size"] for item in self.bandwidth["outbound"]),
                    "inbound_count": len(self.bandwidth["inbound"]),
                    "outbound_count": len(self.bandwidth["outbound"])
                }
            }
            
            # Write metrics to file
            filename = f"metrics_{hour_str}_{int(current_time)}.json"
            file_path = os.path.join(date_dir, filename)
            
            with open(file_path, "w") as f:
                json.dump(metrics_snapshot, f, indent=2)
                
            logger.debug(f"Wrote metrics to {file_path}")
            
        except Exception as e:
            logger.error(f"Error writing metrics to log: {e}")
    
    def record_operation_time(self, operation: str, elapsed: float):
        """Record the time taken by an operation."""
        self.latency[operation].append(elapsed)
        self.operations[operation] += 1
        
        # Log slow operations (over 1 second)
        if elapsed > 1.0:
            logger.info(f"Slow operation detected: {operation} took {elapsed:.3f}s")
    
    def record_bandwidth_usage(self, direction: str, size_bytes: int, source: str = None):
        """Record bandwidth usage."""
        if direction not in ['inbound', 'outbound']:
            raise ValueError(f"Invalid direction: {direction}. Must be 'inbound' or 'outbound'")
        
        record = {
            'timestamp': time.time(),
            'size': size_bytes
        }
        
        if source:
            record['source'] = source
            
        self.bandwidth[direction].append(record)
        
    def record_cache_access(self, result: str, tier: str = None):
        """Record cache access result."""
        timestamp = time.time()
        
        if result.endswith('_hit') or result == 'hit':
            self.cache['hits'] += 1
            if tier:
                self.cache['tiers'][tier]['hits'] += 1
        elif result == 'miss':
            self.cache['misses'] += 1
            if tier:
                self.cache['tiers'][tier]['misses'] += 1
        
        # Calculate hit rate
        total = self.cache['hits'] + self.cache['misses']
        self.cache['hit_rate'] = self.cache['hits'] / total if total > 0 else 0.0
        
        # Record operation details
        self.cache['operations'].append({
            'timestamp': timestamp,
            'result': result,
            'tier': tier
        })
        
        # Keep only the most recent operations if we exceed max_history
        if len(self.cache['operations']) > self.max_history:
            self.cache['operations'] = self.cache['operations'][-self.max_history:]
    
    def get_operation_stats(self, operation: str = None) -> Dict[str, Any]:
        """Get statistics for an operation or all operations."""
        if operation and operation in self.latency:
            # Stats for specific operation
            latency_data = list(self.latency[operation])
            if not latency_data:
                return {'count': 0}
            
            return {
                'count': len(latency_data),
                'avg': statistics.mean(latency_data) if latency_data else 0,
                'min': min(latency_data) if latency_data else 0,
                'max': max(latency_data) if latency_data else 0,
                'median': statistics.median(latency_data) if latency_data else 0,
                'p95': self._percentile(latency_data, 95) if latency_data else 0,
                'p99': self._percentile(latency_data, 99) if latency_data else 0
            }
        else:
            # Stats for all operations
            result = {'operations': {}}
            for op in self.latency:
                result['operations'][op] = self.get_operation_stats(op)
            return result
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate the percentile value from a data list."""
        if not data:
            return 0
            
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile / 100
        f = math.floor(k)
        c = math.ceil(k)
        
        if f == c:
            return sorted_data[int(k)]
            
        d0 = sorted_data[int(f)] * (c - k)
        d1 = sorted_data[int(c)] * (k - f)
        return d0 + d1
    
    def track_latency(self, operation: str, duration: float):
        """Track latency for an operation (alias for record_operation_time)."""
        self.record_operation_time(operation, duration)
    
    def track_bandwidth(self, direction: str, size_bytes: int, endpoint: str = None):
        """Track bandwidth usage (alias for record_bandwidth_usage)."""
        self.record_bandwidth_usage(direction, size_bytes, source=endpoint)
    
    def track_cache_access(self, hit: bool, tier: str = None):
        """Track cache access (hit or miss)."""
        result = "hit" if hit else "miss"
        self.record_cache_access(result, tier)
    
    def analyze_metrics(self) -> Dict[str, Any]:
        """
        Analyze current metrics and return insights.
        
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            "timestamp": time.time(),
            "session_duration": time.time() - self.start_time,
            "summary": {}
        }
        
        # Analyze latency
        latency_avg = {}
        for op, values in self.latency.items():
            if values:
                latency_avg[op] = statistics.mean(values)
                
        analysis["latency_avg"] = latency_avg
        
        # Find slowest operation
        if latency_avg:
            slowest_op = max(latency_avg.items(), key=lambda x: x[1])
            analysis["summary"]["slowest_operation"] = {
                "operation": slowest_op[0],
                "avg_seconds": slowest_op[1]
            }
        
        # Analyze bandwidth
        inbound_total = sum(item["size"] for item in self.bandwidth["inbound"])
        outbound_total = sum(item["size"] for item in self.bandwidth["outbound"])
        
        analysis["bandwidth_total"] = {
            "inbound": inbound_total,
            "outbound": outbound_total,
            "total": inbound_total + outbound_total
        }
        
        # Analyze cache performance
        hits = self.cache["hits"]
        misses = self.cache["misses"]
        total = hits + misses
        
        if total > 0:
            hit_rate = hits / total
        else:
            hit_rate = 0
            
        analysis["cache_hit_rate"] = hit_rate
        
        # Calculate tier-specific hit rates
        tier_hit_rates = {}
        for tier, stats in self.cache["tiers"].items():
            tier_hits = stats["hits"]
            tier_misses = stats["misses"]
            tier_total = tier_hits + tier_misses
            
            if tier_total > 0:
                tier_hit_rates[tier] = tier_hits / tier_total
            else:
                tier_hit_rates[tier] = 0
                
        analysis["tier_hit_rates"] = tier_hit_rates
        
        # Cache efficiency summary
        if hit_rate < 0.5:
            analysis["summary"]["cache_efficiency"] = "poor"
        elif hit_rate < 0.8:
            analysis["summary"]["cache_efficiency"] = "fair"
        else:
            analysis["summary"]["cache_efficiency"] = "good"
        
        return analysis
    
    def shutdown(self):
        """Shut down the metrics handler and perform final logging."""
        if self.enable_logging and hasattr(self, "stop_collection"):
            # Signal thread to stop
            self.stop_collection.set()
            
            # Wait for thread to finish
            if hasattr(self, "collection_thread"):
                self.collection_thread.join(timeout=5)
                
            # Write final metrics to log
            try:
                self._write_metrics_to_log()
            except Exception as e:
                logger.error(f"Error writing final metrics: {e}")
                
            logger.info("Metrics handler shutdown complete")

