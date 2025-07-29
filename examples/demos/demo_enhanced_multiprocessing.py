#!/usr/bin/env python3
"""
Enhanced Multiprocessing Demo

This script demonstrates the multiprocessing capabilities of the enhanced
IPFS-Kit architecture with performance comparisons between single-threaded
and multiprocessing approaches.
"""

import asyncio
import json
import logging
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def create_test_files(count: int = 20) -> List[str]:
    """Create test files for multiprocessing demo."""
    test_files = []
    temp_dir = Path("/tmp/ipfs_kit_mp_test")
    temp_dir.mkdir(exist_ok=True)
    
    for i in range(count):
        file_path = temp_dir / f"test_file_{i}.txt"
        with open(file_path, 'w') as f:
            # Create files with varying sizes
            size = random.randint(100, 10000)
            content = f"Test file {i}\n" + "x" * size
            f.write(content)
        test_files.append(str(file_path))
    
    return test_files


async def demo_enhanced_daemon():
    """Demo the enhanced multiprocessing daemon."""
    print("\n🚀 Enhanced Multiprocessing Daemon Demo")
    print("=" * 60)
    
    try:
        # Import enhanced daemon
        from enhanced_multiprocessing_daemon import EnhancedIPFSKitDaemon
        
        print("✅ Enhanced daemon imported successfully")
        
        # Create daemon instance (but don't start it for demo)
        daemon = EnhancedIPFSKitDaemon()
        
        print(f"✅ Daemon configured with {daemon.cpu_count} CPU cores")
        print(f"   Health workers: {daemon.config['daemon']['workers']['health_workers']}")
        print(f"   Pin index workers: {daemon.config['daemon']['workers']['pin_index_workers']}")
        print(f"   API workers: {daemon.config['daemon']['workers']['api_workers']}")
        
        # Show configuration benefits
        print("\n📊 Multiprocessing Benefits:")
        print(f"   ✅ Parallel health monitoring across {daemon.config['daemon']['workers']['health_workers']} processes")
        print(f"   ✅ Distributed pin index updates with {daemon.config['daemon']['workers']['pin_index_workers']} workers")
        print(f"   ✅ Load-balanced API handling with {daemon.config['daemon']['workers']['api_workers']} threads")
        print(f"   ✅ Shared memory for inter-process communication")
        
    except Exception as e:
        print(f"❌ Error testing enhanced daemon: {e}")


async def demo_enhanced_mcp_server():
    """Demo the enhanced multiprocessing MCP server."""
    print("\n🌐 Enhanced Multiprocessing MCP Server Demo")
    print("=" * 60)
    
    try:
        # Import enhanced server
        from enhanced_multiprocessing_mcp_server import EnhancedMultiprocessingMCPServer
        
        print("✅ Enhanced MCP server imported successfully")
        
        # Create server instance (but don't start it for demo)
        server = EnhancedMultiprocessingMCPServer()
        
        print(f"✅ Server configured with {server.workers} Uvicorn workers")
        print(f"   VFS Pool: {server.vfs_pool._max_workers} processes")
        print(f"   Backend Pool: {server.backend_pool._max_workers} processes")  
        print(f"   Route Pool: {server.route_pool._max_workers} processes")
        print(f"   I/O Thread Pool: {server.io_thread_pool._max_workers} threads")
        print(f"   Daemon Thread Pool: {server.daemon_thread_pool._max_workers} threads")
        
        # Show performance benefits
        print("\n🚀 Performance Benefits:")
        print("   ✅ Parallel VFS operations across multiple processes")
        print("   ✅ Concurrent backend health checks")
        print("   ✅ Distributed route optimization")
        print("   ✅ Load-balanced API request handling")
        print("   ✅ Non-blocking I/O operations")
        
        # Cleanup
        await server.cleanup()
        
    except Exception as e:
        print(f"❌ Error testing enhanced MCP server: {e}")


