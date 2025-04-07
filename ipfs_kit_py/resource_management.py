"""
Resource management module for optimizing thread and memory usage in IPFS Kit.

This module provides sophisticated resource monitoring and management capabilities
to optimize performance in resource-constrained environments while maximizing
throughput when resources are abundant.
"""

import os
import time
import math
import logging
import threading
import queue # Import queue module
import collections
from typing import Dict, List, Optional, Any, Callable, Tuple, Deque
from collections import defaultdict, deque

# Check for optional dependencies
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Initialize logger
logger = logging.getLogger(__name__)


class ResourceMonitor:
    """Monitors system resources and provides adaptive resource management.
    
    Tracks CPU, memory, disk, and network usage to guide resource allocation
    decisions for prefetching, caching, and other operations.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the resource monitor.
        
        Args:
            config: Optional configuration dictionary with resource thresholds
        """
        # Default configuration
        self.default_config = {
            # Memory thresholds (percentage of total)
            "memory_critical": 90,     # Critical threshold (%) - drastically reduce activity
            "memory_high": 80,         # High threshold (%) - reduce activity
            "memory_moderate": 70,     # Moderate threshold (%) - normal activity
            "memory_low": 50,          # Low threshold (%) - can increase activity
            
            # CPU thresholds (percentage utilization)
            "cpu_critical": 90,        # Critical threshold (%) - drastically reduce activity
            "cpu_high": 80,            # High threshold (%) - reduce activity 
            "cpu_moderate": 70,        # Moderate threshold (%) - normal activity
            "cpu_low": 50,             # Low threshold (%) - can increase activity
            
            # Disk thresholds (percentage used)
            "disk_critical": 95,       # Critical threshold (%) - drastically reduce activity
            "disk_high": 90,           # High threshold (%) - reduce activity
            "disk_moderate": 80,       # Moderate threshold (%) - normal activity
            "disk_low": 70,            # Low threshold (%) - can increase activity
            
            # Network thresholds (percentage of estimated max bandwidth)
            "network_critical": 90,    # Critical threshold (%) - drastically reduce activity
            "network_high": 80,        # High threshold (%) - reduce activity
            "network_moderate": 70,    # Moderate threshold (%) - normal activity
            "network_low": 50,         # Low threshold (%) - can increase activity
            
            # Sampling intervals (seconds)
            "sampling_interval": 5,    # How often to sample resource usage
            "averaging_window": 30,    # Window size for moving averages (seconds)
            
            # Thread pool sizing
            "min_threads": 2,          # Minimum number of worker threads
            "max_threads": 16,         # Maximum number of worker threads
            "threads_per_core": 2,     # Threads to allocate per CPU core
            
            # Cache sizing (percentage of available memory)
            "memory_cache_max": 25,    # Maximum memory to use for cache (%)
            "memory_cache_min": 5,     # Minimum memory to reserve for cache (%)
            
            # I/O throttling
            "io_throttle_threshold": 80,  # Disk utilization (%) to begin throttling
            "max_bandwidth_usage": 80,    # Maximum percentage of bandwidth to use
            "bandwidth_estimate": 10 * 1024 * 1024,  # Estimated bandwidth (10 MB/s default)
            
            # Resource check behavior
            "check_on_demand": True,      # Allow on-demand resource checks
            "background_monitoring": True, # Enable background monitoring thread
            "log_resource_usage": False    # Log periodic resource usage to logger
        }
        
        # Merge configurations
        self.config = self.default_config.copy()
        if config:
            self.config.update(config)
        
        # Initialize resource tracking
        self.resources = {
            "cpu": {
                "usage_percent": 0.0,
                "history": collections.deque(maxlen=60),  # 5 minutes at 5-second intervals
                "cores": self._get_cpu_count(),
                "last_check": 0,
                "status": "unknown"
            },
            "memory": {
                "total": 0,
                "available": 0,
                "used_percent": 0.0,
                "history": collections.deque(maxlen=60),
                "last_check": 0,
                "status": "unknown"
            },
            "disk": {
                "total": 0,
                "available": 0,
                "used_percent": 0.0,
                "io_utilization": 0.0,
                "history": collections.deque(maxlen=60),
                "last_check": 0,
                "status": "unknown"
            },
            "network": {
                "bandwidth_usage": 0.0,
                "estimated_max": self.config["bandwidth_estimate"],
                "usage_percent": 0.0,
                "history": collections.deque(maxlen=60),
                "last_check": 0,
                "status": "unknown"
            }
        }
        
        # Thread pool management
        self.thread_pool_info = {
            "recommended_size": self._get_cpu_count() * self.config["threads_per_core"],
            "current_active": 0,
            "utilization_percent": 0.0
        }
        
        # Cache management
        self.cache_info = {
            "recommended_size_bytes": 0,
            "current_size_bytes": 0,
            "utilization_percent": 0.0
        }
        
        # Overall system status
        self.system_status = {
            "overall": "unknown",
            "bottleneck": None,
            "last_update": 0
        }
        
        # Resource check tracking
        self._next_scheduled_check = 0
        self._last_full_check = 0
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        
        # Initialize with a first check
        self.check_resources()
        
        # Start background monitoring if enabled
        if self.config["background_monitoring"]:
            self._start_monitoring()
    
    def _get_cpu_count(self) -> int:
        """Get the number of CPU cores.
        
        Returns:
            Number of CPU cores, or 2 if unable to determine
        """
        try:
            if HAS_PSUTIL:
                return psutil.cpu_count(logical=True) or 2
            else:
                import multiprocessing
                return multiprocessing.cpu_count()
        except (ImportError, NotImplementedError):
            return 2  # Default to 2 cores if we can't determine
    
    def _start_monitoring(self) -> None:
        """Start background resource monitoring thread."""
        if self._monitoring_thread is not None:
            return  # Already running
        
        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            name="resource_monitor",
            daemon=True
        )
        self._monitoring_thread.start()
        logger.debug("Started background resource monitoring thread")
    
    def _stop_monitoring(self) -> None:
        """Stop background resource monitoring thread."""
        if self._monitoring_thread is None:
            return  # Not running
        
        self._stop_monitoring.set()
        self._monitoring_thread.join(timeout=1.0)
        self._monitoring_thread = None
        logger.debug("Stopped background resource monitoring thread")
    
    def _monitoring_loop(self) -> None:
        """Background thread that periodically checks resource usage."""
        while not self._stop_monitoring.is_set():
            try:
                # Check resources
                self.check_resources()
                
                # Log resource usage if enabled
                if self.config["log_resource_usage"]:
                    self._log_resource_usage()
                
                # Sleep until next check
                next_check = time.time() + self.config["sampling_interval"]
                self._next_scheduled_check = next_check
                
                # Use a short sleep interval to respond to stop requests promptly
                while time.time() < next_check and not self._stop_monitoring.is_set():
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Error in resource monitoring thread: {e}")
                time.sleep(self.config["sampling_interval"])
    
    def _log_resource_usage(self) -> None:
        """Log current resource usage information."""
        logger.debug(
            f"Resource usage: CPU: {self.resources['cpu']['usage_percent']:.1f}% "
            f"({self.resources['cpu']['status']}), "
            f"Memory: {self.resources['memory']['used_percent']:.1f}% "
            f"({self.resources['memory']['status']}), "
            f"Disk: {self.resources['disk']['used_percent']:.1f}% "
            f"({self.resources['disk']['status']}), "
            f"Network: {self.resources['network']['usage_percent']:.1f}% "
            f"({self.resources['network']['status']})"
        )
    
    def check_resources(self) -> Dict[str, Any]:
        """Check current system resource usage.
        
        This method performs a full resource check, updating internal state
        and returning the current resource status.
        
        Returns:
            Dictionary with current resource usage information
        """
        current_time = time.time()
        
        # Skip if we checked very recently (unless forced)
        if current_time - self._last_full_check < 0.1:
            return self.get_status()
        
        self._last_full_check = current_time
        
        # Check CPU usage
        self._check_cpu_usage()
        
        # Check memory usage
        self._check_memory_usage()
        
        # Check disk usage
        self._check_disk_usage()
        
        # Check network usage
        self._check_network_usage()
        
        # Update thread pool recommendations
        self._update_thread_pool_recommendations()
        
        # Update cache size recommendations
        self._update_cache_recommendations()
        
        # Update overall system status
        self._update_system_status()
        
        return self.get_status()
    
    def _check_cpu_usage(self) -> None:
        """Check current CPU usage and update status."""
        cpu_info = self.resources["cpu"]
        cpu_info["last_check"] = time.time()
        
        try:
            if HAS_PSUTIL:
                # Get CPU usage percentage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                cpu_info["usage_percent"] = cpu_percent
                
                # Get per-core usage if needed
                # cpu_info["per_core"] = psutil.cpu_percent(interval=0.1, percpu=True)
            else:
                # Fallback method if psutil not available
                try:
                    # Try platform-specific approaches
                    if os.name == 'posix':
                        # Unix-like system, try reading /proc/stat
                        with open('/proc/stat', 'r') as f:
                            cpu_line = f.readline()
                            cpu_values = [float(x) for x in cpu_line.split()[1:]]
                            idle = cpu_values[3]
                            total = sum(cpu_values)
                            cpu_percent = 100.0 * (1.0 - idle / total)
                            cpu_info["usage_percent"] = cpu_percent
                    else:
                        # No good fallback for Windows/other without psutil
                        # Use last known value or default
                        if not cpu_info["history"]:
                            cpu_info["usage_percent"] = 50.0  # Default assumption
                except Exception as e:
                    logger.debug(f"Error getting CPU usage without psutil: {e}")
                    if not cpu_info["history"]:
                        cpu_info["usage_percent"] = 50.0  # Default assumption
        except Exception as e:
            logger.warning(f"Error checking CPU usage: {e}")
            if not cpu_info["history"]:
                cpu_info["usage_percent"] = 50.0  # Default assumption
        
        # Add to history
        cpu_info["history"].append((time.time(), cpu_info["usage_percent"]))
        
        # Update status based on thresholds
        if cpu_info["usage_percent"] >= self.config["cpu_critical"]:
            cpu_info["status"] = "critical"
        elif cpu_info["usage_percent"] >= self.config["cpu_high"]:
            cpu_info["status"] = "high"
        elif cpu_info["usage_percent"] >= self.config["cpu_moderate"]:
            cpu_info["status"] = "moderate"
        else:
            cpu_info["status"] = "low"
    
    def _check_memory_usage(self) -> None:
        """Check current memory usage and update status."""
        memory_info = self.resources["memory"]
        memory_info["last_check"] = time.time()
        
        try:
            if HAS_PSUTIL:
                # Get memory information
                mem = psutil.virtual_memory()
                memory_info["total"] = mem.total
                memory_info["available"] = mem.available
                memory_info["used_percent"] = mem.percent
            else:
                # Fallback method if psutil not available
                try:
                    if os.name == 'posix':
                        # Unix-like system, try reading from /proc/meminfo
                        total = 0
                        available = 0
                        
                        with open('/proc/meminfo', 'r') as f:
                            for line in f:
                                if line.startswith('MemTotal:'):
                                    total = int(line.split()[1]) * 1024  # Convert KB to bytes
                                elif line.startswith('MemAvailable:'):
                                    available = int(line.split()[1]) * 1024  # Convert KB to bytes
                        
                        if total > 0:
                            memory_info["total"] = total
                            if available > 0:
                                memory_info["available"] = available
                                memory_info["used_percent"] = 100.0 * (1.0 - available / total)
                except Exception as e:
                    logger.debug(f"Error getting memory usage without psutil: {e}")
                    # Use last known value or default
                    if memory_info["total"] == 0:
                        memory_info["total"] = 8 * 1024 * 1024 * 1024  # Assume 8GB
                        memory_info["available"] = 4 * 1024 * 1024 * 1024  # Assume 4GB available
                        memory_info["used_percent"] = 50.0
        except Exception as e:
            logger.warning(f"Error checking memory usage: {e}")
            if memory_info["total"] == 0:
                memory_info["total"] = 8 * 1024 * 1024 * 1024  # Assume 8GB
                memory_info["available"] = 4 * 1024 * 1024 * 1024  # Assume 4GB available
                memory_info["used_percent"] = 50.0
        
        # Add to history
        memory_info["history"].append((time.time(), memory_info["used_percent"]))
        
        # Update status based on thresholds
        if memory_info["used_percent"] >= self.config["memory_critical"]:
            memory_info["status"] = "critical"
        elif memory_info["used_percent"] >= self.config["memory_high"]:
            memory_info["status"] = "high"
        elif memory_info["used_percent"] >= self.config["memory_moderate"]:
            memory_info["status"] = "moderate"
        else:
            memory_info["status"] = "low"
    
    def _check_disk_usage(self) -> None:
        """Check current disk usage and update status."""
        disk_info = self.resources["disk"]
        disk_info["last_check"] = time.time()
        
        try:
            if HAS_PSUTIL:
                # Get disk usage for the current directory (where data is stored)
                du = psutil.disk_usage('.')
                disk_info["total"] = du.total
                disk_info["available"] = du.free
                disk_info["used_percent"] = du.percent
                
                # Get I/O statistics if available
                try:
                    io_counters = psutil.disk_io_counters()
                    if 'last_io_counters' in disk_info:
                        last_time, last_counters = disk_info['last_io_counters']
                        time_diff = time.time() - last_time
                        
                        if time_diff > 0:
                            # Calculate I/O rate
                            read_diff = io_counters.read_bytes - last_counters.read_bytes
                            write_diff = io_counters.write_bytes - last_counters.write_bytes
                            
                            io_rate = (read_diff + write_diff) / time_diff
                            
                            # Estimate I/O utilization (very rough)
                            # Assume a typical disk can do 100MB/s
                            estimated_max = 100 * 1024 * 1024  # 100 MB/s
                            disk_info["io_utilization"] = (io_rate / estimated_max) * 100
                    
                    # Store current counters for next comparison
                    disk_info['last_io_counters'] = (time.time(), io_counters)
                except (AttributeError, PermissionError):
                    # Not all systems provide I/O counters
                    pass
            else:
                # Fallback method if psutil not available
                try:
                    if os.name == 'posix':
                        # Use os.statvfs to get disk information
                        st = os.statvfs('.')
                        total = st.f_blocks * st.f_frsize
                        available = st.f_bavail * st.f_frsize
                        used = (st.f_blocks - st.f_bfree) * st.f_frsize
                        
                        disk_info["total"] = total
                        disk_info["available"] = available
                        disk_info["used_percent"] = 100.0 * (used / total) if total > 0 else 0
                except Exception as e:
                    logger.debug(f"Error getting disk usage without psutil: {e}")
                    # Use default values if we can't determine
                    if disk_info["total"] == 0:
                        disk_info["total"] = 100 * 1024 * 1024 * 1024  # Assume 100GB
                        disk_info["available"] = 50 * 1024 * 1024 * 1024  # Assume 50GB available
                        disk_info["used_percent"] = 50.0
        except Exception as e:
            logger.warning(f"Error checking disk usage: {e}")
            if disk_info["total"] == 0:
                disk_info["total"] = 100 * 1024 * 1024 * 1024  # Assume 100GB
                disk_info["available"] = 50 * 1024 * 1024 * 1024  # Assume 50GB available
                disk_info["used_percent"] = 50.0
        
        # Add to history
        disk_info["history"].append((time.time(), disk_info["used_percent"]))
        
        # Update status based on thresholds
        if disk_info["used_percent"] >= self.config["disk_critical"]:
            disk_info["status"] = "critical"
        elif disk_info["used_percent"] >= self.config["disk_high"]:
            disk_info["status"] = "high"
        elif disk_info["used_percent"] >= self.config["disk_moderate"]:
            disk_info["status"] = "moderate"
        else:
            disk_info["status"] = "low"
    
    def _check_network_usage(self) -> None:
        """Check current network usage and update status."""
        network_info = self.resources["network"]
        network_info["last_check"] = time.time()
        
        try:
            if HAS_PSUTIL:
                # Get network I/O information
                net_io = psutil.net_io_counters()
                
                if 'last_net_io' in network_info:
                    last_time, last_io = network_info['last_net_io']
                    time_diff = time.time() - last_time
                    
                    if time_diff > 0:
                        # Calculate network I/O rate
                        sent_diff = net_io.bytes_sent - last_io.bytes_sent
                        recv_diff = net_io.bytes_recv - last_io.bytes_recv
                        
                        # Overall bandwidth usage (bytes/sec)
                        io_rate = (sent_diff + recv_diff) / time_diff
                        network_info["bandwidth_usage"] = io_rate
                        
                        # Calculate percentage of estimated max
                        estimated_max = network_info["estimated_max"]
                        network_info["usage_percent"] = (io_rate / estimated_max) * 100 if estimated_max > 0 else 0
                
                # Store current counters for next comparison
                network_info['last_net_io'] = (time.time(), net_io)
            else:
                # Not much we can do without psutil for network monitoring
                # Use default values
                if "usage_percent" not in network_info or network_info["usage_percent"] == 0:
                    network_info["usage_percent"] = 30.0  # Assume moderate usage
        except Exception as e:
            logger.warning(f"Error checking network usage: {e}")
            if "usage_percent" not in network_info or network_info["usage_percent"] == 0:
                network_info["usage_percent"] = 30.0  # Assume moderate usage
        
        # Add to history
        network_info["history"].append((time.time(), network_info["usage_percent"]))
        
        # Update status based on thresholds
        if network_info["usage_percent"] >= self.config["network_critical"]:
            network_info["status"] = "critical"
        elif network_info["usage_percent"] >= self.config["network_high"]:
            network_info["status"] = "high"
        elif network_info["usage_percent"] >= self.config["network_moderate"]:
            network_info["status"] = "moderate"
        else:
            network_info["status"] = "low"
    
    def _update_thread_pool_recommendations(self) -> None:
        """Update thread pool size recommendations based on resource usage."""
        cpu_info = self.resources["cpu"]
        memory_info = self.resources["memory"]
        
        # Base thread count on CPU cores
        base_thread_count = cpu_info["cores"] * self.config["threads_per_core"]
        
        # Adjust based on resource pressure
        if cpu_info["status"] == "critical" or memory_info["status"] == "critical":
            # Under critical load, reduce thread count to minimum
            recommended_threads = max(1, self.config["min_threads"])
        elif cpu_info["status"] == "high" or memory_info["status"] == "high":
            # Under high load, reduce thread count
            recommended_threads = max(self.config["min_threads"], base_thread_count // 2)
        elif cpu_info["status"] == "moderate":
            # Under moderate load, use normal thread count
            recommended_threads = base_thread_count
        else:
            # Under low load, can use more threads for higher throughput
            recommended_threads = min(base_thread_count * 2, self.config["max_threads"])
        
        # Update recommendation
        self.thread_pool_info["recommended_size"] = recommended_threads
    
    def _update_cache_recommendations(self) -> None:
        """Update cache size recommendations based on resource usage."""
        memory_info = self.resources["memory"]
        
        # Base cache size on available memory and configuration
        available_memory = memory_info["available"]
        
        # Calculate recommended cache size based on resource state
        if memory_info["status"] == "critical":
            # Under critical memory pressure, use minimum cache size
            cache_percent = self.config["memory_cache_min"]
        elif memory_info["status"] == "high":
            # Under high memory pressure, use reduced cache size
            cache_percent = max(
                self.config["memory_cache_min"],
                self.config["memory_cache_max"] / 2
            )
        elif memory_info["status"] == "moderate":
            # Under moderate pressure, use normal cache size
            cache_percent = (self.config["memory_cache_min"] + self.config["memory_cache_max"]) / 2
        else:
            # Under low pressure, can use maximum cache size
            cache_percent = self.config["memory_cache_max"]
        
        # Calculate recommended cache size in bytes
        recommended_size = int((cache_percent / 100.0) * available_memory)
        
        # Update recommendation
        self.cache_info["recommended_size_bytes"] = recommended_size
    
    def _update_system_status(self) -> None:
        """Update overall system status based on component statuses."""
        # Collect component statuses
        cpu_status = self.resources["cpu"]["status"]
        memory_status = self.resources["memory"]["status"]
        disk_status = self.resources["disk"]["status"]
        network_status = self.resources["network"]["status"]
        
        # Determine overall status (worst of all components)
        status_priority = {
            "critical": 3,
            "high": 2,
            "moderate": 1,
            "low": 0,
            "unknown": -1
        }
        
        status_values = {
            "cpu": status_priority.get(cpu_status, -1),
            "memory": status_priority.get(memory_status, -1),
            "disk": status_priority.get(disk_status, -1),
            "network": status_priority.get(network_status, -1)
        }
        
        # Find the resource with the highest priority (most constrained)
        max_resource = max(status_values.items(), key=lambda x: x[1])
        bottleneck = max_resource[0]
        
        # Map priority back to status name
        priority_to_status = {v: k for k, v in status_priority.items()}
        overall_status = priority_to_status.get(max_resource[1], "unknown")
        
        # Update system status
        self.system_status["overall"] = overall_status
        self.system_status["bottleneck"] = bottleneck
        self.system_status["last_update"] = time.time()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current resource status summary.
        
        Returns:
            Dictionary with resource status information
        """
        return {
            "overall": self.system_status["overall"],
            "bottleneck": self.system_status["bottleneck"],
            "cpu": {
                "status": self.resources["cpu"]["status"],
                "usage_percent": self.resources["cpu"]["usage_percent"],
                "cores": self.resources["cpu"]["cores"]
            },
            "memory": {
                "status": self.resources["memory"]["status"],
                "used_percent": self.resources["memory"]["used_percent"],
                "available_bytes": self.resources["memory"]["available"],
                "total_bytes": self.resources["memory"]["total"]
            },
            "disk": {
                "status": self.resources["disk"]["status"],
                "used_percent": self.resources["disk"]["used_percent"],
                "available_bytes": self.resources["disk"]["available"],
                "total_bytes": self.resources["disk"]["total"]
            },
            "network": {
                "status": self.resources["network"]["status"],
                "usage_percent": self.resources["network"]["usage_percent"],
                "bandwidth_usage": self.resources["network"]["bandwidth_usage"],
                "estimated_max": self.resources["network"]["estimated_max"]
            },
            "recommendations": {
                "thread_pool_size": self.thread_pool_info["recommended_size"],
                "memory_cache_bytes": self.cache_info["recommended_size_bytes"],
                "aggressive_prefetch": self.system_status["overall"] in ["low", "moderate"]
            },
            "last_updated": time.time()
        }
    
    def get_resource_history(self, resource_type: str, 
                           interval: Optional[float] = None) -> List[Tuple[float, float]]:
        """Get historical usage data for a specific resource.
        
        Args:
            resource_type: Type of resource ('cpu', 'memory', 'disk', 'network')
            interval: Optional time interval in seconds (returns all data if None)
            
        Returns:
            List of (timestamp, usage_percent) tuples
        """
        if resource_type not in self.resources:
            return []
        
        history = list(self.resources[resource_type]["history"])
        
        if interval is not None:
            # Filter to just the specified interval
            cutoff_time = time.time() - interval
            history = [(ts, val) for ts, val in history if ts >= cutoff_time]
        
        return history
    
    def should_prefetch(self) -> bool:
        """Determine if prefetching should be allowed based on resource state.
        
        Returns:
            True if prefetching should be allowed, False otherwise
        """
        overall_status = self.system_status["overall"]
        
        # Don't prefetch under critical or high load
        if overall_status in ["critical", "high"]:
            return False
        
        # Always allow prefetching under low load
        if overall_status == "low":
            return True
        
        # Under moderate load, check specific constraints
        if overall_status == "moderate":
            # Allow prefetching if memory and network are not the bottleneck
            bottleneck = self.system_status["bottleneck"]
            if bottleneck not in ["memory", "network"]:
                return True
            
            # Allow prefetching but with more limited scope
            return True
        
        # Default to conservative approach
        return False
    
    def get_thread_allocation(self, worker_type: str) -> int:
        """Get recommended thread allocation for a specific worker type.
        
        Different types of work benefit from different thread allocations.
        This method provides type-specific recommendations based on
        current resource state.
        
        Args:
            worker_type: Type of worker ('prefetch', 'io', 'compute', 'network')
            
        Returns:
            Recommended number of threads to allocate
        """
        base_threads = self.thread_pool_info["recommended_size"]
        
        # Adjust based on worker type
        if worker_type == "prefetch":
            # Prefetch benefits from parallelism but is lower priority
            if self.system_status["overall"] in ["critical", "high"]:
                return 1  # Minimum threads under resource pressure
            elif self.system_status["overall"] == "moderate":
                return max(1, base_threads // 4)  # 25% of threads
            else:
                return max(2, base_threads // 2)  # 50% of threads
        
        elif worker_type == "io":
            # I/O operations can benefit from parallelism to hide latency
            if self.system_status["overall"] == "critical":
                return 1  # Minimum threads under critical pressure
            elif self.system_status["overall"] == "high":
                return max(1, base_threads // 3)  # 33% of threads
            else:
                return max(2, base_threads // 2)  # 50% of threads
        
        elif worker_type == "compute":
            # Compute-heavy tasks should be conservative with threads
            if self.system_status["overall"] in ["critical", "high"]:
                return 1  # Single thread under resource pressure
            else:
                return max(1, self.resources["cpu"]["cores"] // 2)  # 50% of cores
        
        elif worker_type == "network":
            # Network operations benefit from parallelism due to latency
            if self.system_status["overall"] == "critical":
                return 1  # Minimum threads under critical pressure
            elif self.system_status["overall"] == "high":
                return 2  # Limited parallelism under high pressure
            else:
                return max(2, base_threads)  # Full allocation otherwise
        
        # Default allocation for unknown worker types
        return max(1, base_threads // 2)
    
    def get_memory_allocation(self, resource_type: str, 
                            base_size: Optional[int] = None) -> int:
        """Get recommended memory allocation for a specific resource type.
        
        Args:
            resource_type: Type of resource ('cache', 'buffer', 'heap')
            base_size: Optional base size to adjust (if None, uses recommended cache size)
            
        Returns:
            Recommended number of bytes to allocate
        """
        if base_size is None:
            base_size = self.cache_info["recommended_size_bytes"]
        
        # Adjust based on resource type
        if resource_type == "cache":
            # Memory cache allocation
            return base_size  # Already calculated appropriately
        
        elif resource_type == "buffer":
            # Buffers for I/O operations
            if self.system_status["overall"] == "critical":
                return min(1024 * 1024, base_size // 10)  # 1MB or 10% of base, whichever is smaller
            elif self.system_status["overall"] == "high":
                return min(4 * 1024 * 1024, base_size // 5)  # 4MB or 20% of base
            else:
                return min(16 * 1024 * 1024, base_size // 2)  # 16MB or 50% of base
        
        elif resource_type == "heap":
            # Dynamic allocations for processing
            if self.system_status["overall"] == "critical":
                return base_size // 5  # 20% of base size
            elif self.system_status["overall"] == "high":
                return base_size // 3  # 33% of base size
            else:
                return base_size // 2  # 50% of base size
        
        # Default allocation for unknown resource types
        return max(1024 * 1024, base_size // 4)  # 1MB or 25% of base size
    
    def get_io_throttle_parameters(self) -> Dict[str, Any]:
        """Get I/O throttling parameters based on current resource state.
        
        Returns:
            Dictionary with throttling parameters:
            - max_concurrent_io: Maximum concurrent I/O operations
            - max_bandwidth_bps: Maximum bandwidth in bytes per second
            - throttle_delay: Delay between operations in seconds
        """
        # Determine throttling based on system status
        system_status = self.system_status["overall"]
        bottleneck = self.system_status["bottleneck"]
        
        # Base values
        max_concurrent_io = 8
        max_bandwidth_bps = self.resources["network"]["estimated_max"]
        throttle_delay = 0.0
        
        # Adjust based on system status
        if system_status == "critical":
            max_concurrent_io = 1
            max_bandwidth_bps = max_bandwidth_bps * 0.2  # 20% of max
            throttle_delay = 0.5  # 500ms delay
        elif system_status == "high":
            max_concurrent_io = 2
            max_bandwidth_bps = max_bandwidth_bps * 0.4  # 40% of max
            throttle_delay = 0.1  # 100ms delay
        elif system_status == "moderate":
            max_concurrent_io = 4
            max_bandwidth_bps = max_bandwidth_bps * 0.6  # 60% of max
            throttle_delay = 0.0  # No delay
        else:  # "low"
            max_concurrent_io = 8
            max_bandwidth_bps = max_bandwidth_bps * 0.8  # 80% of max
            throttle_delay = 0.0  # No delay
        
        # Further adjustments based on specific bottlenecks
        if bottleneck == "disk" and self.resources["disk"]["status"] in ["critical", "high"]:
            max_concurrent_io = max(1, max_concurrent_io // 2)
            throttle_delay = max(throttle_delay, 0.2)
        
        if bottleneck == "network" and self.resources["network"]["status"] in ["critical", "high"]:
            max_bandwidth_bps = max_bandwidth_bps * 0.5  # Further reduce to 50% of already adjusted value
        
        return {
            "max_concurrent_io": max_concurrent_io,
            "max_bandwidth_bps": int(max_bandwidth_bps),
            "throttle_delay": throttle_delay,
            "bandwidth_limit_percent": self.config["max_bandwidth_usage"]
        }
    
    def should_reduce_memory_usage(self) -> bool:
        """Determine if memory usage should be reduced urgently.
        
        Returns:
            True if memory usage should be reduced, False otherwise
        """
        memory_status = self.resources["memory"]["status"]
        return memory_status in ["critical", "high"]
    
    def get_prefetch_parameters(self) -> Dict[str, Any]:
        """Get prefetch parameters based on current resource state.
        
        Returns:
            Dictionary with prefetch parameters:
            - enabled: Whether prefetching should be enabled
            - max_items: Maximum number of items to prefetch
            - chunk_size: Recommended chunk size for prefetching
            - max_concurrent: Maximum concurrent prefetch operations
            - aggressive: Whether to use aggressive prefetching strategy
        """
        # Base parameters
        params = {
            "enabled": self.should_prefetch(),
            "max_items": 10,
            "chunk_size": 5,
            "max_concurrent": 5,
            "aggressive": False
        }
        
        # Adjust based on system status
        system_status = self.system_status["overall"]
        
        if system_status == "critical":
            params["enabled"] = False
            params["max_items"] = 0
            params["max_concurrent"] = 0
        elif system_status == "high":
            params["max_items"] = 3
            params["chunk_size"] = 2
            params["max_concurrent"] = 1
        elif system_status == "moderate":
            params["max_items"] = 5
            params["chunk_size"] = 3
            params["max_concurrent"] = 3
        else:  # "low"
            params["max_items"] = 10
            params["chunk_size"] = 5
            params["max_concurrent"] = 5
            params["aggressive"] = True
        
        return params
    
    def stop(self) -> None:
        """Stop the resource monitor and clean up resources."""
        if self._monitoring_thread is not None:
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=1.0)
            self._monitoring_thread = None


class AdaptiveThreadPool:
    """Thread pool that adapts to system resource conditions.
    
    This thread pool dynamically adjusts its size and behavior based
    on current system resource availability.
    """
    
    def __init__(self, resource_monitor: ResourceMonitor = None, 
               config: Optional[Dict[str, Any]] = None,
               name: str = "prefetch"):
        """Initialize the adaptive thread pool.
        
        Args:
            resource_monitor: ResourceMonitor instance to use
            config: Optional configuration dictionary
            name: Name of this thread pool (for logging)
        """
        # Create resource monitor if not provided
        self.resource_monitor = resource_monitor or ResourceMonitor()
        
        # Default configuration
        self.default_config = {
            "initial_threads": 4,
            "min_threads": 1,
            "max_threads": 16,
            "worker_type": "prefetch",  # Used for resource allocation
            "queue_size": 100,  # Maximum size of task queue
            "dynamic_adjustment": True,  # Whether to adjust thread count dynamically
            "adjustment_interval": 10.0,  # How often to adjust thread count (seconds)
            "thread_idle_timeout": 60.0,  # How long a thread can be idle before termination
            "priority_levels": 3,  # Number of priority levels for tasks
            "shutdown_timeout": 5.0  # Timeout for shutdown in seconds
        }
        
        # Merge configurations
        self.config = self.default_config.copy()
        if config:
            self.config.update(config)
        
        # Pool name
        self.name = name

        # Use a single PriorityQueue
        queue_max_size = self.config["queue_size"] if self.config["queue_size"] > 0 else 0
        self.task_queue = queue.PriorityQueue(maxsize=queue_max_size)

        # Worker threads
        self.workers = []
        
        # Control flags and locks
        self.shutdown_flag = threading.Event()
        self.pool_lock = threading.RLock()
        # self.queue_semaphore = threading.Semaphore(0) # Removed semaphore
        self.adjustment_lock = threading.RLock()

        # Statistics
        self.stats = {
            "tasks_submitted": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "queue_length_history": deque(maxlen=100),
            "thread_count_history": deque(maxlen=100),
            "execution_times": deque(maxlen=100),
            "last_adjustment": 0,
            "current_size": 0
        }
        
        # Adjustment thread
        self.adjustment_thread = None
        
        # Initialize thread pool
        self._initialize()
    
    def _initialize(self) -> None:
        """Initialize the thread pool with initial workers."""
        # Determine initial thread count
        initial_threads = self.config["initial_threads"]
        if initial_threads < 0:
            # Use recommended count from resource monitor
            initial_threads = self.resource_monitor.get_thread_allocation(
                self.config["worker_type"]
            )
        
        # Clamp to configured limits
        initial_threads = max(self.config["min_threads"], 
                            min(initial_threads, self.config["max_threads"]))
        
        # Create initial worker threads
        with self.pool_lock:
            for _ in range(initial_threads):
                self._create_worker()
            
            # Update stats
            self.stats["current_size"] = len(self.workers)
            self.stats["thread_count_history"].append((time.time(), len(self.workers)))
        
        # Start adjustment thread if dynamic adjustment is enabled
        if self.config["dynamic_adjustment"]:
            self.adjustment_thread = threading.Thread(
                target=self._adjustment_loop,
                name=f"{self.name}_adjuster",
                daemon=True
            )
            self.adjustment_thread.start()
    
    def _create_worker(self) -> None:
        """Create a new worker thread for the pool."""
        worker = threading.Thread(
            target=self._worker_loop,
            name=f"{self.name}_worker_{len(self.workers)}",
            daemon=True
        )
        worker.start()
        self.workers.append({
            "thread": worker,
            "created_at": time.time(),
            "last_active": time.time(),
            "tasks_completed": 0,
            "status": "starting"
        })
    
    def _worker_loop(self) -> None:
        """Main worker thread function that processes tasks from the queue."""
        # Get thread name for identification
        thread_name = threading.current_thread().name
        thread_id = thread_name.split('_')[-1]
        
        # Find our worker record
        worker_record = None
        with self.pool_lock: # Lock needed to safely access self.workers
            for worker in self.workers:
                if worker["thread"].name == thread_name:
                    worker_record = worker
                    break
        
        # Mark as started
        if worker_record:
            worker_record["status"] = "idle"

        # Worker main loop
        while not self.shutdown_flag.is_set():
            task_item = None
            try:
                # Wait for a task to be available or shutdown signal
                task_item = self._get_task_with_timeout(self.config["thread_idle_timeout"])

                if not task_item:
                    # Timed out waiting for task, check if we should exit
                    with self.pool_lock:
                        if len(self.workers) > self.config["min_threads"]:
                            if worker_record:
                                worker_record["status"] = "exiting_idle"
                            # Remove worker (best effort, might already be removed by adjustment)
                            self.workers = [w for w in self.workers if w["thread"].name != thread_name]
                            self.stats["current_size"] = len(self.workers)
                            self.stats["thread_count_history"].append((time.time(), len(self.workers)))
                            logger.debug(f"Worker {thread_name} exiting due to idle timeout.")
                            return # Exit thread
                    # Otherwise, continue waiting
                    continue

                # Try to unpack the task_item safely
                if not isinstance(task_item, tuple) or len(task_item) != 2:
                    logger.error(f"Invalid task_item format in {thread_name}: expected (priority, task_tuple) tuple, got {type(task_item).__name__} with {len(task_item) if isinstance(task_item, tuple) else 'N/A'} elements")
                    self.task_queue.task_done() # Mark as done to avoid blocking
                    continue
                
                # Task retrieved successfully, unpack it
                priority, task_tuple = task_item

                # Check for shutdown sentinel
                if task_tuple is None:
                    logger.debug(f"Worker {thread_name} received shutdown sentinel, exiting.")
                    self.task_queue.task_done() # Mark sentinel as done
                    break # Exit loop on sentinel

                # Verify task_tuple has enough elements before unpacking
                if not isinstance(task_tuple, tuple) or len(task_tuple) < 3:
                    logger.error(f"Task tuple format invalid in {thread_name}: expected (func, args, kwargs) but got {type(task_tuple).__name__} with {len(task_tuple) if isinstance(task_tuple, tuple) else 'N/A'} elements")
                    self.task_queue.task_done() # Mark as done
                    continue

                # Safely unpack the task details
                try:
                    func, args, kwargs = task_tuple
                    task_id = f"task_{worker_record['tasks_completed'] if worker_record else 'unknown'}"
                except (ValueError, TypeError) as e:
                    logger.error(f"Error unpacking task tuple in {thread_name}: {e}")
                    self.task_queue.task_done() # Mark as done
                    continue

                # Execute task
                if worker_record:
                    worker_record["status"] = "working"
                    worker_record["last_active"] = time.time()

                start_time = time.time()
                success = False
                try:
                    result = func(*args, **kwargs)
                    success = True
                except Exception as e:
                    logger.error(f"Task failed in {thread_name} (task_id={task_id}): {str(e)}")
                    result = e # Store exception as result for potential inspection

                execution_time = time.time() - start_time

                # Update worker stats
                if worker_record:
                    worker_record["status"] = "idle"
                    worker_record["last_active"] = time.time()
                    worker_record["tasks_completed"] += 1

                # Update execution statistics
                with self.pool_lock:
                    self.stats["execution_times"].append(execution_time)
                    if success:
                        self.stats["tasks_completed"] += 1
                    else:
                        self.stats["tasks_failed"] += 1

                # Only mark task as done if we successfully got to this point
                try:
                    self.task_queue.task_done()
                except ValueError:  # task_done might raise if called too many times
                    logger.warning(f"task_done() called too many times in {thread_name}")
                    pass

            except queue.Empty:
                 # This should ideally not happen with block=True unless timeout occurs
                 # Handled by the 'if not task_item:' check above
                 continue

            except Exception as e:
                # Catch unexpected errors in the loop itself
                logger.error(f"Unexpected error in worker thread {thread_name}: {str(e)}")
                # Mark task as done if we managed to get it, to prevent queue blockage
                if task_item is not None:
                    try:
                        self.task_queue.task_done()
                    except ValueError: # task_done might raise if called too many times
                        pass
                # Small sleep to prevent tight error loops
                time.sleep(0.1)

        # Mark as exited when shutdown
        if worker_record:
            worker_record["status"] = "exited"
    
    def _get_task_with_timeout(self, timeout: float):
        """Wait for a task with timeout.
        
        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            Task item (priority, (func, args, kwargs)) if available, None if timed out or empty.
        """
        try:
            # Get task from priority queue with timeout
            # PriorityQueue.get() blocks until item available or timeout
            task_item = self.task_queue.get(block=True, timeout=timeout)
            return task_item
        except queue.Empty:
            # Timeout occurred or queue is empty
            return None
    
    def _adjustment_loop(self) -> None:
        """Background thread that periodically adjusts thread pool size."""
        while not self.shutdown_flag.is_set():
            try:
                # Sleep before check to allow pool to initialize
                time.sleep(self.config["adjustment_interval"])
                
                # Skip if shutdown is in progress
                if self.shutdown_flag.is_set():
                    break
                
                # Adjust thread pool size
                self._adjust_thread_pool()
                
            except Exception as e:
                logger.error(f"Error in thread pool adjustment: {str(e)}")
    
    def _adjust_thread_pool(self) -> None:
        """Adjust thread pool size based on resource usage and workload."""
        # Skip if another adjustment is in progress
        if not self.adjustment_lock.acquire(blocking=False):
            return
        
        try:
            # Get current time
            current_time = time.time()
            
            # Skip if we adjusted recently
            if current_time - self.stats["last_adjustment"] < self.config["adjustment_interval"] / 2:
                return
            
            # Update last adjustment time
            self.stats["last_adjustment"] = current_time
            
            # Get current thread count
            with self.pool_lock:
                current_threads = len(self.workers)
                active_threads = sum(1 for w in self.workers if w["status"] == "working")
                idle_threads = sum(1 for w in self.workers if w["status"] == "idle")
            
            # Get recommended thread count from resource monitor
            recommended_threads = self.resource_monitor.get_thread_allocation(
                self.config["worker_type"]
            )

            # Calculate queue pressure
            queue_length = self.task_queue.qsize()
            self.stats["queue_length_history"].append((current_time, queue_length))

            # Determine if we need more threads based on backlog
            backlog_pressure = queue_length > idle_threads * 2
            
            # Determine target thread count
            if backlog_pressure and current_threads < self.config["max_threads"]:
                # Increase threads to handle backlog
                target_threads = min(
                    current_threads + 2,  # Add up to 2 threads at a time
                    recommended_threads * 2,  # Up to double recommended
                    self.config["max_threads"]  # But never exceed max
                )
            elif idle_threads > 2 and current_threads > self.config["min_threads"]:
                # Decrease threads if we have excess idle workers
                target_threads = max(
                    current_threads - 1,  # Remove 1 thread at a time
                    recommended_threads,  # Don't go below recommended
                    self.config["min_threads"]  # But never below min
                )
            else:
                # Otherwise, adjust toward recommended count
                if current_threads < recommended_threads:
                    target_threads = min(current_threads + 1, recommended_threads)
                elif current_threads > recommended_threads + 2:  # Allow some buffer
                    target_threads = max(current_threads - 1, recommended_threads)
                else:
                    target_threads = current_threads  # No change needed
            
            # Apply changes if needed
            if target_threads > current_threads:
                # Add threads
                with self.pool_lock:
                    to_add = target_threads - current_threads
                    for _ in range(to_add):
                        self._create_worker()
                    
                    # Update stats
                    self.stats["current_size"] = len(self.workers)
                    self.stats["thread_count_history"].append((current_time, len(self.workers)))
                    
                    logger.debug(f"Added {to_add} workers to {self.name} pool (now {len(self.workers)})")
            
            # Note: Thread removal happens automatically via worker thread idle timeout
        
        finally:
            # Release adjustment lock
            self.adjustment_lock.release()
    
    def submit(self, func: Callable, *args, priority: int = 1, **kwargs) -> None:
        """Submit a task to the thread pool.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            priority: Priority level (0 = highest)
            **kwargs: Keyword arguments to pass to the function
        """
        # Validate priority
        priority = max(0, min(priority, self.config["priority_levels"] - 1))
        
        # Add task to queue
        with self.pool_lock:
            # Add task to priority queue
            # Item format: (priority, (func, args, kwargs))
            task_item = (priority, (func, args, kwargs))
            try:
                 self.task_queue.put(task_item, block=False) # Use block=False to avoid blocking if queue is full
                 # Update statistics
                 self.stats["tasks_submitted"] += 1
            except queue.Full:
                 logger.warning(f"Task queue is full (max size {self.task_queue.maxsize}), rejecting new task")
                 # Optionally, handle rejected task (e.g., raise exception, return status)

    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the thread pool.
        
        Returns:
            Dictionary with thread pool statistics
        """
        with self.pool_lock:
            stats = self.stats.copy()
            # Add current information
            stats["total_queued"] = self.task_queue.qsize()
            stats["total_threads"] = len(self.workers)
            stats["idle_threads"] = sum(1 for w in self.workers if w["status"] == "idle")
            stats["active_threads"] = sum(1 for w in self.workers if w["status"] == "working")
            
            # Calculate average execution time
            if stats["execution_times"]:
                stats["average_execution_time"] = sum(stats["execution_times"]) / len(stats["execution_times"])
            else:
                stats["average_execution_time"] = 0.0
                
            return stats
    
    def shutdown(self, wait: bool = True) -> None:
        """Shut down the thread pool.
        
        Args:
            wait: Whether to wait for tasks to complete
        """
        # Set shutdown flag
        self.shutdown_flag.set()

        # Add sentinel values to wake up workers blocked on get()
        with self.pool_lock:
             num_workers = len(self.workers)
        for _ in range(num_workers):
             try:
                 # Use lowest priority for sentinel to ensure it's processed last
                 self.task_queue.put((self.config["priority_levels"], None), block=False)
             except queue.Full:
                 # Queue is full, workers should eventually exit anyway
                 pass

        # Wait for workers to exit if requested
        if wait:
            end_time = time.time() + self.config["shutdown_timeout"]
            for worker in self.workers:
                remaining = max(0.1, end_time - time.time())
                worker["thread"].join(timeout=remaining)
        
        # Stop adjustment thread
        if self.adjustment_thread:
            self.adjustment_thread.join(timeout=1.0)
            self.adjustment_thread = None


class ResourceAdapter:
    """Adapter to apply resource-aware settings to other components.
    
    This class provides methods to adapt various system components
    to current resource conditions.
    """
    
    def __init__(self, resource_monitor: Optional[ResourceMonitor] = None):
        """Initialize the resource adapter.
        
        Args:
            resource_monitor: ResourceMonitor instance to use
        """
        # Create or store resource monitor
        self.resource_monitor = resource_monitor or ResourceMonitor()
    
    def configure_prefetch_manager(self, prefetch_manager: Any) -> None:
        """Configure a content-aware prefetch manager based on resource state.
        
        Args:
            prefetch_manager: ContentAwarePrefetchManager instance to configure
        """
        # Get current resource status
        status = self.resource_monitor.get_status()
        
        # Get prefetch parameters
        prefetch_params = self.resource_monitor.get_prefetch_parameters()
        
        # Apply configuration if prefetch manager has the right attributes
        if hasattr(prefetch_manager, "config"):
            # Enable/disable prefetching
            prefetch_manager.config["enabled"] = prefetch_params["enabled"]
            
            # Update thread pool size
            if hasattr(prefetch_manager, "prefetch_thread_pool"):
                # Adjust max workers
                max_workers = prefetch_params["max_concurrent"]
                prefetch_manager.prefetch_thread_pool._max_workers = max_workers
            
            # Update prefetch limits
            prefetch_manager.config["max_prefetch_items"] = prefetch_params["max_items"]
            
            # Set prefetch threshold based on resource pressure
            if status["overall"] in ["critical", "high"]:
                # More selective prefetching under resource pressure
                prefetch_manager.config["prefetch_threshold"] = 0.7
            elif status["overall"] == "moderate":
                prefetch_manager.config["prefetch_threshold"] = 0.5
            else:
                prefetch_manager.config["prefetch_threshold"] = 0.3
    
    def configure_thread_pool(self, thread_pool: Any, worker_type: str) -> None:
        """Configure a thread pool based on resource state.
        
        Args:
            thread_pool: Thread pool to configure
            worker_type: Type of worker ('prefetch', 'io', 'compute', 'network')
        """
        # Get thread allocation for this worker type
        thread_count = self.resource_monitor.get_thread_allocation(worker_type)
        
        # Apply to various thread pool implementations
        if hasattr(thread_pool, "_max_workers"):
            # concurrent.futures.ThreadPoolExecutor
            thread_pool._max_workers = thread_count
        elif hasattr(thread_pool, "max_workers"):
            # Some custom thread pools
            thread_pool.max_workers = thread_count
    
    def configure_cache(self, cache_manager: Any) -> None:
        """Configure a cache manager based on resource state.
        
        Args:
            cache_manager: Cache manager to configure
        """
        # Get memory allocation for cache
        cache_size = self.resource_monitor.get_memory_allocation("cache")
        
        # Apply to cache manager if it has config
        if hasattr(cache_manager, "config"):
            # Update memory cache size if configuration has this key
            if "memory_cache_size" in cache_manager.config:
                cache_manager.config["memory_cache_size"] = cache_size
            
            # Also adjust max item size based on available memory
            if "max_item_size" in cache_manager.config:
                status = self.resource_monitor.get_status()
                
                if status["overall"] == "critical":
                    # Very small items only
                    cache_manager.config["max_item_size"] = min(
                        cache_manager.config["max_item_size"],
                        1 * 1024 * 1024  # 1MB maximum
                    )
                elif status["overall"] == "high":
                    # Small items only
                    cache_manager.config["max_item_size"] = min(
                        cache_manager.config["max_item_size"],
                        5 * 1024 * 1024  # 5MB maximum
                    )
    
    def apply_io_throttling(self, io_operation: Callable, *args, **kwargs) -> Any:
        """Apply I/O throttling to an operation based on resource state.
        
        Args:
            io_operation: Function that performs I/O
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Result of the I/O operation
        """
        # Get I/O throttling parameters
        throttle_params = self.resource_monitor.get_io_throttle_parameters()
        
        # Apply throttling delay if needed
        if throttle_params["throttle_delay"] > 0:
            time.sleep(throttle_params["throttle_delay"])
        
        # Execute the operation
        return io_operation(*args, **kwargs)
    
    def get_optimized_config(self, component_type: str) -> Dict[str, Any]:
        """Get optimized configuration for a specific component type.
        
        Args:
            component_type: Type of component ('prefetch', 'cache', 'network', 'thread_pool')
            
        Returns:
            Dictionary with optimized configuration values
        """
        # Get current resource status
        status = self.resource_monitor.get_status()
        
        # Base configurations for each component type
        configs = {
            "prefetch": {
                "enabled": self.resource_monitor.should_prefetch(),
                "max_prefetch_items": self.resource_monitor.get_prefetch_parameters()["max_items"],
                "prefetch_threshold": 0.5,
                "max_concurrent_prefetch": self.resource_monitor.get_prefetch_parameters()["max_concurrent"],
                "sample_size": 1024,  # Bytes to sample for content detection
                "adaptive_resource_management": True
            },
            "cache": {
                "memory_cache_size": self.resource_monitor.get_memory_allocation("cache"),
                "local_cache_size": self.resource_monitor.get_memory_allocation("cache") * 10,
                "max_item_size": 10 * 1024 * 1024,  # 10MB default
                "min_access_count": 2
            },
            "network": {
                "max_concurrent_requests": self.resource_monitor.get_io_throttle_parameters()["max_concurrent_io"],
                "max_bandwidth_bps": self.resource_monitor.get_io_throttle_parameters()["max_bandwidth_bps"],
                "connect_timeout": 10.0,  # seconds
                "read_timeout": 30.0,  # seconds
                "retry_count": 3
            },
            "thread_pool": {
                "min_threads": 1,
                "max_threads": self.resource_monitor.get_thread_allocation("prefetch"),
                "dynamic_adjustment": True,
                "adjustment_interval": 10.0,
                "queue_size": 100
            }
        }
        
        # Return configuration for requested component
        if component_type in configs:
            return configs[component_type]
        
        # Return empty config for unknown component
        return {}
        
    def update_config(self, component_type: str, new_config: Dict[str, Any]) -> None:
        """Update the configuration for a specific component type.
        
        Args:
            component_type: Type of component to update
            new_config: New configuration values to apply
        """

        if component_type in configs:
            configs[component_type].update(new_config)
        else:
            raise ValueError(f"Unknown component type: {component_type}")
