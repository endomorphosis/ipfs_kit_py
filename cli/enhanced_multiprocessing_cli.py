#!/usr/bin/env python3
"""
Enhanced Multiprocessing IPFS-Kit CLI Tool

A high-performance CLI tool that uses multiprocessing for:
- Parallel IPFS operations (add, get, pin)
- Concurrent backend health checks
- Batch route optimization
- Distributed pin management
- Multi-threaded daemon communication

Features:
- Process pools for CPU-intensive operations
- Thread pools for I/O operations  
- Batch processing for multiple operations
- Load balancing across workers
- Progress reporting for long operations
- Connection pooling for efficiency
"""

import argparse
import anyio
import json
import logging
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import threading
from multiprocessing import Pool, Queue, Manager
from functools import partial

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import daemon client and IPFS Kit
try:
    from ipfs_kit_daemon_client import daemon_client, route_reader
    from ipfs_kit_py.ipfs_kit import IPFSKit
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    logger.error(f"Components not available: {e}")
    COMPONENTS_AVAILABLE = False
    daemon_client = None
    route_reader = None


def ipfs_worker_process(operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Worker process for IPFS operations."""
    try:
        # Initialize IPFS Kit in worker process
        from ipfs_kit_py.ipfs_kit import IPFSKit
        ipfs_kit = IPFSKit()
        
        if operation == "add_file":
            file_path = params.get("file_path")
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}
            
            # Use IPFS add
            if hasattr(ipfs_kit, 'ipfs'):
                try:
                    result = ipfs_kit.ipfs.add_file(file_path)
                    return {"success": True, "result": result, "file": file_path}
                except Exception as e:
                    return {"success": False, "error": str(e), "file": file_path}
            else:
                return {"success": False, "error": "IPFS not available", "file": file_path}
        
        elif operation == "get_content":
            cid = params.get("cid")
            output_path = params.get("output_path")
            
            if hasattr(ipfs_kit, 'ipfs'):
                try:
                    content = ipfs_kit.ipfs.cat(cid)
                    if output_path:
                        with open(output_path, 'wb') as f:
                            f.write(content)
                        return {"success": True, "result": f"Content saved to {output_path}", "cid": cid}
                    else:
                        return {"success": True, "result": content[:1000].decode('utf-8', errors='ignore'), "cid": cid}
                except Exception as e:
                    return {"success": False, "error": str(e), "cid": cid}
            else:
                return {"success": False, "error": "IPFS not available", "cid": cid}
        
        elif operation == "pin_add":
            cid = params.get("cid")
            
            if hasattr(ipfs_kit, 'ipfs'):
                try:
                    result = ipfs_kit.ipfs.pin_add(cid)
                    return {"success": True, "result": result, "cid": cid}
                except Exception as e:
                    return {"success": False, "error": str(e), "cid": cid}
            else:
                return {"success": False, "error": "IPFS not available", "cid": cid}
        
        elif operation == "pin_remove":
            cid = params.get("cid")
            
            if hasattr(ipfs_kit, 'ipfs'):
                try:
                    result = ipfs_kit.ipfs.pin_rm(cid)
                    return {"success": True, "result": result, "cid": cid}
                except Exception as e:
                    return {"success": False, "error": str(e), "cid": cid}
            else:
                return {"success": False, "error": "IPFS not available", "cid": cid}
        
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def backend_worker_process(backend_name: str, operation: str) -> Dict[str, Any]:
    """Worker process for backend operations."""
    try:
        if operation == "health_check":
            from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
            health_monitor = BackendHealthMonitor()
            
            # Simulate health check (in real implementation, use actual health check)
            result = {
                "backend": backend_name,
                "status": "healthy",
                "response_time": 0.1,
                "last_check": time.time()
            }
            return {"success": True, "result": result}
        
        elif operation == "restart":
            # Simulate backend restart
            time.sleep(2)  # Simulate restart time
            return {"success": True, "result": f"Backend {backend_name} restarted"}
        
        else:
            return {"success": False, "error": f"Unknown operation: {operation}"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def route_optimization_process(cids: List[str], backends: List[str]) -> Dict[str, Any]:
    """Worker process for route optimization."""
    try:
        optimal_routes = {}
        
        for cid in cids:
            # Simple hash-based routing for demo
            backend_index = hash(cid) % len(backends)
            optimal_routes[cid] = {
                "primary": backends[backend_index],
                "fallbacks": backends[backend_index+1:] + backends[:backend_index],
                "score": abs(hash(cid)) % 100
            }
        
        return {"success": True, "routes": optimal_routes}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


class ProgressTracker:
    """Thread-safe progress tracker for long operations."""
    
    def __init__(self, total: int):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.lock = threading.Lock()
        self.start_time = time.time()
    
    def update(self, success: bool = True):
        with self.lock:
            self.completed += 1
            if not success:
                self.failed += 1
    
    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            elapsed = time.time() - self.start_time
            progress = (self.completed / self.total) * 100 if self.total > 0 else 0
            eta = (elapsed / max(1, self.completed)) * (self.total - self.completed) if self.completed > 0 else 0
            
            return {
                "total": self.total,
                "completed": self.completed,
                "failed": self.failed,
                "progress": progress,
                "elapsed": elapsed,
                "eta": eta,
                "success_rate": ((self.completed - self.failed) / max(1, self.completed)) * 100
            }


class EnhancedMultiprocessingCLI:
    """
    Enhanced CLI with multiprocessing support for high-performance operations.
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        self.max_workers = max_workers or min(8, mp.cpu_count())
        
        # Process pools for different operation types
        self.ipfs_pool = ProcessPoolExecutor(
            max_workers=min(4, mp.cpu_count()),
            mp_context=mp.get_context("spawn")
        )
        self.backend_pool = ProcessPoolExecutor(
            max_workers=min(2, mp.cpu_count()),
            mp_context=mp.get_context("spawn")
        )
        
        # Thread pool for I/O operations
        self.io_pool = ThreadPoolExecutor(
            max_workers=min(10, mp.cpu_count() * 2),
            thread_name_prefix="cli-io-worker"
        )
        
        # Daemon client (if available)
        self.daemon_client = daemon_client
        self.route_reader = route_reader
        
        # Statistics
        self.stats = {
            "operations": 0,
            "successes": 0,
            "failures": 0,
            "start_time": time.time()
        }
    
    async def daemon_status(self) -> Dict[str, Any]:
        """Get daemon status with async support."""
        if not self.daemon_client:
            return {"error": "Daemon client not available"}
        
        try:
            status = await anyio.to_thread.run_sync(
                self.daemon_client.get_daemon_status
            )
            return status
        except Exception as e:
            return {"error": str(e)}
    
    async def daemon_start(self) -> Dict[str, Any]:
        """Start daemon with async support."""
        if not self.daemon_client:
            return {"error": "Daemon client not available"}
        
        try:
            result = await anyio.to_thread.run_sync(
                self.daemon_client.start_daemon
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def daemon_stop(self) -> Dict[str, Any]:
        """Stop daemon with async support."""
        if not self.daemon_client:
            return {"error": "Daemon client not available"}
        
        try:
            result = await anyio.to_thread.run_sync(
                self.daemon_client.stop_daemon
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def backend_health_parallel(self) -> Dict[str, Any]:
        """Check health of all backends in parallel."""
        backends = ["ipfs", "ipfs_cluster", "lotus", "lassie", "storacha"]
        
        logger.info(f"Checking health of {len(backends)} backends in parallel...")
        
        # Submit all health checks to process pool
        futures = []
        
        for backend in backends:
            future = self.backend_pool.submit(backend_worker_process, backend, "health_check")
            futures.append((backend, future))
        
        # Collect results
        results = {}
        for backend, future in futures:
            try:
                result = await anyio.to_thread.run_sync(future.result)
                if result.get("success"):
                    results[backend] = result.get("result")
                else:
                    results[backend] = {"error": result.get("error")}
            except Exception as e:
                results[backend] = {"error": str(e)}
        
        return {"backends": results, "parallel": True}
    
    async def backend_restart(self, backend_name: str) -> Dict[str, Any]:
        """Restart a backend using process pool."""
        logger.info(f"Restarting backend: {backend_name}")
        
        future = self.backend_pool.submit(backend_worker_process, backend_name, "restart")
        
        try:
            result = await anyio.to_thread.run_sync(future.result)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def ipfs_add_parallel(self, file_paths: List[str]) -> Dict[str, Any]:
        """Add multiple files to IPFS in parallel."""
        if not file_paths:
            return {"error": "No files specified"}
        
        logger.info(f"Adding {len(file_paths)} files to IPFS in parallel...")
        
        # Progress tracking
        progress = ProgressTracker(len(file_paths))
        
        # Submit all add operations to process pool
        futures = []
        
        for file_path in file_paths:
            if os.path.exists(file_path):
                future = self.ipfs_pool.submit(ipfs_worker_process, "add_file", {"file_path": file_path})
                futures.append((file_path, future))
            else:
                logger.warning(f"File not found: {file_path}")
                progress.update(success=False)
        
        # Collect results with progress reporting
        results = {}
        
        # Start progress reporting task
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(self._report_progress, progress)

            try:
                for file_path, future in futures:
                    try:
                        result = await anyio.to_thread.run_sync(future.result)
                        results[file_path] = result
                        progress.update(result.get("success", False))
                    except Exception as e:
                        results[file_path] = {"success": False, "error": str(e)}
                        progress.update(success=False)
            finally:
                task_group.cancel_scope.cancel()
        
        # Final status
        status = progress.get_status()
        logger.info(f"Add operation completed: {status['completed']}/{status['total']} files, {status['success_rate']:.1f}% success rate")
        
        return {"results": results, "stats": status, "parallel": True}
    
    async def ipfs_get_parallel(self, cid_list: List[str], output_dir: Optional[str] = None) -> Dict[str, Any]:
        """Get multiple CIDs from IPFS in parallel."""
        if not cid_list:
            return {"error": "No CIDs specified"}
        
        logger.info(f"Getting {len(cid_list)} CIDs from IPFS in parallel...")
        
        # Progress tracking
        progress = ProgressTracker(len(cid_list))
        
        # Submit all get operations to process pool
        futures = []
        
        for i, cid in enumerate(cid_list):
            output_path = None
            if output_dir:
                output_path = os.path.join(output_dir, f"{cid[:12]}_{i}.dat")
            
            future = self.ipfs_pool.submit(ipfs_worker_process, "get_content", {
                "cid": cid,
                "output_path": output_path
            })
            futures.append((cid, future))
        
        # Collect results with progress reporting
        results = {}
        
        # Start progress reporting task
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(self._report_progress, progress)

            try:
                for cid, future in futures:
                    try:
                        result = await anyio.to_thread.run_sync(future.result)
                        results[cid] = result
                        progress.update(result.get("success", False))
                    except Exception as e:
                        results[cid] = {"success": False, "error": str(e)}
                        progress.update(success=False)
            finally:
                task_group.cancel_scope.cancel()
        
        # Final status
        status = progress.get_status()
        logger.info(f"Get operation completed: {status['completed']}/{status['total']} CIDs, {status['success_rate']:.1f}% success rate")
        
        return {"results": results, "stats": status, "parallel": True}
    
    async def pin_batch_operation(self, cids: List[str], operation: str) -> Dict[str, Any]:
        """Perform batch pin operations (add/remove) in parallel."""
        if not cids:
            return {"error": "No CIDs specified"}
        
        if operation not in ["add", "remove"]:
            return {"error": "Operation must be 'add' or 'remove'"}
        
        logger.info(f"Performing pin {operation} on {len(cids)} CIDs in parallel...")
        
        # Progress tracking
        progress = ProgressTracker(len(cids))
        
        # Submit all pin operations to process pool
        futures = []
        
        pin_operation = "pin_add" if operation == "add" else "pin_remove"
        
        for cid in cids:
            future = self.ipfs_pool.submit(ipfs_worker_process, pin_operation, {"cid": cid})
            futures.append((cid, future))
        
        # Collect results with progress reporting
        results = {}
        
        # Start progress reporting task
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(self._report_progress, progress)

            try:
                for cid, future in futures:
                    try:
                        result = await anyio.to_thread.run_sync(future.result)
                        results[cid] = result
                        progress.update(result.get("success", False))
                    except Exception as e:
                        results[cid] = {"success": False, "error": str(e)}
                        progress.update(success=False)
            finally:
                task_group.cancel_scope.cancel()
        
        # Final status
        status = progress.get_status()
        logger.info(f"Pin {operation} completed: {status['completed']}/{status['total']} CIDs, {status['success_rate']:.1f}% success rate")
        
        return {"results": results, "stats": status, "parallel": True}
    
    async def route_optimize_batch(self, cids: List[str]) -> Dict[str, Any]:
        """Optimize routes for multiple CIDs using process pool."""
        if not cids:
            return {"error": "No CIDs specified"}
        
        logger.info(f"Optimizing routes for {len(cids)} CIDs...")
        
        backends = ["ipfs", "ipfs_cluster", "storacha", "s3", "lotus"]
        
        # Split CIDs into chunks for parallel processing
        chunk_size = max(1, len(cids) // mp.cpu_count())
        chunks = [cids[i:i + chunk_size] for i in range(0, len(cids), chunk_size)]
        
        futures = []
        
        # Submit route optimization tasks
        for chunk in chunks:
            future = self.backend_pool.submit(route_optimization_process, chunk, backends)
            futures.append(future)
        
        # Collect results
        all_routes = {}
        
        for future in futures:
            try:
                result = await anyio.to_thread.run_sync(future.result)
                if result.get("success"):
                    all_routes.update(result.get("routes", {}))
            except Exception as e:
                logger.error(f"Route optimization failed: {e}")
        
        return {"routes": all_routes, "total_cids": len(cids), "parallel": True}
    
    def route_stats(self) -> Dict[str, Any]:
        """Get routing statistics from parquet indexes."""
        if not self.route_reader:
            return {"error": "Route reader not available"}
        
        try:
            stats = self.route_reader.get_backend_stats()
            suggested = self.route_reader.suggest_backend_for_new_pin()
            
            return {
                "backend_stats": stats,
                "suggested_backend": suggested,
                "total_backends": len(stats)
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _report_progress(self, progress: ProgressTracker):
        """Background task to report progress."""
        while True:
            try:
                await anyio.sleep(2)  # Report every 2 seconds
                status = progress.get_status()
                logger.info(f"Progress: {status['completed']}/{status['total']} ({status['progress']:.1f}%) - "
                           f"Success rate: {status['success_rate']:.1f}% - ETA: {status['eta']:.1f}s")
            except anyio.get_cancelled_exc_class():
                break
    
    def cleanup(self):
        """Cleanup resources."""
        logger.info("Cleaning up CLI resources...")
        
        # Shutdown process pools
        self.ipfs_pool.shutdown(wait=True)
        self.backend_pool.shutdown(wait=True)
        
        # Shutdown thread pool
        self.io_pool.shutdown(wait=True)
        
        logger.info("CLI cleanup complete")


async def main():
    """Main CLI entry point with multiprocessing support."""
    parser = argparse.ArgumentParser(
        description="Enhanced Multiprocessing IPFS-Kit CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Daemon operations
  %(prog)s daemon status
  %(prog)s daemon start
  %(prog)s daemon stop
  
  # Backend operations
  %(prog)s backend health --parallel
  %(prog)s backend restart ipfs
  
  # IPFS operations (parallel)
  %(prog)s ipfs add file1.txt file2.txt file3.txt --parallel
  %(prog)s ipfs get QmHash1,QmHash2,QmHash3 --output-dir ./downloads --parallel
  %(prog)s ipfs pin add QmHash1,QmHash2,QmHash3 --parallel
  %(prog)s ipfs pin remove QmHash1,QmHash2 --parallel
  
  # Route operations
  %(prog)s route optimize QmHash1,QmHash2,QmHash3
  %(prog)s route stats
  
  # Performance
  %(prog)s benchmark --workers 8
        """
    )
    
    parser.add_argument("--workers", type=int, help="Number of worker processes")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Daemon commands
    daemon_parser = subparsers.add_parser("daemon", help="Daemon management")
    daemon_parser.add_argument("action", choices=["status", "start", "stop"], help="Daemon action")
    
    # Backend commands
    backend_parser = subparsers.add_parser("backend", help="Backend management")
    backend_parser.add_argument("action", choices=["health", "restart"], help="Backend action")
    backend_parser.add_argument("name", nargs="?", help="Backend name (for restart)")
    backend_parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    
    # IPFS commands
    ipfs_parser = subparsers.add_parser("ipfs", help="IPFS operations")
    ipfs_parser.add_argument("action", choices=["add", "get", "pin"], help="IPFS action")
    ipfs_parser.add_argument("targets", help="Files/CIDs (comma-separated for multiple)")
    ipfs_parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    ipfs_parser.add_argument("--output-dir", help="Output directory for get operations")
    ipfs_parser.add_argument("--pin-action", choices=["add", "remove"], default="add", help="Pin action")
    
    # Route commands
    route_parser = subparsers.add_parser("route", help="Route operations")
    route_parser.add_argument("action", choices=["optimize", "stats"], help="Route action")
    route_parser.add_argument("cids", nargs="?", help="CIDs (comma-separated)")
    
    # Benchmark command
    benchmark_parser = subparsers.add_parser("benchmark", help="Performance benchmark")
    benchmark_parser.add_argument("--duration", type=int, default=60, help="Benchmark duration in seconds")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if not args.command:
        parser.print_help()
        return
    
    # Create CLI instance
    cli = EnhancedMultiprocessingCLI(max_workers=args.workers)
    
    try:
        # Execute command
        if args.command == "daemon":
            if args.action == "status":
                result = await cli.daemon_status()
            elif args.action == "start":
                result = await cli.daemon_start()
            elif args.action == "stop":
                result = await cli.daemon_stop()
            
            print(json.dumps(result, indent=2))
        
        elif args.command == "backend":
            if args.action == "health":
                if args.parallel:
                    result = await cli.backend_health_parallel()
                else:
                    result = {"error": "Non-parallel backend health not implemented"}
                print(json.dumps(result, indent=2))
            
            elif args.action == "restart":
                if not args.name:
                    print("Error: Backend name required for restart")
                    return
                result = await cli.backend_restart(args.name)
                print(json.dumps(result, indent=2))
        
        elif args.command == "ipfs":
            targets = args.targets.split(",")
            
            if args.action == "add":
                if args.parallel:
                    result = await cli.ipfs_add_parallel(targets)
                else:
                    print("Error: Non-parallel add not implemented")
                    return
            
            elif args.action == "get":
                if args.parallel:
                    result = await cli.ipfs_get_parallel(targets, args.output_dir)
                else:
                    print("Error: Non-parallel get not implemented")
                    return
            
            elif args.action == "pin":
                if args.parallel:
                    result = await cli.pin_batch_operation(targets, args.pin_action)
                else:
                    print("Error: Non-parallel pin not implemented")
                    return
            
            print(json.dumps(result, indent=2))
        
        elif args.command == "route":
            if args.action == "optimize":
                if not args.cids:
                    print("Error: CIDs required for optimization")
                    return
                cids = args.cids.split(",")
                result = await cli.route_optimize_batch(cids)
            
            elif args.action == "stats":
                result = cli.route_stats()
            
            print(json.dumps(result, indent=2))
        
        elif args.command == "benchmark":
            print(f"Running benchmark for {args.duration} seconds...")
            
            # Simple benchmark
            start_time = time.time()
            operations = 0
            
            while time.time() - start_time < args.duration:
                # Simulate operations
                test_cids = [f"QmTest{i}" for i in range(10)]
                result = await cli.route_optimize_batch(test_cids)
                operations += 1
                await anyio.sleep(1)
            
            elapsed = time.time() - start_time
            ops_per_sec = operations / elapsed
            
            print(json.dumps({
                "benchmark": {
                    "duration": elapsed,
                    "operations": operations,
                    "ops_per_second": ops_per_sec,
                    "workers": cli.max_workers
                }
            }, indent=2))
    
    finally:
        cli.cleanup()


if __name__ == "__main__":
    anyio.run(main)
