"""
Performance Monitor Module for IPFS Kit

This module provides comprehensive performance monitoring:
- Operation timing and profiling
- Resource usage tracking (CPU, memory, I/O)
- Bottleneck detection
- Performance regression detection
- Metrics collection and aggregation
- Historical tracking

Part of Phase 9: Performance Optimization
"""

import logging
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import RLock
import statistics

logger = logging.getLogger(__name__)


@dataclass
class OperationMetrics:
    """Metrics for a single operation"""
    operation_name: str
    operation_id: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    cpu_percent_start: Optional[float] = None
    cpu_percent_end: Optional[float] = None
    memory_mb_start: Optional[float] = None
    memory_mb_end: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    
    def complete(self, success: bool = True, error: Optional[str] = None):
        """Mark operation as complete"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error = error
        
        # Capture end resource usage
        try:
            process = psutil.Process()
            self.cpu_percent_end = process.cpu_percent()
            self.memory_mb_end = process.memory_info().rss / 1024 / 1024
        except:
            pass


@dataclass
class ResourceSnapshot:
    """Snapshot of system resource usage"""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float


@dataclass
class Bottleneck:
    """Identified performance bottleneck"""
    bottleneck_type: str  # 'cpu', 'memory', 'io', 'operation'
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str
    metric_value: float
    threshold: float
    recommendation: str


@dataclass
class PerformanceStats:
    """Aggregated performance statistics"""
    operation_name: str
    count: int
    total_duration: float
    avg_duration: float
    min_duration: float
    max_duration: float
    median_duration: float
    p95_duration: float
    p99_duration: float
    success_count: int
    failure_count: int
    success_rate: float


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system
    
    Tracks operation metrics, resource usage, and identifies
    bottlenecks for optimization opportunities.
    """
    
    def __init__(
        self,
        history_size: int = 10000,
        resource_sample_interval: int = 60
    ):
        """
        Initialize performance monitor
        
        Args:
            history_size: Maximum operations to keep in history
            resource_sample_interval: Seconds between resource samples
        """
        self.history_size = history_size
        self.resource_sample_interval = resource_sample_interval
        
        # Operation tracking
        self.active_operations: Dict[str, OperationMetrics] = {}
        self.operation_history: deque = deque(maxlen=history_size)
        self.operation_counter = 0
        
        # Resource tracking
        self.resource_samples: deque = deque(maxlen=1440)  # 24h at 1min interval
        self.last_resource_sample = 0
        
        # Baseline metrics for regression detection
        self.baselines: Dict[str, PerformanceStats] = {}
        
        # Thread safety
        self.lock = RLock()
        
        # Initialize process handle
        try:
            self.process = psutil.Process()
        except:
            self.process = None
            logger.warning("Could not initialize psutil process")
        
        logger.info("Performance Monitor initialized")
    
    def start_operation(self, operation_name: str) -> str:
        """
        Start timing an operation
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Operation ID for tracking
        """
        with self.lock:
            op_id = f"{operation_name}_{self.operation_counter}"
            self.operation_counter += 1
            
            # Capture start metrics
            metrics = OperationMetrics(
                operation_name=operation_name,
                operation_id=op_id,
                start_time=time.time()
            )
            
            # Capture start resource usage
            if self.process:
                try:
                    metrics.cpu_percent_start = self.process.cpu_percent()
                    metrics.memory_mb_start = self.process.memory_info().rss / 1024 / 1024
                except:
                    pass
            
            self.active_operations[op_id] = metrics
            
            logger.debug(f"Started operation {op_id}")
            return op_id
    
    def end_operation(
        self,
        operation_id: str,
        success: bool = True,
        error: Optional[str] = None
    ):
        """
        End timing and record metrics
        
        Args:
            operation_id: ID returned from start_operation
            success: Whether operation succeeded
            error: Optional error message
        """
        with self.lock:
            if operation_id not in self.active_operations:
                logger.warning(f"Unknown operation ID: {operation_id}")
                return
            
            metrics = self.active_operations.pop(operation_id)
            metrics.complete(success=success, error=error)
            
            # Add to history
            self.operation_history.append(metrics)
            
            logger.debug(
                f"Completed operation {operation_id} in {metrics.duration:.3f}s "
                f"(success={success})"
            )
            
            # Sample resources periodically
            self._maybe_sample_resources()
    
    def _maybe_sample_resources(self):
        """Sample resources if interval has passed"""
        now = time.time()
        if now - self.last_resource_sample >= self.resource_sample_interval:
            self._sample_resources()
            self.last_resource_sample = now
    
    def _sample_resources(self):
        """Sample current resource usage"""
        if not self.process:
            return
        
        try:
            snapshot = ResourceSnapshot(
                timestamp=time.time(),
                cpu_percent=self.process.cpu_percent(),
                memory_mb=self.process.memory_info().rss / 1024 / 1024,
                memory_percent=self.process.memory_percent(),
                disk_io_read_mb=psutil.disk_io_counters().read_bytes / 1024 / 1024,
                disk_io_write_mb=psutil.disk_io_counters().write_bytes / 1024 / 1024,
                network_sent_mb=psutil.net_io_counters().bytes_sent / 1024 / 1024,
                network_recv_mb=psutil.net_io_counters().bytes_recv / 1024 / 1024
            )
            
            self.resource_samples.append(snapshot)
            logger.debug(f"Resource sample: CPU={snapshot.cpu_percent}%, MEM={snapshot.memory_mb:.1f}MB")
        except Exception as e:
            logger.error(f"Error sampling resources: {e}")
    
    def get_metrics(
        self,
        operation_name: Optional[str] = None,
        timeframe: str = '1h'
    ) -> Dict[str, Any]:
        """
        Get performance metrics
        
        Args:
            operation_name: Filter by operation name (None = all)
            timeframe: Time window ('1h', '24h', '7d', 'all')
            
        Returns:
            Dictionary with metrics
        """
        with self.lock:
            # Parse timeframe
            cutoff = self._parse_timeframe(timeframe)
            
            # Filter operations
            filtered = [
                op for op in self.operation_history
                if (operation_name is None or op.operation_name == operation_name)
                and (cutoff is None or op.start_time >= cutoff)
            ]
            
            if not filtered:
                return {
                    'operation_name': operation_name or 'all',
                    'timeframe': timeframe,
                    'count': 0
                }
            
            # Calculate statistics
            durations = [op.duration for op in filtered if op.duration]
            successful = [op for op in filtered if op.success]
            failed = [op for op in filtered if not op.success]
            
            stats = {
                'operation_name': operation_name or 'all',
                'timeframe': timeframe,
                'count': len(filtered),
                'successful': len(successful),
                'failed': len(failed),
                'success_rate': len(successful) / len(filtered) * 100 if filtered else 0,
            }
            
            if durations:
                stats.update({
                    'total_duration': sum(durations),
                    'avg_duration': statistics.mean(durations),
                    'min_duration': min(durations),
                    'max_duration': max(durations),
                    'median_duration': statistics.median(durations),
                })
                
                # Percentiles
                if len(durations) >= 20:
                    sorted_durations = sorted(durations)
                    p95_idx = int(len(sorted_durations) * 0.95)
                    p99_idx = int(len(sorted_durations) * 0.99)
                    stats['p95_duration'] = sorted_durations[p95_idx]
                    stats['p99_duration'] = sorted_durations[p99_idx]
            
            return stats
    
    def _parse_timeframe(self, timeframe: str) -> Optional[float]:
        """Parse timeframe to cutoff timestamp"""
        if timeframe == 'all':
            return None
        
        now = time.time()
        if timeframe.endswith('h'):
            hours = int(timeframe[:-1])
            return now - (hours * 3600)
        elif timeframe.endswith('d'):
            days = int(timeframe[:-1])
            return now - (days * 86400)
        elif timeframe.endswith('m'):
            minutes = int(timeframe[:-1])
            return now - (minutes * 60)
        else:
            return now - 3600  # Default 1 hour
    
    def detect_bottlenecks(
        self,
        cpu_threshold: float = 80.0,
        memory_threshold: float = 80.0,
        slow_operation_factor: float = 2.0
    ) -> List[Bottleneck]:
        """
        Identify performance bottlenecks
        
        Args:
            cpu_threshold: CPU usage percentage threshold
            memory_threshold: Memory usage percentage threshold
            slow_operation_factor: Multiplier for slow operation detection
            
        Returns:
            List of identified bottlenecks
        """
        bottlenecks = []
        
        # Check resource usage
        if self.resource_samples:
            recent_samples = list(self.resource_samples)[-10:]  # Last 10 samples
            
            # CPU bottleneck
            avg_cpu = statistics.mean(s.cpu_percent for s in recent_samples)
            if avg_cpu > cpu_threshold:
                severity = 'critical' if avg_cpu > 95 else 'high' if avg_cpu > cpu_threshold else 'medium'
                bottlenecks.append(Bottleneck(
                    bottleneck_type='cpu',
                    severity=severity,
                    description=f"High CPU usage: {avg_cpu:.1f}%",
                    metric_value=avg_cpu,
                    threshold=cpu_threshold,
                    recommendation="Consider optimizing CPU-intensive operations or scaling horizontally"
                ))
            
            # Memory bottleneck
            avg_mem = statistics.mean(s.memory_percent for s in recent_samples)
            if avg_mem > memory_threshold:
                severity = 'critical' if avg_mem > 95 else 'high' if avg_mem > memory_threshold else 'medium'
                bottlenecks.append(Bottleneck(
                    bottleneck_type='memory',
                    severity=severity,
                    description=f"High memory usage: {avg_mem:.1f}%",
                    metric_value=avg_mem,
                    threshold=memory_threshold,
                    recommendation="Consider implementing caching strategies or reducing memory footprint"
                ))
        
        # Check for slow operations
        operation_stats = self._get_operation_stats()
        for op_name, stats in operation_stats.items():
            if stats.count >= 10:  # Need enough samples
                # Compare to baseline
                if op_name in self.baselines:
                    baseline = self.baselines[op_name]
                    if stats.avg_duration > baseline.avg_duration * slow_operation_factor:
                        bottlenecks.append(Bottleneck(
                            bottleneck_type='operation',
                            severity='high',
                            description=f"Operation '{op_name}' is {slow_operation_factor}x slower than baseline",
                            metric_value=stats.avg_duration,
                            threshold=baseline.avg_duration * slow_operation_factor,
                            recommendation=f"Investigate recent changes to '{op_name}' operation"
                        ))
        
        logger.info(f"Detected {len(bottlenecks)} bottlenecks")
        return bottlenecks
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """
        Get current resource usage
        
        Returns:
            Dictionary with resource usage metrics
        """
        if not self.process:
            return {'error': 'Process monitoring not available'}
        
        try:
            usage = {
                'timestamp': time.time(),
                'cpu_percent': self.process.cpu_percent(),
                'memory_mb': self.process.memory_info().rss / 1024 / 1024,
                'memory_percent': self.process.memory_percent(),
                'num_threads': self.process.num_threads(),
            }
            
            # System-wide metrics
            usage.update({
                'system_cpu_percent': psutil.cpu_percent(interval=0.1),
                'system_memory_percent': psutil.virtual_memory().percent,
                'system_disk_usage_percent': psutil.disk_usage('/').percent,
            })
            
            return usage
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {'error': str(e)}
    
    def set_baseline(self, operation_name: str):
        """
        Set current performance as baseline for regression detection
        
        Args:
            operation_name: Operation to set baseline for
        """
        stats = self.get_metrics(operation_name=operation_name, timeframe='24h')
        if stats['count'] >= 10:
            self.baselines[operation_name] = PerformanceStats(
                operation_name=operation_name,
                count=stats['count'],
                total_duration=stats.get('total_duration', 0),
                avg_duration=stats.get('avg_duration', 0),
                min_duration=stats.get('min_duration', 0),
                max_duration=stats.get('max_duration', 0),
                median_duration=stats.get('median_duration', 0),
                p95_duration=stats.get('p95_duration', 0),
                p99_duration=stats.get('p99_duration', 0),
                success_count=stats.get('successful', 0),
                failure_count=stats.get('failed', 0),
                success_rate=stats.get('success_rate', 0)
            )
            logger.info(f"Set baseline for '{operation_name}' (avg={stats['avg_duration']:.3f}s)")
        else:
            logger.warning(f"Not enough data to set baseline for '{operation_name}' ({stats['count']} < 10)")
    
    def _get_operation_stats(self) -> Dict[str, PerformanceStats]:
        """Get statistics grouped by operation name"""
        stats_by_name = defaultdict(list)
        
        for op in self.operation_history:
            if op.duration:
                stats_by_name[op.operation_name].append(op)
        
        result = {}
        for op_name, ops in stats_by_name.items():
            durations = [op.duration for op in ops]
            successful = [op for op in ops if op.success]
            
            if durations:
                sorted_durations = sorted(durations)
                result[op_name] = PerformanceStats(
                    operation_name=op_name,
                    count=len(ops),
                    total_duration=sum(durations),
                    avg_duration=statistics.mean(durations),
                    min_duration=min(durations),
                    max_duration=max(durations),
                    median_duration=statistics.median(durations),
                    p95_duration=sorted_durations[int(len(sorted_durations) * 0.95)] if len(sorted_durations) >= 20 else 0,
                    p99_duration=sorted_durations[int(len(sorted_durations) * 0.99)] if len(sorted_durations) >= 20 else 0,
                    success_count=len(successful),
                    failure_count=len(ops) - len(successful),
                    success_rate=len(successful) / len(ops) * 100 if ops else 0
                )
        
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get overall monitoring statistics
        
        Returns:
            Dictionary with monitoring stats
        """
        with self.lock:
            return {
                'total_operations_tracked': len(self.operation_history),
                'active_operations': len(self.active_operations),
                'resource_samples_collected': len(self.resource_samples),
                'unique_operations': len(set(op.operation_name for op in self.operation_history)),
                'baselines_set': len(self.baselines)
            }
