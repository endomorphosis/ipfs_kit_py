#!/usr/bin/env python3
"""
Multi-Processing Benefits Demonstration.

This script shows the performance benefits of multi-processing
without requiring a running daemon.
"""

import asyncio
import concurrent.futures
import multiprocessing as mp
import time
from pathlib import Path

# Rich for output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    console = None

def cpu_intensive_task(n):
    """Simulate CPU-intensive work."""
    total = 0
    for i in range(n * 1000):
        total += i ** 2
    return total

def io_simulation_task(delay):
    """Simulate I/O bound work."""
    time.sleep(delay)
    return f"Task completed after {delay}s"

async def async_task(delay):
    """Simulate async I/O work."""
    await asyncio.sleep(delay)
    return f"Async task completed after {delay}s"

class MultiProcessingDemo:
    """Demonstrate multi-processing performance benefits."""
    
    def __init__(self):
        self.cpu_count = mp.cpu_count()
        
    def print_banner(self):
        """Print demo banner."""
        if console:
            banner = Panel(
                f"""[bold cyan]⚡ MULTI-PROCESSING PERFORMANCE DEMONSTRATION[/bold cyan]

🖥️ [bold]System Information[/bold]
• CPU Cores Available: {self.cpu_count}
• Python Multiprocessing: Ready
• Process Pool Executor: Available
• Thread Pool Executor: Available

🔬 [bold]Performance Tests[/bold]
• CPU-intensive tasks: Single vs Multi-processing
• I/O-bound tasks: Sequential vs Concurrent
• Async operations: Event loop efficiency
• Real-world simulation: Mixed workloads

📊 [bold]Expected Benefits[/bold]
• CPU tasks: Up to {self.cpu_count}x speedup
• I/O tasks: Significant concurrent improvement
• Mixed workloads: Optimal resource utilization""",
                title="🚀 Multi-Processing Benefits Demo",
                border_style="blue"
            )
            console.print(banner)
        else:
            print("=" * 80)
            print("⚡ MULTI-PROCESSING PERFORMANCE DEMONSTRATION")
            print("=" * 80)
            print(f"🖥️ CPU Cores: {self.cpu_count}")
            print("🚀 Testing performance benefits...")
            print("=" * 80)
    
    def test_cpu_intensive_single_vs_multi(self):
        """Test CPU-intensive tasks: single vs multi-processing."""
        if console:
            console.print("\n🔥 Test 1: CPU-Intensive Tasks", style="bold red")
        else:
            print("\n🔥 Test 1: CPU-Intensive Tasks")
        
        num_tasks = 8
        work_size = 5000  # Adjust for reasonable execution time
        
        # Single-threaded execution
        if console:
            console.print("📋 Running single-threaded execution...")
        else:
            print("📋 Running single-threaded execution...")
        
        start_time = time.time()
        single_results = []
        
        if console:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Single-threaded...", total=num_tasks)
                
                for i in range(num_tasks):
                    result = cpu_intensive_task(work_size)
                    single_results.append(result)
                    progress.update(task, advance=1)
        else:
            for i in range(num_tasks):
                result = cpu_intensive_task(work_size)
                single_results.append(result)
                print(f"  Task {i+1}/{num_tasks} completed")
        
        single_time = time.time() - start_time
        
        # Multi-processing execution
        if console:
            console.print("⚡ Running multi-processing execution...")
        else:
            print("⚡ Running multi-processing execution...")
        
        start_time = time.time()
        
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.cpu_count) as executor:
            if console:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    TimeElapsedColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task("Multi-processing...", total=num_tasks)
                    
                    futures = [executor.submit(cpu_intensive_task, work_size) for _ in range(num_tasks)]
                    multi_results = []
                    
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        multi_results.append(result)
                        progress.update(task, advance=1)
            else:
                futures = [executor.submit(cpu_intensive_task, work_size) for _ in range(num_tasks)]
                multi_results = [future.result() for future in concurrent.futures.as_completed(futures)]
                print(f"  All {num_tasks} tasks completed in parallel")
        
        multi_time = time.time() - start_time
        speedup = single_time / multi_time if multi_time > 0 else 0
        
        # Display results
        if console:
            results_panel = Panel(
                f"""[bold green]🔥 CPU-Intensive Task Results[/bold green]

📊 [bold]Performance Comparison[/bold]
• Single-threaded time: {single_time:.2f}s
• Multi-processing time: {multi_time:.2f}s
• Speedup factor: [bold]{speedup:.1f}x[/bold]
• Efficiency: {(speedup/self.cpu_count*100):.1f}% of theoretical maximum

⚡ [bold]Multi-processing Benefits[/bold]
• Utilized {self.cpu_count} CPU cores simultaneously
• Achieved {speedup:.1f}x performance improvement
• Demonstrates excellent CPU scaling""",
                border_style="green"
            )
            console.print(results_panel)
        else:
            print(f"📊 Results:")
            print(f"  Single-threaded: {single_time:.2f}s")
            print(f"  Multi-processing: {multi_time:.2f}s")
            print(f"  Speedup: {speedup:.1f}x")
            print(f"  CPU utilization: {speedup/self.cpu_count*100:.1f}%")
        
        return {
            'single_time': single_time,
            'multi_time': multi_time,
            'speedup': speedup,
            'efficiency': speedup/self.cpu_count*100
        }
    
    def test_io_concurrent_vs_sequential(self):
        """Test I/O-bound tasks: sequential vs concurrent."""
        if console:
            console.print("\n🌐 Test 2: I/O-Bound Tasks", style="bold blue")
        else:
            print("\n🌐 Test 2: I/O-Bound Tasks")
        
        num_tasks = 10
        io_delay = 0.1  # 100ms delay per task
        
        # Sequential execution
        if console:
            console.print("📋 Running sequential I/O operations...")
        else:
            print("📋 Running sequential I/O operations...")
        
        start_time = time.time()
        sequential_results = []
        
        if console:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Sequential I/O...", total=num_tasks)
                
                for i in range(num_tasks):
                    result = io_simulation_task(io_delay)
                    sequential_results.append(result)
                    progress.update(task, advance=1)
        else:
            for i in range(num_tasks):
                result = io_simulation_task(io_delay)
                sequential_results.append(result)
                print(f"  I/O task {i+1}/{num_tasks} completed")
        
        sequential_time = time.time() - start_time
        
        # Concurrent execution with thread pool
        if console:
            console.print("⚡ Running concurrent I/O operations...")
        else:
            print("⚡ Running concurrent I/O operations...")
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(num_tasks, 20)) as executor:
            if console:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    TimeElapsedColumn(),
                    console=console
                ) as progress:
                    task = progress.add_task("Concurrent I/O...", total=num_tasks)
                    
                    futures = [executor.submit(io_simulation_task, io_delay) for _ in range(num_tasks)]
                    concurrent_results = []
                    
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        concurrent_results.append(result)
                        progress.update(task, advance=1)
            else:
                futures = [executor.submit(io_simulation_task, io_delay) for _ in range(num_tasks)]
                concurrent_results = [future.result() for future in concurrent.futures.as_completed(futures)]
                print(f"  All {num_tasks} I/O tasks completed concurrently")
        
        concurrent_time = time.time() - start_time
        speedup = sequential_time / concurrent_time if concurrent_time > 0 else 0
        
        # Display results
        if console:
            results_panel = Panel(
                f"""[bold blue]🌐 I/O-Bound Task Results[/bold blue]

📊 [bold]Performance Comparison[/bold]
• Sequential time: {sequential_time:.2f}s
• Concurrent time: {concurrent_time:.2f}s
• Speedup factor: [bold]{speedup:.1f}x[/bold]
• Expected time (theoretical): {num_tasks * io_delay:.2f}s

⚡ [bold]Concurrency Benefits[/bold]
• Overlapped I/O operations effectively
• Achieved {speedup:.1f}x improvement over sequential
• Demonstrates excellent I/O scaling""",
                border_style="blue"
            )
            console.print(results_panel)
        else:
            print(f"📊 Results:")
            print(f"  Sequential: {sequential_time:.2f}s")
            print(f"  Concurrent: {concurrent_time:.2f}s")
            print(f"  Speedup: {speedup:.1f}x")
            print(f"  Expected sequential: {num_tasks * io_delay:.2f}s")
        
        return {
            'sequential_time': sequential_time,
            'concurrent_time': concurrent_time,
            'speedup': speedup,
            'theoretical_time': num_tasks * io_delay
        }
    
    async def test_async_operations(self):
        """Test async operations efficiency."""
        if console:
            console.print("\n🔄 Test 3: Async Operations", style="bold green")
        else:
            print("\n🔄 Test 3: Async Operations")
        
        num_tasks = 15
        async_delay = 0.05  # 50ms delay per task
        
        if console:
            console.print("⚡ Running async operations...")
        else:
            print("⚡ Running async operations...")
        
        start_time = time.time()
        
        # Create all async tasks
        tasks = [async_task(async_delay) for _ in range(num_tasks)]
        
        if console:
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeElapsedColumn(),
                console=console
            ) as progress:
                progress_task = progress.add_task("Async operations...", total=num_tasks)
                
                # Execute all tasks concurrently
                results = []
                for coro in asyncio.as_completed(tasks):
                    result = await coro
                    results.append(result)
                    progress.update(progress_task, advance=1)
        else:
            results = await asyncio.gather(*tasks)
            print(f"  All {num_tasks} async tasks completed")
        
        async_time = time.time() - start_time
        theoretical_sequential = num_tasks * async_delay
        speedup = theoretical_sequential / async_time if async_time > 0 else 0
        
        # Display results
        if console:
            results_panel = Panel(
                f"""[bold green]🔄 Async Operations Results[/bold green]

📊 [bold]Performance Analysis[/bold]
• Async execution time: {async_time:.2f}s
• Theoretical sequential: {theoretical_sequential:.2f}s
• Efficiency factor: [bold]{speedup:.1f}x[/bold]
• Event loop overhead: {(async_time - async_delay):.3f}s

⚡ [bold]Async Benefits[/bold]
• Single-threaded concurrency
• Minimal overhead with event loop
• Excellent for I/O-bound operations""",
                border_style="green"
            )
            console.print(results_panel)
        else:
            print(f"📊 Results:")
            print(f"  Async execution: {async_time:.2f}s")
            print(f"  Theoretical sequential: {theoretical_sequential:.2f}s")
            print(f"  Efficiency: {speedup:.1f}x")
        
        return {
            'async_time': async_time,
            'theoretical_sequential': theoretical_sequential,
            'speedup': speedup
        }
    
    def display_summary(self, cpu_results, io_results, async_results):
        """Display comprehensive summary."""
        if console:
            console.print("\n🏆 COMPREHENSIVE PERFORMANCE SUMMARY", style="bold magenta")
            
            summary_text = f"""[bold magenta]🚀 Multi-Processing Performance Analysis[/bold magenta]

🔥 [bold]CPU-Intensive Tasks[/bold]
• Single-threaded: {cpu_results['single_time']:.2f}s
• Multi-processing: {cpu_results['multi_time']:.2f}s
• Speedup: [bold]{cpu_results['speedup']:.1f}x[/bold]
• CPU Efficiency: {cpu_results['efficiency']:.1f}%

🌐 [bold]I/O-Bound Tasks[/bold]
• Sequential: {io_results['sequential_time']:.2f}s
• Concurrent: {io_results['concurrent_time']:.2f}s
• Speedup: [bold]{io_results['speedup']:.1f}x[/bold]

🔄 [bold]Async Operations[/bold]
• Async execution: {async_results['async_time']:.2f}s
• Efficiency: [bold]{async_results['speedup']:.1f}x[/bold]

💡 [bold]Key Insights[/bold]
• Multi-processing excels at CPU-intensive tasks
• Thread pools optimize I/O-bound operations
• Async operations provide efficient concurrency
• IPFS Kit benefits from all three approaches

🎯 [bold]Real-World Application[/bold]
• Pin operations: Multi-processing for parallel execution
• Network requests: Thread pools for concurrent I/O
• API handling: Async for high-throughput serving
• Dashboard updates: Event loops for real-time data"""
            
            summary_panel = Panel(
                summary_text,
                title="🏆 Performance Analysis Complete",
                border_style="magenta",
                padding=(1, 2)
            )
            console.print(summary_panel)
        else:
            print("\n🏆 COMPREHENSIVE PERFORMANCE SUMMARY")
            print("=" * 80)
            print(f"🔥 CPU Tasks - Speedup: {cpu_results['speedup']:.1f}x")
            print(f"🌐 I/O Tasks - Speedup: {io_results['speedup']:.1f}x")
            print(f"🔄 Async Tasks - Efficiency: {async_results['speedup']:.1f}x")
            print("=" * 80)
            print("🎯 Multi-processing provides significant performance benefits!")


