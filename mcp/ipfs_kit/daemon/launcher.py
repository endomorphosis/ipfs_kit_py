#!/usr/bin/env python3
"""
IPFS Kit Service Launcher.

This script can launch different components of the IPFS Kit system:
- daemon: The backend daemon that manages all heavy operations
- mcp: The lightweight MCP server that communicates with the daemon
- cli: The CLI tool for command-line operations
- all: Start both daemon and MCP server
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

class IPFSKitServiceLauncher:
    """Service launcher for IPFS Kit components."""
    
    def __init__(self):
        self.processes: List[subprocess.Popen] = []
        self.daemon_process: Optional[subprocess.Popen] = None
        self.mcp_process: Optional[subprocess.Popen] = None
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        print(f"\n🛑 Received signal {signum}, shutting down services...")
        self.stop_all()
        sys.exit(0)
    
    def start_daemon(self, 
                    host: str = "127.0.0.1",
                    port: int = 9999,
                    config_dir: str = "/tmp/ipfs_kit_config",
                    data_dir: str = None,
                    debug: bool = False) -> bool:
        """Start the IPFS Kit daemon."""
        print("🔧 Starting IPFS Kit Daemon...")
        
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "ipfs_kit_daemon.py"),
            "--host", host,
            "--port", str(port),
            "--config-dir", config_dir
        ]
        
        if data_dir:
            cmd.extend(["--data-dir", data_dir])
        
        if debug:
            cmd.append("--debug")
        
        try:
            self.daemon_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Wait a moment to check if it started successfully
            time.sleep(2)
            
            if self.daemon_process.poll() is None:
                print(f"✅ Daemon started successfully (PID: {self.daemon_process.pid})")
                print(f"📍 API available at: http://{host}:{port}")
                self.processes.append(self.daemon_process)
                return True
            else:
                print("❌ Daemon failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Error starting daemon: {e}")
            return False
    
    def start_mcp_server(self,
                        host: str = "127.0.0.1", 
                        port: int = 8888,
                        daemon_host: str = "127.0.0.1",
                        daemon_port: int = 9999,
                        debug: bool = False) -> bool:
        """Start the lightweight MCP server."""
        print("🚀 Starting Lightweight MCP Server...")
        
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "lightweight_mcp_server.py"),
            "--host", host,
            "--port", str(port),
            "--daemon-host", daemon_host,
            "--daemon-port", str(daemon_port)
        ]
        
        if debug:
            cmd.append("--debug")
        
        try:
            self.mcp_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Wait a moment to check if it started successfully
            time.sleep(2)
            
            if self.mcp_process.poll() is None:
                print(f"✅ MCP Server started successfully (PID: {self.mcp_process.pid})")
                print(f"🌐 Dashboard available at: http://{host}:{port}")
                self.processes.append(self.mcp_process)
                return True
            else:
                print("❌ MCP Server failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Error starting MCP server: {e}")
            return False
    
    def run_cli(self, args: List[str]) -> int:
        """Run the CLI tool with given arguments."""
        cmd = [
            sys.executable,
            str(project_root / "scripts" / "cli" / "ipfs_kit_cli.py")
        ] + args
        
        try:
            result = subprocess.run(cmd, check=True)
            return result.returncode
        except subprocess.CalledProcessError as e:
            return e.returncode
        except Exception as e:
            print(f"❌ Error running CLI: {e}")
            return 1
    
    def start_all(self,
                 daemon_host: str = "127.0.0.1",
                 daemon_port: int = 9999,
                 mcp_host: str = "127.0.0.1", 
                 mcp_port: int = 8888,
                 config_dir: str = "/tmp/ipfs_kit_config",
                 data_dir: str = None,
                 debug: bool = False) -> bool:
        """Start both daemon and MCP server."""
        print("=" * 80)
        print("🚀 STARTING IPFS KIT SERVICES")
        print("=" * 80)
        
        # Start daemon first
        if not self.start_daemon(daemon_host, daemon_port, config_dir, data_dir, debug):
            print("❌ Failed to start daemon - aborting")
            return False
        
        # Wait for daemon to be ready
        print("⏳ Waiting for daemon to be ready...")
        time.sleep(5)
        
        # Start MCP server
        if not self.start_mcp_server(mcp_host, mcp_port, daemon_host, daemon_port, debug):
            print("❌ Failed to start MCP server")
            self.stop_all()
            return False
        
        print("=" * 80)
        print("✅ ALL SERVICES STARTED SUCCESSFULLY")
        print("=" * 80)
        print(f"🔧 Daemon API: http://{daemon_host}:{daemon_port}")
        print(f"🌐 MCP Dashboard: http://{mcp_host}:{mcp_port}")
        print(f"📁 Config Directory: {config_dir}")
        if data_dir:
            print(f"💾 Data Directory: {data_dir}")
        print("=" * 80)
        print("Press Ctrl+C to stop all services")
        
        return True
    
    def stop_all(self):
        """Stop all running processes."""
        print("🛑 Stopping all services...")
        
        for process in self.processes:
            if process.poll() is None:  # Process is still running
                try:
                    process.terminate()
                    # Wait up to 5 seconds for graceful shutdown
                    process.wait(timeout=5)
                    print(f"✅ Process {process.pid} stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't stop gracefully
                    process.kill()
                    process.wait()
                    print(f"⚠️ Process {process.pid} force killed")
                except Exception as e:
                    print(f"❌ Error stopping process {process.pid}: {e}")
        
        self.processes.clear()
        self.daemon_process = None
        self.mcp_process = None
        
        print("✅ All services stopped")
    
    def wait_for_processes(self):
        """Wait for all processes to complete."""
        try:
            while self.processes:
                # Check if any process has ended
                for process in self.processes[:]:  # Use slice to avoid modification during iteration
                    if process.poll() is not None:
                        print(f"⚠️ Process {process.pid} has ended")
                        self.processes.remove(process)
                
                if not self.processes:
                    break
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")
            self.stop_all()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="IPFS Kit Service Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ipfs-kit-launcher daemon                          # Start only daemon
  ipfs-kit-launcher mcp                             # Start only MCP server  
  ipfs-kit-launcher all                             # Start both services
  ipfs-kit-launcher cli pin list                    # Run CLI command
  ipfs-kit-launcher all --debug                     # Start with debug logging
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Service to launch")
    
    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Start IPFS Kit daemon")
    daemon_parser.add_argument("--host", default="127.0.0.1", help="Daemon host")
    daemon_parser.add_argument("--port", type=int, default=9999, help="Daemon port")
    daemon_parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Config directory")
    daemon_parser.add_argument("--data-dir", help="Data directory")
    daemon_parser.add_argument("--debug", action="store_true", help="Debug logging")
    
    # MCP server command
    mcp_parser = subparsers.add_parser("mcp", help="Start MCP server")
    mcp_parser.add_argument("--host", default="127.0.0.1", help="MCP server host")
    mcp_parser.add_argument("--port", type=int, default=8888, help="MCP server port")
    mcp_parser.add_argument("--daemon-host", default="127.0.0.1", help="Daemon host")
    mcp_parser.add_argument("--daemon-port", type=int, default=9999, help="Daemon port")
    mcp_parser.add_argument("--debug", action="store_true", help="Debug logging")
    
    # All services command
    all_parser = subparsers.add_parser("all", help="Start all services")
    all_parser.add_argument("--daemon-host", default="127.0.0.1", help="Daemon host")
    all_parser.add_argument("--daemon-port", type=int, default=9999, help="Daemon port")
    all_parser.add_argument("--mcp-host", default="127.0.0.1", help="MCP server host")
    all_parser.add_argument("--mcp-port", type=int, default=8888, help="MCP server port")
    all_parser.add_argument("--config-dir", default="/tmp/ipfs_kit_config", help="Config directory")
    all_parser.add_argument("--data-dir", help="Data directory")
    all_parser.add_argument("--debug", action="store_true", help="Debug logging")
    
    # CLI command - pass through remaining args
    cli_parser = subparsers.add_parser("cli", help="Run CLI command")
    cli_parser.add_argument("cli_args", nargs=argparse.REMAINDER, help="CLI arguments")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    launcher = IPFSKitServiceLauncher()
    launcher._setup_signal_handlers()
    
    try:
        if args.command == "daemon":
            if launcher.start_daemon(
                args.host, args.port, args.config_dir, args.data_dir, args.debug
            ):
                launcher.wait_for_processes()
                return 0
            else:
                return 1
                
        elif args.command == "mcp":
            if launcher.start_mcp_server(
                args.host, args.port, args.daemon_host, args.daemon_port, args.debug
            ):
                launcher.wait_for_processes()
                return 0
            else:
                return 1
                
        elif args.command == "all":
            if launcher.start_all(
                args.daemon_host, args.daemon_port,
                args.mcp_host, args.mcp_port,
                args.config_dir, args.data_dir, args.debug
            ):
                launcher.wait_for_processes()
                return 0
            else:
                return 1
                
        elif args.command == "cli":
            return launcher.run_cli(args.cli_args)
        
        else:
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        launcher.stop_all()
        return 130
    except Exception as e:
        print(f"❌ Launcher error: {e}")
        launcher.stop_all()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
