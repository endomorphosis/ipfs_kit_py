#!/usr/bin/env python3
"""
IPFS-Kit Ultra-Fast CLI with Standalone JIT

Ultra-fast CLI that uses standalone JIT imports for sub-second response times.
No heavy dependencies loaded for fast operations.
"""

import asyncio
import argparse
import json
import sys
import time
import os
import subprocess
import signal
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Use standalone JIT system (no heavy imports)
from standalone_jit import get_standalone_jit

jit = get_standalone_jit()


class UltraFastCLI:
    """Ultra-fast CLI with minimal imports."""
    
    def __init__(self):
        self.config_file = "/tmp/ipfs_kit_config/daemon.json"
        self.jit = get_standalone_jit()
    
    def print_banner(self, verbose: bool = False):
        """Print CLI banner."""
        print("🚀 IPFS-Kit Ultra-Fast CLI v4.0 (Standalone JIT)")
        print("=" * 50)
        
        # Fast feature checks
        features = [
            ('daemon', '🔧', 'IPFS-Kit daemon components'),
            ('enhanced_features', '⚡', 'Enhanced pin management'),
            ('wal_system', '📝', 'Write-Ahead Log system'),
            ('bucket_index', '🗂️', 'Bucket discovery system')
        ]
        
        for feature, icon, desc in features:
            available = self.jit.is_available(feature)
            status = "✅" if available else "❌"
            print(f"{status} {icon} {feature}: {desc}")
        
        if verbose:
            metrics = self.jit.get_metrics()
            print(f"\n📊 Performance:")
            print(f"   Startup: {metrics['startup_time']:.3f}s")
            print(f"   Cached modules: {metrics['cached_modules']}")
        
        print()
    
    # Fast operations (no heavy imports)
    
    async def cmd_status(self, verbose: bool = False):
        """Show system status (ultra-fast)."""
        self.print_banner(verbose=verbose)
        
        # Check daemon without importing daemon module
        daemon_running = await self._check_daemon_running()
        print("🔧 DAEMON STATUS")
        print("-" * 20)
        if daemon_running:
            print("✅ Status: Running")
            try:
                with open("/tmp/ipfs_kit_daemon.pid", 'r') as f:
                    pid = int(f.read().strip())
                print(f"   PID: {pid}")
            except:
                pass
        else:
            print("❌ Status: Not Running")
            print("   Start: python ipfs_kit_cli_ultra_fast.py daemon start")
        
        return 0
    
    async def cmd_version(self):
        """Show version (ultra-fast)."""
        print("🚀 IPFS-Kit Ultra-Fast CLI")
        print("=" * 30)
        print("Version: 4.0 (Standalone JIT)")
        print("Startup:", f"{self.jit.get_metrics()['startup_time']:.3f}s")
        
        available_count = sum(1 for feature in ['daemon', 'enhanced_features', 'wal_system', 'bucket_index']
                             if self.jit.is_available(feature))
        print(f"Available features: {available_count}/4")
        
        return 0
    
    async def cmd_help_extended(self):
        """Show extended help (ultra-fast)."""
        print("🚀 IPFS-Kit Ultra-Fast CLI - Commands")
        print("=" * 40)
        
        print("\n⚡ FAST COMMANDS:")
        print("   status                 System status")
        print("   version               Version info")
        print("   help-extended         This help")
        
        print("\n🔧 DAEMON COMMANDS:")
        print("   daemon start          Start daemon")
        print("   daemon stop           Stop daemon")
        print("   daemon status         Daemon status")
        
        print("\n📌 PIN COMMANDS:")
        if self.jit.is_available('wal_system'):
            print("   pin add <cid>         Add pin")
            print("   pin list              List pins")
            print("   ✅ WAL system available")
        else:
            print("   ❌ Pin commands require WAL system")
        
        print("\n🗂️ BUCKET COMMANDS:")
        if self.jit.is_available('bucket_index'):
            print("   bucket list           List buckets")
            print("   bucket info <name>    Bucket details")
            print("   ✅ Bucket index available")
        else:
            print("   ❌ Bucket commands require bucket index")
        
        print("\n📊 SYSTEM COMMANDS:")
        print("   metrics               Performance metrics")
        print("   config show           Show configuration")
        
        return 0
    
    # Heavy operations (with JIT loading)
    
    async def cmd_daemon_start(self, detach: bool = False):
        """Start daemon (loads daemon module only when needed)."""
        print("🚀 Starting IPFS-Kit Daemon...")
        
        if await self._check_daemon_running():
            print("⚠️  Daemon already running")
            return 0
        
        try:
            if detach:
                # Start in background without importing daemon
                cmd = [sys.executable, "ipfs_kit_daemon.py"]
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                
                await asyncio.sleep(2)
                if await self._check_daemon_running():
                    print("✅ Daemon started successfully")
                    return 0
                else:
                    print("❌ Failed to start daemon")
                    return 1
            else:
                # Try to import daemon module for foreground mode
                daemon_module = self.jit.import_module('ipfs_kit_daemon')
                if daemon_module:
                    daemon_class = self.jit.import_from_module('ipfs_kit_daemon', 'IPFSKitDaemon')
                    if daemon_class:
                        daemon = daemon_class()
                        await daemon.start()
                        return 0
                
                print("❌ Daemon components not available for foreground mode")
                return 1
                
        except Exception as e:
            print(f"❌ Error starting daemon: {e}")
            return 1
    
    async def cmd_daemon_stop(self):
        """Stop daemon (minimal imports)."""
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
                        os.kill(pid, 0)
                        await asyncio.sleep(1)
                    except ProcessLookupError:
                        break
                
                print("✅ Daemon stopped successfully")
                return 0
            else:
                print("⚠️  Daemon not running")
                return 0
                
        except Exception as e:
            print(f"❌ Error stopping daemon: {e}")
            return 1
    
    async def cmd_pin_add(self, cid: str, name: Optional[str] = None):
        """Add pin (loads WAL system only when needed)."""
        print(f"📌 Adding pin: {cid}")
        
        # Check if WAL system is available
        if not self.jit.is_available('wal_system'):
            print("❌ WAL system not available")
            return 1
        
        # Import WAL function only when needed
        add_pin_to_wal = self.jit.import_from_module('ipfs_kit_py.pin_wal', 'add_pin_to_wal')
        
        if not add_pin_to_wal:
            print("❌ Could not import WAL system")
            return 1
        
        try:
            metadata = {
                "name": name or "",
                "added_at": time.time(),
                "source": "ultra_fast_cli"
            }
            
            operation_id = await add_pin_to_wal(
                cid=cid,
                name=name,
                recursive=True,
                metadata=metadata,
                priority=1
            )
            
            print("✅ Pin operation queued")
            print(f"   CID: {cid}")
            if name:
                print(f"   Name: {name}")
            print(f"   Operation ID: {operation_id}")
            
            return 0
            
        except Exception as e:
            print(f"❌ Error adding pin: {e}")
            return 1
    
    async def cmd_pin_list(self, limit: int = 10):
        """List pins (loads WAL system only when needed)."""
        print("📋 Listing pins...")
        
        if not self.jit.is_available('wal_system'):
            print("❌ WAL system not available")
            return 1
        
        get_global_pin_wal = self.jit.import_from_module('ipfs_kit_py.pin_wal', 'get_global_pin_wal')
        
        if not get_global_pin_wal:
            print("❌ Could not import WAL system")
            return 1
        
        try:
            wal = get_global_pin_wal()
            stats = await wal.get_stats()
            
            print("📊 PIN STATUS")
            print("-" * 20)
            print(f"Pending: {stats.get('pending', 0)}")
            print(f"Completed: {stats.get('completed', 0)}")
            print(f"Failed: {stats.get('failed', 0)}")
            
            return 0
            
        except Exception as e:
            print(f"❌ Error listing pins: {e}")
            return 1
    
    async def cmd_bucket_list(self, show_metrics: bool = False):
        """List buckets (loads bucket index only when needed)."""
        print("🗂️ Listing Virtual Filesystems...")
        
        if not self.jit.is_available('bucket_index'):
            print("❌ Bucket index not available")
            return 1
        
        # Import bucket index only when needed
        bucket_index_class = self.jit.import_from_module(
            'ipfs_kit_py.enhanced_bucket_index', 
            'EnhancedBucketIndex'
        )
        
        if not bucket_index_class:
            print("❌ Could not import bucket index")
            return 1
        
        try:
            bucket_index = bucket_index_class()
            
            if show_metrics:
                result = bucket_index.get_comprehensive_metrics()
                if result["success"]:
                    metrics = result["data"]
                    print("📊 BUCKET METRICS")
                    print("-" * 20)
                    print(f"Total buckets: {metrics.get('total_buckets', 0)}")
                    print(f"Total files: {metrics.get('total_files', 0)}")
                    print(f"Total size: {metrics.get('total_size', 0)} bytes")
                    return 0
            
            # List buckets
            result = bucket_index.list_all_buckets()
            if result["success"]:
                buckets = result["data"]["buckets"]
                print(f"📋 Found {len(buckets)} bucket(s):")
                for bucket in buckets[:5]:  # Show first 5
                    print(f"   📁 {bucket['name']} ({bucket['type']})")
                    print(f"      Files: {bucket['file_count']:,}")
                return 0
            else:
                print(f"❌ Error: {result.get('error')}")
                return 1
            
        except Exception as e:
            print(f"❌ Error listing buckets: {e}")
            return 1
    
    async def cmd_metrics(self):
        """Show performance metrics (ultra-fast)."""
        print("📊 PERFORMANCE METRICS")
        print("=" * 25)
        
        metrics = self.jit.get_metrics()
        
        print("🚀 JIT System:")
        print(f"   Startup time: {metrics['startup_time']:.3f}s")
        print(f"   Cached modules: {metrics['cached_modules']}")
        print(f"   Failed imports: {metrics['failed_imports']}")
        print(f"   Cache size: {metrics['cache_size']}")
        
        print("\n⚡ Features:")
        for feature in ['daemon', 'enhanced_features', 'wal_system', 'bucket_index']:
            available = self.jit.is_available(feature)
            status = "✅" if available else "❌"
            print(f"   {status} {feature}")
        
        return 0
    
    async def cmd_config_show(self):
        """Show configuration (ultra-fast)."""
        print("⚙️  CONFIGURATION")
        print("-" * 20)
        
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
            print(f"❌ Error: {e}")
            return 1
    
    # Utility methods
    
    async def _check_daemon_running(self) -> bool:
        """Check if daemon is running (fast check)."""
        pid_file = "/tmp/ipfs_kit_daemon.pid"
        try:
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    return True
                except ProcessLookupError:
                    os.remove(pid_file)
                    return False
            return False
        except:
            return False


