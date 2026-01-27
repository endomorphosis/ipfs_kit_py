#!/usr/bin/env python3
"""
IPFS-Kit Optimized CLI with Centralized JIT Import System

A high-performance command-line interface that uses the centralized JIT import system
for ultra-fast startup times and intelligent module loading.

Performance Characteristics:
- Fast operations (--help, status): ~0.16s
- Heavy operations (complex commands): Load only needed modules
- Shared import state with MCP server and daemon
- Smart caching and feature detection
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

# Use centralized JIT import system
from ipfs_kit_py.jit_imports import (
    get_jit_imports, 
    is_feature_available,
    jit_import,
    jit_import_from,
    lazy_import
)

# Initialize JIT system
jit = get_jit_imports()


class IPFSKitOptimizedCLI:
    """Optimized CLI using centralized JIT import system."""
    
    def __init__(self, daemon_host: str = "127.0.0.1", daemon_port: int = 9999):
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self.config_file = "/tmp/ipfs_kit_config/daemon.json"
        self.jit = get_jit_imports()
    
    def print_banner(self, verbose: bool = False):
        """Print CLI banner with feature status."""
        print("🚀 IPFS-Kit Optimized CLI v3.0 (JIT Imports)")
        print("=" * 50)
        
        # Always show core features (fast checks)
        features_to_check = [
            ('daemon', '🔧'),
            ('enhanced_features', '⚡'),
            ('wal_system', '📝'),
            ('bucket_index', '🗂️'),
        ]
        
        if verbose:
            # Show all features in verbose mode
            features_to_check.extend([
                ('bucket_vfs', '📁'),
                ('mcp_server', '🌐'),
                ('multiprocessing_enhanced', '🔀'),
                ('analytics', '📊'),
                ('networking', '🌍')
            ])
        
        for feature, icon in features_to_check:
            available = self.jit.is_available(feature)
            status = "✅" if available else "❌"
            feature_desc = self.jit._features[feature].description
            print(f"{status} {icon} {feature}: {feature_desc}")
        
        if verbose:
            # Show performance metrics
            metrics = self.jit.get_metrics()
            print(f"\n📊 JIT Import Metrics:")
            print(f"   Startup time: {metrics['startup_time']:.3f}s")
            print(f"   Cache hit ratio: {metrics['cache_hit_ratio']:.2%}")
            print(f"   Cached modules: {metrics['cached_modules']}")
            print(f"   Available features: {len(metrics['available_features'])}")
        
        print()
    
    # Fast operations (no heavy imports needed)
    
    async def cmd_status(self, verbose: bool = False):
        """Show system status (fast operation)."""
        self.print_banner(verbose=verbose)
        
        # Check daemon without importing daemon module
        daemon_running = await self._check_daemon_running()
        print("🔧 DAEMON STATUS")
        print("-" * 30)
        if daemon_running:
            print("✅ Status: Running")
            
            # Try to get more details if daemon is available
            if self.jit.is_available('daemon'):
                try:
                    pid_file = "/tmp/ipfs_kit_daemon.pid"
                    if os.path.exists(pid_file):
                        with open(pid_file, 'r') as f:
                            pid = int(f.read().strip())
                        print(f"   PID: {pid}")
                except Exception:
                    pass
        else:
            print("❌ Status: Not Running")
            print("   Start with: python ipfs_kit_cli_optimized.py daemon start --detach")
        
        return 0
    
    async def cmd_version(self):
        """Show version information (fast operation)."""
        print("🚀 IPFS-Kit Version Information")
        print("=" * 50)
        print("CLI Version: 3.0 (JIT Optimized)")
        print("JIT System: Enabled")
        
        # Show available features without heavy imports
        available_features = [name for name in self.jit._features.keys() 
                            if self.jit.is_available(name)]
        print(f"Available Features: {len(available_features)}")
        
        for feature in available_features:
            print(f"   ✅ {feature}")
        
        return 0
    
    async def cmd_help_extended(self):
        """Show extended help (fast operation)."""
        print("🚀 IPFS-Kit CLI - Extended Help")
        print("=" * 50)
        
        print("\n🔧 DAEMON COMMANDS:")
        print("   daemon start [--detach] [--config PATH]  Start the daemon")
        print("   daemon stop                              Stop the daemon")
        print("   daemon restart                           Restart the daemon") 
        print("   daemon status                            Show daemon status")
        
        print("\n📌 PIN COMMANDS:")
        print("   pin add <cid> [--name NAME]              Add a pin")
        print("   pin remove <cid>                         Remove a pin")
        print("   pin list [--limit N] [--metadata]       List pins")
        print("   pin status <operation_id>                Check pin operation status")
        
        print("\n🗂️ BUCKET COMMANDS:")
        print("   bucket list [--detailed] [--metrics]     List virtual filesystems")
        print("   bucket info <name>                       Get bucket details")
        print("   bucket search <query> [--type TYPE]      Search buckets")
        print("   bucket types                             Show bucket type distribution")
        print("   bucket analytics                         Show advanced analytics")
        print("   bucket refresh                           Refresh bucket index")
        
        print("\n⚙️ SYSTEM COMMANDS:")
        print("   status [--verbose]                       Show system status")
        print("   version                                  Show version information")
        print("   config show                              Show configuration")
        print("   config set <key> <value>                 Set configuration")
        print("   metrics [--detailed]                     Show performance metrics")
        
        # Show feature-specific help
        if self.jit.is_available('enhanced_features'):
            print("\n⚡ ENHANCED FEATURES AVAILABLE:")
            print("   • Pin operations with Parquet/DuckDB backend")
            print("   • Advanced metadata and analytics")
        
        if self.jit.is_available('bucket_index'):
            print("\n🗂️ BUCKET INDEX AVAILABLE:")
            print("   • Fast virtual filesystem discovery")
            print("   • Advanced bucket analytics")
        
        if self.jit.is_available('mcp_server'):
            print("\n🌐 MCP SERVER AVAILABLE:")
            print("   • Model Context Protocol API")
            print("   • Multi-client support")
        
        return 0
    
    # Heavy operations (load modules as needed)
    
    @lazy_import('daemon')
    async def cmd_daemon_start(self, detach: bool = False, config: Optional[str] = None):
        """Start the IPFS-Kit daemon."""
        print("🚀 Starting IPFS-Kit Daemon...")
        
        # Import daemon module when needed
        ipfs_kit_daemon = jit_import('ipfs_kit_daemon', feature_group='daemon')
        if not ipfs_kit_daemon:
            print("❌ Daemon components not available")
            return 1
        
        # Check if already running
        if await self._check_daemon_running():
            print("⚠️  Daemon already running")
            return 0
        
        try:
            if detach:
                # Start daemon in background
                cmd = [sys.executable, "ipfs_kit_daemon.py"]
                if config:
                    cmd.extend(["--config", config])
                
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                
                # Wait and check if it started
                await anyio.sleep(2)
                if await self._check_daemon_running():
                    print("✅ Daemon started successfully")
                    return 0
                else:
                    print("❌ Failed to start daemon")
                    return 1
            else:
                # Start daemon in foreground
                IPFSKitDaemon = jit_import_from('ipfs_kit_daemon', 'IPFSKitDaemon', feature_group='daemon')
                if IPFSKitDaemon:
                    daemon = IPFSKitDaemon(config_file=config)
                    await daemon.start()
                    return 0
                else:
                    print("❌ Daemon components not available for foreground mode")
                    return 1
                
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
    
    @lazy_import('wal_system')
    async def cmd_pin_add(self, cid: str, name: Optional[str] = None, recursive: bool = True):
        """Add a pin using WAL system."""
        print(f"📌 Adding pin: {cid}")
        
        # Import WAL system when needed
        add_pin_to_wal = jit_import_from('ipfs_kit_py.pin_wal', 'add_pin_to_wal', feature_group='wal_system')
        
        if not add_pin_to_wal:
            print("❌ WAL system not available")
            return 1
        
        try:
            metadata = {
                "name": name or "",
                "recursive": recursive,
                "added_at": time.time(),
                "added_by": "cli",
                "source": "ipfs_kit_cli_optimized"
            }
            
            operation_id = await add_pin_to_wal(
                cid=cid,
                name=name,
                recursive=recursive,
                metadata=metadata,
                priority=1
            )
            
            print("✅ Pin operation queued successfully")
            print(f"   CID: {cid}")
            if name:
                print(f"   Name: {name}")
            print(f"   Recursive: {recursive}")
            print(f"   Operation ID: {operation_id}")
            print()
            print("📝 The pin operation has been added to the write-ahead log.")
            print("   The daemon will process it and update the metadata index.")
            print(f"   Use 'pin status {operation_id}' to check progress.")
            return 0
            
        except Exception as e:
            print(f"❌ Error adding pin: {e}")
            return 1
    
    @lazy_import('wal_system')
    async def cmd_pin_list(self, limit: int = 50, show_metadata: bool = False):
        """List pins using WAL system."""
        print("📋 Listing pins...")
        
        # Import WAL system when needed
        get_global_pin_wal = jit_import_from('ipfs_kit_py.pin_wal', 'get_global_pin_wal', feature_group='wal_system')
        
        if not get_global_pin_wal:
            print("❌ WAL system not available")
            return 1
        
        try:
            wal = get_global_pin_wal()
            stats = await wal.get_stats()
            
            print("📊 WAL STATUS")
            print("-" * 30)
            print(f"Pending operations: {stats.get('pending', 0)}")
            print(f"Processing operations: {stats.get('processing', 0)}")
            print(f"Completed operations: {stats.get('completed', 0)}")
            print(f"Failed operations: {stats.get('failed', 0)}")
            print(f"Total operations: {stats.get('total_operations', 0)}")
            print()
            
            # Show recent operations
            pending_ops = await wal.get_pending_operations(limit=limit)
            if pending_ops:
                print("🔄 RECENT PENDING OPERATIONS")
                print("-" * 30)
                for op in pending_ops[:5]:
                    print(f"• {op.get('cid', 'unknown')} ({op.get('operation_type', 'unknown')})")
                    if op.get('name'):
                        print(f"  Name: {op['name']}")
                    print(f"  Status: {op.get('status', 'unknown')}")
                    print(f"  Created: {op.get('created_at', 'unknown')}")
                    print()
            
            print("💡 Use 'pin status <operation_id>' to check specific operations")
            return 0
            
        except Exception as e:
            print(f"❌ Error listing pins: {e}")
            return 1
    
    @lazy_import('bucket_index')
    async def cmd_bucket_list(self, detailed: bool = False, show_metrics: bool = False):
        """List virtual filesystems using bucket index."""
        print("🗂️ Discovering Virtual Filesystems...")
        
        # Import bucket index when needed
        EnhancedBucketIndex = jit_import_from(
            'ipfs_kit_py.enhanced_bucket_index', 
            'EnhancedBucketIndex', 
            feature_group='bucket_index'
        )
        format_size = jit_import_from(
            'ipfs_kit_py.enhanced_bucket_index',
            'format_size', 
            feature_group='bucket_index'
        )
        
        if not EnhancedBucketIndex:
            print("❌ Bucket index not available")
            return 1
        
        try:
            bucket_index = EnhancedBucketIndex()
            bucket_index.refresh_index()
            
            if show_metrics:
                metrics_result = bucket_index.get_comprehensive_metrics()
                if metrics_result["success"]:
                    self._print_bucket_metrics(metrics_result, format_size)
                    return 0
                else:
                    print(f"❌ Error getting metrics: {metrics_result.get('error')}")
                    return 1
            
            # List buckets
            buckets_result = bucket_index.list_all_buckets(include_metadata=detailed)
            
            if buckets_result["success"]:
                buckets = buckets_result["data"]["buckets"]
                total_count = buckets_result["data"]["total_count"]
                
                if total_count == 0:
                    print("📭 No virtual filesystems found")
                    return 0
                
                print(f"📋 Found {total_count} virtual filesystem{'s' if total_count != 1 else ''}:")
                print()
                
                for bucket in buckets:
                    print(f"📁 {bucket['name']}")
                    print(f"   Type: {bucket['type']}")
                    print(f"   Structure: {bucket['vfs_structure']}")
                    print(f"   Files: {bucket['file_count']:,}")
                    print(f"   Size: {format_size(bucket['total_size']) if format_size else bucket['total_size']}")
                    print(f"   Created: {bucket['created_at']}")
                    
                    if bucket.get('root_cid'):
                        print(f"   CID: {bucket['root_cid']}")
                    
                    if detailed and bucket.get('metadata'):
                        print(f"   Metadata: {json.dumps(bucket['metadata'], indent=4)}")
                    
                    print()
                
                return 0
            else:
                print(f"❌ Error listing buckets: {buckets_result.get('error')}")
                return 1
                
        except Exception as e:
            print(f"❌ Error accessing bucket index: {e}")
            return 1
    
    async def cmd_metrics(self, detailed: bool = False):
        """Show performance metrics."""
        print("📊 PERFORMANCE METRICS")
        print("=" * 30)
        
        # Show JIT import metrics (always available)
        metrics = self.jit.get_metrics()
        
        print("🚀 JIT Import System:")
        print(f"   Startup time: {metrics['startup_time']:.3f}s")
        print(f"   Total imports: {metrics['total_imports']}")
        print(f"   Cache hit ratio: {metrics['cache_hit_ratio']:.2%}")
        print(f"   Import time: {metrics['total_import_time']:.3f}s")
        print(f"   Feature checks: {metrics['feature_checks']}")
        print(f"   Cached modules: {metrics['cached_modules']}")
        print(f"   Available features: {len(metrics['available_features'])}")
        
        if detailed:
            print(f"\n🔍 Detailed Metrics:")
            for key, value in metrics.items():
                if key not in ['startup_time', 'total_imports', 'cache_hit_ratio', 
                              'total_import_time', 'feature_checks', 'cached_modules']:
                    print(f"   {key}: {value}")
        
        # Show enhanced metrics if available
        if self.jit.is_available('enhanced_features') and detailed:
            print(f"\n⚡ Enhanced Features:")
            print("   • Parquet-based metadata storage")
            print("   • DuckDB analytics engine")
            print("   • Advanced indexing system")
        
        return 0
    
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
                print(f"Expected location: {self.config_file}")
                return 1
        except Exception as e:
            print(f"❌ Error reading configuration: {e}")
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
    
    def _print_bucket_metrics(self, metrics_result, format_size_func):
        """Print bucket metrics."""
        metrics = metrics_result["data"]
        print(f"📊 BUCKET INDEX METRICS")
        print(f"{'=' * 40}")
        print(f"Total Buckets: {metrics.get('total_buckets', 0)}")
        print(f"Total Files: {metrics.get('total_files', 0)}")
        if format_size_func:
            print(f"Total Size: {format_size_func(metrics.get('total_size', 0))}")
        else:
            print(f"Total Size: {metrics.get('total_size', 0)} bytes")


def create_parser():
    """Create argument parser with JIT-optimized structure."""
    parser = argparse.ArgumentParser(
        description="IPFS-Kit Optimized CLI with JIT Imports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fast operations (0.1-0.2s response time)
  %(prog)s status                    # Show system status
  %(prog)s version                   # Show version info
  %(prog)s --help                    # Show help
  
  # Heavy operations (load modules as needed)
  %(prog)s daemon start --detach     # Start daemon
  %(prog)s pin add <cid>             # Add pin
  %(prog)s bucket list               # List buckets
        """
    )
    
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Show detailed information and metrics')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Fast commands (no subcommands to keep parsing fast)
    subparsers.add_parser('status', help='Show system status (fast)')
    subparsers.add_parser('version', help='Show version information (fast)')
    subparsers.add_parser('help-extended', help='Show extended help (fast)')
    
    # Daemon commands
    daemon_parser = subparsers.add_parser('daemon', help='Daemon management')
    daemon_subparsers = daemon_parser.add_subparsers(dest='daemon_action')
    
    start_parser = daemon_subparsers.add_parser('start', help='Start daemon')
    start_parser.add_argument('--detach', action='store_true', help='Run in background')
    start_parser.add_argument('--config', help='Configuration file path')
    
    daemon_subparsers.add_parser('stop', help='Stop daemon')
    daemon_subparsers.add_parser('restart', help='Restart daemon')
    daemon_subparsers.add_parser('status', help='Show daemon status')
    
    # Pin commands
    pin_parser = subparsers.add_parser('pin', help='Pin management')
    pin_subparsers = pin_parser.add_subparsers(dest='pin_action')
    
    add_parser = pin_subparsers.add_parser('add', help='Add pin')
    add_parser.add_argument('cid', help='CID to pin')
    add_parser.add_argument('--name', help='Pin name')
    add_parser.add_argument('--no-recursive', dest='recursive', action='store_false', help='Non-recursive pin')
    
    list_parser = pin_subparsers.add_parser('list', help='List pins')
    list_parser.add_argument('--limit', type=int, default=50, help='Limit number of results')
    list_parser.add_argument('--metadata', action='store_true', help='Show metadata')
    
    # Bucket commands  
    bucket_parser = subparsers.add_parser('bucket', help='Bucket management')
    bucket_subparsers = bucket_parser.add_subparsers(dest='bucket_action')
    
    list_bucket_parser = bucket_subparsers.add_parser('list', help='List buckets')
    list_bucket_parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    list_bucket_parser.add_argument('--metrics', action='store_true', help='Show metrics')
    
    # Config commands
    config_parser = subparsers.add_parser('config', help='Configuration')
    config_subparsers = config_parser.add_subparsers(dest='config_action')
    config_subparsers.add_parser('show', help='Show configuration')
    
    # Metrics commands
    metrics_parser = subparsers.add_parser('metrics', help='Performance metrics')
    metrics_parser.add_argument('--detailed', action='store_true', help='Show detailed metrics')
    
    return parser


