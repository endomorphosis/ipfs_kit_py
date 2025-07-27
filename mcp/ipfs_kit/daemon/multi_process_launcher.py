#!/usr/bin/env python3
"""
Multi-Processing Enhanced Service Launcher.

This launcher coordinates multiple high-performance services:
- Multi-processing daemon with worker processes
- Multi-processing MCP server with process pools
- Multi-processing CLI with concurrent operations
- Performance monitoring and coordination
- Resource management and optimization
"""

import asyncio
import argparse
import logging
import multiprocessing as mp
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List, Optional

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
    print("⚠️ Install 'rich' for enhanced output: pip install rich")

# Core components
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from .multi_process_daemon import MultiProcessIPFSKitDaemon
from .multi_process_mcp_server import MultiProcessMCPServer
from .multi_process_cli import MultiProcessIPFSKitCLI

logger = logging.getLogger(__name__)

class MultiProcessServiceLauncher:
    """
    Multi-processing service launcher for high-performance IPFS Kit operations.
    
    Features:
    - Coordinated launch of multiple services
    - Resource optimization across services
    - Performance monitoring and load balancing
    - Graceful shutdown and cleanup
    - Health monitoring and auto-restart
    """
    
    def __init__(self, 
                 daemon_host: str = "127.0.0.1",
                 daemon_port: int = 9999,
                 mcp_web_host: str = "127.0.0.1", 
                 mcp_web_port: int = 8080,
                 config_dir: str = "/tmp/ipfs_kit_config",
                 data_dir: str = None,
                 total_workers: int = None):
        
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self.mcp_web_host = mcp_web_host
        self.mcp_web_port = mcp_web_port
        self.config_dir = Path(config_dir)
        self.data_dir = Path(data_dir or str(Path.home() / ".ipfs_kit"))
        
        # Resource allocation
        total_cpus = mp.cpu_count()
        self.total_workers = total_workers or min(total_cpus, 16)
        
        # Distribute workers across services
        self.daemon_workers = max(1, self.total_workers // 2)
        self.mcp_workers = max(1, self.total_workers // 3)
        self.cli_workers = max(1, self.total_workers // 4)
        
        # Service instances
        self.daemon = None
        self.mcp_server = None
        self.cli = None
        
        # Process management
        self.running_services = {}
        self.service_processes = {}
        
        # Performance monitoring
        self.performance_monitor = None
        self.monitoring_active = False
        
        # Console for rich output
        self.console = Console() if RICH_AVAILABLE else None
        
        logger.info(f"🔧 Multi-Processing Service Launcher initialized")
        logger.info(f"🖥️ Total CPUs: {total_cpus}")
        logger.info(f"⚡ Total workers: {self.total_workers}")
        logger.info(f"🔧 Daemon workers: {self.daemon_workers}")
        logger.info(f"🌐 MCP workers: {self.mcp_workers}")
        logger.info(f"💻 CLI workers: {self.cli_workers}")
    
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
    
    def print_banner(self):
        """Print startup banner."""
        if self.console:
            banner = Panel(
                f"""[bold cyan]⚡ MULTI-PROCESSING IPFS KIT SERVICES[/bold cyan]

🔧 [bold]Resource Allocation[/bold]
• Total CPU Cores: {mp.cpu_count()}
• Total Workers: {self.total_workers}
• Daemon Workers: {self.daemon_workers}
• MCP Workers: {self.mcp_workers}
• CLI Workers: {self.cli_workers}

🌐 [bold]Service Endpoints[/bold]
• Daemon API: http://{self.daemon_host}:{self.daemon_port}
• MCP Dashboard: http://{self.mcp_web_host}:{self.mcp_web_port}
• Config Directory: {self.config_dir}
• Data Directory: {self.data_dir}

🚀 [bold]High-Performance Features[/bold]
• Multi-processing daemon with worker pools
• Concurrent MCP server with process pools
• Batch operations with parallel processing
• Real-time performance monitoring
• Automatic load balancing""",
                title="🚀 IPFS Kit Multi-Processing Services",
                border_style="blue",
                padding=(1, 2)
            )
            self.console.print(banner)
        else:
            print("=" * 80)
            print("⚡ MULTI-PROCESSING IPFS KIT SERVICES")
            print("=" * 80)
            print(f"🔧 Total Workers: {self.total_workers}")
            print(f"🌐 Daemon: http://{self.daemon_host}:{self.daemon_port}")
            print(f"📊 Dashboard: http://{self.mcp_web_host}:{self.mcp_web_port}")
            print("=" * 80)
    
    async def start_daemon(self) -> bool:
        """Start the multi-processing daemon."""
        try:
            self.print_status("Starting multi-processing daemon...", "info")
            
            self.daemon = MultiProcessIPFSKitDaemon(
                host=self.daemon_host,
                port=self.daemon_port,
                config_dir=str(self.config_dir),
                data_dir=str(self.data_dir),
                num_workers=self.daemon_workers
            )
            
            # Start daemon in background task
            daemon_task = asyncio.create_task(self.daemon.start())
            self.running_services['daemon'] = daemon_task
            
            # Wait a bit for daemon to start
            await asyncio.sleep(2)
            
            # Verify daemon is running
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"http://{self.daemon_host}:{self.daemon_port}/health/fast",
                        timeout=5
                    )
                    if response.status_code == 200:
                        self.print_status("Multi-processing daemon started successfully", "success")
                        return True
                    else:
                        self.print_status(f"Daemon health check failed: {response.status_code}", "error")
                        return False
                        
            except Exception as e:
                self.print_status(f"Failed to verify daemon startup: {e}", "error")
                return False
                
        except Exception as e:
            self.print_status(f"Failed to start daemon: {e}", "error")
            return False
    
    async def start_mcp_server(self) -> bool:
        """Start the multi-processing MCP server."""
        try:
            self.print_status("Starting multi-processing MCP server...", "info")
            
            daemon_url = f"http://{self.daemon_host}:{self.daemon_port}"
            
            self.mcp_server = MultiProcessMCPServer(
                daemon_url=daemon_url,
                web_host=self.mcp_web_host,
                web_port=self.mcp_web_port,
                max_workers=self.mcp_workers
            )
            
            # Start MCP server in background task
            mcp_task = asyncio.create_task(self.mcp_server.start())
            self.running_services['mcp_server'] = mcp_task
            
            # Wait a bit for MCP server to start
            await asyncio.sleep(2)
            
            # Verify MCP server dashboard is accessible
            try:
                import httpx
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"http://{self.mcp_web_host}:{self.mcp_web_port}/api/stats",
                        timeout=5
                    )
                    if response.status_code == 200:
                        self.print_status("Multi-processing MCP server started successfully", "success")
                        return True
                    else:
                        self.print_status(f"MCP server health check failed: {response.status_code}", "error")
                        return False
                        
            except Exception as e:
                self.print_status(f"Failed to verify MCP server startup: {e}", "error")
                return False
                
        except Exception as e:
            self.print_status(f"Failed to start MCP server: {e}", "error")
            return False
    
    def setup_cli(self) -> bool:
        """Setup the multi-processing CLI."""
        try:
            self.print_status("Setting up multi-processing CLI...", "info")
            
            daemon_url = f"http://{self.daemon_host}:{self.daemon_port}"
            
            self.cli = MultiProcessIPFSKitCLI(
                daemon_url=daemon_url,
                max_workers=self.cli_workers,
                batch_size=100
            )
            
            self.print_status("Multi-processing CLI ready", "success")
            return True
            
        except Exception as e:
            self.print_status(f"Failed to setup CLI: {e}", "error")
            return False
    
    async def start_performance_monitoring(self):
        """Start performance monitoring for all services."""
        try:
            self.print_status("Starting performance monitoring...", "info")
            
            self.monitoring_active = True
            
            async def monitor_loop():
                """Performance monitoring loop."""
                while self.monitoring_active:
                    try:
                        # Collect performance data from all services
                        performance_data = await self._collect_performance_data()
                        
                        # Display performance summary
                        if self.console:
                            await self._display_performance_dashboard(performance_data)
                        else:
                            await self._display_performance_text(performance_data)
                        
                        # Wait 10 seconds before next update
                        await asyncio.sleep(10)
                        
                    except Exception as e:
                        logger.error(f"Performance monitoring error: {e}")
                        await asyncio.sleep(30)  # Wait longer on error
            
            # Start monitoring in background
            monitor_task = asyncio.create_task(monitor_loop())
            self.running_services['performance_monitor'] = monitor_task
            
            self.print_status("Performance monitoring started", "success")
            
        except Exception as e:
            self.print_status(f"Failed to start performance monitoring: {e}", "error")
    
    async def _collect_performance_data(self) -> Dict[str, Any]:
        """Collect performance data from all services."""
        performance_data = {
            'timestamp': time.time(),
            'daemon': {},
            'mcp_server': {},
            'system': {}
        }
        
        try:
            # Get daemon performance data
            import httpx
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        f"http://{self.daemon_host}:{self.daemon_port}/performance",
                        timeout=5
                    )
                    if response.status_code == 200:
                        performance_data['daemon'] = response.json()
                except Exception as e:
                    performance_data['daemon'] = {'error': str(e)}
                
                # Get MCP server stats
                try:
                    response = await client.get(
                        f"http://{self.mcp_web_host}:{self.mcp_web_port}/api/stats",
                        timeout=5
                    )
                    if response.status_code == 200:
                        performance_data['mcp_server'] = response.json()
                except Exception as e:
                    performance_data['mcp_server'] = {'error': str(e)}
            
            # Get system stats
            try:
                import psutil
                performance_data['system'] = {
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_usage': psutil.disk_usage('/').percent,
                    'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
                }
            except ImportError:
                performance_data['system'] = {'error': 'psutil not available'}
            
        except Exception as e:
            logger.error(f"Error collecting performance data: {e}")
        
        return performance_data
    
    async def _display_performance_dashboard(self, data: Dict[str, Any]):
        """Display performance dashboard with rich formatting."""
        if not self.console:
            return
        
        # Clear screen for dashboard update
        self.console.clear()
        
        # Create performance table
        table = Table(title="📊 Multi-Processing Services Performance")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Workers", style="yellow")
        table.add_column("Operations", style="blue")
        table.add_column("Response Time", style="magenta")
        
        # Daemon stats
        daemon_data = data.get('daemon', {})
        daemon_status = "🟢 Running" if not daemon_data.get('error') else "🔴 Error"
        daemon_workers = str(daemon_data.get('workers', 'N/A'))
        daemon_ops = str(daemon_data.get('total_operations', 'N/A'))
        daemon_response = f"{daemon_data.get('memory_usage', {}).get('rss_mb', 0):.1f}MB"
        
        table.add_row("Daemon", daemon_status, daemon_workers, daemon_ops, daemon_response)
        
        # MCP server stats
        mcp_data = data.get('mcp_server', {})
        mcp_status = "🟢 Running" if not mcp_data.get('error') else "🔴 Error"
        mcp_workers = str(mcp_data.get('workers', 'N/A'))
        mcp_ops = str(mcp_data.get('mcp_operations', 'N/A'))
        mcp_response = f"{mcp_data.get('total_response_time', 0) / max(mcp_data.get('mcp_operations', 1), 1):.1f}ms"
        
        table.add_row("MCP Server", mcp_status, mcp_workers, mcp_ops, mcp_response)
        
        # System stats
        system_data = data.get('system', {})
        system_status = "🟢 Healthy" if system_data.get('cpu_percent', 0) < 80 else "⚠️ High Load"
        system_workers = str(self.total_workers)
        system_ops = f"CPU: {system_data.get('cpu_percent', 0):.1f}%"
        system_response = f"MEM: {system_data.get('memory_percent', 0):.1f}%"
        
        table.add_row("System", system_status, system_workers, system_ops, system_response)
        
        self.console.print(table)
        
        # Display service endpoints
        endpoints_panel = Panel(
            f"""[bold]🌐 Service Endpoints[/bold]
• Daemon API: http://{self.daemon_host}:{self.daemon_port}
• MCP Dashboard: http://{self.mcp_web_host}:{self.mcp_web_port}
• Health Check: http://{self.daemon_host}:{self.daemon_port}/health/fast
• Performance: http://{self.daemon_host}:{self.daemon_port}/performance

[bold]⚡ Resource Usage[/bold]
• Total Workers: {self.total_workers}
• Active Services: {len([s for s in self.running_services.values() if not s.done()])}
• Uptime: {time.time() - data.get('timestamp', time.time()):.0f}s""",
            title="🚀 Service Status",
            border_style="green"
        )
        self.console.print(endpoints_panel)
    
    async def _display_performance_text(self, data: Dict[str, Any]):
        """Display performance data in text format."""
        print(f"\n📊 Performance Update - {time.strftime('%H:%M:%S')}")
        print("-" * 50)
        
        # Daemon stats
        daemon_data = data.get('daemon', {})
        print(f"🔧 Daemon: {daemon_data.get('workers', 'N/A')} workers, {daemon_data.get('total_operations', 'N/A')} ops")
        
        # MCP server stats
        mcp_data = data.get('mcp_server', {})
        print(f"🌐 MCP Server: {mcp_data.get('workers', 'N/A')} workers, {mcp_data.get('mcp_operations', 'N/A')} ops")
        
        # System stats
        system_data = data.get('system', {})
        print(f"🖥️ System: CPU {system_data.get('cpu_percent', 0):.1f}%, MEM {system_data.get('memory_percent', 0):.1f}%")
        print("-" * 50)
    
    async def run_all_services(self):
        """Run all services with performance monitoring."""
        try:
            self.print_banner()
            
            # Start daemon first
            self.print_status("🔧 Starting daemon service...", "info")
            if not await self.start_daemon():
                self.print_status("Failed to start daemon - aborting", "error")
                return False
            
            # Start MCP server
            self.print_status("🌐 Starting MCP server...", "info")
            if not await self.start_mcp_server():
                self.print_status("Failed to start MCP server - continuing with daemon only", "warning")
            
            # Setup CLI
            self.print_status("💻 Setting up CLI...", "info")
            if not self.setup_cli():
                self.print_status("Failed to setup CLI - continuing without CLI", "warning")
            
            # Start performance monitoring
            await self.start_performance_monitoring()
            
            # Display success message
            if self.console:
                success_panel = Panel(
                    f"""[bold green]🎉 All Services Started Successfully![/bold green]

🔗 [bold]Quick Access[/bold]
• Dashboard: http://{self.mcp_web_host}:{self.mcp_web_port}
• API: http://{self.daemon_host}:{self.daemon_port}/health
• CLI: python multi_process_cli.py --help

⚡ [bold]Performance Features Active[/bold]
• Multi-processing daemon with {self.daemon_workers} workers
• Concurrent MCP server with {self.mcp_workers} workers  
• Batch CLI operations with {self.cli_workers} workers
• Real-time monitoring and metrics

🔥 [bold]Ready for High-Throughput Operations![/bold]""",
                    title="✅ Multi-Processing Services Ready",
                    border_style="green"
                )
                self.console.print(success_panel)
            else:
                print("✅ All services started successfully!")
                print(f"🌐 Dashboard: http://{self.mcp_web_host}:{self.mcp_web_port}")
                print(f"🔗 API: http://{self.daemon_host}:{self.daemon_port}")
            
            # Wait for services to run
            await self._wait_for_services()
            
            return True
            
        except Exception as e:
            self.print_status(f"Failed to run services: {e}", "error")
            return False
    
    async def _wait_for_services(self):
        """Wait for all services to complete."""
        try:
            # Wait for all running services
            if self.running_services:
                await asyncio.gather(*self.running_services.values(), return_exceptions=True)
        except KeyboardInterrupt:
            self.print_status("Services interrupted by user", "warning")
        except Exception as e:
            self.print_status(f"Service error: {e}", "error")
    
    async def stop_all_services(self):
        """Stop all running services gracefully."""
        self.print_status("🛑 Stopping all services...", "info")
        
        # Stop performance monitoring
        self.monitoring_active = False
        
        # Stop all running services
        for service_name, service_task in self.running_services.items():
            try:
                if not service_task.done():
                    self.print_status(f"Stopping {service_name}...", "info")
                    service_task.cancel()
                    
                    try:
                        await asyncio.wait_for(service_task, timeout=10)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                        
            except Exception as e:
                logger.error(f"Error stopping {service_name}: {e}")
        
        # Stop individual service instances
        if self.daemon:
            try:
                await self.daemon.stop()
            except Exception as e:
                logger.error(f"Error stopping daemon: {e}")
        
        if self.mcp_server:
            try:
                await self.mcp_server.stop()
            except Exception as e:
                logger.error(f"Error stopping MCP server: {e}")
        
        self.print_status("All services stopped", "success")


