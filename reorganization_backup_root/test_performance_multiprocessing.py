#!/usr/bin/env python3
"""
Performance Test Suite for IPFS-Kit Multiprocessing Enhancements

This test compares performance between single-threaded and multiprocessing approaches.
"""

import asyncio
import time
import statistics
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import multiprocessing as mp
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


class PerformanceTestSuite:
    """Performance testing for multiprocessing improvements"""
    
    def __init__(self):
        self.cpu_count = mp.cpu_count()
        self.test_data_size = 100
        self.results = {}
    
    def cpu_intensive_task(self, n: int) -> int:
        """Simulate CPU-intensive work"""
        result = 0
        for i in range(n * 1000):
            result += i * i
        return result
    
    def io_intensive_task(self, delay: float) -> float:
        """Simulate I/O-intensive work"""
        time.sleep(delay)
        return delay
    
    async def async_io_task(self, delay: float) -> float:
        """Async I/O task"""
        await asyncio.sleep(delay)
        return delay
    
    def test_sequential_cpu_work(self, tasks: List[int]) -> Dict[str, Any]:
        """Test sequential CPU work"""
        start_time = time.time()
        
        results = []
        for task in tasks:
            result = self.cpu_intensive_task(task)
            results.append(result)
        
        duration = time.time() - start_time
        
        return {
            "method": "sequential",
            "tasks": len(tasks),
            "duration": duration,
            "throughput": len(tasks) / duration,
            "results_count": len(results)
        }
    
    def test_multiprocessing_cpu_work(self, tasks: List[int], workers: Optional[int] = None) -> Dict[str, Any]:
        """Test multiprocessing CPU work"""
        if workers is None:
            workers = min(self.cpu_count, len(tasks))
        
        start_time = time.time()
        
        with ProcessPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(self.cpu_intensive_task, tasks))
        
        duration = time.time() - start_time
        
        return {
            "method": "multiprocessing",
            "workers": workers,
            "tasks": len(tasks),
            "duration": duration,
            "throughput": len(tasks) / duration,
            "results_count": len(results)
        }
    
    def test_sequential_io_work(self, tasks: List[float]) -> Dict[str, Any]:
        """Test sequential I/O work"""
        start_time = time.time()
        
        results = []
        for task in tasks:
            result = self.io_intensive_task(task)
            results.append(result)
        
        duration = time.time() - start_time
        
        return {
            "method": "sequential",
            "tasks": len(tasks),
            "duration": duration,
            "throughput": len(tasks) / duration,
            "results_count": len(results)
        }
    
    def test_threading_io_work(self, tasks: List[float], workers: Optional[int] = None) -> Dict[str, Any]:
        """Test threaded I/O work"""
        if workers is None:
            workers = min(10, len(tasks))  # I/O doesn't need as many workers
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(self.io_intensive_task, tasks))
        
        duration = time.time() - start_time
        
        return {
            "method": "threading",
            "workers": workers,
            "tasks": len(tasks),
            "duration": duration,
            "throughput": len(tasks) / duration,
            "results_count": len(results)
        }
    
    async def test_async_io_work(self, tasks: List[float], concurrency: Optional[int] = None) -> Dict[str, Any]:
        """Test async I/O work"""
        if concurrency is None:
            concurrency = min(50, len(tasks))  # High concurrency for async
        
        start_time = time.time()
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(concurrency)
        
        async def limited_task(delay):
            async with semaphore:
                return await self.async_io_task(delay)
        
        results = await asyncio.gather(*[limited_task(task) for task in tasks])
        
        duration = time.time() - start_time
        
        return {
            "method": "async",
            "concurrency": concurrency,
            "tasks": len(tasks),
            "duration": duration,
            "throughput": len(tasks) / duration,
            "results_count": len(results)
        }
    
    def calculate_speedup(self, baseline: Dict[str, Any], optimized: Dict[str, Any]) -> float:
        """Calculate speedup factor"""
        if optimized["duration"] == 0:
            return float('inf')
        return baseline["duration"] / optimized["duration"]
    
    def calculate_efficiency(self, speedup: float, workers: int) -> float:
        """Calculate parallel efficiency"""
        if workers == 0:
            return 0.0
        return speedup / workers * 100
    
    async def run_cpu_performance_tests(self) -> Dict[str, Any]:
        """Run CPU-intensive performance tests"""
        if console:
            console.print("🔥 Running CPU Performance Tests", style="bold red")
        
        # Create test data
        cpu_tasks = [50] * 20  # 20 tasks of medium intensity
        
        # Sequential test
        sequential_result = self.test_sequential_cpu_work(cpu_tasks)
        
        # Multiprocessing tests with different worker counts
        worker_counts = [2, 4, min(8, self.cpu_count), self.cpu_count]
        mp_results = []
        
        for workers in worker_counts:
            if workers <= self.cpu_count:
                result = self.test_multiprocessing_cpu_work(cpu_tasks, workers)
                mp_results.append(result)
        
        # Calculate speedups
        best_mp_result = min(mp_results, key=lambda x: x["duration"])
        speedup = self.calculate_speedup(sequential_result, best_mp_result)
        efficiency = self.calculate_efficiency(speedup, best_mp_result["workers"])
        
        return {
            "test_type": "CPU-intensive",
            "sequential": sequential_result,
            "multiprocessing": mp_results,
            "best_multiprocessing": best_mp_result,
            "speedup": speedup,
            "efficiency": efficiency
        }
    
    async def run_io_performance_tests(self) -> Dict[str, Any]:
        """Run I/O-intensive performance tests"""
        if console:
            console.print("💾 Running I/O Performance Tests", style="bold blue")
        
        # Create test data (smaller delays for faster testing)
        io_tasks = [0.01] * 50  # 50 tasks with 10ms delay each
        
        # Sequential test
        sequential_result = self.test_sequential_io_work(io_tasks)
        
        # Threading test
        threading_result = self.test_threading_io_work(io_tasks, workers=10)
        
        # Async test
        async_result = await self.test_async_io_work(io_tasks, concurrency=25)
        
        # Calculate speedups
        threading_speedup = self.calculate_speedup(sequential_result, threading_result)
        async_speedup = self.calculate_speedup(sequential_result, async_result)
        
        return {
            "test_type": "I/O-intensive",
            "sequential": sequential_result,
            "threading": threading_result,
            "async": async_result,
            "threading_speedup": threading_speedup,
            "async_speedup": async_speedup
        }
    
    def test_memory_efficiency(self) -> Dict[str, Any]:
        """Test memory usage patterns"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create some test data
        test_data = [list(range(10000)) for _ in range(100)]
        
        peak_memory = process.memory_info().rss
        memory_usage = peak_memory - initial_memory
        
        # Cleanup
        del test_data
        
        return {
            "initial_memory_mb": initial_memory / 1024 / 1024,
            "peak_memory_mb": peak_memory / 1024 / 1024,
            "memory_usage_mb": memory_usage / 1024 / 1024
        }
    
    async def run_load_balancing_test(self) -> Dict[str, Any]:
        """Test load balancing effectiveness"""
        if console:
            console.print("⚖️ Running Load Balancing Tests", style="bold yellow")
        
        # Mixed workload - some tasks heavy, some light
        mixed_tasks = [10] * 5 + [100] * 5 + [50] * 10  # 20 tasks total
        
        # Test with different worker configurations
        results = []
        
        worker_configs = [1, 2, 4, min(8, self.cpu_count)]
        
        for workers in worker_configs:
            if workers <= self.cpu_count:
                result = self.test_multiprocessing_cpu_work(mixed_tasks, workers)
                result["load_balance_score"] = self._calculate_load_balance_score(result)
                results.append(result)
        
        return {
            "test_type": "load_balancing",
            "mixed_workload": True,
            "results": results,
            "optimal_workers": min(results, key=lambda x: x["duration"])["workers"] if results else 1
        }
    
    def _calculate_load_balance_score(self, result: Dict[str, Any]) -> float:
        """Calculate load balancing effectiveness score"""
        # Simple heuristic: efficiency relative to theoretical maximum
        workers = result.get("workers", 1)
        throughput = result.get("throughput", 0)
        
        # Theoretical max assuming perfect scaling
        theoretical_max = throughput * workers
        
        # Score as percentage of theoretical maximum
        if theoretical_max > 0:
            return min(100.0, (throughput / theoretical_max) * 100)
        return 0.0
    
    async def run_comprehensive_performance_tests(self) -> Dict[str, Any]:
        """Run all performance tests"""
        if console:
            console.print("🚀 Starting Comprehensive Performance Tests", style="bold green")
            console.print(f"System: {self.cpu_count} CPU cores detected", style="cyan")
            console.print("=" * 60)
        
        results = {}
        
        # CPU tests
        cpu_results = await self.run_cpu_performance_tests()
        results["cpu_performance"] = cpu_results
        
        # I/O tests
        io_results = await self.run_io_performance_tests()
        results["io_performance"] = io_results
        
        # Load balancing tests
        load_balance_results = await self.run_load_balancing_test()
        results["load_balancing"] = load_balance_results
        
        # Memory efficiency
        memory_results = self.test_memory_efficiency()
        results["memory_efficiency"] = memory_results
        
        # System information
        results["system_info"] = {
            "cpu_count": self.cpu_count,
            "python_version": sys.version,
            "platform": sys.platform
        }
        
        return results
    
    def print_performance_summary(self, results: Dict[str, Any]):
        """Print performance test summary"""
        if console and RICH_AVAILABLE:
            # CPU Performance Table
            cpu_table = Table(title="CPU Performance Results")
            cpu_table.add_column("Method", style="cyan")
            cpu_table.add_column("Workers", style="yellow")
            cpu_table.add_column("Duration (s)", style="green")
            cpu_table.add_column("Throughput", style="blue")
            cpu_table.add_column("Speedup", style="red")
            
            cpu_data = results["cpu_performance"]
            
            # Sequential baseline
            seq = cpu_data["sequential"]
            cpu_table.add_row("Sequential", "1", f"{seq['duration']:.2f}", f"{seq['throughput']:.1f}", "1.0x")
            
            # Multiprocessing results
            for mp_result in cpu_data["multiprocessing"]:
                speedup = seq["duration"] / mp_result["duration"]
                cpu_table.add_row(
                    "Multiprocessing",
                    str(mp_result["workers"]),
                    f"{mp_result['duration']:.2f}",
                    f"{mp_result['throughput']:.1f}",
                    f"{speedup:.1f}x"
                )
            
            console.print(cpu_table)
            
            # I/O Performance Table
            io_table = Table(title="I/O Performance Results")
            io_table.add_column("Method", style="cyan")
            io_table.add_column("Concurrency", style="yellow")
            io_table.add_column("Duration (s)", style="green")
            io_table.add_column("Throughput", style="blue")
            io_table.add_column("Speedup", style="red")
            
            io_data = results["io_performance"]
            
            seq_io = io_data["sequential"]
            io_table.add_row("Sequential", "1", f"{seq_io['duration']:.2f}", f"{seq_io['throughput']:.1f}", "1.0x")
            
            threading_io = io_data["threading"]
            threading_speedup = io_data["threading_speedup"]
            io_table.add_row(
                "Threading",
                str(threading_io["workers"]),
                f"{threading_io['duration']:.2f}",
                f"{threading_io['throughput']:.1f}",
                f"{threading_speedup:.1f}x"
            )
            
            async_io = io_data["async"]
            async_speedup = io_data["async_speedup"]
            io_table.add_row(
                "Async",
                str(async_io["concurrency"]),
                f"{async_io['duration']:.2f}",
                f"{async_io['throughput']:.1f}",
                f"{async_speedup:.1f}x"
            )
            
            console.print(io_table)
            
            # Summary Panel
            best_cpu_speedup = cpu_data["speedup"]
            best_io_speedup = max(io_data["threading_speedup"], io_data["async_speedup"])
            
            summary_text = f"""
