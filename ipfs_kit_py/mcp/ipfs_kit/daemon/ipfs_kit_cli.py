#!/usr/bin/env python3
"""
IPFS Kit CLI Tool - Daemon Client Version.

Lightweight CLI tool that communicates with the IPFS Kit daemon
for all operations. The CLI focuses on providing a user-friendly
interface while delegating heavy operations to the daemon.
"""

import anyio
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import daemon client
from mcp.ipfs_kit.daemon.daemon_client import IPFSKitDaemonClient, ensure_daemon_running

class IPFSKitCLI:
    """
    CLI tool for IPFS Kit that communicates with the daemon.
    
    Provides commands for:
    - Pin management
    - Backend control
    - Health monitoring
    - Configuration
    """
    
    def __init__(self, daemon_host: str = "127.0.0.1", daemon_port: int = 9999):
        self.daemon_client = IPFSKitDaemonClient(daemon_host, daemon_port)
        
    async def ensure_daemon(self) -> bool:
        """Ensure daemon is running before executing commands."""
        if not await ensure_daemon_running(self.daemon_client.daemon_host, self.daemon_client.daemon_port):
            print("❌ IPFS Kit daemon is not running")
            print(f"Please start the daemon with: ipfs-kit daemon --host {self.daemon_client.daemon_host} --port {self.daemon_client.daemon_port}")
            return False
        return True
    
    # Pin management commands
    async def cmd_pin_add(self, cid: str) -> int:
        """Add a pin."""
        if not await self.ensure_daemon():
            return 1
        
        print(f"📎 Adding pin: {cid}")
        
        result = await self.daemon_client.add_pin(cid)
        
        if result.get("success"):
            print(f"✅ Pin added successfully")
            if "routing_info" in result:
                routing = result["routing_info"]
                print(f"   Primary backend: {routing.get('primary_backend')}")
                print(f"   Storage tiers: {routing.get('storage_tiers')}")
                print(f"   Replication factor: {routing.get('replication_factor')}")
        else:
            print(f"❌ Failed to add pin: {result.get('error')}")
            return 1
        
        return 0
    
    async def cmd_pin_remove(self, cid: str) -> int:
        """Remove a pin."""
        if not await self.ensure_daemon():
            return 1
        
        print(f"📎 Removing pin: {cid}")
        
        result = await self.daemon_client.remove_pin(cid)
        
        if result.get("success"):
            print(f"✅ Pin removed successfully")
        else:
            print(f"❌ Failed to remove pin: {result.get('error')}")
            return 1
        
        return 0
    
    async def cmd_pin_list(self) -> int:
        """List all pins."""
        if not await self.ensure_daemon():
            return 1
        
        print("📋 Listing pins...")
        
        result = await self.daemon_client.list_pins()
        
        if result.get("pins"):
            pins = result["pins"]
            total = result.get("total", len(pins))
            
            print(f"📊 Found {total} pins:")
            print("-" * 80)
            
            for pin in pins[:20]:  # Show first 20
                cid = pin.get("cid", "unknown")[:16] + "..." if len(pin.get("cid", "")) > 16 else pin.get("cid", "unknown")
                size = pin.get("size_bytes", 0)
                name = pin.get("name", "unnamed")
                tier = pin.get("primary_tier", "ipfs")
                
                # Format size
                if size > 1024**3:
                    size_str = f"{size / 1024**3:.1f} GB"
                elif size > 1024**2:
                    size_str = f"{size / 1024**2:.1f} MB" 
                elif size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                
                print(f"📎 {cid:<20} {size_str:>10} {tier:<8} {name}")
            
            if total > 20:
                print(f"... and {total - 20} more pins")
                
        else:
            print("📭 No pins found")
            if "error" in result:
                print(f"Error: {result['error']}")
        
        return 0
    
    # Health monitoring commands
    async def cmd_health(self, verbose: bool = False) -> int:
        """Show health status."""
        if not await self.ensure_daemon():
            return 1
        
        print("🏥 Checking system health...")
        
        health_result = await self.daemon_client.get_health()
        
        if health_result.get("system_healthy"):
            print("✅ System is healthy")
        else:
            print("⚠️ System has issues")
        
        # Show component status
        components = health_result.get("components", {})
        if components:
            print("\n📊 Component Status:")
            for name, component in components.items():
                if isinstance(component, dict):
                    healthy = component.get("healthy", False)
                    status_icon = "✅" if healthy else "❌"
                    print(f"   {status_icon} {name.replace('_', ' ').title()}")
                    
                    if verbose and not healthy:
                        errors = component.get("errors", [])
                        for error in errors[:3]:  # Show first 3 errors
                            print(f"      ❌ {error}")
        
        # Show backend status
        backend_result = await self.daemon_client.get_backend_health()
        backends = backend_result.get("backends", {})
        
        if backends:
            print("\n🖥️ Backend Status:")
            for name, backend in backends.items():
                health = backend.get("health", "unknown")
                status = backend.get("status", "unknown")
                
                if health == "healthy":
                    icon = "✅"
                elif health == "unhealthy":
                    icon = "❌"
                else:
                    icon = "⚠️"
                
                print(f"   {icon} {name:<15} {status:<10} ({health})")
        
        return 0
    
    async def cmd_status(self) -> int:
        """Show daemon status."""
        if not await self.ensure_daemon():
            return 1
        
        print("📊 Daemon Status:")
        
        status_result = await self.daemon_client.get_daemon_status()
        
        if status_result.get("running"):
            print("✅ Daemon is running")
            uptime = status_result.get("uptime_seconds", 0)
            if uptime > 0:
                hours = uptime // 3600
                minutes = (uptime % 3600) // 60
                seconds = uptime % 60
                print(f"⏱️ Uptime: {hours:02.0f}:{minutes:02.0f}:{seconds:02.0f}")
        else:
            print("❌ Daemon is not running")
        
        # Show component status
        components = status_result.get("components", {})
        if components:
            print("\n🔧 Components:")
            for name, available in components.items():
                icon = "✅" if available else "❌"
                print(f"   {icon} {name.replace('_', ' ').title()}")
        
        print(f"\n🌐 API Version: {status_result.get('api_version', 'unknown')}")
        
        return 0
    
    # Backend control commands
    async def cmd_backend_start(self, backend: str) -> int:
        """Start a backend service."""
        if not await self.ensure_daemon():
            return 1
        
        print(f"🚀 Starting {backend} backend...")
        
        result = await self.daemon_client.start_backend(backend)
        
        if result.get("success"):
            print(f"✅ {backend} backend started successfully")
        else:
            print(f"❌ Failed to start {backend}: {result.get('error')}")
            return 1
        
        return 0
    
    async def cmd_backend_stop(self, backend: str) -> int:
        """Stop a backend service.""" 
        if not await self.ensure_daemon():
            return 1
        
        print(f"🛑 Stopping {backend} backend...")
        
        result = await self.daemon_client.stop_backend(backend)
        
        if result.get("success"):
            print(f"✅ {backend} backend stopped successfully")
        else:
            print(f"❌ Failed to stop {backend}: {result.get('error')}")
            return 1
        
        return 0
    
    async def cmd_backend_logs(self, backend: str, lines: int = 50) -> int:
        """Show backend logs."""
        if not await self.ensure_daemon():
            return 1
        
        print(f"📋 {backend} logs (last {lines} lines):")
        print("-" * 80)
        
        result = await self.daemon_client.get_backend_logs(backend, lines)
        
        if result.get("logs"):
            for log_line in result["logs"]:
                print(log_line)
        else:
            print("No logs available")
            if "error" in result:
                print(f"Error: {result['error']}")
        
        return 0
    
    # Configuration commands
    async def cmd_config_show(self) -> int:
        """Show configuration."""
        if not await self.ensure_daemon():
            return 1
        
        print("⚙️ Daemon Configuration:")
        
        result = await self.daemon_client.get_config()
        
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("No configuration found")
        
        return 0