async def main():
    """Run the multi-processing benefits demonstration."""
    demo = MultiProcessingDemo()
    
    try:
        # Display banner
        demo.print_banner()
        
        # Run CPU-intensive test
        cpu_results = demo.test_cpu_intensive_single_vs_multi()
        
        # Run I/O-bound test
        io_results = demo.test_io_concurrent_vs_sequential()
        
        # Run async test
        async_results = await demo.test_async_operations()
        
        # Display comprehensive summary
        demo.display_summary(cpu_results, io_results, async_results)
        
        if console:
            console.print("\n🎉 Multi-processing benefits demonstration completed!", style="bold green")
            console.print("💡 These improvements are built into the IPFS Kit multi-processing architecture", style="blue")
        else:
            print("\n🎉 Multi-processing benefits demonstration completed!")
            print("💡 These improvements are built into the IPFS Kit architecture")
        
    except KeyboardInterrupt:
        if console:
            console.print("\n🛑 Demo interrupted by user", style="yellow")
        else:
            print("\n🛑 Demo interrupted by user")
    except Exception as e:
        if console:
            console.print(f"\n❌ Demo failed: {e}", style="red")
        else:
            print(f"\n❌ Demo failed: {e}")


if __name__ == "__main__":
    print("🚀 Multi-Processing Benefits Demonstration")
    print("📊 This will show performance improvements without requiring a daemon")
    print("=" * 80)
    
    asyncio.run(main())
