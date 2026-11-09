#!/usr/bin/env python3
"""
IPFS-Kit Enhanced CLI Tool

A comprehensive command-line interface for the IPFS-Kit daemon that provides:
- Daemon management and monitoring
- Pin operations with enhanced metadata
- Backend health monitoring
- Configuration management
- Performance analytics
- Replication management
- VFS operations

Usage:
    ipfs-kit daemon start                    # Start the daemon
    ipfs-kit daemon stop                     # Stop the daemon
    ipfs-kit daemon status                   # Show daemon status
    ipfs-kit daemon restart                  # Restart the daemon
    ipfs-kit pin add <cid>                   # Add a pin
    ipfs-kit pin list                        # List all pins
    ipfs-kit pin remove <cid>                # Remove a pin
    ipfs-kit backend start <name>            # Start a backend
    ipfs-kit backend stop <name>             # Stop a backend
    ipfs-kit backend status [name]           # Show backend status
    ipfs-kit health check [backend]          # Check health
    ipfs-kit config show                     # Show configuration
    ipfs-kit config set <key> <value>        # Set configuration
    ipfs-kit metrics                         # Show performance metrics
    ipfs-kit replication status              # Show replication status
    ipfs-kit vfs mount <path>                # Mount VFS path
    ipfs-kit vfs list                        # List VFS mounts
"""

import anyio
import argparse
import json
import sys
import time
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import subprocess
import signal

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ipfs_kit_daemon import IPFSKitDaemon
    from ipfs_kit_daemon_client import DaemonClient as IPFSKitDaemonClient
    DAEMON_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Daemon components not available: {e}")
    DAEMON_AVAILABLE = False

try:
    from enhanced_pin_cli import format_bytes, print_metrics
    from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
    ENHANCED_FEATURES_AVAILABLE = True
except ImportError:
    ENHANCED_FEATURES_AVAILABLE = False

