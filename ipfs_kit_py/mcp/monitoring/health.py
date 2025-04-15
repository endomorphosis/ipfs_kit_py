"""
Health Check System for MCP Server

This module provides health check capabilities for MCP components and backends
as specified in the MCP roadmap for Phase 1: Core Functionality Enhancements (Q3 2025).

Key features:
- Configurable health checks for all components
- Comprehensive system health monitoring
- Backend connectivity and status checks
- Health check aggregation and reporting
- Integration with the alerting system
"""

import os
import re
import time
import socket
import logging
import threading
import json
import psutil
import platform
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Union, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from ..monitoring import MonitoringManager, MetricTag, MetricType

# Configure logging
logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Definition of a health check."""
    id: str
    name: str
    description: str
    check_type: str  # e.g., "backend", "system", "component"
    target: str  # The specific backend, system component, etc.
    check_function: Callable[[], Dict[str, Any]]
    interval: int = 60  # seconds
    timeout: int = 10  # seconds
    critical: bool = False  # Whether failure affects overall status
    enabled: bool = True
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """Result of a health check execution."""
    check_id: str
    status: HealthStatus
    timestamp: datetime
    details: Dict[str, Any]
    duration_ms: float
    error: Optional[str] = None


class HealthCheckManager:
    """
    Manager for health checks.
    
    This class handles health check configuration, execution, and aggregation.
    """
    
    def __init__(
        self,
        monitoring_manager: MonitoringManager,
        backend_registry: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the health check manager.
        
        Args:
            monitoring_manager: MCP monitoring manager
            backend_registry: Optional backend registry
        """
        self.monitoring = monitoring_manager
        self.backend_registry = backend_registry or {}
        
        # Health checks by ID
        self.checks: Dict[str, HealthCheck] = {}
        
        # Latest results by check ID
        self.results: Dict[str, HealthCheckResult] = {}
        
        # History of results (limited)
        self.history: Dict[str, List[HealthCheckResult]] = {}
        self.max_history_per_check = 100
        
        # Overall health status
        self.overall_status = HealthStatus.UNKNOWN
        self.last_update = datetime.now()
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Background thread for health checking
        self.check_thread = None
        self.running = False
        
        # Register standard metrics
        self._register_metrics()
        
        # Register standard health checks
        self._register_standard_checks()
    
    def _register_metrics(self) -> None:
        """Register health check metrics."""
        # Register health check metrics
        self.monitoring.metrics.register_metric(
            "health_check_status",
            self.monitoring.metrics.MetricType.GAUGE,
            "Health check status (0=unknown, 1=healthy, 2=degraded, 3=unhealthy)",
            self.monitoring.metrics.MetricUnit.COUNT,
            [self.monitoring.metrics.MetricTag.SYSTEM],
            ["check_id", "name", "check_type", "target"]
        )
        
        self.monitoring.metrics.register_metric(
            "health_check_duration",
            self.monitoring.metrics.MetricType.GAUGE,
            "Health check execution duration in milliseconds",
            self.monitoring.metrics.MetricUnit.MILLISECONDS,
            [self.monitoring.metrics.MetricTag.SYSTEM],
            ["check_id", "name", "check_type", "target"]
        )
        
        self.monitoring.metrics.register_metric(
            "health_check_execution_count",
            self.monitoring.metrics.MetricType.COUNTER,
            "Health check execution count",
            self.monitoring.metrics.MetricUnit.COUNT,
            [self.monitoring.metrics.MetricTag.SYSTEM],
            ["check_id", "name", "status"]
        )
        
        self.monitoring.metrics.register_metric(
            "overall_health_status",
            self.monitoring.metrics.MetricType.GAUGE,
            "Overall system health status (0=unknown, 1=healthy, 2=degraded, 3=unhealthy)",
            self.monitoring.metrics.MetricUnit.COUNT,
            [self.monitoring.metrics.MetricTag.SYSTEM],
            []
        )
    
    def _register_standard_checks(self) -> None:
        """Register standard system and backend health checks."""
        # System health checks
        self.add_check(HealthCheck(
            id="system_cpu",
            name="System CPU Usage",
            description="Check system CPU usage",
            check_type="system",
            target="cpu",
            check_function=self._check_cpu_usage,
            interval=60,
            timeout=10,
            critical=True,
            enabled=True,
        ))
        
        self.add_check(HealthCheck(
            id="system_memory",
            name="System Memory Usage",
            description="Check system memory usage",
            check_type="system",
            target="memory",
            check_function=self._check_memory_usage,
            interval=60,
            timeout=10,
            critical=True,
            enabled=True,
        ))
        
        self.add_check(HealthCheck(
            id="system_disk",
            name="System Disk Usage",
            description="Check system disk usage",
            check_type="system",
            target="disk",
            check_function=self._check_disk_usage,
            interval=120,
            timeout=10,
            critical=True,
            enabled=True,
        ))
        
        # Network connectivity check
        self.add_check(HealthCheck(
            id="network_connectivity",
            name="Network Connectivity",
            description="Check network connectivity",
            check_type="system",
            target="network",
            check_function=self._check_network_connectivity,
            interval=60,
            timeout=10,
            critical=True,
            enabled=True,
        ))
        
        # Backend health checks
        for backend_id, backend in self.backend_registry.items():
            self.add_check(HealthCheck(
                id=f"backend_{backend_id}",
                name=f"Backend {backend_id}",
                description=f"Check {backend_id} backend health",
                check_type="backend",
                target=backend_id,
                check_function=lambda b_id=backend_id: self._check_backend_health(b_id),
                interval=60,
                timeout=30,
                critical=True,
                enabled=True,
            ))
    
    def _check_cpu_usage(self) -> Dict[str, Any]:
        """
        Check system CPU usage.
        
        Returns:
            Dictionary with check results
        """
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Determine status based on usage
            status = HealthStatus.HEALTHY
            if cpu_percent > 90:
                status = HealthStatus.UNHEALTHY
            elif cpu_percent > 75:
                status = HealthStatus.DEGRADED
            
            return {
                "status": status,
                "cpu_percent": cpu_percent,
                "cpu_count": psutil.cpu_count(),
                "thresholds": {
                    "degraded": 75,
                    "unhealthy": 90
                }
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNKNOWN,
                "error": str(e)
            }
    
    def _check_memory_usage(self) -> Dict[str, Any]:
        """
        Check system memory usage.
        
        Returns:
            Dictionary with check results
        """
        try:
            # Get memory usage
            memory = psutil.virtual_memory()
            percent = memory.percent
            
            # Determine status based on usage
            status = HealthStatus.HEALTHY
            if percent > 90:
                status = HealthStatus.UNHEALTHY
            elif percent > 80:
                status = HealthStatus.DEGRADED
            
            return {
                "status": status,
                "memory_percent": percent,
                "memory_used": memory.used,
                "memory_total": memory.total,
                "memory_available": memory.available,
                "thresholds": {
                    "degraded": 80,
                    "unhealthy": 90
                }
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNKNOWN,
                "error": str(e)
            }
    
    def _check_disk_usage(self) -> Dict[str, Any]:
        """
        Check system disk usage.
        
        Returns:
            Dictionary with check results
        """
        try:
            # Get disk usage for root path
            paths_to_check = ["/", "/home"]
            results = {}
            overall_status = HealthStatus.HEALTHY
            
            for path in paths_to_check:
                try:
                    usage = psutil.disk_usage(path)
                    percent = usage.percent
                    
                    # Determine status for this path
                    path_status = HealthStatus.HEALTHY
                    if percent > 90:
                        path_status = HealthStatus.UNHEALTHY
                    elif percent > 80:
                        path_status = HealthStatus.DEGRADED
                    
                    # Update overall status (worst case)
                    if path_status == HealthStatus.UNHEALTHY:
                        overall_status = HealthStatus.UNHEALTHY
                    elif path_status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                        overall_status = HealthStatus.DEGRADED
                    
                    # Add path result
                    results[path] = {
                        "status": path_status,
                        "percent": percent,
                        "used": usage.used,
                        "total": usage.total,
                        "free": usage.free,
                    }
                except Exception as e:
                    results[path] = {
                        "status": HealthStatus.UNKNOWN,
                        "error": str(e)
                    }
            
            return {
                "status": overall_status,
                "paths": results,
                "thresholds": {
                    "degraded": 80,
                    "unhealthy": 90
                }
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNKNOWN,
                "error": str(e)
            }
    
    def _check_network_connectivity(self) -> Dict[str, Any]:
        """
        Check network connectivity.
        
        Returns:
            Dictionary with check results
        """
        try:
            # Hosts to ping
            hosts = [
                "1.1.1.1",  # Cloudflare DNS
                "8.8.8.8",  # Google DNS
                "ipfs.io"   # IPFS website
            ]
            
            results = {}
            reachable_count = 0
            
            # Check each host
            for host in hosts:
                try:
                    # Try DNS resolution
                    if not re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
                        socket.gethostbyname(host)
                    
                    # Try socket connect
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    
                    # Connect to port 80 (HTTP)
                    result = sock.connect_ex((host, 80))
                    sock.close()
                    
                    if result == 0:
                        # Reachable
                        results[host] = {
                            "status": "reachable",
                            "port": 80,
                            "error": None
                        }
                        reachable_count += 1
                    else:
                        # Not reachable on port 80
                        results[host] = {
                            "status": "unreachable",
                            "port": 80,
                            "error": f"Connection failed with code {result}"
                        }
                except Exception as e:
                    results[host] = {
                        "status": "error",
                        "error": str(e)
                    }
            
            # Determine overall status
            status = HealthStatus.HEALTHY
            if reachable_count == 0:
                status = HealthStatus.UNHEALTHY
            elif reachable_count < len(hosts):
                status = HealthStatus.DEGRADED
            
            return {
                "status": status,
                "hosts": results,
                "reachable_count": reachable_count,
                "total_hosts": len(hosts)
            }
        except Exception as e:
            return {
                "status": HealthStatus.UNKNOWN,
                "error": str(e)
            }
    
    def _check_backend_health(self, backend_id: str) -> Dict[str, Any]:
        """
        Check health of a specific backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            Dictionary with check results
        """
        try:
            # Get backend instance
            backend = self.backend_registry.get(backend_id)
            if not backend:
                return {
                    "status": HealthStatus.UNKNOWN,
                    "error": f"Backend {backend_id} not found in registry"
                }
            
            # Check if backend has get_status method
            if not hasattr(backend, "get_status"):
                return {
                    "status": HealthStatus.UNKNOWN,
                    "error": f"Backend {backend_id} does not support status checks"
                }
            
            # Call status method
            status_result = backend.get_status()
            
            # Determine health status
            if status_result.get("success", False):
                return {
                    "status": HealthStatus.HEALTHY,
                    "backend_status": status_result
                }
            else:
                return {
                    "status": HealthStatus.UNHEALTHY,
                    "error": status_result.get("error", "Unknown error"),
                    "backend_status": status_result
                }
        except Exception as e:
            return {
                "status": HealthStatus.UNKNOWN,
                "error": str(e)
            }
    
    def add_check(self, check: HealthCheck) -> None:
        """
        Add a health check.
        
        Args:
            check: Health check to add
        """
        with self.lock:
            # Add check
            self.checks[check.id] = check
            
            # Initialize history
            self.history[check.id] = []
            
            logger.info(f"Added health check {check.id}: {check.name}")
    
    def remove_check(self, check_id: str) -> bool:
        """
        Remove a health check.
        
        Args:
            check_id: ID of the check to remove
            
        Returns:
            True if check was removed
        """
        with self.lock:
            if check_id in self.checks:
                del self.checks[check_id]
                
                # Remove results and history
                if check_id in self.results:
                    del self.results[check_id]
                
                if check_id in self.history:
                    del self.history[check_id]
                
                logger.info(f"Removed health check {check_id}")
                return True
            
            return False
    
    def get_check(self, check_id: str) -> Optional[HealthCheck]:
        """
        Get a health check by ID.
        
        Args:
            check_id: ID of the check to get
            
        Returns:
            Health check or None if not found
        """
        with self.lock:
            return self.checks.get(check_id)
    
    def get_checks(self) -> List[HealthCheck]:
        """
        Get all health checks.
        
        Returns:
            List of health checks
        """
        with self.lock:
            return list(self.checks.values())
    
    def get_result(self, check_id: str) -> Optional[HealthCheckResult]:
        """
        Get the latest result for a health check.
        
        Args:
            check_id: ID of the check
            
        Returns:
            Latest result or None if not found
        """
        with self.lock:
            return self.results.get(check_id)
    
    def get_results(self) -> Dict[str, HealthCheckResult]:
        """
        Get all latest results.
        
        Returns:
            Dictionary of check ID to latest result
        """
        with self.lock:
            return self.results.copy()
    
    def get_result_history(self, check_id: str, limit: int = 10) -> List[HealthCheckResult]:
        """
        Get result history for a health check.
        
        Args:
            check_id: ID of the check
            limit: Maximum number of results to return
            
        Returns:
            List of historical results
        """
        with self.lock:
            if check_id not in self.history:
                return []
            
            return self.history[check_id][-limit:]
    
    def run_check(self, check_id: str) -> Optional[HealthCheckResult]:
        """
        Run a specific health check.
        
        Args:
            check_id: ID of the check to run
            
        Returns:
            Check result or None if check not found
        """
        with self.lock:
            # Get check
            check = self.checks.get(check_id)
            if not check:
                logger.warning(f"Health check {check_id} not found")
                return None
            
            if not check.enabled:
                logger.debug(f"Health check {check_id} is disabled")
                return None
            
            try:
                # Run check with timeout
                import concurrent.futures
                
                start_time = time.time()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(check.check_function)
                    
                    try:
                        result_data = future.result(timeout=check.timeout)
                    except concurrent.futures.TimeoutError:
                        result_data = {
                            "status": HealthStatus.UNHEALTHY,
                            "error": f"Check timed out after {check.timeout} seconds"
                        }
                
                end_time = time.time()
                duration_ms = (end_time - start_time) * 1000
                
                # Create result object
                result = HealthCheckResult(
                    check_id=check.id,
                    status=HealthStatus(result_data.get("status", HealthStatus.UNKNOWN)),
                    timestamp=datetime.now(),
                    details=result_data,
                    duration_ms=duration_ms,
                    error=result_data.get("error")
                )
                
                # Update latest result
                self.results[check.id] = result
                
                # Add to history
                self.history[check.id].append(result)
                
                # Trim history if needed
                if len(self.history[check.id]) > self.max_history_per_check:
                    self.history[check.id] = self.history[check.id][-self.max_history_per_check:]
                
                # Update metrics
                self._update_metrics(check, result)
                
                # Update overall status
                self._update_overall_status()
                
                return result
            
            except Exception as e:
                logger.error(f"Error running health check {check_id}: {e}")
                
                # Create error result
                result = HealthCheckResult(
                    check_id=check.id,
                    status=HealthStatus.UNKNOWN,
                    timestamp=datetime.now(),
                    details={},
                    duration_ms=0,
                    error=str(e)
                )
                
                # Update latest result
                self.results[check.id] = result
                
                # Add to history
                self.history[check.id].append(result)
                
                # Update metrics
                self._update_metrics(check, result)
                
                return result
    
    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """
        Run all health checks.
        
        Returns:
            Dictionary of check ID to result
        """
        results = {}
        
        for check_id in list(self.checks.keys()):
            result = self.run_check(check_id)
            if result:
                results[check_id] = result
        
        return results
    
    def _update_metrics(self, check: HealthCheck, result: HealthCheckResult) -> None:
        """
        Update metrics for a health check result.
        
        Args:
            check: Health check
            result: Check result
        """
        # Map status to numeric value for Prometheus
        status_value = 0  # unknown
        if result.status == HealthStatus.HEALTHY:
            status_value = 1
        elif result.status == HealthStatus.DEGRADED:
            status_value = 2
        elif result.status == HealthStatus.UNHEALTHY:
            status_value = 3
        
        # Update status metric
        self.monitoring.metrics.set_gauge(
            "health_check_status",
            status_value,
            label_values={
                "check_id": check.id,
                "name": check.name,
                "check_type": check.check_type,
                "target": check.target
            }
        )
        
        # Update duration metric
        self.monitoring.metrics.set_gauge(
            "health_check_duration",
            result.duration_ms,
            label_values={
                "check_id": check.id,
                "name": check.name,
                "check_type": check.check_type,
                "target": check.target
            }
        )
        
        # Increment execution count
        self.monitoring.metrics.increment_counter(
            "health_check_execution_count",
            label_values={
                "check_id": check.id,
                "name": check.name,
                "status": result.status
            }
        )
    
    def _update_overall_status(self) -> None:
        """Update the overall health status based on all check results."""
        with self.lock:
            # Default to healthy if we have results, otherwise unknown
            if not self.results:
                self.overall_status = HealthStatus.UNKNOWN
                return
            
            overall = HealthStatus.HEALTHY
            
            # Count checks by status
            counts = {
                HealthStatus.HEALTHY: 0,
                HealthStatus.DEGRADED: 0,
                HealthStatus.UNHEALTHY: 0,
                HealthStatus.UNKNOWN: 0,
            }
            
            # Check each result
            critical_issues = False
            for check_id, result in self.results.items():
                # Update counts
                counts[result.status] = counts.get(result.status, 0) + 1
                
                # Check if critical
                check = self.checks.get(check_id)
                if check and check.critical and result.status == HealthStatus.UNHEALTHY:
                    critical_issues = True
            
            # Determine overall status
            if critical_issues or counts[HealthStatus.UNHEALTHY] > 0:
                overall = HealthStatus.UNHEALTHY
            elif counts[HealthStatus.DEGRADED] > 0:
                overall = HealthStatus.DEGRADED
            elif counts[HealthStatus.UNKNOWN] > 0 and counts[HealthStatus.HEALTHY] == 0:
                overall = HealthStatus.UNKNOWN
            
            # Update status and timestamp
            self.overall_status = overall
            self.last_update = datetime.now()
            
            # Update metric
            status_value = 0  # unknown
            if overall == HealthStatus.HEALTHY:
                status_value = 1
            elif overall == HealthStatus.DEGRADED:
                status_value = 2
            elif overall == HealthStatus.UNHEALTHY:
                status_value = 3
            
            self.monitoring.metrics.set_gauge("overall_health_status", status_value)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the system health.
        
        Returns:
            Dictionary with health summary
        """
        with self.lock:
            # Count checks by status
            counts = {
                HealthStatus.HEALTHY: 0,
                HealthStatus.DEGRADED: 0,
                HealthStatus.UNHEALTHY: 0,
                HealthStatus.UNKNOWN: 0,
            }
            
            for result in self.results.values():
                counts[result.status] = counts.get(result.status, 0) + 1
            
            return {
                "status": self.overall_status,
                "last_update": self.last_update.isoformat(),
                "counts": counts,
                "total_checks": len(self.checks),
                "enabled_checks": sum(1 for check in self.checks.values() if check.enabled),
                "completed_checks": len(self.results),
            }
    
    def start(self, initial_delay: int = 0) -> None:
        """
        Start background health checking.
        
        Args:
            initial_delay: Initial delay in seconds before starting checks
        """
        if self.running:
            return
        
        self.running = True
        
        self.check_thread = threading.Thread(
            target=self._check_loop,
            args=(initial_delay,),
            daemon=True
        )
        self.check_thread.start()
        
        logger.info("Started health check monitoring")
    
    def stop(self) -> None:
        """Stop background health checking."""
        self.running = False
        
        if self.check_thread:
            self.check_thread.join(timeout=5.0)
            logger.info("Stopped health check monitoring")
    
    def _check_loop(self, initial_delay: int) -> None:
        """
        Background thread for periodic health checking.
        
        Args:
            initial_delay: Initial delay in seconds
        """
        # Wait for initial delay
        if initial_delay > 0:
            time.sleep(initial_delay)
        
        while self.running:
            try:
                # Run all checks
                logger.debug("Running all health checks")
                self.run_all_checks()
                
                # Schedule next checks based on intervals
                next_run_time = {}
                
                for check_id, check in self.checks.items():
                    if not check.enabled:
                        continue
                    
                    # Get last run time
                    last_result = self.results.get(check_id)
                    if last_result:
                        last_run = last_result.timestamp
                    else:
                        last_run = datetime.now() - timedelta(seconds=check.interval * 2)
                    
                    # Calculate next run
                    next_run = last_run + timedelta(seconds=check.interval)
                    next_run_time[check_id] = next_run
                
                # Sleep until next check
                now = datetime.now()
                next_checks = [t for t in next_run_time.values() if t > now]
                
                if next_checks:
                    # Find soonest check
                    next_check = min(next_checks)
                    sleep_time = (next_check - now).total_seconds()
                    
                    # Ensure minimum sleep time
                    sleep_time = max(sleep_time, 1.0)
                    
                    # Sleep until next check
                    logger.debug(f"Sleeping for {sleep_time:.1f}s until next health check")
                    time.sleep(sleep_time)
                else:
                    # No checks scheduled, sleep for a bit
                    time.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                time.sleep(30)  # Sleep after error


# Singleton instance
_instance = None

def get_instance(
    monitoring_manager: MonitoringManager,
    backend_registry: Optional[Dict[str, Any]] = None,
) -> HealthCheckManager:
    """
    Get or create the singleton health check manager instance.
    
    Args:
        monitoring_manager: MCP monitoring manager
        backend_registry: Optional backend registry
        
    Returns:
        HealthCheckManager instance
    """
    global _instance
    if _instance is None:
        _instance = HealthCheckManager(monitoring_manager, backend_registry)
    return _instance