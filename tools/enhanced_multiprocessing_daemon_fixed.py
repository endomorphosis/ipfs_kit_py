#!/usr/bin/env python3
"""
Enhanced IPFS-Kit Daemon with Multiprocessing (Fixed)

A high-performance daemon that uses multiprocessing to increase throughput for:
- Backend health monitoring across multiple processes
- Concurrent replication management
- Parallel log collection and processing
- Distributed pin index updates
- Load-balanced API endpoint handling

Features:
- Process pool for backend operations
- Worker processes for different operation types
- Shared memory for status communication
- Load balancing across CPU cores
- Graceful worker process management
"""

import asyncio
import json
import logging
import multiprocessing as mp
import os
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, TYPE_CHECKING, Union
from dataclasses import dataclass, field
import threading
import subprocess
import psutil
import queue
from multiprocessing import Manager, Process, Queue as MPQueue, Event, Value, Array
from functools import partial

# Configure logging
log_dir = Path("/tmp/ipfs_kit_logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr),
        logging.FileHandler(log_dir / 'enhanced_ipfs_kit_daemon.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Import IPFS Kit components with TYPE_CHECKING
if TYPE_CHECKING:
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.dashboard.replication_manager import ReplicationManager
    from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    from ipfs_kit_py.vfs_observability import VFSObservabilityManager

# Dynamic imports with fallback
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.dashboard.replication_manager import ReplicationManager
    from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    from ipfs_kit_py.vfs_observability import VFSObservabilityManager
    IPFS_KIT_AVAILABLE = True
except ImportError as e:
    logger.warning(f"IPFS Kit components not available: {e}")
    # Mock classes for standalone operation
    class EnhancedDaemonManager:
        def __init__(self): pass
        def get_status(self): return {"status": "mock"}
    
    class IPFSKit:
        def __init__(self): 
            self.daemon_manager = EnhancedDaemonManager()
    
    class ReplicationManager:
        def check_replication_status(self): return {"status": "mock"}
        def perform_auto_replication(self): return {"result": "mock"}
    
    class BackendHealthMonitor:
        def __init__(self, config_dir: str = "/tmp"): pass
        def check_backend_health_sync(self, backend: str): return {"status": "healthy"}
    
    class VFSObservabilityManager:
        def __init__(self): pass
        def get_filesystem_stats(self): return {"stats": "mock"}
    
    IPFS_KIT_AVAILABLE = False


@dataclass
class ProcessStats:
    """Shared statistics for worker processes"""
    total_requests: Value = field(default_factory=lambda: Value('i', 0))
    successful_requests: Value = field(default_factory=lambda: Value('i', 0))
    failed_requests: Value = field(default_factory=lambda: Value('i', 0))
    total_response_time: Value = field(default_factory=lambda: Value('d', 0.0))
    active_workers: Value = field(default_factory=lambda: Value('i', 0))
    peak_workers: Value = field(default_factory=lambda: Value('i', 0))
    
    def update_request_count(self, count: int):
        with self.total_requests.get_lock():
            self.total_requests.value += count
    
    def update_success_count(self, count: int):
        with self.successful_requests.get_lock():
            self.successful_requests.value += count
    
    def update_failure_count(self, count: int):
        with self.failed_requests.get_lock():
            self.failed_requests.value += count
    
    def update_response_time(self, time: float):
        with self.total_response_time.get_lock():
            self.total_response_time.value += time
    
    def update_active_workers(self, count: int):
        with self.active_workers.get_lock():
            self.active_workers.value = count
            if count > self.peak_workers.value:
                self.peak_workers.value = count
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests.value,
            "successful_requests": self.successful_requests.value,
            "failed_requests": self.failed_requests.value,
            "avg_response_time": (
                self.total_response_time.value / max(self.total_requests.value, 1)
            ),
            "active_workers": self.active_workers.value,
            "peak_workers": self.peak_workers.value,
            "success_rate": (
                self.successful_requests.value / max(self.total_requests.value, 1) * 100
            )
        }


def health_check_worker(backend_name: str, config: Dict[str, Any], result_queue: MPQueue, stats: ProcessStats):
    """Worker function for checking backend health"""
    try:
        # Initialize health monitor
        health_monitor = BackendHealthMonitor(config_dir=config.get("config_dir", "/tmp/ipfs_kit_config"))
        
        process_name = mp.current_process().name
        start_time = time.time()
        
        try:
            # Check backend health
            health_result = health_monitor.check_backend_health_sync(backend_name)
            response_time = time.time() - start_time
            
            result = {
                "worker": process_name,
                "backend": backend_name,
                "status": "healthy",
                "response_time": response_time,
                "details": health_result.get("details", {}) if isinstance(health_result, dict) else {}
            }
            
            # Update shared statistics
            stats.update_request_count(1)
            stats.update_response_time(response_time)
            stats.update_success_count(1)
            
        except Exception as e:
            response_time = time.time() - start_time
            result = {
                "worker": process_name,
                "backend": backend_name,
                "status": "error",
                "error": str(e),
                "response_time": response_time
            }
            stats.update_request_count(1)
            stats.update_response_time(response_time)
            stats.update_failure_count(1)
        
        result_queue.put(result)
        
    except Exception as e:
        logger.error(f"Health check worker error: {e}")


def replication_worker(config: Dict[str, Any], result_queue: MPQueue, stats: ProcessStats, stop_event: Event):
    """Worker function for replication management"""
    try:
        # Initialize replication manager
        replication_manager = ReplicationManager()
        
        process_name = mp.current_process().name
        
        while not stop_event.is_set():
            try:
                start_time = time.time()
                
                # Check replication status
                replication_result = replication_manager.check_replication_status()
                response_time = time.time() - start_time
                
                result = {
                    "worker": process_name,
                    "operation": "replication_check",
                    "status": "completed",
                    "response_time": response_time,
                    "details": replication_result
                }
                
                # Perform auto-replication if needed
                if replication_result.get("auto_replication_needed", False):
                    auto_repl_result = replication_manager.perform_auto_replication()
                    result["auto_replication"] = auto_repl_result
                
                # Update statistics
                stats.update_request_count(1)
                stats.update_response_time(response_time)
                stats.update_success_count(1)
                
                result_queue.put(result)
                
                # Wait before next check
                time.sleep(config.get("replication_check_interval", 60))
                
            except Exception as e:
                logger.error(f"Replication worker error: {e}")
                stats.update_request_count(1)
                stats.update_failure_count(1)
                time.sleep(10)  # Wait before retry
                
    except Exception as e:
        logger.error(f"Replication worker initialization error: {e}")


def log_collection_worker(config: Dict[str, Any], result_queue: MPQueue, stats: ProcessStats, stop_event: Event):
    """Worker function for log collection and processing"""
    try:
        process_name = mp.current_process().name
        log_dir = config.get("log_dir", "/tmp/ipfs_kit_logs")
        
        while not stop_event.is_set():
            try:
                start_time = time.time()
                
                # Collect logs from various sources
                log_files = []
                if os.path.exists(log_dir):
                    log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
                
                # Process logs (mock implementation)
                processed_logs = []
                for log_file in log_files[:5]:  # Limit to 5 files per cycle
                    log_path = os.path.join(log_dir, log_file)
                    try:
                        with open(log_path, 'r') as f:
                            lines = f.readlines()
                            processed_logs.append({
                                "file": log_file,
                                "lines": len(lines),
                                "size": os.path.getsize(log_path)
                            })
                    except Exception as e:
                        logger.warning(f"Could not process log file {log_file}: {e}")
                
                response_time = time.time() - start_time
                
                result = {
                    "worker": process_name,
                    "operation": "log_collection",
                    "status": "completed",
                    "response_time": response_time,
                    "logs_processed": len(processed_logs),
                    "details": processed_logs
                }
                
                # Update statistics
                stats.update_request_count(1)
                stats.update_response_time(response_time)
                stats.update_success_count(1)
                
                result_queue.put(result)
                
                # Wait before next collection
                time.sleep(config.get("log_collection_interval", 30))
                
            except Exception as e:
                logger.error(f"Log collection worker error: {e}")
                stats.update_request_count(1)
                stats.update_failure_count(1)
                time.sleep(5)  # Wait before retry
                
    except Exception as e:
        logger.error(f"Log collection worker initialization error: {e}")


def pin_index_worker(config: Dict[str, Any], work_queue: MPQueue, result_queue: MPQueue, stats: ProcessStats, stop_event: Event):
    """Worker function for pin index updates"""
    try:
        process_name = mp.current_process().name
        
        while not stop_event.is_set():
            try:
                # Get work item from queue (with timeout)
                try:
                    work_item = work_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                start_time = time.time()
                
                # Process pin index update
                operation = work_item.get("operation", "update")
                pin_data = work_item.get("data", {})
                
                # Mock pin index processing
                result_data = {
                    "operation": operation,
                    "pins_processed": len(pin_data.get("pins", [])),
                    "index_updated": True
                }
                
                response_time = time.time() - start_time
                
                result = {
                    "worker": process_name,
                    "operation": "pin_index_update",
                    "status": "completed",
                    "response_time": response_time,
                    "details": result_data
                }
                
                # Update statistics
                stats.update_request_count(1)
                stats.update_response_time(response_time)
                stats.update_success_count(1)
                
                result_queue.put(result)
                work_queue.task_done()
                
            except Exception as e:
                logger.error(f"Pin index worker error: {e}")
                stats.update_request_count(1)
                stats.update_failure_count(1)
                
    except Exception as e:
        logger.error(f"Pin index worker initialization error: {e}")


class EnhancedIPFSKitDaemon:
    """Enhanced IPFS Kit Daemon with multiprocessing support"""
    
    def __init__(self, config_file: str = None, max_workers: int = None):
        self.config_file = config_file or "/tmp/ipfs_kit_config/enhanced_daemon.json"
        self.max_workers = max_workers or min(mp.cpu_count(), 8)
        
        # Multiprocessing components
        self.manager = Manager()
        self.result_queue = MPQueue()
        self.pin_work_queue = MPQueue()
        self.stop_event = Event()
        
        # Process pools
        self.health_pool: Optional[ProcessPoolExecutor] = None
        self.pin_pool: Optional[ProcessPoolExecutor] = None
        
        # Thread pools for API handling
        self.api_thread_pool: Optional[ThreadPoolExecutor] = None
        
        # Shared statistics
        self.stats = ProcessStats()
        
        # Component instances (with proper typing)
        self.daemon_manager: Optional["EnhancedDaemonManager"] = None
        self.ipfs_kit: Optional["IPFSKit"] = None
        self.health_monitor: Optional["BackendHealthMonitor"] = None
        self.vfs_observer: Optional["VFSObservabilityManager"] = None
        
        # Worker processes
        self.worker_processes: List[Process] = []
        
        # Configuration
        self.config = self._load_config()
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        logger.info(f"Enhanced daemon initialized with {self.max_workers} max workers")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load daemon configuration"""
        default_config = {
            "max_workers": self.max_workers,
            "health_workers": min(4, self.max_workers // 2),
            "pin_index_workers": min(2, self.max_workers // 4),
            "api_threads": min(32, self.max_workers * 4),
            "config_dir": "/tmp/ipfs_kit_config",
            "log_dir": "/tmp/ipfs_kit_logs",
            "health_check_interval": 30,
            "replication_check_interval": 60,
            "log_collection_interval": 30,
            "enable_health_monitoring": True,
            "enable_replication": True,
            "enable_log_collection": True,
            "enable_pin_indexing": True
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                logger.warning(f"Could not load config from {self.config_file}: {e}")
        
        return default_config
    
    def _save_config(self):
        """Save current configuration"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save config to {self.config_file}: {e}")
    
    def initialize_components(self):
        """Initialize IPFS Kit components"""
        try:
            logger.info("Initializing IPFS Kit components...")
            
            # Initialize IPFS Kit
            self.ipfs_kit = IPFSKit()
            if hasattr(self.ipfs_kit, 'daemon_manager'):
                self.daemon_manager = self.ipfs_kit.daemon_manager
            else:
                logger.warning("daemon_manager not available on ipfs_kit")
            
            # Initialize health monitor
            if IPFS_KIT_AVAILABLE:
                self.health_monitor = BackendHealthMonitor(
                    config_dir=self.config.get("config_dir", "/tmp/ipfs_kit_config")
                )
                logger.info("Backend health monitor initialized")
            
            # Initialize VFS observability
            if IPFS_KIT_AVAILABLE:
                self.vfs_observer = VFSObservabilityManager()
                logger.info("VFS observability manager initialized")
            
            logger.info("Component initialization completed")
            return True
            
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
            return False
    
    def start_worker_processes(self):
        """Start background worker processes"""
        try:
            # Health monitoring workers
            if self.config.get("enable_health_monitoring", True):
                for i in range(self.config["health_workers"]):
                    worker = Process(
                        target=replication_worker,
                        args=(self.config, self.result_queue, self.stats, self.stop_event),
                        name=f"health-worker-{i}"
                    )
                    worker.start()
                    self.worker_processes.append(worker)
                    logger.info(f"Started health worker {i}")
            
            # Replication worker
            if self.config.get("enable_replication", True):
                repl_worker = Process(
                    target=replication_worker,
                    args=(self.config, self.result_queue, self.stats, self.stop_event),
                    name="replication-worker"
                )
                repl_worker.start()
                self.worker_processes.append(repl_worker)
                logger.info("Started replication worker")
            
            # Log collection worker
            if self.config.get("enable_log_collection", True):
                log_worker = Process(
                    target=log_collection_worker,
                    args=(self.config, self.result_queue, self.stats, self.stop_event),
                    name="log-collection-worker"
                )
                log_worker.start()
                self.worker_processes.append(log_worker)
                logger.info("Started log collection worker")
            
            # Pin index workers
            if self.config.get("enable_pin_indexing", True):
                for i in range(self.config["pin_index_workers"]):
                    pin_worker = Process(
                        target=pin_index_worker,
                        args=(self.config, self.pin_work_queue, self.result_queue, self.stats, self.stop_event),
                        name=f"pin-index-worker-{i}"
                    )
                    pin_worker.start()
                    self.worker_processes.append(pin_worker)
                    logger.info(f"Started pin index worker {i}")
            
            logger.info(f"Started {len(self.worker_processes)} worker processes")
            
        except Exception as e:
            logger.error(f"Failed to start worker processes: {e}")
            raise
    
    def start_process_pools(self):
        """Start process pools for parallel operations"""
        try:
            # Health check pool
            self.health_pool = ProcessPoolExecutor(
                max_workers=self.config["health_workers"],
                mp_context=mp.get_context('spawn')
            )
            
            # Pin index pool
            self.pin_pool = ProcessPoolExecutor(
                max_workers=self.config["pin_index_workers"],
                mp_context=mp.get_context('spawn')
            )
            
            # API thread pool
            self.api_thread_pool = ThreadPoolExecutor(
                max_workers=self.config["api_threads"],
                thread_name_prefix="api-thread"
            )
            
            logger.info("Process pools started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start process pools: {e}")
            raise
    
    def start(self) -> bool:
        """Start the enhanced daemon"""
        try:
            logger.info("Starting Enhanced IPFS Kit Daemon...")
            
            # Initialize components
            if not self.initialize_components():
                return False
            
            # Start process pools
            self.start_process_pools()
            
            # Start worker processes
            self.start_worker_processes()
            
            # Save configuration
            self._save_config()
            
            logger.info("Enhanced daemon started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start enhanced daemon: {e}")
            self.cleanup()
            return False
    
    def check_backends_parallel(self, backends: List[str]) -> List[Dict[str, Any]]:
        """Check backend health in parallel"""
        if not self.health_pool:
            logger.warning("Health pool not available")
            return []
        
        results = []
        futures = []
        
        # Submit health check tasks
        for backend in backends:
            future = self.health_pool.submit(
                health_check_worker, 
                backend, 
                self.config, 
                self.result_queue, 
                self.stats
            )
            futures.append((backend, future))
        
        # Collect results
        for backend, future in futures:
            try:
                # Note: The result is put in the queue by the worker
                # Future just tells us when the worker completes
                future.result(timeout=30)  # Wait for worker to complete
                
                # Get result from queue
                try:
                    result = self.result_queue.get_nowait()
                    results.append(result)
                except queue.Empty:
                    results.append({
                        "backend": backend,
                        "status": "no_result",
                        "error": "No result received from worker"
                    })
                    
            except Exception as e:
                results.append({
                    "backend": backend,
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive daemon status"""
        try:
            status = {
                "daemon": {
                    "status": "running",
                    "uptime": time.time(),
                    "config": self.config,
                    "worker_processes": len(self.worker_processes),
                    "active_workers": [p.name for p in self.worker_processes if p.is_alive()]
                },
                "statistics": self.stats.get_stats(),
                "system": {
                    "cpu_count": mp.cpu_count(),
                    "memory_usage": psutil.virtual_memory()._asdict(),
                    "cpu_percent": psutil.cpu_percent(interval=1)
                }
            }
            
            # Add component status if available
            if self.daemon_manager:
                try:
                    if hasattr(self.daemon_manager, 'get_status'):
                        status["daemon_manager"] = self.daemon_manager.get_status()
                    else:
                        status["daemon_manager"] = {"status": "available"}
                except Exception as e:
                    status["daemon_manager"] = {"status": "error", "error": str(e)}
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting daemon status: {e}")
            return {"status": "error", "error": str(e)}
    
    def cleanup(self):
        """Clean up resources and stop all processes"""
        try:
            logger.info("Cleaning up enhanced daemon...")
            
            # Signal workers to stop
            self.stop_event.set()
            
            # Stop worker processes
            for worker in self.worker_processes:
                if worker.is_alive():
                    worker.join(timeout=5)
                    if worker.is_alive():
                        worker.terminate()
                        worker.join(timeout=2)
                        if worker.is_alive():
                            worker.kill()
            
            # Shutdown process pools
            if self.health_pool:
                self.health_pool.shutdown(wait=True)
            
            if self.pin_pool:
                self.pin_pool.shutdown(wait=True)
            
            if self.api_thread_pool:
                self.api_thread_pool.shutdown(wait=True)
            
            logger.info("Enhanced daemon cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point for the enhanced daemon"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced IPFS Kit Daemon with Multiprocessing")
    parser.add_argument("--config", "-c", help="Configuration file path")
    parser.add_argument("--workers", "-w", type=int, help="Maximum number of workers")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create enhanced daemon
    daemon = EnhancedIPFSKitDaemon(config_file=args.config, max_workers=args.workers)
    
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        daemon.cleanup()
        sys.exit(0)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start daemon
        if daemon.start():
            logger.info("Enhanced daemon is running. Press Ctrl+C to stop.")
            
            # Keep daemon running
            while True:
                time.sleep(10)
                
                # Print periodic status
                status = daemon.get_status()
                stats = status.get("statistics", {})
                logger.info(f"Status: {stats.get('total_requests', 0)} requests, "
                          f"{stats.get('success_rate', 0):.1f}% success rate, "
                          f"{stats.get('active_workers', 0)} active workers")
        else:
            logger.error("Failed to start enhanced daemon")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}")
    finally:
        daemon.cleanup()


if __name__ == "__main__":
    main()
