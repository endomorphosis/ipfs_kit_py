#!/usr/bin/env python3
"""
Multi-Processing Enhanced IPFS Kit CLI.

This CLI uses concurrent operations for high throughput:
- Async HTTP operations for daemon communication
- Thread pools for I/O bound operations  
- Process pools for CPU intensive tasks
- Batch operations with parallel processing
- Progress bars for long-running operations
"""

import asyncio
import argparse
import concurrent.futures
import json
import logging
import multiprocessing as mp
import sys
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Optional

# Rich for beautiful CLI output
try:
    from rich.console import Console
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️ Install 'rich' for enhanced CLI experience: pip install rich")

# HTTP client for async operations
import httpx

# Core daemon communication
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from .daemon_client import IPFSKitDaemonClient

logger = logging.getLogger(__name__)

class MultiProcessIPFSKitCLI:
    """
    Multi-processing enhanced CLI for IPFS Kit operations.
    
    Features:
    - Concurrent HTTP requests to daemon
    - Batch operations with progress tracking
    - Parallel pin management
    - Background task monitoring
    - High-performance data processing
    """
    
    def __init__(self, 
                 daemon_url: str = "http://127.0.0.1:9999",
                 max_workers: int = None,
                 batch_size: int = 100):
        
        self.daemon_url = daemon_url
        self.daemon_client = IPFSKitDaemonClient(daemon_url)
        
        # Multi-processing configuration
        self.max_workers = max_workers or min(mp.cpu_count(), 16)
        self.batch_size = batch_size
        
        # Console for rich output
        self.console = Console() if RICH_AVAILABLE else None
        
        # Performance tracking
        self.operation_stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'start_time': None
        }
        
        logger.info(f"🔧 Multi-Processing CLI initialized")
        logger.info(f"🌐 Daemon: {daemon_url}")
        logger.info(f"⚡ Workers: {self.max_workers}")
        logger.info(f"📦 Batch size: {batch_size}")
    
    def print_status(self, message: str, style: str = "info"):
        """Print status message with formatting."""
        if self.console:
            if style == "success":
                self.console.print(f"✅ {message}", style="green")
            elif style == "error":
                self.console.print(f"❌ {message}", style="red")
            elif style == "warning":
                self.console.print(f"⚠️ {message}", style="yellow")
            else:
                self.console.print(f"ℹ️ {message}", style="blue")
        else:
            print(f"{message}")
    
    async def health_check(self, fast: bool = False) -> Dict[str, Any]:
        """Perform health check with optional fast mode."""
        try:
            self.print_status("Checking daemon health...")
            
            start_time = time.time()
            
            endpoint = "/health/fast" if fast else "/health"
            health_status = await self.daemon_client.get_health(endpoint=endpoint)
            
            response_time = (time.time() - start_time) * 1000
            
            if self.console:
                # Create health status table
                table = Table(title="🏥 Daemon Health Status")
                table.add_column("Component", style="cyan")
                table.add_column("Status", style="green")
                table.add_column("Details")
                
                # Add daemon info
                daemon_status = "🟢 Running" if health_status.get('daemon_running') else "🔴 Stopped"
                table.add_row("Daemon", daemon_status, f"Response: {response_time:.1f}ms")
                
                if 'workers' in health_status:
                    table.add_row("Workers", str(health_status['workers']), "Multi-processing enabled")
                
                if 'active_operations' in health_status:
                    table.add_row("Active Ops", str(health_status['active_operations']), "Currently processing")
                
                if 'total_operations' in health_status:
                    table.add_row("Total Ops", str(health_status['total_operations']), "Lifetime count")
                
                # Add backend health if available
                if 'backends' in health_status:
                    for backend, status in health_status['backends'].items():
                        backend_status = "🟢 Healthy" if status.get('healthy') else "🔴 Unhealthy"
                        table.add_row(f"Backend ({backend})", backend_status, status.get('status', 'Unknown'))
                
                self.console.print(table)
            else:
                print(f"✅ Health check complete: {json.dumps(health_status, indent=2)}")
            
            return health_status
            
        except Exception as e:
            self.print_status(f"Health check failed: {e}", "error")
            return {"success": False, "error": str(e)}
    
    async def list_pins_concurrent(self, limit: int = None) -> Dict[str, Any]:
        """List pins with concurrent processing."""
        try:
            self.print_status("Fetching pins with concurrent processing...")
            
            start_time = time.time()
            
            # Get pins data
            pins_data = await self.daemon_client.list_pins()
            
            processing_time = (time.time() - start_time) * 1000
            
            pins = pins_data.get('pins', [])
            total_pins = pins_data.get('total', len(pins))
            
            if limit:
                pins = pins[:limit]
            
            if self.console:
                # Create pins table
                table = Table(title=f"📌 Pin List ({len(pins)}/{total_pins})")
                table.add_column("CID", style="cyan", width=50)
                table.add_column("Name", style="green")
                table.add_column("Size", style="yellow")
                table.add_column("Type", style="blue")
                
                for pin in pins[:20]:  # Show first 20 for readability
                    cid = pin.get('cid', 'Unknown')[:47] + "..." if len(pin.get('cid', '')) > 50 else pin.get('cid', 'Unknown')
                    name = pin.get('name', 'Unnamed')[:20]
                    size = pin.get('size', 'Unknown')
                    pin_type = pin.get('type', 'Unknown')
                    
                    table.add_row(cid, name, str(size), pin_type)
                
                if len(pins) > 20:
                    table.add_row("...", f"... and {len(pins) - 20} more", "...", "...")
                
                self.console.print(table)
                self.console.print(f"🚀 Processing time: {processing_time:.1f}ms")
            else:
                print(f"✅ Found {len(pins)} pins (total: {total_pins})")
                for pin in pins[:10]:  # Show first 10
                    print(f"  📌 {pin.get('cid', 'Unknown')[:50]}... - {pin.get('name', 'Unnamed')}")
            
            return pins_data
            
        except Exception as e:
            self.print_status(f"Failed to list pins: {e}", "error")
            return {"pins": [], "error": str(e)}
    
    async def batch_pin_operations(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process pin operations in parallel batches."""
        try:
            total_ops = len(operations)
            self.print_status(f"Processing {total_ops} pin operations in parallel batches...")
            
            self.operation_stats['start_time'] = time.time()
            self.operation_stats['total_operations'] = total_ops
            
            # Process in batches for optimal performance
            batch_results = []
            
            if self.console:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    TimeElapsedColumn(),
                    console=self.console
                ) as progress:
                    
                    task = progress.add_task("Processing batches...", total=total_ops)
                    
                    for i in range(0, total_ops, self.batch_size):
                        batch = operations[i:i + self.batch_size]
                        
                        # Process batch concurrently
                        batch_result = await self.daemon_client.batch_pin_operations(batch)
                        batch_results.append(batch_result)
                        
                        # Update progress
                        progress.update(task, advance=len(batch))
                        
                        # Update statistics
                        if batch_result.get('success'):
                            self.operation_stats['successful_operations'] += batch_result.get('successful', 0)
                            self.operation_stats['failed_operations'] += batch_result.get('failed', 0)
            else:
                # Process without progress bar
                for i in range(0, total_ops, self.batch_size):
                    batch = operations[i:i + self.batch_size]
                    batch_result = await self.daemon_client.batch_pin_operations(batch)
                    batch_results.append(batch_result)
                    
                    print(f"⚡ Processed batch {i//self.batch_size + 1}/{(total_ops + self.batch_size - 1)//self.batch_size}")
            
            # Aggregate results
            total_successful = sum(r.get('successful', 0) for r in batch_results)
            total_failed = sum(r.get('failed', 0) for r in batch_results)
            
            processing_time = time.time() - self.operation_stats['start_time']
            
            result = {
                "success": True,
                "total_operations": total_ops,
                "successful": total_successful,
                "failed": total_failed,
                "batches_processed": len(batch_results),
                "processing_time_seconds": processing_time,
                "operations_per_second": total_ops / processing_time if processing_time > 0 else 0,
                "batch_results": batch_results
            }
            
            if self.console:
                # Display results summary
                panel = Panel(
                    f"""[green]✅ Batch Processing Complete[/green]
                    
📊 [bold]Results Summary[/bold]
• Total Operations: {total_ops}
• Successful: {total_successful} 
• Failed: {total_failed}
• Success Rate: {(total_successful/total_ops*100):.1f}%

⚡ [bold]Performance[/bold]
• Processing Time: {processing_time:.2f}s
• Operations/Second: {result['operations_per_second']:.1f}
• Batches: {len(batch_results)}
• Workers: {self.max_workers}""",
                    title="🚀 Batch Operation Results",
                    border_style="green"
                )
                self.console.print(panel)
            else:
                print(f"✅ Batch processing complete: {total_successful}/{total_ops} successful")
                print(f"⚡ Performance: {result['operations_per_second']:.1f} ops/sec")
            
            return result
            
        except Exception as e:
            self.print_status(f"Batch operation failed: {e}", "error")
            return {"success": False, "error": str(e)}
    
    async def concurrent_pin_add(self, cids: List[str]) -> Dict[str, Any]:
        """Add multiple pins concurrently."""
        operations = [{"operation": "add", "cid": cid} for cid in cids]
        return await self.batch_pin_operations(operations)
    
    async def concurrent_pin_remove(self, cids: List[str]) -> Dict[str, Any]:
        """Remove multiple pins concurrently."""
        operations = [{"operation": "remove", "cid": cid} for cid in cids]
        return await self.batch_pin_operations(operations)
    
    async def performance_monitor(self, duration: int = 60) -> Dict[str, Any]:
        """Monitor daemon performance for specified duration."""
        try:
            self.print_status(f"Monitoring daemon performance for {duration} seconds...")
            
            performance_data = []
            
            if self.console:
                with Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    TimeElapsedColumn(),
                    console=self.console
                ) as progress:
                    
                    task = progress.add_task("Monitoring performance...", total=duration)
                    
                    for i in range(duration):
                        # Get performance metrics
                        perf_data = await self.daemon_client._make_request("GET", "/performance")
                        perf_data['timestamp'] = time.time()
                        performance_data.append(perf_data)
                        
                        progress.update(task, advance=1)
                        await asyncio.sleep(1)
            else:
                for i in range(duration):
                    perf_data = await self.daemon_client._make_request("GET", "/performance")
                    perf_data['timestamp'] = time.time()
                    performance_data.append(perf_data)
                    
                    print(f"📊 Monitoring... {i+1}/{duration}s")
                    await asyncio.sleep(1)
            
            # Analyze performance data
            avg_active_ops = sum(d.get('active_operations', 0) for d in performance_data) / len(performance_data)
            max_active_ops = max(d.get('active_operations', 0) for d in performance_data)
            total_ops_increase = performance_data[-1].get('total_operations', 0) - performance_data[0].get('total_operations', 0)
            
            analysis = {
                "monitoring_duration": duration,
                "samples_collected": len(performance_data),
                "average_active_operations": avg_active_ops,
                "max_active_operations": max_active_ops,
                "total_operations_processed": total_ops_increase,
                "operations_per_second": total_ops_increase / duration,
                "raw_data": performance_data
            }
            
            if self.console:
                # Display performance analysis
                table = Table(title="📊 Performance Analysis")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                
                table.add_row("Duration", f"{duration}s")
                table.add_row("Samples", str(len(performance_data)))
                table.add_row("Avg Active Ops", f"{avg_active_ops:.1f}")
                table.add_row("Max Active Ops", str(max_active_ops))
                table.add_row("Total Ops Processed", str(total_ops_increase))
                table.add_row("Ops/Second", f"{analysis['operations_per_second']:.2f}")
                
                self.console.print(table)
            else:
                print(f"📊 Performance Analysis:")
                print(f"  Average Active Operations: {avg_active_ops:.1f}")
                print(f"  Operations per Second: {analysis['operations_per_second']:.2f}")
            
            return analysis
            
        except Exception as e:
            self.print_status(f"Performance monitoring failed: {e}", "error")
            return {"success": False, "error": str(e)}
    
    async def stress_test(self, num_operations: int = 1000, operation_type: str = "mixed") -> Dict[str, Any]:
        """Run stress test with many concurrent operations."""
        try:
            self.print_status(f"Running stress test: {num_operations} {operation_type} operations...")
            
            # Generate test operations
            operations = []
            test_cid_base = "QmTest" + "0" * 40  # Test CID format
            
            if operation_type == "add":
                operations = [{"operation": "add", "cid": f"{test_cid_base}{i:06d}"} 
                             for i in range(num_operations)]
            elif operation_type == "remove":
                operations = [{"operation": "remove", "cid": f"{test_cid_base}{i:06d}"} 
                             for i in range(num_operations)]
            else:  # mixed
                operations = []
                for i in range(num_operations):
                    op_type = "add" if i % 2 == 0 else "remove"
                    operations.append({"operation": op_type, "cid": f"{test_cid_base}{i:06d}"})
            
            # Run stress test
            start_time = time.time()
            result = await self.batch_pin_operations(operations)
            total_time = time.time() - start_time
            
            # Add stress test specific metrics
            result.update({
                "stress_test": True,
                "operation_type": operation_type,
                "total_time_seconds": total_time,
                "throughput_ops_per_second": num_operations / total_time,
                "workers_used": self.max_workers,
                "batch_size": self.batch_size
            })
            
            if self.console:
                panel = Panel(
                    f"""[green]🚀 Stress Test Complete[/green]
                    
📈 [bold]Stress Test Results[/bold]
• Operation Type: {operation_type}
• Total Operations: {num_operations}
• Total Time: {total_time:.2f}s
• Throughput: {result['throughput_ops_per_second']:.1f} ops/sec
• Workers: {self.max_workers}
• Batch Size: {self.batch_size}

✅ [bold]Success Rate[/bold]
• Successful: {result.get('successful', 0)}
• Failed: {result.get('failed', 0)}
• Rate: {(result.get('successful', 0)/num_operations*100):.1f}%""",
                    title="🔥 Stress Test Results",
                    border_style="red"
                )
                self.console.print(panel)
            else:
                print(f"🔥 Stress test complete!")
                print(f"   Throughput: {result['throughput_ops_per_second']:.1f} ops/sec")
                print(f"   Success rate: {(result.get('successful', 0)/num_operations*100):.1f}%")
            
            return result
            
        except Exception as e:
            self.print_status(f"Stress test failed: {e}", "error")
            return {"success": False, "error": str(e)}


async def main():
    """Main CLI entry point with multi-processing support."""
    parser = argparse.ArgumentParser(description="Multi-Processing IPFS Kit CLI")
    parser.add_argument("--daemon-url", default="http://127.0.0.1:9999", 
                       help="Daemon URL")
    parser.add_argument("--workers", type=int, 
                       help="Max worker processes")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="Batch size for operations")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Check daemon health")
    health_parser.add_argument("--fast", action="store_true", help="Fast health check")
    
    # Pin commands
    pin_parser = subparsers.add_parser("pins", help="Pin management")
    pin_subparsers = pin_parser.add_subparsers(dest="pin_command")
    
    pin_subparsers.add_parser("list", help="List pins").add_argument("--limit", type=int, help="Limit results")
    
    add_parser = pin_subparsers.add_parser("add", help="Add pins")
    add_parser.add_argument("cids", nargs="+", help="CIDs to add")
    
    remove_parser = pin_subparsers.add_parser("remove", help="Remove pins")
    remove_parser.add_argument("cids", nargs="+", help="CIDs to remove")
    
    batch_parser = pin_subparsers.add_parser("batch", help="Batch operations")
    batch_parser.add_argument("operations_file", help="JSON file with operations")
    
    # Performance commands
    perf_parser = subparsers.add_parser("performance", help="Performance tools")
    perf_subparsers = perf_parser.add_subparsers(dest="perf_command")
    
    monitor_parser = perf_subparsers.add_parser("monitor", help="Monitor performance")
    monitor_parser.add_argument("--duration", type=int, default=60, help="Monitor duration in seconds")
    
    stress_parser = perf_subparsers.add_parser("stress", help="Run stress test")
    stress_parser.add_argument("--operations", type=int, default=1000, help="Number of operations")
    stress_parser.add_argument("--type", choices=["add", "remove", "mixed"], default="mixed", help="Operation type")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize CLI
    cli = MultiProcessIPFSKitCLI(
        daemon_url=args.daemon_url,
        max_workers=args.workers,
        batch_size=args.batch_size
    )
    
    # Execute commands
    try:
        if args.command == "health":
            await cli.health_check(fast=args.fast)
            
        elif args.command == "pins":
            if args.pin_command == "list":
                await cli.list_pins_concurrent(limit=args.limit)
            elif args.pin_command == "add":
                await cli.concurrent_pin_add(args.cids)
            elif args.pin_command == "remove":
                await cli.concurrent_pin_remove(args.cids)
            elif args.pin_command == "batch":
                with open(args.operations_file, 'r') as f:
                    operations = json.load(f)
                await cli.batch_pin_operations(operations)
            else:
                pin_parser.print_help()
                
        elif args.command == "performance":
            if args.perf_command == "monitor":
                await cli.performance_monitor(duration=args.duration)
            elif args.perf_command == "stress":
                await cli.stress_test(num_operations=args.operations, operation_type=args.type)
            else:
                perf_parser.print_help()
                
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n🛑 CLI interrupted by user")
    except Exception as e:
        print(f"❌ CLI error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Set multiprocessing start method
    mp.set_start_method('spawn', force=True)
    asyncio.run(main())