async def demo_enhanced_cli():
    """Demo the enhanced multiprocessing CLI."""
    print("\n💻 Enhanced Multiprocessing CLI Demo")
    print("=" * 60)
    
    try:
        # Import enhanced CLI
        from enhanced_multiprocessing_cli import EnhancedMultiprocessingCLI
        
        print("✅ Enhanced CLI imported successfully")
        
        # Create CLI instance
        cli = EnhancedMultiprocessingCLI()
        
        print(f"✅ CLI configured with {cli.max_workers} max workers")
        print(f"   IPFS Pool: {cli.ipfs_pool._max_workers} processes")
        print(f"   Backend Pool: {cli.backend_pool._max_workers} processes")
        print(f"   I/O Thread Pool: {cli.io_pool._max_workers} threads")
        
        # Test routing stats (non-blocking)
        print("\n📊 Testing route statistics...")
        route_stats = cli.route_stats()
        if route_stats.get("error"):
            print(f"   ⚠️ Route stats: {route_stats['error']}")
        else:
            print("   ✅ Route statistics retrieved")
            print(f"   Backends: {route_stats.get('total_backends', 0)}")
        
        # Test daemon status (async)
        print("\n🔧 Testing daemon status...")
        daemon_status = await cli.daemon_status()
        if daemon_status.get("error"):
            print(f"   ⚠️ Daemon status: {daemon_status['error']}")
        else:
            print("   ✅ Daemon status retrieved")
        
        # Test backend health (parallel)
        print("\n🏥 Testing parallel backend health...")
        health_result = await cli.backend_health_parallel()
        if health_result.get("backends"):
            backends = health_result["backends"]
            print(f"   ✅ Checked {len(backends)} backends in parallel")
            for backend, status in backends.items():
                health = status.get("status", "unknown") if not status.get("error") else "error"
                print(f"   {backend}: {health}")
        else:
            print("   ⚠️ Backend health check failed")
        
        # Performance benefits
        print("\n⚡ CLI Performance Benefits:")
        print("   ✅ Parallel file operations (add, get, pin)")
        print("   ✅ Batch processing with progress tracking")
        print("   ✅ Concurrent backend operations")
        print("   ✅ Route optimization across multiple processes")
        print("   ✅ Non-blocking daemon communication")
        
        # Cleanup
        cli.cleanup()
        
    except Exception as e:
        print(f"❌ Error testing enhanced CLI: {e}")


async def demo_performance_comparison():
    """Demo performance comparison between single-threaded and multiprocessing."""
    print("\n⚡ Performance Comparison Demo")
    print("=" * 60)
    
    # Create test data
    test_cids = [f"QmTest{i:06d}{'x' * 40}" for i in range(100)]
    test_backends = ["ipfs", "ipfs_cluster", "storacha", "s3", "lotus"]
    
    print(f"Test data: {len(test_cids)} CIDs, {len(test_backends)} backends")
    
    try:
        from enhanced_multiprocessing_cli import route_optimization_process
        
        # Single-threaded approach
        print("\n🐌 Single-threaded route optimization...")
        start_time = time.time()
        
        single_result = route_optimization_process(test_cids, test_backends)
        
        single_time = time.time() - start_time
        print(f"   Time: {single_time:.2f} seconds")
        print(f"   CIDs processed: {len(single_result.get('routes', {}))}")
        
        # Multiprocessing approach
        print("\n🚀 Multiprocessing route optimization...")
        start_time = time.time()
        
        # Split into chunks for parallel processing
        chunk_size = len(test_cids) // mp.cpu_count()
        chunks = [test_cids[i:i + chunk_size] for i in range(0, len(test_cids), chunk_size)]
        
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=mp.cpu_count()) as executor:
            futures = []
            for chunk in chunks:
                future = executor.submit(route_optimization_process, chunk, test_backends)
                futures.append(future)
            
            # Collect results
            all_routes = {}
            for future in futures:
                result = future.result()
                if result.get("success"):
                    all_routes.update(result.get("routes", {}))
        
        mp_time = time.time() - start_time
        print(f"   Time: {mp_time:.2f} seconds")
        print(f"   CIDs processed: {len(all_routes)}")
        
        # Performance comparison
        speedup = single_time / mp_time if mp_time > 0 else 1
        print(f"\n📈 Performance Results:")
        print(f"   Single-threaded: {single_time:.2f}s")
        print(f"   Multiprocessing: {mp_time:.2f}s")
        print(f"   Speedup: {speedup:.2f}x")
        print(f"   Efficiency: {(speedup / mp.cpu_count()) * 100:.1f}%")
        
    except Exception as e:
        print(f"❌ Error in performance comparison: {e}")


async def demo_file_operations():
    """Demo parallel file operations."""
    print("\n📁 Parallel File Operations Demo")
    print("=" * 60)
    
    try:
        from enhanced_multiprocessing_cli import EnhancedMultiprocessingCLI
        
        # Create test files
        print("Creating test files...")
        test_files = create_test_files(count=10)
        print(f"✅ Created {len(test_files)} test files")
        
        # Create CLI instance
        cli = EnhancedMultiprocessingCLI()
        
        # Test parallel file adding
        print("\n📤 Testing parallel file add operations...")
        start_time = time.time()
        
        add_result = await cli.ipfs_add_parallel(test_files)
        
        add_time = time.time() - start_time
        
        if add_result.get("results"):
            successful = sum(1 for r in add_result["results"].values() if r.get("success"))
            print(f"   ✅ Added {successful}/{len(test_files)} files in {add_time:.2f}s")
            print(f"   Success rate: {add_result['stats']['success_rate']:.1f}%")
            print(f"   Avg response time: {add_result['stats']['avg_response_time']:.3f}s")
        else:
            print("   ⚠️ File add operation failed")
        
        # Test parallel CID retrieval
        test_cids = ["QmTest1", "QmTest2", "QmTest3", "QmTest4", "QmTest5"]
        
        print("\n📥 Testing parallel CID get operations...")
        start_time = time.time()
        
        get_result = await cli.ipfs_get_parallel(test_cids)
        
        get_time = time.time() - start_time
        
        if get_result.get("results"):
            successful = sum(1 for r in get_result["results"].values() if r.get("success"))
            print(f"   ✅ Retrieved {successful}/{len(test_cids)} CIDs in {get_time:.2f}s")
            print(f"   Success rate: {get_result['stats']['success_rate']:.1f}%")
        else:
            print("   ⚠️ CID get operation failed")
        
        # Cleanup
        cli.cleanup()
        
        # Clean up test files
        for file_path in test_files:
            try:
                os.remove(file_path)
            except:
                pass
        
    except Exception as e:
        print(f"❌ Error in file operations demo: {e}")


