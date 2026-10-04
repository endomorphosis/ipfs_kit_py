"""
Performance Tracking for Storage Backend Selection

This module implements performance tracking and analysis for selecting
the optimal storage backend based on observed performance metrics.
"""

import logging
import time
import threading
from typing import Dict, List, Any, Optional, Set, Tuple

from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)


class BackendPerformanceTracker:
    """
    Tracks performance metrics for each backend.
    
    This is used by the router to make performance-based decisions.
    """
    
    def __init__(self, window_size: int = 100, decay_factor: float = 0.95):
        """
        Initialize the performance tracker.
        
        Args:
            window_size: Number of operations to track per backend
            decay_factor: Decay factor for weighted averages (0.0-1.0)
        """
        self.window_size = window_size
        self.decay_factor = decay_factor
        
        # Performance data
        self.latency = {}  # Backend type -> list of operation latencies
        self.throughput = {}  # Backend type -> list of operation throughputs
        self.error_rates = {}  # Backend type -> error count
        self.operation_counts = {}  # Backend type -> operation count
        
        # Operation-specific metrics
        self.operation_latency = {}  # Backend type -> operation type -> list of latencies
        self.operation_errors = {}  # Backend type -> operation type -> error count
        self.operation_throughput = {}  # Backend type -> operation type -> list of throughputs
        
        # Weighted averages
        self.weighted_latency = {}  # Backend type -> weighted average latency
        self.weighted_throughput = {}  # Backend type -> weighted average throughput
        self.weighted_error_rate = {}  # Backend type -> weighted average error rate
        
        # Last update times
        self.last_updated = {}  # Backend type -> last update time
        
        # Lock for thread safety
        self.lock = threading.RLock()
    
    def record_operation(
        self,
        backend_type: StorageBackendType,
        operation_type: str,
        latency: float,
        size: Optional[int] = None,
        success: bool = True,
    ):
        """
        Record a backend operation.
        
        Args:
            backend_type: Backend type
            operation_type: Type of operation (store, retrieve, etc.)
            latency: Operation latency in seconds
            size: Size of data in bytes (for throughput calculation)
            success: Whether operation was successful
        """
        with self.lock:
            backend_name = backend_type.value
            
            # Initialize data structures if needed
            if backend_name not in self.latency:
                self.latency[backend_name] = []
                self.throughput[backend_name] = []
                self.error_rates[backend_name] = 0
                self.operation_counts[backend_name] = 0
                self.weighted_latency[backend_name] = 0
                self.weighted_throughput[backend_name] = 0
                self.weighted_error_rate[backend_name] = 0
                self.last_updated[backend_name] = time.time()
                self.operation_latency[backend_name] = {}
                self.operation_errors[backend_name] = {}
                self.operation_throughput[backend_name] = {}
            
            # Initialize operation-specific data structures if needed
            if operation_type not in self.operation_latency[backend_name]:
                self.operation_latency[backend_name][operation_type] = []
                self.operation_errors[backend_name][operation_type] = 0
                self.operation_throughput[backend_name][operation_type] = []
            
            # Record latency
            self.latency[backend_name].append(latency)
            if len(self.latency[backend_name]) > self.window_size:
                self.latency[backend_name].pop(0)
            
            # Record operation-specific latency
            self.operation_latency[backend_name][operation_type].append(latency)
            if len(self.operation_latency[backend_name][operation_type]) > self.window_size:
                self.operation_latency[backend_name][operation_type].pop(0)
            
            # Record throughput (if size is provided)
            if size is not None and latency > 0:
                throughput = size / latency  # bytes per second
                self.throughput[backend_name].append(throughput)
                if len(self.throughput[backend_name]) > self.window_size:
                    self.throughput[backend_name].pop(0)
                
                # Record operation-specific throughput
                self.operation_throughput[backend_name][operation_type].append(throughput)
                if len(self.operation_throughput[backend_name][operation_type]) > self.window_size:
                    self.operation_throughput[backend_name][operation_type].pop(0)
            
            # Record success/failure
            self.operation_counts[backend_name] += 1
            if not success:
                self.error_rates[backend_name] += 1
                self.operation_errors[backend_name][operation_type] += 1
            
            # Update weighted averages
            self._update_weighted_averages(backend_name)
    
    def _update_weighted_averages(self, backend_name: str):
        """
        Update weighted averages for a backend.
        
        Args:
            backend_name: Backend name
        """
        # Update latency average
        if self.latency[backend_name]:
            avg_latency = sum(self.latency[backend_name]) / len(self.latency[backend_name])
            if self.weighted_latency[backend_name] == 0:
                self.weighted_latency[backend_name] = avg_latency
            else:
                self.weighted_latency[backend_name] = (
                    self.decay_factor * self.weighted_latency[backend_name] +
                    (1 - self.decay_factor) * avg_latency
                )
        
        # Update throughput average
        if self.throughput[backend_name]:
            avg_throughput = sum(self.throughput[backend_name]) / len(self.throughput[backend_name])
            if self.weighted_throughput[backend_name] == 0:
                self.weighted_throughput[backend_name] = avg_throughput
            else:
                self.weighted_throughput[backend_name] = (
                    self.decay_factor * self.weighted_throughput[backend_name] +
                    (1 - self.decay_factor) * avg_throughput
                )
        
        # Update error rate
        if self.operation_counts[backend_name] > 0:
            error_rate = self.error_rates[backend_name] / self.operation_counts[backend_name]
            if self.weighted_error_rate[backend_name] == 0:
                self.weighted_error_rate[backend_name] = error_rate
            else:
                self.weighted_error_rate[backend_name] = (
                    self.decay_factor * self.weighted_error_rate[backend_name] +
                    (1 - self.decay_factor) * error_rate
                )
        
        # Update last updated time
        self.last_updated[backend_name] = time.time()
    
    def get_performance_score(self, backend_type: StorageBackendType) -> float:
        """
        Calculate a performance score for a backend.
        
        Args:
            backend_type: Backend type
            
        Returns:
            Performance score (higher is better)
        """
        with self.lock:
            backend_name = backend_type.value
            
            # If no data, return neutral score
            if backend_name not in self.operation_counts or self.operation_counts[backend_name] == 0:
                return 0.5
            
            # Get weighted metrics
            latency = self.weighted_latency.get(backend_name, 0)
            throughput = self.weighted_throughput.get(backend_name, 0)
            error_rate = self.weighted_error_rate.get(backend_name, 0)
            
            # Normalize latency (lower is better, invert for score)
            latency_score = 0.5
            if latency > 0:
                # Map latency to a score (1.0 for very fast, 0.0 for very slow)
                # Use exponential function to prefer lower latencies
                normalized_latency = min(latency, 10.0) / 10.0  # Cap at 10 seconds
                latency_score = 1.0 - normalized_latency
            
            # Normalize throughput (higher is better)
            throughput_score = 0.5
            if throughput > 0:
                # Map throughput to a score (1.0 for very fast, 0.0 for very slow)
                # 10 MB/s or higher gets a perfect score
                normalized_throughput = min(throughput / (10 * 1024 * 1024), 1.0)
                throughput_score = normalized_throughput
            
            # Normalize error rate (lower is better, invert for score)
            error_score = 1.0 - error_rate  # 1.0 for no errors, 0.0 for all errors
            
            # Calculate weighted score
            # Give higher weight to error rate as reliability is important
            score = 0.3 * latency_score + 0.3 * throughput_score + 0.4 * error_score
            
            return score
    
    def get_operation_performance(
        self, 
        backend_type: StorageBackendType, 
        operation_type: str
    ) -> Dict[str, Any]:
        """
        Get performance metrics for a specific operation.
        
        Args:
            backend_type: Backend type
            operation_type: Operation type
            
        Returns:
            Dictionary of performance metrics
        """
        with self.lock:
            backend_name = backend_type.value
            
            # Check if we have data for this backend and operation
            if (backend_name not in self.operation_latency or 
                operation_type not in self.operation_latency[backend_name]):
                return {
                    "operation_count": 0,
                    "error_count": 0,
                    "average_latency": 0,
                    "average_throughput": 0,
                    "error_rate": 0,
                    "performance_score": 0.5,
                }
            
            # Get operation metrics
            latencies = self.operation_latency[backend_name][operation_type]
            throughputs = self.operation_throughput[backend_name][operation_type]
            error_count = self.operation_errors[backend_name][operation_type]
            
            # Calculate averages
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            avg_throughput = sum(throughputs) / len(throughputs) if throughputs else 0
            operation_count = len(latencies)
            error_rate = error_count / operation_count if operation_count > 0 else 0
            
            # Calculate performance score
            latency_score = 0.5
            if avg_latency > 0:
                normalized_latency = min(avg_latency, 10.0) / 10.0
                latency_score = 1.0 - normalized_latency
            
            throughput_score = 0.5
            if avg_throughput > 0:
                normalized_throughput = min(avg_throughput / (10 * 1024 * 1024), 1.0)
                throughput_score = normalized_throughput
            
            error_score = 1.0 - error_rate
            
            # Calculate weighted score
            performance_score = 0.3 * latency_score + 0.3 * throughput_score + 0.4 * error_score
            
            return {
                "operation_count": operation_count,
                "error_count": error_count,
                "average_latency": avg_latency,
                "average_throughput": avg_throughput,
                "error_rate": error_rate,
                "performance_score": performance_score,
            }
    
    def get_operation_performance_score(
        self, 
        backend_type: StorageBackendType, 
        operation_type: str
    ) -> float:
        """
        Calculate a performance score for a specific operation.
        
        Args:
            backend_type: Backend type
            operation_type: Operation type
            
        Returns:
            Performance score (higher is better)
        """
        metrics = self.get_operation_performance(backend_type, operation_type)
        return metrics["performance_score"]
    
    def get_fastest_backend(
        self, 
        backends: List[StorageBackendType],
        operation_type: str
    ) -> Optional[StorageBackendType]:
        """
        Get the fastest backend for a specific operation.
        
        Args:
            backends: List of available backends
            operation_type: Operation type
            
        Returns:
            Fastest backend or None if no backends available
        """
        if not backends:
            return None
        
        # Calculate performance scores for each backend
        backend_scores = {}
        for backend in backends:
            score = self.get_operation_performance_score(backend, operation_type)
            backend_scores[backend] = score
        
        # Find backend with highest score
        return max(backend_scores.items(), key=lambda x: x[1])[0]
    
    def get_most_reliable_backend(self, backends: List[StorageBackendType]) -> Optional[StorageBackendType]:
        """
        Get the most reliable backend based on error rates.
        
        Args:
            backends: List of available backends
            
        Returns:
            Most reliable backend or None if no backends available
        """
        if not backends:
            return None
        
        # Calculate reliability scores for each backend
        backend_scores = {}
        for backend in backends:
            backend_name = backend.value
            
            if backend_name in self.weighted_error_rate:
                # Invert error rate to get reliability score
                reliability = 1.0 - self.weighted_error_rate[backend_name]
                backend_scores[backend] = reliability
            else:
                # No data, use neutral score
                backend_scores[backend] = 0.5
        
        # Find backend with highest reliability score
        return max(backend_scores.items(), key=lambda x: x[1])[0]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current performance statistics.
        
        Returns:
            Dictionary of performance statistics
        """
        with self.lock:
            stats = {
                "backends": {},
                "window_size": self.window_size,
            }
            
            for backend_name in self.operation_counts.keys():
                operation_stats = {}
                for op_type in self.operation_latency.get(backend_name, {}):
                    operation_stats[op_type] = self.get_operation_performance(
                        StorageBackendType.from_string(backend_name), 
                        op_type
                    )
                
                backend_stats = {
                    "operation_count": self.operation_counts.get(backend_name, 0),
                    "error_count": self.error_rates.get(backend_name, 0),
                    "weighted_latency": self.weighted_latency.get(backend_name, 0),
                    "weighted_throughput": self.weighted_throughput.get(backend_name, 0),
                    "weighted_error_rate": self.weighted_error_rate.get(backend_name, 0),
                    "last_updated": self.last_updated.get(backend_name, 0),
                    "performance_score": self.get_performance_score(
                        StorageBackendType.from_string(backend_name)
                    ),
                    "operations": operation_stats,
                }
                
                stats["backends"][backend_name] = backend_stats
            
            return stats
    
    def reset(self):
        """Reset all metrics."""
        with self.lock:
            self.latency = {}
            self.throughput = {}
            self.error_rates = {}
            self.operation_counts = {}
            self.operation_latency = {}
            self.operation_errors = {}
            self.operation_throughput = {}
            self.weighted_latency = {}
            self.weighted_throughput = {}
            self.weighted_error_rate = {}
            self.last_updated = {}


# Singleton instance
_instance = None

def get_instance(window_size: int = 100, decay_factor: float = 0.95) -> BackendPerformanceTracker:
    """
    Get or create the singleton performance tracker instance.
    
    Args:
        window_size: Number of operations to track per backend
        decay_factor: Decay factor for weighted averages (0.0-1.0)
        
    Returns:
        BackendPerformanceTracker instance
    """
    global _instance
    if _instance is None:
        _instance = BackendPerformanceTracker(window_size, decay_factor)
    return _instance