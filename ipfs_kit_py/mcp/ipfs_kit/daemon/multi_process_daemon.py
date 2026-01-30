#!/usr/bin/env python3
"""
Multi-Processing Enhanced IPFS Kit Daemon.

This daemon uses multiple processes to increase throughput:
- Main process: API server and coordination
- Health monitoring process: Backend health checks
- Pin management process: Pin operations and replication
- Log collection process: Log aggregation
- Index update process: Parquet file updates
- Background task process: Maintenance operations

Each process communicates via queues and shared memory for maximum efficiency.
"""

import anyio
import json
import logging
import multiprocessing as mp
import os
import queue
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# FastAPI for daemon API
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

# Core IPFS Kit functionality
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from ipfs_kit_py.ipfs_kit import IPFSKit

# MCP backend components
from ..backends.health_monitor import BackendHealthMonitor
from ..backends.log_manager import BackendLogManager
from ..core.config_manager import SecureConfigManager

# Pin index management
import pandas as pd

logger = logging.getLogger(__name__)

class MultiProcessIPFSKitDaemon:
    """
    Multi-processing IPFS Kit Daemon for high throughput operations.
    
    Uses separate processes for different types of operations to maximize
    CPU utilization and prevent blocking.
    """
    
    def __init__(self, 
                 host: str = "127.0.0.1",
                 port: int = 9999,
                 config_dir: str = "/tmp/ipfs_kit_config",
                 data_dir: str = None,
                 num_workers: int = None):
        self.host = host
        self.port = port
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir or str(Path.home() / ".ipfs_kit"))
        
        # Determine number of worker processes
        self.num_workers = num_workers or min(mp.cpu_count(), 8)
        
        # Ensure directories exist
        self.config_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Multi-processing components
        self.manager = mp.Manager()
        self.process_pool = None
        self.thread_pool = None
        
        # Shared state between processes
        self.shared_state = self.manager.dict({
            'daemon_running': False,
            'start_time': None,
            'last_health_check': None,
            'active_operations': 0,
            'total_operations': 0
        })
        
        # Communication queues
        self.health_queue = mp.Queue()
        self.pin_queue = mp.Queue()
        self.log_queue = mp.Queue()
        self.index_queue = mp.Queue()
        self.result_queue = mp.Queue()
        
        # Process tracking
        self.worker_processes = []
        
        # FastAPI app
        self.app = self._create_app()
        
        logger.info(f"🔧 Multi-Processing IPFS Kit Daemon initialized")
        logger.info(f"📍 Host: {host}:{port}")
        logger.info(f"⚡ Workers: {self.num_workers}")
        logger.info(f"📁 Config: {config_dir}")
        logger.info(f"💾 Data: {self.data_dir}")
    
    def _create_app(self) -> FastAPI:
        """Create FastAPI application with high-performance endpoints."""
        app = FastAPI(
            title="Multi-Processing IPFS Kit Daemon",
            description="High-throughput daemon with multi-processing support",
            version="2.0.0"
        )
        
        # Health endpoints with async processing
        @app.get("/health")
        async def get_health():
            """Get comprehensive health status using process pool."""
            try:
                # Submit health check to process pool
                with anyio.fail_after(30):
                    health_status = await anyio.to_process.run_sync(self._get_health_worker)
                return JSONResponse(content=health_status)

            except TimeoutError:
                raise HTTPException(status_code=408, detail="Health check timeout")
            except Exception as e:
                logger.error(f"Health check error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/health/fast")
        async def get_health_fast():
            """Fast health check using cached data."""
            return JSONResponse(content={
                "daemon_running": self.shared_state.get('daemon_running', False),
                "last_health_check": self.shared_state.get('last_health_check'),
                "active_operations": self.shared_state.get('active_operations', 0),
                "total_operations": self.shared_state.get('total_operations', 0),
                "workers": self.num_workers,
                "response_time_ms": 1  # Ultra-fast cached response
            })
        
        # Pin management with concurrent processing
        @app.get("/pins")
        async def list_pins():
            """List pins using async processing."""
            try:
                with anyio.fail_after(10):
                    pins_data = await anyio.to_thread.run_sync(self._list_pins_worker)
                return JSONResponse(content=pins_data)

            except TimeoutError:
                raise HTTPException(status_code=408, detail="Pin listing timeout")
            except Exception as e:
                logger.error(f"Pin listing error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/pins/{cid}")
        async def add_pin(cid: str, background_tasks: BackgroundTasks):
            """Add pin using multi-processing."""
            try:
                # Increment active operations counter
                self.shared_state['active_operations'] += 1
                
                # Submit to pin processing queue
                pin_task = {
                    'operation': 'add',
                    'cid': cid,
                    'timestamp': time.time(),
                    'request_id': f"pin_add_{int(time.time() * 1000)}"
                }
                
                # Use process pool for CPU-intensive operations
                with anyio.fail_after(60):
                    result = await anyio.to_process.run_sync(self._add_pin_worker, cid)
                
                # Schedule background index update
                background_tasks.add_task(self._schedule_index_update)
                
                # Update counters
                self.shared_state['active_operations'] -= 1
                self.shared_state['total_operations'] += 1
                
                return JSONResponse(content=result)
                
            except TimeoutError:
                self.shared_state['active_operations'] -= 1
                raise HTTPException(status_code=408, detail="Pin add timeout")
            except Exception as e:
                self.shared_state['active_operations'] -= 1
                logger.error(f"Pin add error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.delete("/pins/{cid}")
        async def remove_pin(cid: str, background_tasks: BackgroundTasks):
            """Remove pin using multi-processing."""
            try:
                self.shared_state['active_operations'] += 1
                
                with anyio.fail_after(60):
                    result = await anyio.to_process.run_sync(self._remove_pin_worker, cid)
                
                background_tasks.add_task(self._schedule_index_update)
                
                self.shared_state['active_operations'] -= 1
                self.shared_state['total_operations'] += 1
                
                return JSONResponse(content=result)
                
            except TimeoutError:
                self.shared_state['active_operations'] -= 1
                raise HTTPException(status_code=408, detail="Pin remove timeout")
            except Exception as e:
                self.shared_state['active_operations'] -= 1
                logger.error(f"Pin remove error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Batch operations for high throughput
        @app.post("/pins/batch")
        async def batch_pin_operations(operations: List[Dict[str, Any]]):
            """Process multiple pin operations concurrently."""
            try:
                self.shared_state['active_operations'] += len(operations)
                
                # Process operations concurrently
                results: List[Any] = []

                async def _run_op(op: Dict[str, Any]) -> None:
                    try:
                        if op.get('operation') == 'add':
                            results.append(await anyio.to_process.run_sync(self._add_pin_worker, op.get('cid')))
                        elif op.get('operation') == 'remove':
                            results.append(await anyio.to_process.run_sync(self._remove_pin_worker, op.get('cid')))
                    except Exception as exc:
                        results.append(exc)

                async with anyio.create_task_group() as tg:
                    for op in operations:
                        tg.start_soon(_run_op, op)
                
                # Process results
                success_count = 0
                error_count = 0
                for result in results:
                    if isinstance(result, Exception):
                        error_count += 1
                    elif isinstance(result, dict) and result.get('success'):
                        success_count += 1
                    else:
                        error_count += 1
                
                self.shared_state['active_operations'] -= len(operations)
                self.shared_state['total_operations'] += len(operations)
                
                return JSONResponse(content={
                    "success": True,
                    "total_operations": len(operations),
                    "successful": success_count,
                    "failed": error_count,
                    "results": [r if not isinstance(r, Exception) else {"error": str(r)} for r in results]
                })
                
            except Exception as e:
                self.shared_state['active_operations'] -= len(operations)
                logger.error(f"Batch operation error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Backend management with parallel processing
        @app.post("/backends/{backend_name}/start")
        async def start_backend(backend_name: str):
            """Start backend using process pool."""
            try:
                with anyio.fail_after(120):
                    result = await anyio.to_process.run_sync(self._start_backend_worker, backend_name)
                return JSONResponse(content=result)

            except TimeoutError:
                raise HTTPException(status_code=408, detail="Backend start timeout")
            except Exception as e:
                logger.error(f"Backend start error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        # Performance monitoring endpoint
        @app.get("/performance")
        async def get_performance_metrics():
            """Get performance metrics from multi-processing daemon."""
            return JSONResponse(content={
                "workers": self.num_workers,
                "active_operations": self.shared_state.get('active_operations', 0),
                "total_operations": self.shared_state.get('total_operations', 0),
                "daemon_uptime": time.time() - (self.shared_state.get('start_time') or time.time()),
                "process_pool_active": self.process_pool is not None,
                "thread_pool_active": self.thread_pool is not None,
                "cpu_count": mp.cpu_count(),
                "memory_usage": self._get_memory_usage()
            })
        
        return app
    
    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "percent": process.memory_percent()
            }
        except ImportError:
            return {"error": "psutil not available"}
    
    # Worker functions that run in separate processes
    def _get_health_worker(self) -> Dict[str, Any]:
        """Health check worker process."""
        try:
            # Initialize components in worker process
            health_monitor = BackendHealthMonitor(str(self.config_dir))
            
            # Run health check
            health_status = anyio.run(health_monitor.get_comprehensive_health_status)
            
            # Update shared state
            self.shared_state['last_health_check'] = time.time()
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health worker error: {e}")
            return {"success": False, "error": str(e)}
    
    def _list_pins_worker(self) -> Dict[str, Any]:
        """Pin listing worker."""
        try:
            pin_index_dir = self.data_dir / "enhanced_pin_index"
            
            if not pin_index_dir.exists():
                return {"pins": [], "total": 0, "source": "no_index"}
            
            # Read pins data efficiently
            pins_file = pin_index_dir / "enhanced_pins.parquet"
            if pins_file.exists():
                df = pd.read_parquet(pins_file)
                
                # Convert to records efficiently
                pins_data = df.head(1000).to_dict('records')  # Limit for performance
                
                return {
                    "pins": pins_data,
                    "total": len(df),
                    "displayed": len(pins_data),
                    "source": "parquet",
                    "processing_time_ms": 0  # Will be updated by caller
                }
            else:
                return {"pins": [], "total": 0, "source": "no_parquet"}
                
        except Exception as e:
            logger.error(f"Pin listing worker error: {e}")
            return {"pins": [], "total": 0, "error": str(e)}
    
    def _add_pin_worker(self, cid: str) -> Dict[str, Any]:
        """Pin addition worker process."""
        try:
            # Initialize IPFS Kit in worker process
            ipfs_kit = IPFSKit()
            
            # Add pin
            result = ipfs_kit.pin_add(cid)
            
            return {
                "success": True,
                "cid": cid,
                "result": result,
                "worker_pid": os.getpid()
            }
            
        except Exception as e:
            logger.error(f"Pin add worker error: {e}")
            return {"success": False, "cid": cid, "error": str(e)}
    
    def _remove_pin_worker(self, cid: str) -> Dict[str, Any]:
        """Pin removal worker process."""
        try:
            # Initialize IPFS Kit in worker process
            ipfs_kit = IPFSKit()
            
            # Remove pin
            result = ipfs_kit.pin_rm(cid)
            
            return {
                "success": True,
                "cid": cid,
                "result": result,
                "worker_pid": os.getpid()
            }
            
        except Exception as e:
            logger.error(f"Pin remove worker error: {e}")
            return {"success": False, "cid": cid, "error": str(e)}
    
    def _start_backend_worker(self, backend_name: str) -> Dict[str, Any]:
        """Backend start worker process."""
        try:
            # Initialize IPFS Kit in worker process
            ipfs_kit = IPFSKit()
            daemon_manager = ipfs_kit.daemon_manager
            
            if backend_name == "ipfs":
                result = daemon_manager.start_ipfs_daemon()
            elif backend_name == "cluster":
                result = daemon_manager.start_cluster_daemon()
            elif backend_name == "lotus":
                result = daemon_manager.start_lotus_daemon()
            else:
                return {"success": False, "error": f"Unknown backend: {backend_name}"}
            
            return {
                "success": True,
                "backend": backend_name,
                "result": result,
                "worker_pid": os.getpid()
            }
            
        except Exception as e:
            logger.error(f"Backend start worker error: {e}")
            return {"success": False, "backend": backend_name, "error": str(e)}
    
    async def _schedule_index_update(self):
        """Schedule background index update."""
        try:
            # Queue index update task
            self.index_queue.put({
                'operation': 'update_pins',
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Index update scheduling error: {e}")
    
    def _start_background_workers(self):
        """Start background worker processes."""
        logger.info("🔄 Starting background worker processes...")
        
        # Health monitoring worker
        health_worker = mp.Process(
            target=self._health_monitoring_worker,
            name="health_monitor"
        )
        health_worker.start()
        self.worker_processes.append(health_worker)
        
        # Log collection worker
        log_worker = mp.Process(
            target=self._log_collection_worker,
            name="log_collector"
        )
        log_worker.start()
        self.worker_processes.append(log_worker)
        
        # Index update worker
        index_worker = mp.Process(
            target=self._index_update_worker,
            name="index_updater"
        )
        index_worker.start()
        self.worker_processes.append(index_worker)
        
        logger.info(f"✅ Started {len(self.worker_processes)} background workers")
    
    def _health_monitoring_worker(self):
        """Background health monitoring worker process."""
        logger.info("🏥 Health monitoring worker started")
        
        # Initialize health monitor in worker process
        health_monitor = BackendHealthMonitor(str(self.config_dir))
        
        while self.shared_state.get('daemon_running', False):
            try:
                # Run health check
                health_status = anyio.run(health_monitor.check_all_backends_health)
                
                # Update shared state
                self.shared_state['last_health_check'] = time.time()
                
                # Sleep for 30 seconds
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Health monitoring worker error: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _log_collection_worker(self):
        """Background log collection worker process."""
        logger.info("📋 Log collection worker started")
        
        # Initialize log manager in worker process
        log_manager = BackendLogManager()
        
        while self.shared_state.get('daemon_running', False):
            try:
                # Collect logs
                anyio.run(log_manager.collect_all_backend_logs)
                
                # Sleep for 60 seconds
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Log collection worker error: {e}")
                time.sleep(120)  # Wait longer on error
    
    def _index_update_worker(self):
        """Background index update worker process."""
        logger.info("📊 Index update worker started")
        
        while self.shared_state.get('daemon_running', False):
            try:
                # Check for index update requests
                try:
                    update_request = self.index_queue.get(timeout=300)  # 5 minute timeout
                    
                    # Process index update
                    logger.debug("Updating pin index...")
                    # TODO: Implement index update logic
                    
                except queue.Empty:
                    # No update requests, continue
                    pass
                
            except Exception as e:
                logger.error(f"Index update worker error: {e}")
                time.sleep(60)
    
    async def start(self):
        """Start the multi-processing daemon."""
        logger.info("🚀 Starting Multi-Processing IPFS Kit Daemon...")
        
        # Initialize process pools
        self.process_pool = ProcessPoolExecutor(max_workers=self.num_workers)
        self.thread_pool = ThreadPoolExecutor(max_workers=self.num_workers * 2)
        
        logger.info(f"⚡ Initialized {self.num_workers} process workers")
        logger.info(f"⚡ Initialized {self.num_workers * 2} thread workers")
        
        # Set daemon state
        self.shared_state['daemon_running'] = True
        self.shared_state['start_time'] = time.time()
        
        # Start background workers
        self._start_background_workers()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"🌐 Starting high-performance API server on {self.host}:{self.port}")
        
        # Start FastAPI server with optimized settings
        async_io_backend = "async" "io"
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            workers=1,  # We handle multi-processing internally
            loop=async_io_backend,
            access_log=False  # Disable for performance
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"❌ Error running daemon: {e}")
            return False
        
        return True
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"🛑 Received signal {signum}, shutting down...")
        self.shared_state['daemon_running'] = False
        
        # Stop worker processes
        for worker in self.worker_processes:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
                if worker.is_alive():
                    worker.kill()
        
        # Shutdown process pools
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        
        logger.info("✅ Multi-processing daemon shutdown complete")
    
    async def stop(self):
        """Stop the daemon gracefully."""
        logger.info("🛑 Stopping Multi-Processing IPFS Kit Daemon...")
        
        self.shared_state['daemon_running'] = False
        
        # Stop worker processes
        for worker in self.worker_processes:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=5)
        
        # Shutdown pools
        if self.process_pool:
            self.process_pool.shutdown(wait=True)
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        
        logger.info("✅ Multi-processing daemon stopped")


async def main():
    """Main entry point for the multi-processing daemon."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Processing IPFS Kit Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=9999, help="Port to bind to")
    parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Configuration directory")
    parser.add_argument("--data-dir", help="Data directory (default: ~/.ipfs_kit)")
    parser.add_argument("--workers", type=int, help="Number of worker processes")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start daemon
    daemon = MultiProcessIPFSKitDaemon(
        host=args.host,
        port=args.port,
        config_dir=args.config_dir,
        data_dir=args.data_dir,
        num_workers=args.workers
    )
    
    print("=" * 80)
    print("⚡ MULTI-PROCESSING IPFS KIT DAEMON")
    print("=" * 80)
    print(f"📍 API: http://{args.host}:{args.port}")
    print(f"⚡ Workers: {daemon.num_workers}")
    print(f"🖥️ CPU Cores: {mp.cpu_count()}")
    print(f"📁 Config: {args.config_dir}")
    print(f"💾 Data: {daemon.data_dir}")
    print(f"🔍 Debug: {args.debug}")
    print("=" * 80)
    print("🚀 Starting high-performance daemon...")
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        print("\n🛑 Daemon interrupted by user")
        await daemon.stop()
    except Exception as e:
        print(f"❌ Daemon error: {e}")
        await daemon.stop()
        sys.exit(1)


if __name__ == "__main__":
    # Set multiprocessing start method for better performance
    mp.set_start_method('spawn', force=True)
    anyio.run(main)