def create_parser():
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        description="IPFS-Kit Ultra-Fast CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Ultra-fast operations (0.1-0.2s)
  %(prog)s status                    # System status
  %(prog)s version                   # Version info  
  %(prog)s metrics                   # Performance metrics
  
  # Heavy operations (load modules as needed)
  %(prog)s daemon start              # Start daemon
  %(prog)s pin add <cid>             # Add pin
  %(prog)s bucket list               # List buckets
        """
    )
    
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Show detailed information')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Fast commands
    subparsers.add_parser('status', help='System status')
    subparsers.add_parser('version', help='Version info')
    subparsers.add_parser('help-extended', help='Extended help')
    subparsers.add_parser('metrics', help='Performance metrics')
    
    # Daemon commands
    daemon_parser = subparsers.add_parser('daemon', help='Daemon management')
    daemon_subparsers = daemon_parser.add_subparsers(dest='daemon_action')
    
    start_parser = daemon_subparsers.add_parser('start', help='Start daemon')
    start_parser.add_argument('--detach', action='store_true', help='Background mode')
    
    daemon_subparsers.add_parser('stop', help='Stop daemon')
    daemon_subparsers.add_parser('status', help='Daemon status')
    
    # Pin commands
    pin_parser = subparsers.add_parser('pin', help='Pin management')
    pin_subparsers = pin_parser.add_subparsers(dest='pin_action')
    
    add_parser = pin_subparsers.add_parser('add', help='Add pin')
    add_parser.add_argument('cid', help='CID to pin')
    add_parser.add_argument('--name', help='Pin name')
    
    list_parser = pin_subparsers.add_parser('list', help='List pins')
    list_parser.add_argument('--limit', type=int, default=10, help='Limit results')
    
    # Bucket commands
    bucket_parser = subparsers.add_parser('bucket', help='Bucket management')
    bucket_subparsers = bucket_parser.add_subparsers(dest='bucket_action')
    
    list_bucket_parser = bucket_subparsers.add_parser('list', help='List buckets')
    list_bucket_parser.add_argument('--metrics', action='store_true', help='Show metrics')
    
    # Config commands
    config_parser = subparsers.add_parser('config', help='Configuration')
    config_subparsers = config_parser.add_subparsers(dest='config_action')
    config_subparsers.add_parser('show', help='Show config')
    
    return parser


async def main():
    """Main entry point."""
    start_time = time.time()
    
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle help immediately (fastest possible)
    if not args.command:
        parser.print_help()
        print(f"\n⚡ Response time: {time.time() - start_time:.3f}s")
        return 0
    
    cli = UltraFastCLI()
    
    try:
        # Fast operations
        if args.command == 'status':
            return await cli.cmd_status(verbose=args.verbose)
        elif args.command == 'version':
            return await cli.cmd_version()
        elif args.command == 'help-extended':
            return await cli.cmd_help_extended()
        elif args.command == 'metrics':
            return await cli.cmd_metrics()
        elif args.command == 'config' and args.config_action == 'show':
            return await cli.cmd_config_show()
            
        # Heavy operations
        elif args.command == 'daemon':
            if args.daemon_action == 'start':
                return await cli.cmd_daemon_start(detach=args.detach)
            elif args.daemon_action == 'stop':
                return await cli.cmd_daemon_stop()
            elif args.daemon_action == 'status':
                return await cli.cmd_status(verbose=True)
                
        elif args.command == 'pin':
            if args.pin_action == 'add':
                return await cli.cmd_pin_add(args.cid, name=args.name)
            elif args.pin_action == 'list':
                return await cli.cmd_pin_list(limit=args.limit)
                
        elif args.command == 'bucket':
            if args.bucket_action == 'list':
                return await cli.cmd_bucket_list(show_metrics=args.metrics)
        
        parser.print_help()
        return 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Cancelled")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
