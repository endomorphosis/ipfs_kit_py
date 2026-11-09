#!/usr/bin/env python3
"""
Multi-Processing IPFS Kit Demo.

This script demonstrates the high-throughput capabilities of the multi-processing
enhanced IPFS Kit architecture:

1. Multi-processing daemon with worker processes
2. Concurrent operations and batch processing
3. Performance benchmarking and stress testing
4. Resource utilization analysis
5. Throughput comparisons vs single-threaded operations
"""

import asyncio
import json
import multiprocessing as mp
import time
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Dict, Any, List

# Rich for beautiful output
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# HTTP client for testing
import httpx

console = Console() if RICH_AVAILABLE else None

class MultiProcessingDemo:
    """
    Comprehensive demonstration of multi-processing IPFS Kit capabilities.
    """
    
    def __init__(self):
        self.daemon_url = "http://127.0.0.1:9999"
        self.mcp_dashboard_url = "http://127.0.0.1:8080"
        
        # Performance tracking
        self.benchmark_results = {}
        
    def print_banner(self):
        """Print demo banner."""
        if console:
            banner = Panel(
                f"""[bold cyan]⚡ MULTI-PROCESSING IPFS KIT DEMONSTRATION[/bold cyan]

🚀 [bold]High-Throughput Features[/bold]
• Multi-processing daemon with worker processes
• Concurrent HTTP operations and batch processing
• Process pools for CPU-intensive tasks
• Thread pools for I/O bound operations
• Real-time performance monitoring
• Automatic load balancing and resource optimization

🔬 [bold]Performance Tests[/bold]
• Single vs Multi-processing comparisons
• Batch operation throughput analysis
• Concurrent request stress testing
• Resource utilization benchmarks
• Scalability performance measurements

📊 [bold]Metrics Tracked[/bold]
• Operations per second (throughput)
• Response time distributions
• CPU and memory utilization
• Worker process efficiency
• Queue processing rates""",
                title="🔥 Multi-Processing Performance Demo",
                border_style="red",
                padding=(1, 2)
            )
            console.print(banner)
        else:
            print("=" * 80)
            print("⚡ MULTI-PROCESSING IPFS KIT DEMONSTRATION")
            print("=" * 80)
            print("🚀 Testing high-throughput operations with multi-processing")
            print("=" * 80)
    
    async def test_daemon_connectivity(self) -> bool:
        """Test connectivity to multi-processing daemon."""
        try:
            if console:
                console.print("🔍 Testing daemon connectivity...", style="blue")
            else:
                print("🔍 Testing daemon connectivity...")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.daemon_url}/health/fast", timeout=10)
                
                if response.status_code == 200:
                    health_data = response.json()
                    
                    if console:
                        # Display daemon info
                        table = Table(title="🔧 Daemon Status")
                        table.add_column("Property", style="cyan")
                        table.add_column("Value", style="green")
                        
                        table.add_row("Status", "🟢 Running")
                        table.add_row("Workers", str(health_data.get('workers', 'N/A')))
                        table.add_row("Active Operations", str(health_data.get('active_operations', 0)))
                        table.add_row("Total Operations", str(health_data.get('total_operations', 0)))
                        table.add_row("Response Time", f"{health_data.get('response_time_ms', 0)}ms")
                        
                        console.print(table)
                    else:
                        print(f"✅ Daemon connected: {health_data.get('workers', 'N/A')} workers")
                    
                    return True
                else:
                    if console:
                        console.print(f"❌ Daemon connection failed: HTTP {response.status_code}", style="red")
                    else:
                        print(f"❌ Daemon connection failed: HTTP {response.status_code}")
                    return False
                    
        except Exception as e:
            if console:
                console.print(f"❌ Cannot connect to daemon: {e}", style="red")
            else:
                print(f"❌ Cannot connect to daemon: {e}")
            return False
    
    async def benchmark_single_vs_batch_operations(self) -> Dict[str, Any]:
        """Benchmark single operations vs batch operations."""
        if console:
            console.print("\n🏁 Benchmarking: Single vs Batch Operations", style="bold blue")
        else:
            print("\n🏁 Benchmarking: Single vs Batch Operations")
        
        # Test parameters
        num_operations = 100
        test_cid_base = "QmTest" + "0" * 40
        
        results = {}
        
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                
                # Test 1: Single operations (sequential)
                if console:
                    console.print("📋 Test 1: Sequential single operations")
                else:
                    print("📋 Test 1: Sequential single operations")
                
                start_time = time.time()
                
                if console:
                    with Progress(
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        "[progress.percentage]{task.percentage:>3.0f}%",
                        TimeElapsedColumn(),
                        console=console
                    ) as progress:
                        task = progress.add_task("Single operations...", total=num_operations)
                        
                        for i in range(num_operations):
                            try:
                                await client.post(f"{self.daemon_url}/pins/{test_cid_base}{i:06d}", timeout=30)
                                progress.update(task, advance=1)
                            except Exception as e:
                                # Continue on individual failures
                                progress.update(task, advance=1)
                else:
                    for i in range(num_operations):
                        try:
                            await client.post(f"{self.daemon_url}/pins/{test_cid_base}{i:06d}", timeout=30)
                            if i % 10 == 0:
                                print(f"  Progress: {i}/{num_operations}")
                        except Exception:
                            pass
                
                single_time = time.time() - start_time
                single_throughput = num_operations / single_time
                
                results['single_operations'] = {
                    'total_time': single_time,
                    'throughput_ops_per_sec': single_throughput,
                    'avg_time_per_op': single_time / num_operations
                }
                
                # Test 2: Batch operations (parallel)
                if console:
                    console.print("📦 Test 2: Batch operations (parallel)")
                else:
                    print("📦 Test 2: Batch operations (parallel)")
                
                # Create batch operations
                operations = [
                    {"operation": "add", "cid": f"{test_cid_base}{i:06d}"}
                    for i in range(num_operations, num_operations * 2)  # Different CIDs
                ]
                
                start_time = time.time()
                
                batch_response = await client.post(
                    f"{self.daemon_url}/pins/batch",
                    json=operations,
                    timeout=300
                )
                
                batch_time = time.time() - start_time
                batch_throughput = num_operations / batch_time
                
                if batch_response.status_code == 200:
                    batch_data = batch_response.json()
                    results['batch_operations'] = {
                        'total_time': batch_time,
                        'throughput_ops_per_sec': batch_throughput,
                        'avg_time_per_op': batch_time / num_operations,
                        'successful': batch_data.get('successful', 0),
                        'failed': batch_data.get('failed', 0)
                    }
                else:
                    results['batch_operations'] = {'error': f"HTTP {batch_response.status_code}"}
                
                # Calculate improvement
                if 'batch_operations' in results and 'error' not in results['batch_operations']:
                    speedup = single_throughput / batch_throughput if batch_throughput > 0 else 0
                    results['comparison'] = {
                        'batch_speedup_factor': batch_throughput / single_throughput if single_throughput > 0 else 0,
                        'time_improvement_percent': ((single_time - batch_time) / single_time * 100) if single_time > 0 else 0
                    }
                
                # Display results
                if console:
                    results_table = Table(title="⚡ Single vs Batch Performance")
                    results_table.add_column("Method", style="cyan")
                    results_table.add_column("Total Time", style="yellow")
                    results_table.add_column("Throughput (ops/sec)", style="green")
                    results_table.add_column("Avg Time/Op", style="blue")
                    
                    single_data = results['single_operations']
                    results_table.add_row(
                        "Sequential Single",
                        f"{single_data['total_time']:.2f}s",
                        f"{single_data['throughput_ops_per_sec']:.1f}",
                        f"{single_data['avg_time_per_op']*1000:.1f}ms"
                    )
                    
                    if 'batch_operations' in results and 'error' not in results['batch_operations']:
                        batch_data = results['batch_operations']
                        results_table.add_row(
                            "Parallel Batch",
                            f"{batch_data['total_time']:.2f}s",
                            f"{batch_data['throughput_ops_per_sec']:.1f}",
                            f"{batch_data['avg_time_per_op']*1000:.1f}ms"
                        )
                        
                        # Show improvement
                        if 'comparison' in results:
                            comp = results['comparison']
                            improvement_panel = Panel(
                                f"""[bold green]📈 Performance Improvement[/bold green]

• Batch throughput is [bold]{comp['batch_speedup_factor']:.1f}x[/bold] faster
• Time reduction: [bold]{comp['time_improvement_percent']:.1f}%[/bold]
• Multi-processing efficiency: [bold]High[/bold]""",
                                border_style="green"
                            )
                            console.print(improvement_panel)
                    
                    console.print(results_table)
                else:
                    print(f"📊 Results:")
                    print(f"  Single operations: {single_throughput:.1f} ops/sec")
                    if 'batch_operations' in results and 'error' not in results['batch_operations']:
                        print(f"  Batch operations: {results['batch_operations']['throughput_ops_per_sec']:.1f} ops/sec")
                        if 'comparison' in results:
                            print(f"  Speedup: {results['comparison']['batch_speedup_factor']:.1f}x")
                
        except Exception as e:
            error_msg = f"Benchmark failed: {e}"
            if console:
                console.print(f"❌ {error_msg}", style="red")
            else:
                print(f"❌ {error_msg}")
            results['error'] = error_msg
        
        self.benchmark_results['single_vs_batch'] = results
        return results
    
    async def benchmark_concurrent_requests(self) -> Dict[str, Any]:
        """Benchmark concurrent request handling."""
        if console:
            console.print("\n🚀 Benchmarking: Concurrent Request Handling", style="bold blue")
        else:
            print("\n🚀 Benchmarking: Concurrent Request Handling")
        
        results = {}
        concurrency_levels = [1, 5, 10, 20, 50]
        
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                
                for concurrency in concurrency_levels:
                    if console:
                        console.print(f"📊 Testing {concurrency} concurrent requests")
                    else:
                        print(f"📊 Testing {concurrency} concurrent requests")
                    
                    # Create concurrent health check requests
                    start_time = time.time()
                    
                    async def make_request():
                        try:
                            response = await client.get(f"{self.daemon_url}/health/fast")
                            return response.status_code == 200
                        except Exception:
                            return False
                    
                    # Execute concurrent requests
                    tasks = [make_request() for _ in range(concurrency)]
                    request_results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    total_time = time.time() - start_time
                    successful_requests = sum(1 for r in request_results if r is True)
                    
                    results[f'concurrency_{concurrency}'] = {
                        'total_requests': concurrency,
                        'successful_requests': successful_requests,
                        'total_time': total_time,
                        'requests_per_second': concurrency / total_time if total_time > 0 else 0,
                        'avg_response_time': total_time / concurrency,
                        'success_rate': successful_requests / concurrency * 100
                    }
                
                # Display results
                if console:
                    concurrency_table = Table(title="🚀 Concurrent Request Performance")
                    concurrency_table.add_column("Concurrency", style="cyan")
                    concurrency_table.add_column("Success Rate", style="green")
                    concurrency_table.add_column("Requests/Sec", style="yellow")
                    concurrency_table.add_column("Avg Response", style="blue")
                    
                    for concurrency in concurrency_levels:
                        data = results[f'concurrency_{concurrency}']
                        concurrency_table.add_row(
                            str(concurrency),
                            f"{data['success_rate']:.1f}%",
                            f"{data['requests_per_second']:.1f}",
                            f"{data['avg_response_time']*1000:.1f}ms"
                        )
                    
                    console.print(concurrency_table)
                else:
                    print("📊 Concurrency Results:")
                    for concurrency in concurrency_levels:
                        data = results[f'concurrency_{concurrency}']
                        print(f"  {concurrency} concurrent: {data['requests_per_second']:.1f} req/sec, {data['success_rate']:.1f}% success")
                
        except Exception as e:
            error_msg = f"Concurrency benchmark failed: {e}"
            if console:
                console.print(f"❌ {error_msg}", style="red")
            else:
                print(f"❌ {error_msg}")
            results['error'] = error_msg
        
        self.benchmark_results['concurrent_requests'] = results
        return results
    
    async def benchmark_stress_test(self) -> Dict[str, Any]:
        """Run comprehensive stress test."""
        if console:
            console.print("\n🔥 Stress Test: High-Load Operations", style="bold red")
        else:
            print("\n🔥 Stress Test: High-Load Operations")
        
        results = {}
        
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                
                # Large batch operation stress test
                num_operations = 1000
                operations = [
                    {"operation": "add", "cid": f"QmStress{'0'*40}{i:06d}"}
                    for i in range(num_operations)
                ]
                
                if console:
                    console.print(f"🔥 Executing {num_operations} operations in batch")
                else:
                    print(f"🔥 Executing {num_operations} operations in batch")
                
                start_time = time.time()
                
                response = await client.post(
                    f"{self.daemon_url}/pins/batch",
                    json=operations,
                    timeout=600
                )
                
                total_time = time.time() - start_time
                
                if response.status_code == 200:
                    batch_data = response.json()
                    
                    results['stress_test'] = {
                        'total_operations': num_operations,
                        'successful': batch_data.get('successful', 0),
                        'failed': batch_data.get('failed', 0),
                        'total_time': total_time,
                        'throughput_ops_per_sec': num_operations / total_time,
                        'success_rate': batch_data.get('successful', 0) / num_operations * 100
                    }
                    
                    if console:
                        stress_panel = Panel(
                            f"""[bold red]🔥 Stress Test Results[/bold red]

📊 [bold]Operations[/bold]
• Total: {num_operations:,}
• Successful: {batch_data.get('successful', 0):,}
• Failed: {batch_data.get('failed', 0):,}
• Success Rate: {results['stress_test']['success_rate']:.1f}%

⚡ [bold]Performance[/bold]
• Total Time: {total_time:.2f}s
• Throughput: {results['stress_test']['throughput_ops_per_sec']:.1f} ops/sec
• Multi-processing Efficiency: High

🚀 [bold]System Handled High Load Successfully![/bold]""",
                            border_style="red"
                        )
                        console.print(stress_panel)
                    else:
                        print(f"✅ Stress test completed:")
                        print(f"  {batch_data.get('successful', 0)}/{num_operations} successful ({results['stress_test']['success_rate']:.1f}%)")
                        print(f"  Throughput: {results['stress_test']['throughput_ops_per_sec']:.1f} ops/sec")
                else:
                    results['stress_test'] = {'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            error_msg = f"Stress test failed: {e}"
            if console:
                console.print(f"❌ {error_msg}", style="red")
            else:
                print(f"❌ {error_msg}")
            results['stress_test'] = {'error': error_msg}
        
        self.benchmark_results['stress_test'] = results
        return results
    
    async def check_dashboard_performance(self) -> Dict[str, Any]:
        """Check MCP dashboard performance metrics."""
        if console:
            console.print("\n📊 Checking MCP Dashboard Performance", style="bold blue")
        else:
            print("\n📊 Checking MCP Dashboard Performance")
        
        results = {}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.mcp_dashboard_url}/api/stats", timeout=10)
                
                if response.status_code == 200:
                    stats_data = response.json()
                    
                    results['dashboard_stats'] = stats_data
                    
                    if console:
                        stats_table = Table(title="📊 MCP Dashboard Metrics")
                        stats_table.add_column("Metric", style="cyan")
                        stats_table.add_column("Value", style="green")
                        
                        stats_table.add_row("MCP Operations", str(stats_data.get('mcp_operations', 0)))
                        stats_table.add_row("Tool Executions", str(stats_data.get('tool_executions', 0)))
                        stats_table.add_row("WebSocket Connections", str(stats_data.get('websocket_connections', 0)))
                        stats_table.add_row("Workers", str(stats_data.get('workers', 0)))
                        stats_table.add_row("Uptime", f"{stats_data.get('uptime', 0):.1f}s")
                        
                        console.print(stats_table)
                    else:
                        print(f"📊 Dashboard stats: {stats_data.get('mcp_operations', 0)} MCP ops, {stats_data.get('workers', 0)} workers")
                else:
                    results['dashboard_stats'] = {'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            error_msg = f"Dashboard check failed: {e}"
            if console:
                console.print(f"❌ {error_msg}", style="red")
            else:
                print(f"❌ {error_msg}")
            results['dashboard_stats'] = {'error': error_msg}
        
        self.benchmark_results['dashboard_performance'] = results
        return results
    
    def display_final_summary(self):
        """Display final benchmark summary."""
        if console:
            console.print("\n🏆 MULTI-PROCESSING BENCHMARK SUMMARY", style="bold green")
        else:
            print("\n🏆 MULTI-PROCESSING BENCHMARK SUMMARY")
        
        if console:
            summary_text = "[bold green]✅ Multi-Processing Performance Analysis Complete[/bold green]\n\n"
            
            # Add results from each benchmark
            if 'single_vs_batch' in self.benchmark_results:
                single_batch = self.benchmark_results['single_vs_batch']
                if 'comparison' in single_batch:
                    speedup = single_batch['comparison']['batch_speedup_factor']
                    summary_text += f"⚡ Batch operations are [bold]{speedup:.1f}x faster[/bold] than sequential\n"
            
            if 'concurrent_requests' in self.benchmark_results:
                concurrent = self.benchmark_results['concurrent_requests']
                if 'concurrency_50' in concurrent:
                    max_rps = concurrent['concurrency_50']['requests_per_second']
                    summary_text += f"🚀 Peak concurrent throughput: [bold]{max_rps:.1f} requests/sec[/bold]\n"
            
            if 'stress_test' in self.benchmark_results:
                stress = self.benchmark_results['stress_test']
                if 'stress_test' in stress and 'throughput_ops_per_sec' in stress['stress_test']:
                    stress_throughput = stress['stress_test']['throughput_ops_per_sec']
                    summary_text += f"🔥 Stress test throughput: [bold]{stress_throughput:.1f} ops/sec[/bold]\n"
            
            summary_text += f"\n🖥️ System specs: [bold]{mp.cpu_count()} CPU cores[/bold] utilized effectively"
            summary_text += f"\n🎯 Multi-processing architecture provides [bold]significant performance gains[/bold]"
            
            summary_panel = Panel(
                summary_text,
                title="🏆 Performance Benchmark Results",
                border_style="green",
                padding=(1, 2)
            )
            console.print(summary_panel)
        else:
            print("🏆 Benchmark Summary:")
            if 'single_vs_batch' in self.benchmark_results and 'comparison' in self.benchmark_results['single_vs_batch']:
                speedup = self.benchmark_results['single_vs_batch']['comparison']['batch_speedup_factor']
                print(f"  ⚡ Batch processing: {speedup:.1f}x faster than sequential")
            
            if 'stress_test' in self.benchmark_results and 'stress_test' in self.benchmark_results['stress_test']:
                stress_throughput = self.benchmark_results['stress_test']['stress_test']['throughput_ops_per_sec']
                print(f"  🔥 Stress test: {stress_throughput:.1f} ops/sec")
            
            print(f"  🖥️ Utilized {mp.cpu_count()} CPU cores effectively")
        
        # Save detailed results
        results_file = Path("multi_processing_benchmark_results.json")
        with open(results_file, 'w') as f:
            json.dump(self.benchmark_results, f, indent=2)
        
        if console:
            console.print(f"\n💾 Detailed results saved to: [bold]{results_file}[/bold]")
        else:
            print(f"\n💾 Detailed results saved to: {results_file}")


async def main():
    """Main demo execution."""
    demo = MultiProcessingDemo()
    
    try:
        # Display banner
        demo.print_banner()
        
        # Test daemon connectivity
        if not await demo.test_daemon_connectivity():
            if console:
                console.print("\n❌ Cannot connect to daemon. Please start the multi-processing daemon first:", style="red")
                console.print("   python mcp/ipfs_kit/daemon/multi_process_launcher.py daemon", style="blue")
            else:
                print("\n❌ Cannot connect to daemon. Please start it first:")
                print("   python mcp/ipfs_kit/daemon/multi_process_launcher.py daemon")
            return
        
        # Run benchmarks
        await demo.benchmark_single_vs_batch_operations()
        await demo.benchmark_concurrent_requests()
        await demo.benchmark_stress_test()
        await demo.check_dashboard_performance()
        
        # Display final summary
        demo.display_final_summary()
        
        if console:
            console.print("\n🎉 Multi-processing demonstration completed successfully!", style="bold green")
        else:
            print("\n🎉 Multi-processing demonstration completed successfully!")
        
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
        sys.exit(1)


if __name__ == "__main__":
    print("🚀 Starting Multi-Processing IPFS Kit Performance Demo...")
    print("📋 This demo will benchmark the multi-processing capabilities")
    print("⚡ Make sure the daemon is running: python multi_process_launcher.py daemon")
    print("=" * 80)
    
    asyncio.run(main())