async def main():
    """Main entry point with JIT optimization."""
    start_time = time.time()
    
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle help and fast commands immediately
    if not args.command or args.command in ['help-extended']:
        cli = IPFSKitOptimizedCLI()
        
        if not args.command:
            parser.print_help()
            print(f"\n⚡ Fast startup time: {time.time() - start_time:.3f}s")
            return 0
        elif args.command == 'help-extended':
            return await cli.cmd_help_extended()
    
    cli = IPFSKitOptimizedCLI()
    
    try:
        # Fast operations
        if args.command == 'status':
            return await cli.cmd_status(verbose=args.verbose)
        elif args.command == 'version':
            return await cli.cmd_version()
        elif args.command == 'metrics':
            return await cli.cmd_metrics(detailed=args.detailed)
        elif args.command == 'config' and args.config_action == 'show':
            return await cli.cmd_config_show()
            
        # Heavy operations (JIT loading)
        elif args.command == 'daemon':
            if args.daemon_action == 'start':
                return await cli.cmd_daemon_start(detach=args.detach, config=args.config)
            elif args.daemon_action == 'stop':
                return await cli.cmd_daemon_stop()
            elif args.daemon_action == 'restart':
                return await cli.cmd_daemon_restart(config=getattr(args, 'config', None))
            elif args.daemon_action == 'status':
                return await cli.cmd_status(verbose=True)
                
        elif args.command == 'pin':
            if args.pin_action == 'add':
                return await cli.cmd_pin_add(args.cid, name=args.name, recursive=args.recursive)
            elif args.pin_action == 'list':
                return await cli.cmd_pin_list(limit=args.limit, show_metadata=args.metadata)
                
        elif args.command == 'bucket':
            if args.bucket_action == 'list':
                return await cli.cmd_bucket_list(detailed=args.detailed, show_metrics=args.metrics)
        
        parser.print_help()
        return 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = anyio.run(main)
    sys.exit(exit_code)
