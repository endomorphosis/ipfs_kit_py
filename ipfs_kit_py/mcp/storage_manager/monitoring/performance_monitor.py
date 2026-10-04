"""
Performance monitoring utilities for IPFS backend.

This module implements performance monitoring capabilities for the IPFS backend,
addressing the 'Test performance monitoring after fix' item in the MCP roadmap.
"""

import time
import logging
import threading
import statistics
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
import json
import os

# Configure logger
logger = logging.getLogger(__name__)

class OperationType:
    """Constants for different operation types."""
    ADD = "add"
    GET = "get"
    PIN = "pin"
    UNPIN = "unpin"
    LIST = "list"
    STAT = "stat"

class IPFSPerformanceMonitor:
    """
    Monitors and tracks performance metrics for IPFS operations.
    
    This class implements the performance monitoring capability required
    in the MCP roadmap for the IPFS backend implementation.
    """
    
    def __init__(self, metrics_file: Optional[str] = None):
        """
        Initialize the performance monitor.
        
        Args:
            metrics_file: Optional file path to store metrics persistently
        """
        self.metrics_file = metrics_file or os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "ipfs_performance_metrics.json"
        )
        
        # Initialize metrics data structure
        self.metrics = {
            "operations": {
                OperationType.ADD: {"count": 0, "success": 0, "failed": 0, "response_times": []},
                OperationType.GET: {"count": 0, "success": 0, "failed": 0, "response_times": []},
                OperationType.PIN: {"count": 0, "success": 0, "failed": 0, "response_times": []},
                OperationType.UNPIN: {"count": 0, "success": 0, "failed": 0, "response_times": []},
                OperationType.LIST: {"count": 0, "success": 0, "failed": 0, "response_times": []},
                OperationType.STAT: {"count": 0, "success": 0, "failed": 0, "response_times": []},
            },
            "throughput": {
                "uploads": {"bytes": 0, "operations": 0},
                "downloads": {"bytes": 0, "operations": 0},
            },
            "last_hour": {
                "operations": 0,
                "success_rate": 0,
                "avg_response_time": 0,
            },
            "total": {
                "operations": 0,
                "success_rate": 0,
                "avg_response_time": 0,
            },
            "last_updated": time.time(),
        }
        
        # Load existing metrics if available
        self._load_metrics()
        
        # Set up periodic metrics calculation
        self._setup_periodic_calculations()
    
    def _load_metrics(self):
        """Load metrics from file if available."""
        try:
            if os.path.exists(self.metrics_file):
                with open(self.metrics_file, 'r') as f:
                    stored_metrics = json.load(f)
                    # Update metrics but keep the data structures intact
                    if "operations" in stored_metrics:
                        for op_type, data in stored_metrics["operations"].items():
                            if op_type in self.metrics["operations"]:
                                # Only keep the counts, not the response times from file
                                self.metrics["operations"][op_type]["count"] = data.get("count", 0)
                                self.metrics["operations"][op_type]["success"] = data.get("success", 0)
                                self.metrics["operations"][op_type]["failed"] = data.get("failed", 0)
                    
                    if "throughput" in stored_metrics:
                        for direction, data in stored_metrics["throughput"].items():
                            if direction in self.metrics["throughput"]:
                                self.metrics["throughput"][direction]["bytes"] = data.get("bytes", 0)
                                self.metrics["throughput"][direction]["operations"] = data.get("operations", 0)
                    
                    # Update totals
                    if "total" in stored_metrics:
                        self.metrics["total"]["operations"] = stored_metrics["total"].get("operations", 0)
                        self.metrics["total"]["success_rate"] = stored_metrics["total"].get("success_rate", 0)
                        self.metrics["total"]["avg_response_time"] = stored_metrics["total"].get("avg_response_time", 0)
                        
                    logger.info(f"Loaded performance metrics from {self.metrics_file}")
        except Exception as e:
            logger.error(f"Error loading metrics file: {e}")
    
    def _save_metrics(self):
        """Save metrics to file."""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            
            # Serialize and save
            with open(self.metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
            logger.debug(f"Saved performance metrics to {self.metrics_file}")
        except Exception as e:
            logger.error(f"Error saving metrics file: {e}")
    
    def _setup_periodic_calculations(self):
        """Set up periodic metrics calculation and saving."""
        def _periodic_task():
            while True:
                try:
                    # Calculate aggregate metrics
                    self._calculate_aggregate_metrics()
                    # Save metrics to file
                    self._save_metrics()
                    # Sleep for a while
                    time.sleep(300)  # Run every 5 minutes
                except Exception as e:
                    logger.error(f"Error in periodic metrics task: {e}")
        
        # Start the background thread
        thread = threading.Thread(target=_periodic_task, daemon=True)
        thread.start()
    
    def _calculate_aggregate_metrics(self):
        """Calculate aggregate metrics from raw data."""
        # Update last_updated timestamp
        self.metrics["last_updated"] = time.time()
        
        # Calculate totals
        total_ops = 0
        total_success = 0
        all_response_times = []
        
        for op_type, data in self.metrics["operations"].items():
            total_ops += data["count"]
            total_success += data["success"]
            all_response_times.extend(data["response_times"][-100:])  # Only use recent times
        
        # Update total metrics
        self.metrics["total"]["operations"] = total_ops
        self.metrics["total"]["success_rate"] = (total_success / total_ops * 100) if total_ops > 0 else 0
        
        # Calculate average response time
        if all_response_times:
            self.metrics["total"]["avg_response_time"] = sum(all_response_times) / len(all_response_times)
        
        # Calculate last hour metrics
        # This would typically filter operations from the last hour, but we're simplifying
        # In a production system, you'd store timestamps with each operation
        self.metrics["last_hour"]["operations"] = total_ops
        self.metrics["last_hour"]["success_rate"] = self.metrics["total"]["success_rate"]
        self.metrics["last_hour"]["avg_response_time"] = self.metrics["total"]["avg_response_time"]
    
    def record_operation(self, operation_type: str, success: bool, response_time: float, size: Optional[int] = None):
        """
        Record a completed IPFS operation.
        
        Args:
            operation_type: Type of operation (use OperationType constants)
            success: Whether the operation succeeded
            response_time: Time taken to complete the operation in seconds
            size: Size of data processed in bytes (for add/get operations)
        """
        # Ensure operation type exists
        if operation_type not in self.metrics["operations"]:
            self.metrics["operations"][operation_type] = {
                "count": 0, "success": 0, "failed": 0, "response_times": []
            }
        
        # Update operation counts
        self.metrics["operations"][operation_type]["count"] += 1
        if success:
            self.metrics["operations"][operation_type]["success"] += 1
        else:
            self.metrics["operations"][operation_type]["failed"] += 1
        
        # Keep last 100 response times for each operation type
        self.metrics["operations"][operation_type]["response_times"].append(response_time)
        if len(self.metrics["operations"][operation_type]["response_times"]) > 100:
            self.metrics["operations"][operation_type]["response_times"].pop(0)
        
        # Update throughput for add/get operations if size is provided
        if size is not None:
            if operation_type == OperationType.ADD:
                self.metrics["throughput"]["uploads"]["bytes"] += size
                self.metrics["throughput"]["uploads"]["operations"] += 1
            elif operation_type == OperationType.GET:
                self.metrics["throughput"]["downloads"]["bytes"] += size
                self.metrics["throughput"]["downloads"]["operations"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics.
        
        Returns:
            Dict with current performance metrics
        """
        # Calculate latest metrics
        self._calculate_aggregate_metrics()
        
        # Return a copy of the metrics
        return {
            "operations": {
                op_type: {
                    "count": data["count"],
                    "success": data["success"],
                    "failed": data["failed"],
                    "success_rate": (data["success"] / data["count"] * 100) if data["count"] > 0 else 0,
                    "avg_response_time": sum(data["response_times"][-20:]) / len(data["response_times"][-20:]) if data["response_times"] else 0,
                    "min_response_time": min(data["response_times"]) if data["response_times"] else 0,
                    "max_response_time": max(data["response_times"]) if data["response_times"] else 0,
                }
                for op_type, data in self.metrics["operations"].items()
            },
            "throughput": {
                "uploads": {
                    "bytes": self.metrics["throughput"]["uploads"]["bytes"],
                    "operations": self.metrics["throughput"]["uploads"]["operations"],
                    "avg_bytes_per_op": (
                        self.metrics["throughput"]["uploads"]["bytes"] / 
                        self.metrics["throughput"]["uploads"]["operations"]
                    ) if self.metrics["throughput"]["uploads"]["operations"] > 0 else 0
                },
                "downloads": {
                    "bytes": self.metrics["throughput"]["downloads"]["bytes"],
                    "operations": self.metrics["throughput"]["downloads"]["operations"],
                    "avg_bytes_per_op": (
                        self.metrics["throughput"]["downloads"]["bytes"] / 
                        self.metrics["throughput"]["downloads"]["operations"]
                    ) if self.metrics["throughput"]["downloads"]["operations"] > 0 else 0
                }
            },
            "total": self.metrics["total"],
            "last_hour": self.metrics["last_hour"],
            "last_updated": self.metrics["last_updated"]
        }
    
    def get_operation_stats(self, operation_type: str) -> Dict[str, Any]:
        """
        Get detailed statistics for a specific operation type.
        
        Args:
            operation_type: Type of operation to get stats for
            
        Returns:
            Dict with detailed statistics for the operation
        """
        if operation_type not in self.metrics["operations"]:
            return {"error": f"Unknown operation type: {operation_type}"}
        
        data = self.metrics["operations"][operation_type]
        response_times = data["response_times"]
        
        if not response_times:
            return {
                "count": data["count"],
                "success": data["success"],
                "failed": data["failed"],
                "success_rate": (data["success"] / data["count"] * 100) if data["count"] > 0 else 0,
                "avg_response_time": 0,
                "min_response_time": 0,
                "max_response_time": 0,
                "median_response_time": 0,
                "percentiles": {}
            }
        
        # Calculate statistics
        return {
            "count": data["count"],
            "success": data["success"],
            "failed": data["failed"],
            "success_rate": (data["success"] / data["count"] * 100) if data["count"] > 0 else 0,
            "avg_response_time": sum(response_times) / len(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "median_response_time": statistics.median(response_times) if len(response_times) > 0 else 0,
            "percentiles": {
                "p50": statistics.median(response_times) if len(response_times) > 0 else 0,
                "p90": sorted(response_times)[int(len(response_times) * 0.9)] if len(response_times) > 10 else max(response_times),
                "p95": sorted(response_times)[int(len(response_times) * 0.95)] if len(response_times) > 20 else max(response_times),
                "p99": sorted(response_times)[int(len(response_times) * 0.99)] if len(response_times) > 100 else max(response_times),
            }
        }
    
    def reset_metrics(self):
        """Reset all metrics to zero."""
        for op_type in self.metrics["operations"]:
            self.metrics["operations"][op_type] = {"count": 0, "success": 0, "failed": 0, "response_times": []}
        
        self.metrics["throughput"]["uploads"] = {"bytes": 0, "operations": 0}
        self.metrics["throughput"]["downloads"] = {"bytes": 0, "operations": 0}
        
        self.metrics["total"] = {
            "operations": 0,
            "success_rate": 0,
            "avg_response_time": 0,
        }
        
        self.metrics["last_hour"] = {
            "operations": 0,
            "success_rate": 0,
            "avg_response_time": 0,
        }
        
        self.metrics["last_updated"] = time.time()
        
        # Save reset metrics
        self._save_metrics()

class PerformanceTracker:
    """
    Decorator and context manager for tracking IPFS operation performance.
    """
    
    def __init__(self, monitor: IPFSPerformanceMonitor, operation_type: str):
        """
        Initialize the performance tracker.
        
        Args:
            monitor: Performance monitor instance
            operation_type: Type of operation being tracked
        """
        self.monitor = monitor
        self.operation_type = operation_type
        self.start_time = None
        self.size = None
    
    def __enter__(self):
        """Start tracking when entering the context."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Record metrics when exiting the context."""
        if self.start_time is not None:
            response_time = time.time() - self.start_time
            success = exc_type is None
            self.monitor.record_operation(
                self.operation_type, 
                success, 
                response_time, 
                self.size
            )
    
    def set_size(self, size: int):
        """Set the size of data being processed."""
        self.size = size
    
    @classmethod
    def track(cls, monitor, operation_type):
        """
        Decorator for tracking performance of a function.
        
        Args:
            monitor: Performance monitor instance
            operation_type: Type of operation being tracked
            
        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                with cls(monitor, operation_type) as tracker:
                    # Try to set size if it's available in the first argument
                    if len(args) > 1 and isinstance(args[1], (bytes, str)):
                        tracker.set_size(len(args[1]))
                    
                    result = func(*args, **kwargs)
                    
                    # Try to set size from result if not set already
                    if tracker.size is None and isinstance(result, dict):
                        if "size" in result:
                            tracker.set_size(result["size"])
                        elif "details" in result and isinstance(result["details"], dict):
                            tracker.set_size(result["details"].get("size", 0))
                    
                    return result
            return wrapper
        return decorator