class IPFSKitCLI:
    """Enhanced CLI for IPFS-Kit with comprehensive daemon integration."""
    
    def __init__(self, daemon_host: str = "127.0.0.1", daemon_port: int = 9999):
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self.daemon_client = None
        self.config_file = "/tmp/ipfs_kit_config/daemon.json"
        
        if DAEMON_AVAILABLE:
            self.daemon_client = IPFSKitDaemonClient(daemon_host, daemon_port)
    
    def print_banner(self):
        """Print CLI banner with status."""
        print("🚀 IPFS-Kit Enhanced CLI v2.0")
        print("=" * 50)
        if DAEMON_AVAILABLE:
            print("✅ Daemon support: Available")
        else:
            print("❌ Daemon support: Not available")
        if ENHANCED_FEATURES_AVAILABLE:
            print("✅ Enhanced features: Available")
        else:
            print("❌ Enhanced features: Limited")
        print()
    
    # Daemon Management Commands
    
    async def cmd_daemon_start(self, detach: bool = False, config: Optional[str] = None):
        """Start the IPFS-Kit daemon."""
        if not DAEMON_AVAILABLE:
            print("❌ Daemon components not available")
            return 1
        
        print("🚀 Starting IPFS-Kit Daemon...")
        
        # Check if already running
        if await self._check_daemon_running():
            print("⚠️  Daemon already running")
            return 0
        
        try:
            if detach:
                # Start daemon in background
                cmd = [sys.executable, "-m", "ipfs_kit_daemon"]
                if config:
                    cmd.extend(["--config", config])
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                
                # Wait a moment and check if it started
                await anyio.sleep(2)
                if await self._check_daemon_running():
                    print("✅ Daemon started successfully")
                    return 0
                else:
                    print("❌ Failed to start daemon")
                    return 1
            else:
                # Start daemon in foreground
                daemon = IPFSKitDaemon(config_file=config)
                await daemon.start()
                return 0
                
        except Exception as e:
            print(f"❌ Error starting daemon: {e}")
            return 1
    
    async def cmd_daemon_stop(self):
        """Stop the IPFS-Kit daemon."""
        print("🛑 Stopping IPFS-Kit Daemon...")
        
        pid_file = "/tmp/ipfs_kit_daemon.pid"
        try:
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                os.kill(pid, signal.SIGTERM)
                
                # Wait for shutdown
                for _ in range(10):
                    try:
                        os.kill(pid, 0)  # Check if process exists
                        await anyio.sleep(1)
                    except ProcessLookupError:
                        break
                
                print("✅ Daemon stopped successfully")
                return 0
            else:
                print("⚠️  Daemon not running (no PID file)")
                return 0
                
        except Exception as e:
            print(f"❌ Error stopping daemon: {e}")
            return 1
    
    async def cmd_daemon_restart(self, config: Optional[str] = None):
        """Restart the IPFS-Kit daemon."""
        print("🔄 Restarting IPFS-Kit Daemon...")
        
        await self.cmd_daemon_stop()
        await anyio.sleep(2)
        return await self.cmd_daemon_start(detach=True, config=config)
    
    async def cmd_daemon_status(self, verbose: bool = False):
        """Show daemon status."""
        self.print_banner()
        
        if not await self._check_daemon_running():
            print("❌ Daemon Status: Not Running")
            print()
            print("Start the daemon with: ipfs-kit daemon start --detach")
            return 1
        
        if not self.daemon_client:
            print("❌ Daemon client not available")
            return 1
        
        try:
            status = await self.daemon_client.get_status()
            
            print("✅ Daemon Status: Running")
            print()
            
            # Basic daemon info
            daemon_info = status.get("daemon", {})
            print("📊 DAEMON INFORMATION")
            print("-" * 30)
            print(f"PID: {daemon_info.get('pid', 'Unknown')}")
            print(f"Uptime: {self._format_duration(daemon_info.get('uptime', 0))}")
            print(f"Version: {daemon_info.get('version', 'Unknown')}")
            print()
            
            # Backend status
            backends = status.get("backends", {})
            print("🔧 BACKEND STATUS")
            print("-" * 20)
            for name, backend in backends.items():
                status_icon = "✅" if backend.get("status") == "running" else "❌"
                health_icon = "💚" if backend.get("health") == "healthy" else "💔"
                print(f"{status_icon} {health_icon} {name}: {backend.get('status', 'unknown')}")
                
                if verbose and backend.get("metrics"):
                    metrics = backend["metrics"]
                    for key, value in metrics.items():
                        print(f"    {key}: {value}")
            print()
            
            # Replication status
            if verbose:
                replication = status.get("replication", {})
                if replication:
                    print("🔄 REPLICATION STATUS")
                    print("-" * 25)
                    for key, value in replication.items():
                        print(f"{key}: {value}")
                    print()
            
            return 0
            
        except Exception as e:
            print(f"❌ Error getting daemon status: {e}")
            return 1
    
    # Pin Management Commands
    
    async def cmd_pin_add(self, cid: str, name: Optional[str] = None, recursive: bool = True):
        """Add a pin with enhanced metadata."""
        if not await self._ensure_daemon():
            return 1
        
        print(f"📌 Adding pin: {cid}")
        
        try:
            result = await self.daemon_client.add_pin(cid, name=name, recursive=recursive)
            
            if result.get("success"):
                print("✅ Pin added successfully")
                if result.get("metadata"):
                    metadata = result["metadata"]
                    print(f"   Size: {format_bytes(metadata.get('size', 0))}")
                    print(f"   Type: {metadata.get('type', 'unknown')}")
                return 0
            else:
                print(f"❌ Failed to add pin: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error adding pin: {e}")
            return 1
    
    async def cmd_pin_remove(self, cid: str):
        """Remove a pin."""
        if not await self._ensure_daemon():
            return 1
        
        print(f"🗑️  Removing pin: {cid}")
        
        try:
            result = await self.daemon_client.remove_pin(cid)
            
            if result.get("success"):
                print("✅ Pin removed successfully")
                return 0
            else:
                print(f"❌ Failed to remove pin: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error removing pin: {e}")
            return 1
    
    async def cmd_pin_list(self, limit: int = 50, show_metadata: bool = False):
        """List pins with metadata."""
        if not await self._ensure_daemon():
            return 1
        
        print("📋 Listing pins...")
        
        try:
            result = await self.daemon_client.list_pins(limit=limit, include_metadata=show_metadata)
            
            if result.get("success"):
                pins = result.get("pins", [])
                print(f"Found {len(pins)} pins")
                print()
                
                for pin in pins:
                    cid = pin.get("cid", "unknown")
                    name = pin.get("name", "")
                    size = pin.get("size", 0)
                    pin_type = pin.get("type", "unknown")
                    
                    print(f"📌 {cid}")
                    if name:
                        print(f"   Name: {name}")
                    print(f"   Size: {format_bytes(size)}")
                    print(f"   Type: {pin_type}")
                    
                    if show_metadata and pin.get("metadata"):
                        metadata = pin["metadata"]
                        print(f"   Added: {metadata.get('added_at', 'unknown')}")
                        print(f"   Access Count: {metadata.get('access_count', 0)}")
                    print()
                
                return 0
            else:
                print(f"❌ Failed to list pins: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error listing pins: {e}")
            return 1
    
    # Backend Management Commands
    
    async def cmd_backend_start(self, backend_name: str):
        """Start a specific backend."""
        if not await self._ensure_daemon():
            return 1
        
        print(f"🔌 Starting backend: {backend_name}")
        
        try:
            result = await self.daemon_client.start_backend(backend_name)
            
            if result.get("success"):
                print(f"✅ Backend {backend_name} started successfully")
                return 0
            else:
                print(f"❌ Failed to start backend: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error starting backend: {e}")
            return 1
    
    async def cmd_backend_stop(self, backend_name: str):
        """Stop a specific backend."""
        if not await self._ensure_daemon():
            return 1
        
        print(f"🛑 Stopping backend: {backend_name}")
        
        try:
            result = await self.daemon_client.stop_backend(backend_name)
            
            if result.get("success"):
                print(f"✅ Backend {backend_name} stopped successfully")
                return 0
            else:
                print(f"❌ Failed to stop backend: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error stopping backend: {e}")
            return 1
    
    async def cmd_backend_status(self, backend_name: Optional[str] = None):
        """Show backend status."""
        if not await self._ensure_daemon():
            return 1
        
        try:
            result = await self.daemon_client.get_backend_status(backend_name)
            
            if result.get("success"):
                backends = result.get("backends", {})
                
                if backend_name:
                    # Show single backend
                    backend = backends.get(backend_name, {})
                    if backend:
                        self._print_backend_details(backend_name, backend)
                    else:
                        print(f"❌ Backend {backend_name} not found")
                        return 1
                else:
                    # Show all backends
                    print("🔧 BACKEND STATUS")
                    print("=" * 30)
                    for name, backend in backends.items():
                        self._print_backend_details(name, backend)
                        print()
                
                return 0
            else:
                print(f"❌ Failed to get backend status: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error getting backend status: {e}")
            return 1
    
    # Health Commands
    
    async def cmd_health_check(self, backend_name: Optional[str] = None):
        """Perform health check."""
        if not await self._ensure_daemon():
            return 1
        
        print("🏥 Performing health check...")
        
        try:
            result = await self.daemon_client.health_check(backend_name)
            
            if result.get("success"):
                health_data = result.get("health", {})
                
                print("📊 HEALTH CHECK RESULTS")
                print("-" * 30)
                
                overall_health = health_data.get("overall", "unknown")
                health_icon = "✅" if overall_health == "healthy" else "❌"
                print(f"{health_icon} Overall Health: {overall_health}")
                print()
                
                # Backend health details
                backends = health_data.get("backends", {})
                for name, backend_health in backends.items():
                    status = backend_health.get("status", "unknown")
                    health = backend_health.get("health", "unknown")
                    
                    status_icon = "✅" if status == "running" else "❌"
                    health_icon = "💚" if health == "healthy" else "💔"
                    
                    print(f"{status_icon} {health_icon} {name}")
                    print(f"   Status: {status}")
                    print(f"   Health: {health}")
                    
                    if backend_health.get("metrics"):
                        print(f"   Metrics:")
                        for key, value in backend_health["metrics"].items():
                            print(f"     {key}: {value}")
                    print()
                
                return 0
            else:
                print(f"❌ Health check failed: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error performing health check: {e}")
            return 1
    
    # Configuration Commands
    
    async def cmd_config_show(self):
        """Show current configuration."""
        print("⚙️  CONFIGURATION")
        print("=" * 30)
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                print(json.dumps(config, indent=2))
                return 0
            else:
                print("❌ Configuration file not found")
                return 1
                
        except Exception as e:
            print(f"❌ Error reading configuration: {e}")
            return 1
    
    async def cmd_config_set(self, key: str, value: str):
        """Set configuration value."""
        print(f"⚙️  Setting {key} = {value}")
        
        try:
            # Load current config
            config = {}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            
            # Parse nested key (e.g., "daemon.health_check_interval")
            keys = key.split('.')
            current = config
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            
            # Try to parse value as appropriate type
            try:
                if value.lower() in ['true', 'false']:
                    current[keys[-1]] = value.lower() == 'true'
                elif value.isdigit():
                    current[keys[-1]] = int(value)
                elif '.' in value and value.replace('.', '').isdigit():
                    current[keys[-1]] = float(value)
                else:
                    current[keys[-1]] = value
            except:
                current[keys[-1]] = value
            
            # Save config
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("✅ Configuration updated")
            
            # Notify daemon if running
            if await self._check_daemon_running():
                try:
                    await self.daemon_client.reload_config()
                    print("✅ Daemon notified of configuration change")
                except:
                    print("⚠️  Could not notify daemon of configuration change")
            
            return 0
            
        except Exception as e:
            print(f"❌ Error setting configuration: {e}")
            return 1
    
    # Metrics Commands
    
    async def cmd_metrics(self, detailed: bool = False):
        """Show performance metrics."""
        print("📊 PERFORMANCE METRICS")
        print("=" * 30)
        
        if ENHANCED_FEATURES_AVAILABLE:
            try:
                from ipfs_kit_py.enhanced_pin_index import get_cli_pin_metrics
                metrics = get_cli_pin_metrics()
                print_metrics(metrics)
                return 0
            except Exception as e:
                print(f"⚠️  Enhanced metrics not available: {e}")
        
        # Fallback to daemon metrics
        if await self._check_daemon_running() and self.daemon_client:
            try:
                result = await self.daemon_client.get_metrics()
                if result.get("success"):
                    metrics = result.get("metrics", {})
                    for category, data in metrics.items():
                        print(f"\n{category.upper()}")
                        print("-" * 20)
                        for key, value in data.items():
                            print(f"{key}: {value}")
                    return 0
            except Exception as e:
                print(f"❌ Error getting metrics: {e}")
        
        print("❌ No metrics available")
        return 1
    
    # Replication Commands
    
    async def cmd_replication_status(self):
        """Show replication status."""
        if not await self._ensure_daemon():
            return 1
        
        print("🔄 REPLICATION STATUS")
        print("=" * 25)
        
        try:
            result = await self.daemon_client.get_replication_status()
            
            if result.get("success"):
                replication = result.get("replication", {})
                
                enabled = replication.get("enabled", False)
                print(f"Enabled: {'✅' if enabled else '❌'}")
                print(f"Auto Replication: {'✅' if replication.get('auto_replication') else '❌'}")
                print(f"Min Replicas: {replication.get('min_replicas', 'unknown')}")
                print(f"Max Replicas: {replication.get('max_replicas', 'unknown')}")
                print()
                
                # Replication stats
                stats = replication.get("stats", {})
                if stats:
                    print("📊 REPLICATION STATISTICS")
                    print("-" * 30)
                    for key, value in stats.items():
                        print(f"{key}: {value}")
                
                return 0
            else:
                print(f"❌ Failed to get replication status: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error getting replication status: {e}")
            return 1
    
    # VFS Commands
    
    async def cmd_vfs_mount(self, path: str, mount_point: Optional[str] = None):
        """Mount a VFS path."""
        if not await self._ensure_daemon():
            return 1
        
        print(f"💾 Mounting VFS path: {path}")
        
        try:
            result = await self.daemon_client.vfs_mount(path, mount_point)
            
            if result.get("success"):
                print("✅ VFS path mounted successfully")
                if result.get("mount_point"):
                    print(f"   Mount point: {result['mount_point']}")
                return 0
            else:
                print(f"❌ Failed to mount VFS path: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error mounting VFS path: {e}")
            return 1
    
    async def cmd_vfs_list(self):
        """List VFS mounts."""
        if not await self._ensure_daemon():
            return 1
        
        print("💾 VFS MOUNTS")
        print("=" * 20)
        
        try:
            result = await self.daemon_client.vfs_list()
            
            if result.get("success"):
                mounts = result.get("mounts", [])
                
                if not mounts:
                    print("No VFS mounts found")
                    return 0
                
                for mount in mounts:
                    path = mount.get("path", "unknown")
                    mount_point = mount.get("mount_point", "unknown")
                    size = mount.get("size", 0)
                    
                    print(f"📁 {path}")
                    print(f"   Mount Point: {mount_point}")
                    print(f"   Size: {format_bytes(size)}")
                    print()
                
                return 0
            else:
                print(f"❌ Failed to list VFS mounts: {result.get('error', 'Unknown error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error listing VFS mounts: {e}")
            return 1
    
    # Utility Methods
    
    async def _check_daemon_running(self) -> bool:
        """Check if daemon is running."""
        pid_file = "/tmp/ipfs_kit_daemon.pid"
        try:
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is actually running
                try:
                    os.kill(pid, 0)
                    return True
                except ProcessLookupError:
                    # Stale PID file
                    os.remove(pid_file)
                    return False
            return False
        except:
            return False
    
    async def _ensure_daemon(self) -> bool:
        """Ensure daemon is running."""
        if not await self._check_daemon_running():
            print("❌ IPFS-Kit daemon is not running")
            print("Start the daemon with: ipfs-kit daemon start --detach")
            return False
        return True
    
    def _print_backend_details(self, name: str, backend: Dict[str, Any]):
        """Print detailed backend information."""
        status = backend.get("status", "unknown")
        health = backend.get("health", "unknown")
        
        status_icon = "✅" if status == "running" else "❌"
        health_icon = "💚" if health == "healthy" else "💔"
        
        print(f"{status_icon} {health_icon} {name.upper()}")
        print(f"   Status: {status}")
        print(f"   Health: {health}")
        
        if backend.get("pid"):
            print(f"   PID: {backend['pid']}")
        
        if backend.get("started_at"):
            uptime = time.time() - backend['started_at']
            print(f"   Uptime: {self._format_duration(uptime)}")
        
        if backend.get("metrics"):
            print("   Metrics:")
            for key, value in backend["metrics"].items():
                print(f"     {key}: {value}")
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            return f"{days}d {hours}h"


