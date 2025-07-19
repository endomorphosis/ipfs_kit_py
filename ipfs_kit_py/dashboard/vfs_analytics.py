#!/usr/bin/env python3
"""
Advanced VFS Analytics Module

This module provides comprehensive virtual filesystem analytics including:
- Real-time bandwidth monitoring
- Filesystem operation tracking
- Replication health monitoring
- Performance metrics and bottleneck detection
- Cache efficiency analysis
- Storage backend health monitoring
- Network traffic analysis
- Error rate tracking and alerting
"""

import asyncio
import time
import json
import logging
import psutil
import threading
from datetime import datetime, timedelta
from collections import deque, defaultdict
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

@dataclass
class VFSOperationMetric:
    """Individual VFS operation metric."""
    timestamp: float
    operation: str
    path: str
    size_bytes: int
    duration_ms: float
    success: bool
    error_msg: Optional[str] = None
    backend: Optional[str] = None
    cache_hit: bool = False

@dataclass
class BandwidthMetric:
    """Bandwidth usage metric."""
    timestamp: float
    direction: str  # 'in' or 'out'
    bytes_per_second: float
    interface: str  # 'ipfs', 'local', 's3', etc.
    operation_type: str  # 'read', 'write', 'sync'

@dataclass
class ReplicationStatus:
    """Replication health status."""
    timestamp: float
    total_replicas: int
    healthy_replicas: int
    unhealthy_replicas: int
    sync_lag_seconds: float
    last_sync_time: float
    pending_operations: int
    failed_operations: int

@dataclass
class CacheMetrics:
    """Cache performance metrics."""
    timestamp: float
    hit_rate: float
    miss_rate: float
    eviction_rate: float
    size_bytes: int
    max_size_bytes: int
    avg_lookup_time_ms: float
    memory_pressure: float

@dataclass
class VFSHealthStatus:
    """Overall VFS health status."""
    timestamp: float
    overall_health: str  # 'healthy', 'warning', 'critical'
    available_backends: List[str]
    failed_backends: List[str]
    total_operations_per_second: float
    error_rate: float
    average_latency_ms: float
    storage_utilization: float