CPU Performance:
  Best Speedup: {best_cpu_speedup:.1f}x
  Efficiency: {cpu_data['efficiency']:.1f}%
  Optimal Workers: {cpu_data['best_multiprocessing']['workers']}

I/O Performance:
  Threading Speedup: {io_data['threading_speedup']:.1f}x
  Async Speedup: {io_data['async_speedup']:.1f}x

System Resources:
  CPU Cores: {results['system_info']['cpu_count']}
  Memory Usage: {results['memory_efficiency']['memory_usage_mb']:.1f} MB
"""
            
            panel = Panel(
                summary_text,
                title="Performance Summary",
                border_style="green"
            )
            console.print(panel)
        
        else:
            print("\n" + "=" * 60)
            print("PERFORMANCE TEST RESULTS")
            print("=" * 60)
            
            cpu_data = results["cpu_performance"]
            print(f"CPU Best Speedup: {cpu_data['speedup']:.1f}x")
            print(f"CPU Efficiency: {cpu_data['efficiency']:.1f}%")
            
            io_data = results["io_performance"]
            print(f"I/O Threading Speedup: {io_data['threading_speedup']:.1f}x")
            print(f"I/O Async Speedup: {io_data['async_speedup']:.1f}x")
            
            print(f"System CPU Cores: {results['system_info']['cpu_count']}")
            print("=" * 60)


async def main():
    """Main performance test runner"""
    test_suite = PerformanceTestSuite()
    
    try:
        results = await test_suite.run_comprehensive_performance_tests()
        test_suite.print_performance_summary(results)
        
        # Save results to file
        import json
        with open("/tmp/ipfs_kit_performance_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        if console:
            console.print("📊 Performance results saved to /tmp/ipfs_kit_performance_results.json", style="green")
        else:
            print("Performance results saved to /tmp/ipfs_kit_performance_results.json")
        
        return 0
        
    except Exception as e:
        if console:
            console.print(f"❌ Performance tests failed: {e}", style="red")
        else:
            print(f"Performance tests failed: {e}")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nPerformance tests interrupted by user")
        sys.exit(1)