def create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="IPFS-Kit Enhanced CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Daemon commands
    daemon_parser = subparsers.add_parser('daemon', help='Daemon management')
    daemon_subparsers = daemon_parser.add_subparsers(dest='daemon_action')
    
    start_parser = daemon_subparsers.add_parser('start', help='Start daemon')
    start_parser.add_argument('--detach', action='store_true', help='Run in background')
    start_parser.add_argument('--config', help='Configuration file path')
    
    daemon_subparsers.add_parser('stop', help='Stop daemon')
    daemon_subparsers.add_parser('status', help='Show daemon status')
    daemon_subparsers.add_parser('restart', help='Restart daemon')
    
    # Pin commands
    pin_parser = subparsers.add_parser('pin', help='Pin management')
    pin_subparsers = pin_parser.add_subparsers(dest='pin_action')
    
    add_parser = pin_subparsers.add_parser('add', help='Add pin')
    add_parser.add_argument('cid', help='CID to pin')
    add_parser.add_argument('--name', help='Pin name')
    add_parser.add_argument('--no-recursive', dest='recursive', action='store_false', help='Non-recursive pin')
    
    remove_parser = pin_subparsers.add_parser('remove', help='Remove pin')
    remove_parser.add_argument('cid', help='CID to unpin')
    
    list_parser = pin_subparsers.add_parser('list', help='List pins')
    list_parser.add_argument('--limit', type=int, default=50, help='Limit number of results')
    list_parser.add_argument('--metadata', action='store_true', help='Show metadata')
    
    # Backend commands
    backend_parser = subparsers.add_parser('backend', help='Backend management')
    backend_subparsers = backend_parser.add_subparsers(dest='backend_action')
    
    start_backend_parser = backend_subparsers.add_parser('start', help='Start backend')
    start_backend_parser.add_argument('name', help='Backend name')
    
    stop_backend_parser = backend_subparsers.add_parser('stop', help='Stop backend')
    stop_backend_parser.add_argument('name', help='Backend name')
    
    status_backend_parser = backend_subparsers.add_parser('status', help='Backend status')
    status_backend_parser.add_argument('name', nargs='?', help='Backend name (optional)')
    
    # Health commands
    health_parser = subparsers.add_parser('health', help='Health monitoring')
    health_subparsers = health_parser.add_subparsers(dest='health_action')
    
    check_parser = health_subparsers.add_parser('check', help='Perform health check')
    check_parser.add_argument('backend', nargs='?', help='Backend name (optional)')
    
    # Config commands
    config_parser = subparsers.add_parser('config', help='Configuration management')
    config_subparsers = config_parser.add_subparsers(dest='config_action')
    
    config_subparsers.add_parser('show', help='Show configuration')
    
    set_parser = config_subparsers.add_parser('set', help='Set configuration value')
    set_parser.add_argument('key', help='Configuration key')
    set_parser.add_argument('value', help='Configuration value')
    
    # Metrics commands
    metrics_parser = subparsers.add_parser('metrics', help='Show performance metrics')
    metrics_parser.add_argument('--detailed', action='store_true', help='Show detailed metrics')
    
    # Replication commands
    replication_parser = subparsers.add_parser('replication', help='Replication management')
    replication_subparsers = replication_parser.add_subparsers(dest='replication_action')
    
    replication_subparsers.add_parser('status', help='Show replication status')
    
    # VFS commands
    vfs_parser = subparsers.add_parser('vfs', help='Virtual filesystem operations')
    vfs_subparsers = vfs_parser.add_subparsers(dest='vfs_action')
    
    mount_parser = vfs_subparsers.add_parser('mount', help='Mount VFS path')
    mount_parser.add_argument('path', help='Path to mount')
    mount_parser.add_argument('--mount-point', help='Mount point')
    
    vfs_subparsers.add_parser('list', help='List VFS mounts')
    
    return parser


