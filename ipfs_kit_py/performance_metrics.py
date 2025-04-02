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
from typing import Dict, List, Any, Optional, Union
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """
    Tracks performance metrics for IPFS operations.
    
    This class provides tools to measure and analyze performance for IPFS operations,
    including latency tracking, bandwidth monitoring, and cache efficiency metrics.
    """
    
    def __init__(self, max_history: int = 1000):
        """
        Initialize the performance metrics tracker.
        
        Args:
            max_history: Maximum number of data points to keep in history for each metric
        """
        self.max_history = max_history
        self.reset()
    
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

