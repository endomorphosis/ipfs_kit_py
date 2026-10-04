#!/usr/bin/env python3
"""
Enhanced IPFS-Kit Daemon with Multiprocessing

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
from typing import Dict, Any, List, Optional, Set
import threading
import subprocess
import psutil
import queue
from multiprocessing import Manager, Process, Queue, Event, Value, Array
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

# Import IPFS Kit components
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.dashboard.replication_manager import ReplicationManager
    from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    from ipfs_kit_py.vfs_observability import VFSObservabilityManager
    IPFS_KIT_AVAILABLE = True
    logger.info("IPFS Kit components imported successfully")
except ImportError as e:
    logger.warning(f"IPFS Kit components not available: {e}")
    # Create mock classes for standalone operation
    class EnhancedDaemonManager:
        def get_status(self): return {"status": "mock"}
    
    class IPFSKit:
        def __init__(self): 
            self.daemon_manager = EnhancedDaemonManager()
    
    class ReplicationManager:
        def check_replication_status(self): return {"status": "mock"}
        def perform_auto_replication(self): return {"result": "mock"}
    
    class BackendHealthMonitor:
        def __init__(self, config_dir="/tmp"): pass
        def check_backend_health_sync(self, backend): return {"status": "healthy"}
    
    class VFSObservabilityManager:
        def __init__(self): pass
        def get_filesystem_stats(self): return {"stats": "mock"}
    
    IPFS_KIT_AVAILABLE = False


class ProcessStats:
    """Shared statistics for worker processes"""
    
    def __init__(self):
        self.total_requests = Value('i', 0)
        self.successful_requests = Value('i', 0)
        self.failed_requests = Value('i', 0)
        self.total_response_time = Value('d', 0.0)
        self.active_workers = Value('i', 0)
        self.peak_workers = Value('i', 0)
    
    def update_request_count(self, count: int):
        with self.total_requests.get_lock():
            self.total_requests.value += count
    
    def update_success_count(self, count: int):
        with self.successful_requests.get_lock():
            self.successful_requests.value += count
    
    def update_failure_count(self, count: int):
        with self.failed_requests.get_lock():
            self.failed_requests.value += count
    
    def update_response_time(self, time_val: float):
        with self.total_response_time.get_lock():
            self.total_response_time.value += time_val
    
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

# Import IPFS Kit components
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
    from ipfs_kit_py.ipfs_kit import IPFSKit
    from ipfs_kit_py.dashboard.replication_manager import ReplicationManager
    from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
    from ipfs_kit_py.mcp.ipfs_kit.backends.vfs_observer import VFSObservabilityManager
    CORE_COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import core components: {e}")
    CORE_COMPONENTS_AVAILABLE = False


class ProcessStats:
    """Shared statistics across processes."""
    
    def __init__(self, manager):
        self.health_checks = manager.Value('i', 0)
        self.replication_ops = manager.Value('i', 0)
        self.log_operations = manager.Value('i', 0)
        self.api_requests = manager.Value('i', 0)
        self.errors = manager.Value('i', 0)
        self.start_time = manager.Value('d', time.time())
        
    def to_dict(self):
        return {
            'health_checks': self.health_checks.value,
            'replication_ops': self.replication_ops.value,
            'log_operations': self.log_operations.value,
            'api_requests': self.api_requests.value,
            'errors': self.errors.value,
            'uptime': time.time() - self.start_time.value
        }


def health_check_worker(backend_name: str, config: Dict[str, Any], result_queue: MPQueue, stats: "ProcessStats"):
    """Worker function for checking backend health"""
    try:
        # Initialize health monitor (mock for demo)
        health_monitor = BackendHealthMonitor(config_dir=config.get("config_dir", "/tmp/ipfs_kit_config"))
        
        process_name = mp.current_process().name
        start_time = time.time()
        
        try:
            # Mock health check (replace with actual implementation)
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
        
        result_queue.put(result)
        
    except Exception as e:
        logger.error(f"Health check worker error: {e}")


def replication_worker(config: Dict[str, Any], result_queue: MPQueue, stats: "ProcessStats", stop_event: Event):


def replication_worker(config: Dict[str, Any], result_queue: "Queue[Dict[str, Any]]", stats: "ProcessStats", stop_event: Event):
    """Worker process for replication management."""
    try:
        # Initialize replication manager in worker process
        replication_manager = ReplicationManager()
        
        while not stop_event.is_set():
            try:
                # Perform replication check
                replication_result = replication_manager.check_replication_status()
                
                # Send result back
                result_queue.put({
                    'type': 'replication_result',
                    'result': replication_result,
                    'timestamp': time.time()
                })
                
                # Perform auto-replication if enabled
                if config.get("auto_replication", True):
                    auto_repl_result = replication_manager.perform_auto_replication()
                    result_queue.put({
                        'type': 'auto_replication_result',
                        'result': auto_repl_result,
                        'timestamp': time.time()
                    })
                
                # Update stats
                with stats.replication_ops.get_lock():
                    stats.replication_ops.value += 1
                
                # Sleep between checks
                time.sleep(config.get("replication_check_interval", 300))
                
            except Exception as e:
                logger.error(f"Replication worker error: {e}")
                with stats.errors.get_lock():
                    stats.errors.value += 1
                time.sleep(60)
                
    except Exception as e:
        logger.error(f"Replication worker failed: {e}")


def log_collection_worker(config: Dict[str, Any], result_queue: Queue, stats: ProcessStats, stop_event: Event):
    """Worker process for log collection and processing."""
    try:
        while not stop_event.is_set():
            try:
                # Collect logs from various sources
                log_files = []
                
                # IPFS daemon logs
                if os.path.exists("/tmp/ipfs_logs"):
                    log_files.extend(Path("/tmp/ipfs_logs").glob("*.log"))
                
                # Process log files in parallel
                for log_file in log_files:
                    try:
                        # Rotate if needed
                        if log_file.stat().st_size > 50 * 1024 * 1024:  # 50MB
                            rotated_name = f"{log_file}.{int(time.time())}"
                            log_file.rename(rotated_name)
                            
                        # Update stats
                        with stats.log_operations.get_lock():
                            stats.log_operations.value += 1
                            
                    except Exception as e:
                        logger.error(f"Error processing log file {log_file}: {e}")
                
                # Sleep between collections
                time.sleep(config.get("log_rotation_interval", 3600))
                
            except Exception as e:
                logger.error(f"Log collection worker error: {e}")
                with stats.errors.get_lock():
                    stats.errors.value += 1
                time.sleep(300)
                
    except Exception as e:
        logger.error(f"Log collection worker failed: {e}")


def pin_index_worker(config: Dict[str, Any], work_queue: Queue, result_queue: Queue, stats: ProcessStats, stop_event: Event):
    """Worker process for pin index updates."""
    try:
        while not stop_event.is_set():
            try:
                # Wait for work with timeout
                work_item = work_queue.get(timeout=30)
                
                if work_item is None:  # Poison pill
                    break
                
                operation = work_item.get('operation')
                data = work_item.get('data', {})
                
                if operation == 'update_index':
                    # Simulate index update (in real implementation, this would update parquet files)
                    time.sleep(0.1)  # Simulate work
                    
                    result_queue.put({
                        'type': 'index_updated',
                        'backend': data.get('backend'),
                        'pins_processed': data.get('pin_count', 0),
                        'timestamp': time.time()
                    })
                
                elif operation == 'rebuild_index':
                    # Simulate index rebuild
                    time.sleep(1)  # Simulate more intensive work
                    
                    result_queue.put({
                        'type': 'index_rebuilt',
                        'backend': data.get('backend'),
                        'timestamp': time.time()
                    })
                
            except queue.Empty:
                continue  # No work available, check stop event
            except Exception as e:
                logger.error(f"Pin index worker error: {e}")
                with stats.errors.get_lock():
                    stats.errors.value += 1
                
    except Exception as e:
        logger.error(f"Pin index worker failed: {e}")


class EnhancedIPFSKitDaemon:
    """
    Enhanced multiprocessing daemon for managing IPFS-Kit infrastructure.
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "/tmp/ipfs_kit_config/enhanced_daemon.json"
        self.pid_file = "/tmp/enhanced_ipfs_kit_daemon.pid"
        self.running = False
        self.start_time = time.time()
        
        # Multiprocessing components
        self.manager = Manager()
        self.result_queue = Queue()
        self.pin_work_queue = Queue()
        self.stop_event = Event()
        
        # Shared statistics
        self.stats = ProcessStats(self.manager)
        
        # Process pools
        self.cpu_count = mp.cpu_count()
        self.health_workers = []
        self.replication_process = None
        self.log_collection_process = None
        self.pin_index_workers = []
        
        # Thread pools for async operations
        self.api_thread_pool = ThreadPoolExecutor(
            max_workers=min(32, self.cpu_count * 4),
            thread_name_prefix="api-worker"
        )
        
        # Core managers (main process)
        self.daemon_manager: Optional[EnhancedDaemonManager] = None
        self.ipfs_kit: Optional[IPFSKit] = None
        self.health_monitor: Optional[BackendHealthMonitor] = None
        self.vfs_observer: Optional[VFSObservabilityManager] = None
        
        # Status tracking (shared)
        self.backend_status = self.manager.dict()
        self.daemon_status = self.manager.dict()
        self.replication_status = self.manager.dict()
        
        # Load configuration
        self.config = self._load_config()
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _load_config(self) -> Dict[str, Any]:
        """Load enhanced daemon configuration."""
        default_config = {
            "daemon": {
                "pid_file": "/tmp/enhanced_ipfs_kit_daemon.pid",
                "log_level": "INFO",
                "health_check_interval": 30,
                "replication_check_interval": 300,
                "log_rotation_interval": 3600,
                "workers": {
                    "health_workers": min(4, self.cpu_count),
                    "pin_index_workers": min(2, self.cpu_count // 2),
                    "api_workers": min(32, self.cpu_count * 4)
                }
            },
            "backends": {
                "ipfs": {"enabled": True, "auto_start": True},
                "ipfs_cluster": {"enabled": True, "auto_start": True},
                "lotus": {"enabled": False, "auto_start": False},
                "lassie": {"enabled": True, "auto_start": True},
                "storacha": {"enabled": False, "auto_start": False},
                "s3": {"enabled": False, "auto_start": False},
                "huggingface": {"enabled": False, "auto_start": False}
            },
            "replication": {
                "enabled": True,
                "auto_replication": True,
                "min_replicas": 2,
                "max_replicas": 5,
                "check_interval": 300
            },
            "performance": {
                "parallel_health_checks": True,
                "concurrent_replication": True,
                "batch_pin_updates": True,
                "load_balance_requests": True
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    loaded_config = json.load(f)
                return {**default_config, **loaded_config}
            else:
                os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
                with open(self.config_file, 'w') as f:
                    json.dump(default_config, f, indent=2)
                logger.info(f"Created enhanced config file: {self.config_file}")
                return default_config
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            return default_config
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down enhanced daemon...")
        self.running = False
        self.stop_event.set()
    
    async def start(self):
        """Start the enhanced daemon with multiprocessing."""
        logger.info("🚀 Starting Enhanced IPFS-Kit Daemon with Multiprocessing")
        logger.info("=" * 70)
        logger.info(f"CPU cores detected: {self.cpu_count}")
        logger.info(f"Health workers: {self.config['daemon']['workers']['health_workers']}")
        logger.info(f"Pin index workers: {self.config['daemon']['workers']['pin_index_workers']}")
        logger.info(f"API workers: {self.config['daemon']['workers']['api_workers']}")
        
        if not CORE_COMPONENTS_AVAILABLE:
            logger.error("Core components not available, cannot start daemon")
            return False
        
        # Write PID file
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            logger.info(f"PID file written: {self.pid_file}")
        except Exception as e:
            logger.error(f"Failed to write PID file: {e}")
            return False
        
        try:
            # Initialize core components
            await self._initialize_components()
            
            # Start worker processes
            await self._start_worker_processes()
            
            # Start result processing
            await self._start_result_processing()
            
            # Start main daemon loop
            self.running = True
            logger.info("✅ Enhanced IPFS-Kit Daemon started successfully")
            await self._main_loop()
            
        except Exception as e:
            logger.error(f"Failed to start enhanced daemon: {e}")
            return False
        finally:
            await self._cleanup()
    
    async def _initialize_components(self):
        """Initialize core daemon components."""
        logger.info("🔧 Initializing enhanced daemon components...")
        
        # Initialize IPFS Kit
        try:
            self.ipfs_kit = IPFSKit()
            self.daemon_manager = self.ipfs_kit.daemon_manager
            logger.info("✅ IPFS Kit initialized")
        except Exception as e:
            logger.error(f"Failed to initialize IPFS Kit: {e}")
            raise
        
        # Initialize health monitor
        try:
            self.health_monitor = BackendHealthMonitor(
                config_dir="/tmp/ipfs_kit_config"
            )
            logger.info("✅ Health monitor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize health monitor: {e}")
            raise
        
        # Initialize VFS observer
        try:
            self.vfs_observer = VFSObservabilityManager()
            logger.info("✅ VFS observer initialized")
        except Exception as e:
            logger.warning(f"VFS observer not available: {e}")
            self.vfs_observer = None
    
    async def _start_worker_processes(self):
        """Start all worker processes."""
        logger.info("🏭 Starting worker processes...")
        
        # Start health check workers for each backend
        enabled_backends = [
            name for name, config in self.config["backends"].items()
            if config.get("enabled", False)
        ]
        
        workers_per_backend = max(1, self.config['daemon']['workers']['health_workers'] // len(enabled_backends))
        
        for backend_name in enabled_backends:
            for i in range(workers_per_backend):
                worker = Process(
                    target=health_check_worker,
                    args=(backend_name, self.config, self.result_queue, self.stats),
                    name=f"health-{backend_name}-{i}"
                )
                worker.start()
                self.health_workers.append(worker)
                logger.info(f"Started health worker for {backend_name} (worker {i})")
        
        # Start replication worker
        if self.config["replication"]["enabled"]:
            self.replication_process = Process(
                target=replication_worker,
                args=(self.config["replication"], self.result_queue, self.stats, self.stop_event),
                name="replication-worker"
            )
            self.replication_process.start()
            logger.info("Started replication worker")
        
        # Start log collection worker
        self.log_collection_process = Process(
            target=log_collection_worker,
            args=(self.config["daemon"], self.result_queue, self.stats, self.stop_event),
            name="log-collection-worker"
        )
        self.log_collection_process.start()
        logger.info("Started log collection worker")
        
        # Start pin index workers
        num_pin_workers = self.config['daemon']['workers']['pin_index_workers']
        for i in range(num_pin_workers):
            worker = Process(
                target=pin_index_worker,
                args=(self.config, self.pin_work_queue, self.result_queue, self.stats, self.stop_event),
                name=f"pin-index-{i}"
            )
            worker.start()
            self.pin_index_workers.append(worker)
            logger.info(f"Started pin index worker {i}")
    
    async def _start_result_processing(self):
        """Start result processing from worker processes."""
        logger.info("📨 Starting result processing...")
        
        # Start result processing task
        asyncio.create_task(self._result_processing_loop())
    
    async def _result_processing_loop(self):
        """Process results from worker processes."""
        while self.running:
            try:
                # Check for results (non-blocking)
                try:
                    result = self.result_queue.get_nowait()
                    await self._process_result(result)
                except:
                    # No results available
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in result processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_result(self, result: Dict[str, Any]):
        """Process a result from a worker process."""
        result_type = result.get('type')
        
        if result_type == 'health_result':
            backend = result['backend']
            health_data = result['result']
            self.backend_status[backend] = {
                **health_data,
                'last_updated': result['timestamp']
            }
        
        elif result_type == 'replication_result':
            self.replication_status.update({
                **result['result'],
                'last_updated': result['timestamp']
            })
        
        elif result_type == 'index_updated':
            logger.debug(f"Pin index updated for {result.get('backend')}")
        
        elif result_type == 'index_rebuilt':
            logger.info(f"Pin index rebuilt for {result.get('backend')}")
    
    async def _main_loop(self):
        """Enhanced main daemon loop with multiprocessing coordination."""
        logger.info("🔄 Starting enhanced main daemon loop")
        
        while self.running:
            try:
                # Update daemon status
                await self._update_daemon_status()
                
                # Schedule pin index updates
                await self._schedule_pin_updates()
                
                # Check worker health
                await self._check_worker_health()
                
                # Sleep for main loop interval
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in enhanced main daemon loop: {e}")
                await asyncio.sleep(10)
    
    async def _update_daemon_status(self):
        """Update overall daemon status."""
        self.daemon_status.update({
            'uptime': time.time() - self.start_time,
            'workers': {
                'health_workers': len([w for w in self.health_workers if w.is_alive()]),
                'replication_worker': self.replication_process.is_alive() if self.replication_process else False,
                'log_worker': self.log_collection_process.is_alive() if self.log_collection_process else False,
                'pin_workers': len([w for w in self.pin_index_workers if w.is_alive()])
            },
            'stats': self.stats.to_dict(),
            'last_updated': time.time(),
            'pid': os.getpid(),
            'version': "1.1.0-mp"
        })
    
    async def _schedule_pin_updates(self):
        """Schedule pin index updates."""
        # Example: periodically schedule pin index work
        if hasattr(self, '_last_pin_schedule') and time.time() - self._last_pin_schedule < 300:
            return
        
        # Schedule some work for pin index workers
        for backend in self.config["backends"].keys():
            if self.config["backends"][backend].get("enabled"):
                work_item = {
                    'operation': 'update_index',
                    'data': {
                        'backend': backend,
                        'pin_count': 100  # Example
                    }
                }
                self.pin_work_queue.put(work_item)
        
        self._last_pin_schedule = time.time()
    
    async def _check_worker_health(self):
        """Check health of worker processes."""
        # Check health workers
        dead_workers = [w for w in self.health_workers if not w.is_alive()]
        if dead_workers:
            logger.warning(f"Found {len(dead_workers)} dead health workers")
            # Could restart them here
        
        # Check other workers
        if self.replication_process and not self.replication_process.is_alive():
            logger.warning("Replication worker died")
        
        if self.log_collection_process and not self.log_collection_process.is_alive():
            logger.warning("Log collection worker died")
        
        dead_pin_workers = [w for w in self.pin_index_workers if not w.is_alive()]
        if dead_pin_workers:
            logger.warning(f"Found {len(dead_pin_workers)} dead pin workers")
    
    async def _cleanup(self):
        """Enhanced cleanup with worker process management."""
        logger.info("🧹 Cleaning up enhanced daemon resources...")
        
        # Signal all workers to stop
        self.stop_event.set()
        
        # Send poison pills to pin workers
        for _ in self.pin_index_workers:
            self.pin_work_queue.put(None)
        
        # Wait for workers to finish
        timeout = 10
        
        # Wait for health workers
        for worker in self.health_workers:
            worker.join(timeout=timeout)
            if worker.is_alive():
                logger.warning(f"Force terminating health worker {worker.name}")
                worker.terminate()
        
        # Wait for other workers
        if self.replication_process:
            self.replication_process.join(timeout=timeout)
            if self.replication_process.is_alive():
                self.replication_process.terminate()
        
        if self.log_collection_process:
            self.log_collection_process.join(timeout=timeout)
            if self.log_collection_process.is_alive():
                self.log_collection_process.terminate()
        
        for worker in self.pin_index_workers:
            worker.join(timeout=timeout)
            if worker.is_alive():
                logger.warning(f"Force terminating pin worker {worker.name}")
                worker.terminate()
        
        # Shutdown thread pools
        self.api_thread_pool.shutdown(wait=True)
        
        # Remove PID file
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
        except Exception as e:
            logger.error(f"Error removing PID file: {e}")
        
        logger.info("✅ Enhanced daemon cleanup complete")
    
    # Enhanced API methods with multiprocessing support
    
    def get_status(self) -> Dict[str, Any]:
        """Get enhanced daemon status with worker information."""
        return {
            "daemon": dict(self.daemon_status),
            "backends": dict(self.backend_status),
            "replication": dict(self.replication_status),
            "workers": {
                "health_workers": [w.name for w in self.health_workers if w.is_alive()],
                "other_workers": {
                    "replication": self.replication_process.is_alive() if self.replication_process else False,
                    "log_collection": self.log_collection_process.is_alive() if self.log_collection_process else False,
                    "pin_workers": [w.name for w in self.pin_index_workers if w.is_alive()]
                }
            },
            "performance": self.stats.to_dict(),
            "config": self.config
        }
    
    def get_backend_health(self, backend_name: Optional[str] = None) -> Dict[str, Any]:
        """Get backend health status from shared memory."""
        if backend_name:
            return dict(self.backend_status.get(backend_name, {}))
        return dict(self.backend_status)


def main():
    """Main entry point for the enhanced daemon."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced IPFS-Kit Daemon with Multiprocessing")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--stop", action="store_true", help="Stop running daemon")
    parser.add_argument("--status", action="store_true", help="Show daemon status")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--workers", type=int, help="Override number of worker processes")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.stop:
        # Stop daemon
        pid_file = "/tmp/enhanced_ipfs_kit_daemon.pid"
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped enhanced daemon (PID {pid})")
        except FileNotFoundError:
            print("No enhanced daemon running")
        except Exception as e:
            print(f"Error stopping enhanced daemon: {e}")
        return
    
    if args.status:
        # Show status
        pid_file = "/tmp/enhanced_ipfs_kit_daemon.pid"
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            if psutil.pid_exists(pid):
                print(f"Enhanced daemon running (PID {pid})")
                # Could show worker stats here
            else:
                print("Enhanced daemon not running (stale PID file)")
        except FileNotFoundError:
            print("Enhanced daemon not running")
        except Exception as e:
            print(f"Error checking enhanced daemon status: {e}")
        return
    
    # Start enhanced daemon
    daemon = EnhancedIPFSKitDaemon(config_file=args.config)
    
    # Override worker count if specified
    if args.workers:
        daemon.config['daemon']['workers']['health_workers'] = args.workers
        daemon.config['daemon']['workers']['pin_index_workers'] = max(1, args.workers // 2)
    
    if args.daemon:
        print("Enhanced daemon mode not implemented yet, running in foreground")
    
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        print("\nEnhanced daemon stopped by user")
    except Exception as e:
        print(f"Enhanced daemon failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