async def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="IPFS Kit CLI - Daemon Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ipfs-kit pin add QmHash123...              # Add a pin
  ipfs-kit pin remove QmHash123...           # Remove a pin 
  ipfs-kit pin list                          # List all pins
  ipfs-kit health                            # Check system health
  ipfs-kit health --verbose                  # Detailed health info
  ipfs-kit status                            # Show daemon status
  ipfs-kit backend start ipfs                # Start IPFS backend
  ipfs-kit backend stop cluster              # Stop cluster backend
  ipfs-kit backend logs lotus --lines 100    # Show lotus logs
  ipfs-kit config show                       # Show configuration
        """
    )
    
    parser.add_argument("--daemon-host", default="127.0.0.1", help="Daemon host")
    parser.add_argument("--daemon-port", type=int, default=9999, help="Daemon port")
    parser.add_argument("--json", action="store_true", help="JSON output format")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Pin commands
    pin_parser = subparsers.add_parser("pin", help="Pin management")
    pin_subparsers = pin_parser.add_subparsers(dest="pin_command")
    
    pin_add_parser = pin_subparsers.add_parser("add", help="Add a pin")
    pin_add_parser.add_argument("cid", help="Content ID to pin")
    
    pin_remove_parser = pin_subparsers.add_parser("remove", help="Remove a pin")
    pin_remove_parser.add_argument("cid", help="Content ID to unpin")
    
    pin_subparsers.add_parser("list", help="List pins")
    
    # Health commands
    health_parser = subparsers.add_parser("health", help="Check system health")
    health_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    # Status command
    subparsers.add_parser("status", help="Show daemon status")
    
    # Backend commands
    backend_parser = subparsers.add_parser("backend", help="Backend management")
    backend_subparsers = backend_parser.add_subparsers(dest="backend_command")
    
    backend_start_parser = backend_subparsers.add_parser("start", help="Start backend")
    backend_start_parser.add_argument("backend", help="Backend name")
    
    backend_stop_parser = backend_subparsers.add_parser("stop", help="Stop backend")
    backend_stop_parser.add_argument("backend", help="Backend name")
    
    backend_logs_parser = backend_subparsers.add_parser("logs", help="Show backend logs")
    backend_logs_parser.add_argument("backend", help="Backend name")
    backend_logs_parser.add_argument("--lines", type=int, default=50, help="Number of lines")
    
    # Config commands
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_subparsers.add_parser("show", help="Show configuration")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Create CLI instance
    cli = IPFSKitCLI(args.daemon_host, args.daemon_port)
    
    try:
        # Route commands
        if args.command == "pin":
            if args.pin_command == "add":
                return await cli.cmd_pin_add(args.cid)
            elif args.pin_command == "remove":
                return await cli.cmd_pin_remove(args.cid)
            elif args.pin_command == "list":
                return await cli.cmd_pin_list()
            else:
                pin_parser.print_help()
                return 1
                
        elif args.command == "health":
            return await cli.cmd_health(args.verbose)
            
        elif args.command == "status":
            return await cli.cmd_status()
            
        elif args.command == "backend":
            if args.backend_command == "start":
                return await cli.cmd_backend_start(args.backend)
            elif args.backend_command == "stop":
                return await cli.cmd_backend_stop(args.backend)
            elif args.backend_command == "logs":
                return await cli.cmd_backend_logs(args.backend, args.lines)
            else:
                backend_parser.print_help()
                return 1
                
        elif args.command == "config":
            if args.config_command == "show":
                return await cli.cmd_config_show()
            else:
                config_parser.print_help()
                return 1
        
        else:
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        return 130
    except Exception as e:
        print(f"❌ CLI error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)