async def main():
    """Main entry point for multi-processing service launcher."""
    parser = argparse.ArgumentParser(description="Multi-Processing IPFS Kit Service Launcher")
    
    # Service selection
    parser.add_argument("mode", choices=["daemon", "mcp", "cli", "all"], 
                       help="Services to run")
    
    # Daemon configuration
    parser.add_argument("--daemon-host", default="127.0.0.1", help="Daemon host")
    parser.add_argument("--daemon-port", type=int, default=9999, help="Daemon port")
    
    # MCP server configuration
    parser.add_argument("--mcp-host", default="127.0.0.1", help="MCP web host")
    parser.add_argument("--mcp-port", type=int, default=8080, help="MCP web port")
    
    # Resource configuration
    parser.add_argument("--workers", type=int, help="Total worker processes")
    parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Configuration directory")
    parser.add_argument("--data-dir", help="Data directory")
    
    # CLI options
    parser.add_argument("--cli-command", help="CLI command to run (for cli mode)")
    parser.add_argument("--cli-args", nargs="*", help="CLI arguments")
    
    # Monitoring
    parser.add_argument("--no-monitoring", action="store_true", help="Disable performance monitoring")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create service launcher
    launcher = MultiProcessServiceLauncher(
        daemon_host=args.daemon_host,
        daemon_port=args.daemon_port,
        mcp_web_host=args.mcp_host,
        mcp_web_port=args.mcp_port,
        config_dir=args.config_dir,
        data_dir=args.data_dir,
        total_workers=args.workers
    )
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}, shutting down...")
        asyncio.create_task(launcher.stop_all_services())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if args.mode == "daemon":
            # Run daemon only
            await launcher.start_daemon()
            await launcher._wait_for_services()
            
        elif args.mode == "mcp":
            # Run MCP server (requires daemon)
            await launcher.start_daemon()
            await launcher.start_mcp_server()
            await launcher._wait_for_services()
            
        elif args.mode == "cli":
            # Run CLI command
            launcher.setup_cli()
            
            if args.cli_command:
                # Execute specific CLI command
                cli_args = [args.cli_command] + (args.cli_args or [])
                
                if args.cli_command == "health":
                    await launcher.cli.health_check()
                elif args.cli_command == "pins" and args.cli_args:
                    if args.cli_args[0] == "list":
                        await launcher.cli.list_pins_concurrent()
                    # Add more CLI commands as needed
                else:
                    print(f"CLI command not implemented: {args.cli_command}")
            else:
                print("Use --cli-command to specify CLI operation")
                
        elif args.mode == "all":
            # Run all services
            await launcher.run_all_services()
            
    except KeyboardInterrupt:
        print("\n🛑 Services interrupted by user")
    except Exception as e:
        print(f"❌ Service error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        await launcher.stop_all_services()


if __name__ == "__main__":
    # Set multiprocessing start method for better performance
    mp.set_start_method('spawn', force=True)
    asyncio.run(main())