async def demo_load_balancing():
    """Demo load balancing and worker management."""
    print("\n⚖️ Load Balancing Demo")
    print("=" * 60)
    
    print(f"System information:")
    print(f"   CPU cores: {mp.cpu_count()}")
    print(f"   Recommended workers: {min(8, mp.cpu_count())}")
    
    # Simulate different workload scenarios
    scenarios = [
        {"name": "Light Load", "operations": 10, "workers": 2},
        {"name": "Medium Load", "operations": 50, "workers": 4},
        {"name": "Heavy Load", "operations": 100, "workers": mp.cpu_count()},
    ]
    
    for scenario in scenarios:
        print(f"\n📊 {scenario['name']} Scenario:")
        print(f"   Operations: {scenario['operations']}")
        print(f"   Workers: {scenario['workers']}")
        
        # Simulate workload distribution
        ops_per_worker = scenario['operations'] // scenario['workers']
        remaining_ops = scenario['operations'] % scenario['workers']
        
        print(f"   Ops per worker: {ops_per_worker}")
        print(f"   Load balance: {(1 - remaining_ops/scenario['operations']) * 100:.1f}%")
        
        # Estimate performance
        estimated_time = ops_per_worker * 0.1  # 0.1s per operation
        sequential_time = scenario['operations'] * 0.1
        speedup = sequential_time / estimated_time if estimated_time > 0 else 1
        
        print(f"   Estimated time: {estimated_time:.2f}s (vs {sequential_time:.2f}s sequential)")
        print(f"   Estimated speedup: {speedup:.2f}x")


async def main():
    """Main demo function."""
    print("🎉 Enhanced Multiprocessing IPFS-Kit Demo")
    print("=" * 70)
    print(f"System: {mp.cpu_count()} CPU cores detected")
    print(f"Python multiprocessing support: {'✅' if mp.get_start_method() else '❌'}")
    
    try:
        # Run all demos
        await demo_enhanced_daemon()
        await demo_enhanced_mcp_server() 
        await demo_enhanced_cli()
        await demo_performance_comparison()
        await demo_file_operations()
        await demo_load_balancing()
        
        print("\n" + "=" * 70)
        print("🎯 Multiprocessing Enhancement Summary")
        print("=" * 70)
        
        print("\n✅ Enhanced Components:")
        print("   🔧 Daemon: Process pools for health, replication, logging, pin indexing")
        print("   🌐 MCP Server: Uvicorn workers + process pools for VFS, backend, routing")
        print("   💻 CLI: Process pools for IPFS ops + thread pools for I/O")
        
        print("\n🚀 Performance Benefits:")
        print("   ⚡ Parallel processing across multiple CPU cores")
        print("   📈 Improved throughput for batch operations")
        print("   🔄 Non-blocking I/O and concurrent request handling")
        print("   ⚖️ Load balancing and optimal resource utilization")
        print("   📊 Real-time progress tracking and statistics")
        
        print("\n🎛️ Configuration Options:")
        print("   --workers: Override number of worker processes")
        print("   --parallel: Enable parallel processing for operations")
        print("   --debug: Enable detailed logging")
        
        print("\n📋 Usage Examples:")
        print("   # Enhanced daemon")
        print("   python enhanced_multiprocessing_daemon.py --workers 8")
        print("   ")
        print("   # Enhanced MCP server")
        print("   python enhanced_multiprocessing_mcp_server.py --workers 4 --vfs-workers 2")
        print("   ")
        print("   # Enhanced CLI")
        print("   python enhanced_multiprocessing_cli.py ipfs add file1,file2,file3 --parallel")
        print("   python enhanced_multiprocessing_cli.py backend health --parallel")
        print("   python enhanced_multiprocessing_cli.py route optimize QmHash1,QmHash2")
        
        print("\n✅ Enhanced multiprocessing demo completed successfully!")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"\nDemo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