async def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    cli = IPFSKitCLI()
    
    try:
        # Daemon commands
        if args.command == 'daemon':
            if args.daemon_action == 'start':
                return await cli.cmd_daemon_start(detach=args.detach, config=args.config)
            elif args.daemon_action == 'stop':
                return await cli.cmd_daemon_stop()
            elif args.daemon_action == 'status':
                return await cli.cmd_daemon_status()
            elif args.daemon_action == 'restart':
                return await cli.cmd_daemon_restart(config=getattr(args, 'config', None))
        
        # Pin commands
        elif args.command == 'pin':
            if args.pin_action == 'add':
                return await cli.cmd_pin_add(args.cid, name=args.name, recursive=args.recursive)
            elif args.pin_action == 'remove':
                return await cli.cmd_pin_remove(args.cid)
            elif args.pin_action == 'list':
                return await cli.cmd_pin_list(limit=args.limit, show_metadata=args.metadata)
        
        # Backend commands
        elif args.command == 'backend':
            if args.backend_action == 'start':
                return await cli.cmd_backend_start(args.name)
            elif args.backend_action == 'stop':
                return await cli.cmd_backend_stop(args.name)
            elif args.backend_action == 'status':
                return await cli.cmd_backend_status(args.name)
        
        # Health commands
        elif args.command == 'health':
            if args.health_action == 'check':
                return await cli.cmd_health_check(args.backend)
        
        # Config commands
        elif args.command == 'config':
            if args.config_action == 'show':
                return await cli.cmd_config_show()
            elif args.config_action == 'set':
                return await cli.cmd_config_set(args.key, args.value)
        
        # Metrics commands
        elif args.command == 'metrics':
            return await cli.cmd_metrics(detailed=args.detailed)
        
        # Replication commands
        elif args.command == 'replication':
            if args.replication_action == 'status':
                return await cli.cmd_replication_status()
        
        # VFS commands
        elif args.command == 'vfs':
            if args.vfs_action == 'mount':
                return await cli.cmd_vfs_mount(args.path, args.mount_point)
            elif args.vfs_action == 'list':
                return await cli.cmd_vfs_list()
        
        parser.print_help()
        return 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)