class VFSPerformanceMonitor:
    """Advanced VFS performance monitoring system."""
    
    def __init__(self, max_history_hours: int = 24):
        self.max_history_hours = max_history_hours
        self.max_entries = max_history_hours * 3600  # 1 per second max
        
        # Operation tracking
        self.operations = deque(maxlen=self.max_entries)
        self.operation_stats = defaultdict(lambda: {
            'count': 0, 'total_time': 0, 'errors': 0, 'bytes': 0
        })
        
        # Bandwidth tracking
        self.bandwidth_metrics = deque(maxlen=self.max_entries)
        self.bandwidth_by_interface = defaultdict(lambda: deque(maxlen=1000))
        
        # Replication tracking
        self.replication_history = deque(maxlen=self.max_entries)
        
        # Cache tracking
        self.cache_history = deque(maxlen=self.max_entries)
        
        # Health tracking
        self.health_history = deque(maxlen=self.max_entries)
        
        # Real-time counters
        self.realtime_ops_counter = 0
        self.realtime_bytes_counter = 0
        self.realtime_errors_counter = 0
        self.last_reset_time = time.time()
        
        # Backend monitoring
        self.backend_health = {}
        self.backend_latencies = defaultdict(lambda: deque(maxlen=100))
        
        # Alert thresholds
        self.alert_thresholds = {
            'error_rate': 0.05,  # 5%
            'latency_ms': 5000,  # 5 seconds
            'bandwidth_threshold': 100 * 1024 * 1024,  # 100MB/s
            'cache_hit_rate': 0.8  # 80%
        }
        
        self.lock = threading.Lock()
        
    def record_operation(self, operation: str, path: str, size_bytes: int, 
                        duration_ms: float, success: bool, error_msg: str = None,
                        backend: str = None, cache_hit: bool = False):
        """Record a VFS operation for analytics."""
        with self.lock:
            metric = VFSOperationMetric(
                timestamp=time.time(),
                operation=operation,
                path=path,
                size_bytes=size_bytes,
                duration_ms=duration_ms,
                success=success,
                error_msg=error_msg,
                backend=backend,
                cache_hit=cache_hit
            )
            
            self.operations.append(metric)
            
            # Update operation stats
            key = f"{operation}:{backend or 'unknown'}"
            stats = self.operation_stats[key]
            stats['count'] += 1
            stats['total_time'] += duration_ms
            stats['bytes'] += size_bytes
            if not success:
                stats['errors'] += 1
            
            # Update real-time counters
            self.realtime_ops_counter += 1
            self.realtime_bytes_counter += size_bytes
            if not success:
                self.realtime_errors_counter += 1
                
    def record_bandwidth(self, direction: str, bytes_per_second: float, 
                        interface: str, operation_type: str):
        """Record bandwidth usage."""
        with self.lock:
            metric = BandwidthMetric(
                timestamp=time.time(),
                direction=direction,
                bytes_per_second=bytes_per_second,
                interface=interface,
                operation_type=operation_type
            )
            
            self.bandwidth_metrics.append(metric)
            self.bandwidth_by_interface[interface].append(metric)
            
    def record_replication_status(self, total_replicas: int, healthy_replicas: int,
                                sync_lag_seconds: float, pending_ops: int, failed_ops: int):
        """Record replication health status."""
        with self.lock:
            status = ReplicationStatus(
                timestamp=time.time(),
                total_replicas=total_replicas,
                healthy_replicas=healthy_replicas,
                unhealthy_replicas=total_replicas - healthy_replicas,
                sync_lag_seconds=sync_lag_seconds,
                last_sync_time=time.time() - sync_lag_seconds,
                pending_operations=pending_ops,
                failed_operations=failed_ops
            )
            
            self.replication_history.append(status)
            
    def record_cache_metrics(self, hit_rate: float, miss_rate: float, eviction_rate: float,
                           size_bytes: int, max_size_bytes: int, avg_lookup_time_ms: float):
        """Record cache performance metrics."""
        with self.lock:
            metrics = CacheMetrics(
                timestamp=time.time(),
                hit_rate=hit_rate,
                miss_rate=miss_rate,
                eviction_rate=eviction_rate,
                size_bytes=size_bytes,
                max_size_bytes=max_size_bytes,
                avg_lookup_time_ms=avg_lookup_time_ms,
                memory_pressure=size_bytes / max_size_bytes if max_size_bytes > 0 else 0
            )
            
            self.cache_history.append(metrics)
            
    def update_backend_health(self, backend: str, is_healthy: bool, latency_ms: float = None):
        """Update backend health status."""
        with self.lock:
            self.backend_health[backend] = {
                'healthy': is_healthy,
                'last_check': time.time(),
                'latency_ms': latency_ms
            }
            
            if latency_ms is not None:
                self.backend_latencies[backend].append(latency_ms)
                
    def get_realtime_metrics(self) -> Dict[str, Any]:
        """Get real-time performance metrics."""
        with self.lock:
            current_time = time.time()
            time_delta = current_time - self.last_reset_time
            
            if time_delta == 0:
                time_delta = 1  # Avoid division by zero
                
            ops_per_second = self.realtime_ops_counter / time_delta
            bytes_per_second = self.realtime_bytes_counter / time_delta
            error_rate = (self.realtime_errors_counter / max(self.realtime_ops_counter, 1))
            
            return {
                'timestamp': current_time,
                'operations_per_second': ops_per_second,
                'bytes_per_second': bytes_per_second,
                'error_rate': error_rate,
                'total_operations': self.realtime_ops_counter,
                'total_bytes': self.realtime_bytes_counter,
                'total_errors': self.realtime_errors_counter,
                'monitoring_duration_seconds': time_delta
            }
    
    def get_bandwidth_analysis(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get detailed bandwidth analysis."""
        with self.lock:
            cutoff_time = time.time() - (time_window_minutes * 60)
            recent_metrics = [m for m in self.bandwidth_metrics if m.timestamp > cutoff_time]
            
            if not recent_metrics:
                return {'error': 'No bandwidth data available'}
            
            # Analyze by interface
            interface_stats = defaultdict(lambda: {'in': [], 'out': []})
            for metric in recent_metrics:
                interface_stats[metric.interface][metric.direction].append(metric.bytes_per_second)
            
            analysis = {}
            total_in = 0
            total_out = 0
            
            for interface, directions in interface_stats.items():
                in_bps = sum(directions['in']) / len(directions['in']) if directions['in'] else 0
                out_bps = sum(directions['out']) / len(directions['out']) if directions['out'] else 0
                
                analysis[interface] = {
                    'average_in_bps': in_bps,
                    'average_out_bps': out_bps,
                    'peak_in_bps': max(directions['in']) if directions['in'] else 0,
                    'peak_out_bps': max(directions['out']) if directions['out'] else 0,
                    'total_samples': len(directions['in']) + len(directions['out'])
                }
                
                total_in += in_bps
                total_out += out_bps
            
            return {
                'time_window_minutes': time_window_minutes,
                'total_average_in_bps': total_in,
                'total_average_out_bps': total_out,
                'total_average_bps': total_in + total_out,
                'interfaces': analysis,
                'sample_count': len(recent_metrics)
            }
    
    def get_operation_analysis(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get detailed operation analysis."""
        with self.lock:
            cutoff_time = time.time() - (time_window_minutes * 60)
            recent_ops = [op for op in self.operations if op.timestamp > cutoff_time]
            
            if not recent_ops:
                return {'error': 'No operation data available'}
            
            # Analyze by operation type
            op_analysis = defaultdict(lambda: {
                'count': 0, 'success_count': 0, 'total_duration': 0, 
                'total_bytes': 0, 'errors': []
            })
            
            for op in recent_ops:
                key = f"{op.operation}:{op.backend or 'unknown'}"
                stats = op_analysis[key]
                stats['count'] += 1
                stats['total_duration'] += op.duration_ms
                stats['total_bytes'] += op.size_bytes
                
                if op.success:
                    stats['success_count'] += 1
                else:
                    stats['errors'].append({
                        'timestamp': op.timestamp,
                        'path': op.path,
                        'error': op.error_msg
                    })
            
            # Calculate derived metrics
            analysis = {}
            for op_key, stats in op_analysis.items():
                success_rate = stats['success_count'] / stats['count'] if stats['count'] > 0 else 0
                avg_duration = stats['total_duration'] / stats['count'] if stats['count'] > 0 else 0
                avg_bytes = stats['total_bytes'] / stats['count'] if stats['count'] > 0 else 0
                
                analysis[op_key] = {
                    'total_operations': stats['count'],
                    'success_rate': success_rate,
                    'error_rate': 1 - success_rate,
                    'average_duration_ms': avg_duration,
                    'average_size_bytes': avg_bytes,
                    'total_bytes': stats['total_bytes'],
                    'operations_per_minute': stats['count'] / time_window_minutes,
                    'recent_errors': stats['errors'][-5:],  # Last 5 errors
                    'error_count': len(stats['errors'])
                }
            
            return {
                'time_window_minutes': time_window_minutes,
                'total_operations': len(recent_ops),
                'operations_by_type': analysis
            }
    
    def get_replication_health(self) -> Dict[str, Any]:
        """Get replication health analysis."""
        with self.lock:
            if not self.replication_history:
                return {'error': 'No replication data available'}
            
            latest = self.replication_history[-1]
            
            # Calculate trends
            if len(self.replication_history) > 1:
                previous = self.replication_history[-2]
                health_trend = latest.healthy_replicas - previous.healthy_replicas
                sync_trend = latest.sync_lag_seconds - previous.sync_lag_seconds
            else:
                health_trend = 0
                sync_trend = 0
            
            health_percentage = (latest.healthy_replicas / latest.total_replicas * 100) if latest.total_replicas > 0 else 0
            
            return {
                'current_status': {
                    'total_replicas': latest.total_replicas,
                    'healthy_replicas': latest.healthy_replicas,
                    'unhealthy_replicas': latest.unhealthy_replicas,
                    'health_percentage': health_percentage,
                    'sync_lag_seconds': latest.sync_lag_seconds,
                    'pending_operations': latest.pending_operations,
                    'failed_operations': latest.failed_operations
                },
                'trends': {
                    'health_change': health_trend,
                    'sync_lag_change': sync_trend
                },
                'alerts': self._generate_replication_alerts(latest)
            }
    
    def get_cache_analysis(self) -> Dict[str, Any]:
        """Get cache performance analysis."""
        with self.lock:
            if not self.cache_history:
                return {'error': 'No cache data available'}
            
            latest = self.cache_history[-1]
            
            # Calculate historical averages
            recent_cache_metrics = list(self.cache_history)[-60:]  # Last 60 entries
            if recent_cache_metrics:
                avg_hit_rate = sum(m.hit_rate for m in recent_cache_metrics) / len(recent_cache_metrics)
                avg_lookup_time = sum(m.avg_lookup_time_ms for m in recent_cache_metrics) / len(recent_cache_metrics)
            else:
                avg_hit_rate = latest.hit_rate
                avg_lookup_time = latest.avg_lookup_time_ms
            
            return {
                'current_metrics': {
                    'hit_rate': latest.hit_rate,
                    'miss_rate': latest.miss_rate,
                    'eviction_rate': latest.eviction_rate,
                    'size_bytes': latest.size_bytes,
                    'max_size_bytes': latest.max_size_bytes,
                    'utilization': latest.memory_pressure,
                    'avg_lookup_time_ms': latest.avg_lookup_time_ms
                },
                'historical_averages': {
                    'avg_hit_rate': avg_hit_rate,
                    'avg_lookup_time_ms': avg_lookup_time
                },
                'alerts': self._generate_cache_alerts(latest)
            }
    
    def get_backend_health_status(self) -> Dict[str, Any]:
        """Get backend health status."""
        with self.lock:
            current_time = time.time()
            backend_status = {}
            
            for backend, health_info in self.backend_health.items():
                age_seconds = current_time - health_info['last_check']
                is_stale = age_seconds > 300  # 5 minutes
                
                # Calculate average latency
                latencies = list(self.backend_latencies[backend])
                avg_latency = sum(latencies) / len(latencies) if latencies else None
                p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else None
                
                backend_status[backend] = {
                    'healthy': health_info['healthy'] and not is_stale,
                    'last_check_age_seconds': age_seconds,
                    'is_stale': is_stale,
                    'current_latency_ms': health_info.get('latency_ms'),
                    'average_latency_ms': avg_latency,
                    'p95_latency_ms': p95_latency,
                    'latency_samples': len(latencies)
                }
            
            healthy_backends = [b for b, s in backend_status.items() if s['healthy']]
            total_backends = len(backend_status)
            
            return {
                'backends': backend_status,
                'summary': {
                    'total_backends': total_backends,
                    'healthy_backends': len(healthy_backends),
                    'unhealthy_backends': total_backends - len(healthy_backends),
                    'health_percentage': len(healthy_backends) / total_backends * 100 if total_backends > 0 else 0
                }
            }
    
    def get_comprehensive_health_report(self) -> Dict[str, Any]:
        """Get comprehensive VFS health report."""
        realtime = self.get_realtime_metrics()
        bandwidth = self.get_bandwidth_analysis()
        operations = self.get_operation_analysis()
        replication = self.get_replication_health()
        cache = self.get_cache_analysis()
        backends = self.get_backend_health_status()
        
        # Generate overall health score
        health_score = self._calculate_overall_health_score(
            realtime, bandwidth, operations, replication, cache, backends
        )
        
        return {
            'timestamp': time.time(),
            'overall_health': health_score,
            'realtime_metrics': realtime,
            'bandwidth_analysis': bandwidth,
            'operation_analysis': operations,
            'replication_health': replication,
            'cache_analysis': cache,
            'backend_health': backends,
            'alerts': self._generate_all_alerts(realtime, bandwidth, operations, replication, cache, backends)
        }
    
    def _generate_replication_alerts(self, status: ReplicationStatus) -> List[Dict[str, Any]]:
        """Generate replication-related alerts."""
        alerts = []
        
        health_percentage = (status.healthy_replicas / status.total_replicas * 100) if status.total_replicas > 0 else 0
        
        if health_percentage < 80:
            alerts.append({
                'severity': 'critical' if health_percentage < 50 else 'warning',
                'type': 'replication_health',
                'message': f'Only {health_percentage:.1f}% of replicas are healthy',
                'value': health_percentage,
                'threshold': 80
            })
        
        if status.sync_lag_seconds > 300:  # 5 minutes
            alerts.append({
                'severity': 'warning',
                'type': 'sync_lag',
                'message': f'Replication sync lag is {status.sync_lag_seconds:.1f} seconds',
                'value': status.sync_lag_seconds,
                'threshold': 300
            })
        
        if status.failed_operations > 0:
            alerts.append({
                'severity': 'warning',
                'type': 'replication_failures',
                'message': f'{status.failed_operations} replication operations have failed',
                'value': status.failed_operations,
                'threshold': 0
            })
        
        return alerts
    
    def _generate_cache_alerts(self, metrics: CacheMetrics) -> List[Dict[str, Any]]:
        """Generate cache-related alerts."""
        alerts = []
        
        if metrics.hit_rate < self.alert_thresholds['cache_hit_rate']:
            alerts.append({
                'severity': 'warning',
                'type': 'cache_hit_rate',
                'message': f'Cache hit rate is {metrics.hit_rate:.1%}',
                'value': metrics.hit_rate,
                'threshold': self.alert_thresholds['cache_hit_rate']
            })
        
        if metrics.memory_pressure > 0.9:
            alerts.append({
                'severity': 'warning',
                'type': 'cache_memory_pressure',
                'message': f'Cache memory usage is {metrics.memory_pressure:.1%}',
                'value': metrics.memory_pressure,
                'threshold': 0.9
            })
        
        if metrics.avg_lookup_time_ms > 1000:  # 1 second
            alerts.append({
                'severity': 'warning',
                'type': 'cache_latency',
                'message': f'Average cache lookup time is {metrics.avg_lookup_time_ms:.1f}ms',
                'value': metrics.avg_lookup_time_ms,
                'threshold': 1000
            })
        
        return alerts
    
    def _generate_all_alerts(self, realtime, bandwidth, operations, replication, cache, backends) -> List[Dict[str, Any]]:
        """Generate all system alerts."""
        alerts = []
        
        # Realtime alerts
        if realtime['error_rate'] > self.alert_thresholds['error_rate']:
            alerts.append({
                'severity': 'critical' if realtime['error_rate'] > 0.2 else 'warning',
                'type': 'high_error_rate',
                'message': f'Error rate is {realtime["error_rate"]:.1%}',
                'value': realtime['error_rate'],
                'threshold': self.alert_thresholds['error_rate']
            })
        
        # Backend alerts
        unhealthy_backends = backends['summary']['unhealthy_backends']
        if unhealthy_backends > 0:
            alerts.append({
                'severity': 'critical' if unhealthy_backends == backends['summary']['total_backends'] else 'warning',
                'type': 'backend_health',
                'message': f'{unhealthy_backends} backends are unhealthy',
                'value': unhealthy_backends,
                'threshold': 0
            })
        
        # Add replication and cache alerts
        if 'current_status' in replication:
            alerts.extend(self._generate_replication_alerts(
                type('obj', (object,), replication['current_status'])()
            ))
        
        if 'current_metrics' in cache:
            cache_obj = type('obj', (object,), cache['current_metrics'])()
            alerts.extend(self._generate_cache_alerts(cache_obj))
        
        return alerts
    
    def _calculate_overall_health_score(self, realtime, bandwidth, operations, replication, cache, backends) -> Dict[str, Any]:
        """Calculate overall VFS health score."""
        scores = []
        factors = []
        
        # Error rate score (0-100)
        error_rate = realtime.get('error_rate', 0)
        error_score = max(0, 100 - (error_rate * 1000))  # Penalize heavily
        scores.append(error_score)
        factors.append(f"Error rate: {error_rate:.2%}")
        
        # Backend health score
        backend_health_pct = backends.get('summary', {}).get('health_percentage', 0)
        scores.append(backend_health_pct)
        factors.append(f"Backend health: {backend_health_pct:.1f}%")
        
        # Replication health score
        if 'current_status' in replication:
            repl_health_pct = replication['current_status'].get('health_percentage', 0)
            scores.append(repl_health_pct)
            factors.append(f"Replication health: {repl_health_pct:.1f}%")
        
        # Cache performance score
        if 'current_metrics' in cache:
            cache_hit_rate = cache['current_metrics'].get('hit_rate', 0)
            cache_score = cache_hit_rate * 100
            scores.append(cache_score)
            factors.append(f"Cache hit rate: {cache_hit_rate:.1%}")
        
        # Calculate weighted average
        overall_score = sum(scores) / len(scores) if scores else 0
        
        # Determine health status
        if overall_score >= 80:
            status = 'healthy'
        elif overall_score >= 60:
            status = 'warning'
        else:
            status = 'critical'
        
        return {
            'score': overall_score,
            'status': status,
            'factors': factors,
            'individual_scores': dict(zip(['error_rate', 'backends', 'replication', 'cache'], scores))
        }
    
    def reset_realtime_counters(self):
        """Reset real-time counters for fresh metrics."""
        with self.lock:
            self.realtime_ops_counter = 0
            self.realtime_bytes_counter = 0
            self.realtime_errors_counter = 0
            self.last_reset_time = time.time()


class VFSSystemMonitor:
    """System-level VFS monitoring."""
    
    def __init__(self):
        self.performance_monitor = VFSPerformanceMonitor()
        self.monitoring_active = False
        self.monitor_thread = None
        
    async def start_monitoring(self):
        """Start background monitoring."""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._background_monitoring, daemon=True)
        self.monitor_thread.start()
        logger.info("VFS system monitoring started")
        
    async def stop_monitoring(self):
        """Stop background monitoring."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("VFS system monitoring stopped")
        
    def _background_monitoring(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                # Monitor system resources
                self._monitor_system_resources()
                
                # Monitor IPFS if available
                self._monitor_ipfs_metrics()
                
                # Simulate VFS operations for demo
                self._simulate_vfs_activity()
                
                time.sleep(1)  # 1-second monitoring interval
                
            except Exception as e:
                logger.error(f"Error in background monitoring: {e}")
                time.sleep(5)  # Wait longer on error
                
    def _monitor_system_resources(self):
        """Monitor system resource usage."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            # Record as bandwidth metrics
            self.performance_monitor.record_bandwidth(
                'in', net_io.bytes_recv, 'system', 'network'
            )
            self.performance_monitor.record_bandwidth(
                'out', net_io.bytes_sent, 'system', 'network'
            )
            
        except Exception as e:
            logger.warning(f"Failed to monitor system resources: {e}")
            
    def _monitor_ipfs_metrics(self):
        """Monitor IPFS daemon metrics."""
        try:
            # Try to get IPFS stats
            result = subprocess.run(
                ['ipfs', 'stats', 'bw'],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                # Parse IPFS bandwidth stats
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'in' in line.lower():
                        # Extract bandwidth values
                        self.performance_monitor.record_bandwidth(
                            'in', 1024 * 1024, 'ipfs', 'daemon'  # Placeholder
                        )
                    elif 'out' in line.lower():
                        self.performance_monitor.record_bandwidth(
                            'out', 512 * 1024, 'ipfs', 'daemon'  # Placeholder
                        )
                        
        except Exception as e:
            logger.debug(f"IPFS monitoring unavailable: {e}")
            
    def _simulate_vfs_activity(self):
        """Simulate VFS activity for demonstration."""
        import random
        
        # Simulate various VFS operations
        operations = ['vfs_read', 'vfs_write', 'vfs_sync', 'vfs_mount', 'vfs_ls']
        backends = ['ipfs', 'local', 's3', 'cache']
        
        # Random operation
        op = random.choice(operations)
        backend = random.choice(backends)
        size = random.randint(1024, 10 * 1024 * 1024)  # 1KB - 10MB
        duration = random.uniform(10, 1000)  # 10ms - 1s
        success = random.random() > 0.05  # 95% success rate
        cache_hit = random.random() > 0.3  # 70% cache hit rate
        
        self.performance_monitor.record_operation(
            operation=op,
            path=f"/vfs/test/file_{random.randint(1, 1000)}.dat",
            size_bytes=size,
            duration_ms=duration,
            success=success,
            error_msg=None if success else "Simulated error",
            backend=backend,
            cache_hit=cache_hit
        )
        
        # Simulate replication status
        if random.random() > 0.9:  # 10% chance to update replication
            self.performance_monitor.record_replication_status(
                total_replicas=5,
                healthy_replicas=random.randint(3, 5),
                sync_lag_seconds=random.uniform(0, 60),
                pending_ops=random.randint(0, 10),
                failed_ops=random.randint(0, 2)
            )
            
        # Simulate cache metrics
        if random.random() > 0.8:  # 20% chance to update cache
            self.performance_monitor.record_cache_metrics(
                hit_rate=random.uniform(0.7, 0.95),
                miss_rate=random.uniform(0.05, 0.3),
                eviction_rate=random.uniform(0, 0.1),
                size_bytes=random.randint(100 * 1024 * 1024, 500 * 1024 * 1024),
                max_size_bytes=1024 * 1024 * 1024,  # 1GB
                avg_lookup_time_ms=random.uniform(1, 50)
            )
            
        # Update backend health
        for backend in backends:
            if random.random() > 0.95:  # 5% chance to update each backend
                self.performance_monitor.update_backend_health(
                    backend=backend,
                    is_healthy=random.random() > 0.1,  # 90% healthy
                    latency_ms=random.uniform(10, 500)
                )
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """Get comprehensive VFS analytics summary."""
        return self.performance_monitor.get_comprehensive_health_report()


# Global VFS monitor instance
vfs_monitor = VFSSystemMonitor()
