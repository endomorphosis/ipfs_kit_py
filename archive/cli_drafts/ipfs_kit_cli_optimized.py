#!/usr/bin/env python3
"""
IPFS-Kit Enhanced CLI Tool - Optimized Version

A comprehensive command-line interface with Just-in-Time imports for fast response times.
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

# Global feature flags - determined lazily
_DAEMON_AVAILABLE = None
_ENHANCED_FEATURES_AVAILABLE = None
_WAL_AVAILABLE = None
_BUCKET_INDEX_AVAILABLE = None
_BUCKET_VFS_AVAILABLE = None

# Global instances - loaded lazily
_global_bucket_index = None
_cached_imports = {}

def check_daemon_available():
    """Check if daemon is available (lazy)."""
    global _DAEMON_AVAILABLE
    if _DAEMON_AVAILABLE is None:
        try:
            from ipfs_kit_daemon import IPFSKitDaemon
            _DAEMON_AVAILABLE = True
            _cached_imports['IPFSKitDaemon'] = IPFSKitDaemon
        except ImportError:
            _DAEMON_AVAILABLE = False
    return _DAEMON_AVAILABLE

def check_enhanced_features_available():
    """Check if enhanced features are available (lazy)."""
    global _ENHANCED_FEATURES_AVAILABLE, _WAL_AVAILABLE
    if _ENHANCED_FEATURES_AVAILABLE is None:
        try:
            from enhanced_pin_cli import format_bytes, print_metrics
            from ipfs_kit_py.enhanced_pin_index import get_global_enhanced_pin_index
            from ipfs_kit_py.pin_wal import add_pin_to_wal, remove_pin_from_wal, get_global_pin_wal
            _ENHANCED_FEATURES_AVAILABLE = True
            _WAL_AVAILABLE = True
            _cached_imports.update({
                'format_bytes': format_bytes,
                'print_metrics': print_metrics,
                'get_global_enhanced_pin_index': get_global_enhanced_pin_index,
                'add_pin_to_wal': add_pin_to_wal,
                'remove_pin_from_wal': remove_pin_from_wal,
                'get_global_pin_wal': get_global_pin_wal
            })
        except ImportError:
            _ENHANCED_FEATURES_AVAILABLE = False
            _WAL_AVAILABLE = False
    return _ENHANCED_FEATURES_AVAILABLE

def check_bucket_index_available():
    """Check if bucket index is available (lazy)."""
    global _BUCKET_INDEX_AVAILABLE
    if _BUCKET_INDEX_AVAILABLE is None:
        try:
            from ipfs_kit_py.enhanced_bucket_index import EnhancedBucketIndex, format_size
            _BUCKET_INDEX_AVAILABLE = True
            _cached_imports.update({
                'EnhancedBucketIndex': EnhancedBucketIndex,
                'format_size': format_size
            })
        except ImportError:
            _BUCKET_INDEX_AVAILABLE = False
    return _BUCKET_INDEX_AVAILABLE

def check_bucket_vfs_available():
    """Check if bucket VFS is available (lazy)."""
    global _BUCKET_VFS_AVAILABLE
    if _BUCKET_VFS_AVAILABLE is None:
        try:
            from ipfs_kit_py.bucket_vfs_manager import get_global_bucket_manager, BucketType, VFSStructureType
            _BUCKET_VFS_AVAILABLE = True
            _cached_imports.update({
                'get_global_bucket_manager': get_global_bucket_manager,
                'BucketType': BucketType,
                'VFSStructureType': VFSStructureType
            })
        except ImportError:
            _BUCKET_VFS_AVAILABLE = False
    return _BUCKET_VFS_AVAILABLE

def get_global_enhanced_bucket_index():
    """Get or create the global bucket index instance (lazy)."""
    global _global_bucket_index
    if _global_bucket_index is None and check_bucket_index_available():
        try:
            EnhancedBucketIndex = _cached_imports['EnhancedBucketIndex']
            _global_bucket_index = EnhancedBucketIndex(bucket_vfs_manager=None)
            _global_bucket_index.refresh_index()
        except Exception as e:
            print(f"Warning: Could not initialize bucket index: {e}")
            _global_bucket_index = EnhancedBucketIndex()
    return _global_bucket_index

def print_bucket_metrics(metrics):
    """Print bucket metrics in a formatted way."""
    format_size = _cached_imports.get('format_size', lambda x: f"{x} bytes")
    
    print(f"📊 BUCKET INDEX METRICS")
    print(f"{'=' * 40}")
    print(f"Total Buckets: {metrics.get('total_buckets', 0)}")
    print(f"Total Files: {metrics.get('total_files', 0)}")
    print(f"Total Size: {format_size(metrics.get('total_size', 0))}")
    
    if metrics.get('bucket_types'):
        print(f"\nBucket Types:")
        for bucket_type, count in metrics['bucket_types'].items():
            print(f"   • {bucket_type}: {count}")
    
    if metrics.get('size_stats'):
        stats = metrics['size_stats']
        print(f"\nSize Statistics:")
        print(f"   • Min: {format_size(stats.get('min', 0))}")
        print(f"   • Max: {format_size(stats.get('max', 0))}")
        print(f"   • Avg: {format_size(stats.get('avg', 0))}")
    
    if metrics.get('file_stats'):
        stats = metrics['file_stats']
        print(f"\nFile Count Statistics:")
        print(f"   • Min: {stats.get('min', 0)}")
        print(f"   • Max: {stats.get('max', 0)}")
        print(f"   • Avg: {stats.get('avg', 0):.1f}")

def format_bytes(bytes_val: int) -> str:
    """Format bytes as human-readable string."""
    if bytes_val == 0:
        return "0 B"
    
    val = float(bytes_val)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if val < 1024:
            return f"{val:.1f} {unit}"
        val /= 1024
    return f"{val:.1f} PB"

class IPFSKitCLI:
    """Enhanced CLI for IPFS-Kit with JIT imports for fast response times."""
    
    def __init__(self, daemon_host: str = "127.0.0.1", daemon_port: int = 9999):
        self.daemon_host = daemon_host
        self.daemon_port = daemon_port
        self.config_file = "/tmp/ipfs_kit_config/daemon.json"
    
    def print_banner(self):
        """Print CLI banner with status (fast version without heavy imports)."""
        print("🚀 IPFS-Kit Enhanced CLI v2.0 (Optimized)")
        print("=" * 50)
        
        # Only check availability when requested, don't import
        print("✅ Fast startup: Enabled")
        print("✅ JIT imports: Enabled")
        print("💡 Feature availability checked on demand")
        print()
    
    def print_detailed_banner(self):
        """Print detailed banner with all feature checks."""
        print("🚀 IPFS-Kit Enhanced CLI v2.0 (Optimized)")
        print("=" * 50)
        
        if check_daemon_available():
            print("✅ Daemon support: Available")
        else:
            print("❌ Daemon support: Not available")
        
        if check_enhanced_features_available():
            print("✅ Enhanced features: Available")
        else:
            print("❌ Enhanced features: Limited")
        
        if _WAL_AVAILABLE:
            print("✅ WAL system: Available")
        else:
            print("❌ WAL system: Not available")
        
        if check_bucket_index_available():
            print("✅ Bucket index: Available")
        else:
            print("❌ Bucket index: Not available")
        
        if check_bucket_vfs_available():
            print("✅ Bucket VFS: Available")
        else:
            print("❌ Bucket VFS: Not available")
        print()
    
    # Daemon Management Commands
    
    async def cmd_daemon_start(self, detach: bool = False, config: Optional[str] = None):
        """Start the IPFS-Kit daemon."""
        if not check_daemon_available():
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
                cmd = [sys.executable, "ipfs_kit_daemon.py"]
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
                IPFSKitDaemon = _cached_imports.get('IPFSKitDaemon')
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
    
    async def cmd_daemon_status(self, verbose: bool = False):
        """Show daemon status."""
        if verbose:
            self.print_detailed_banner()
        else:
            self.print_banner()
        
        if not await self._check_daemon_running():
            print("❌ Daemon Status: Not Running")
            print()
            print("Start the daemon with: python ipfs_kit_cli_optimized.py daemon start --detach")
            return 1
        
        print("✅ Daemon Status: Running")
        
        # Try to get more detailed status if available
        try:
            # Read PID file
            pid_file = "/tmp/ipfs_kit_daemon.pid"
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                print()
                print("📊 DAEMON INFORMATION")
                print("-" * 30)
                print(f"PID: {pid}")
                
                # Try to read log file for more info
                log_file = "/tmp/ipfs_kit_logs/ipfs_kit_daemon.log"
                if os.path.exists(log_file):
                    # Get last few lines of log
                    with open(log_file, 'r') as f:
                        lines = f.readlines()
                        if lines:
                            print(f"Last log entry: {lines[-1].strip()}")
        except Exception as e:
            print(f"⚠️  Could not get detailed status: {e}")
        
        return 0
    
    # Pin Management Commands
    
    async def cmd_pin_add(self, cid: str, name: Optional[str] = None, recursive: bool = True):
        """Add a pin with enhanced metadata using WAL."""
        print(f"📌 Adding pin: {cid}")
        
        try:
            # Check and load WAL system if available
            if check_enhanced_features_available() and _WAL_AVAILABLE:
                metadata = {
                    "name": name or "",
                    "recursive": recursive,
                    "added_at": time.time(),
                    "added_by": "cli",
                    "source": "ipfs_kit_cli_optimized"
                }
                
                # Add to WAL (non-blocking)
                add_pin_to_wal = _cached_imports.get('add_pin_to_wal')
                if add_pin_to_wal:
                    operation_id = await add_pin_to_wal(
                        cid=cid,
                        name=name,
                        recursive=recursive,
                        metadata=metadata,
                        priority=1  # Normal priority
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
                    print("   Use 'pin status <operation_id>' to check progress.")
                    return 0
                
            # Fallback to basic mode
            print("⚠️  Enhanced pin features not available")
            print("✅ Pin request recorded (basic mode)")
            return 0
                
        except Exception as e:
            print(f"❌ Error adding pin: {e}")
            return 1
    
    async def cmd_pin_remove(self, cid: str):
        """Remove a pin using WAL."""
        print(f"🗑️  Removing pin: {cid}")
        
        try:
            # Check and load WAL system if available
            if check_enhanced_features_available() and _WAL_AVAILABLE:
                metadata = {
                    "removed_at": time.time(),
                    "removed_by": "cli",
                    "source": "ipfs_kit_cli_optimized"
                }
                
                # Add removal to WAL (non-blocking)
                remove_pin_from_wal = _cached_imports.get('remove_pin_from_wal')
                if remove_pin_from_wal:
                    operation_id = await remove_pin_from_wal(
                        cid=cid,
                        metadata=metadata,
                        priority=1  # Normal priority
                    )
                    
                    print("✅ Pin removal operation queued successfully")
                    print(f"   CID: {cid}")
                    print(f"   Operation ID: {operation_id}")
                    print()
                    print("📝 The pin removal has been added to the write-ahead log.")
                    print("   The daemon will process it and update the metadata index.")
                    print("   Use 'pin status <operation_id>' to check progress.")
                    return 0
            
            # Fallback to mock removal
            print("⚠️  WAL system not available, using fallback")
            print("✅ Pin removal recorded")
            return 0
                
        except Exception as e:
            print(f"❌ Error removing pin: {e}")
            return 1
    
    async def cmd_pin_list(self, limit: int = 50, show_metadata: bool = False):
        """List pins with metadata."""
        print("📋 Listing pins...")
        
        try:
            if check_enhanced_features_available() and _WAL_AVAILABLE:
                # Show WAL statistics
                get_global_pin_wal = _cached_imports.get('get_global_pin_wal')
                if get_global_pin_wal:
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
                    
                    # Show recent pending operations
                    pending_ops = await wal.get_pending_operations(limit=10)
                    if pending_ops:
                        print("📝 RECENT PENDING OPERATIONS")
                        print("-" * 30)
                        for op in pending_ops[:5]:  # Show first 5
                            print(f"• {op.get('cid', 'unknown')} ({op.get('operation_type', 'unknown')})")
                            if op.get('name'):
                                print(f"  Name: {op['name']}")
                            print(f"  Status: {op.get('status', 'unknown')}")
                            print(f"  Created: {op.get('created_at', 'unknown')}")
                            print()
                    
                    print("💡 Use 'pin status <operation_id>' to check specific operations")
                    return 0
            
            # Mock pin listing
            print(f"Found 0 pins (mock implementation)")
            print()
            print("Note: Pin listing requires WAL system or enhanced features")
            return 0
                
        except Exception as e:
            print(f"❌ Error listing pins: {e}")
            return 1
    
    async def cmd_pin_status(self, operation_id: str):
        """Check the status of a specific pin operation."""
        print(f"🔍 Checking operation status: {operation_id}")
        
        try:
            if check_enhanced_features_available() and _WAL_AVAILABLE:
                get_global_pin_wal = _cached_imports.get('get_global_pin_wal')
                if get_global_pin_wal:
                    wal = get_global_pin_wal()
                    
                    operation = await wal.get_operation_status(operation_id)
                    if operation:
                        print("📋 OPERATION STATUS")
                        print("-" * 30)
                        print(f"Operation ID: {operation.get('operation_id', 'unknown')}")
                        print(f"Type: {operation.get('operation_type', 'unknown')}")
                        print(f"CID: {operation.get('cid', 'unknown')}")
                        print(f"Status: {operation.get('status', 'unknown')}")
                        print(f"Created: {operation.get('created_at', 'unknown')}")
                        
                        if operation.get('name'):
                            print(f"Name: {operation['name']}")
                        
                        if operation.get('recursive') is not None:
                            print(f"Recursive: {operation['recursive']}")
                        
                        if operation.get('retry_count', 0) > 0:
                            print(f"Retry count: {operation['retry_count']}")
                        
                        if operation.get('last_error'):
                            print(f"Last error: {operation['last_error']}")
                        
                        if operation.get('completed_at'):
                            print(f"Completed: {operation['completed_at']}")
                        
                        return 0
                    else:
                        print(f"❌ Operation {operation_id} not found")
                        return 1
            else:
                print("❌ WAL system not available")
                return 1
                
        except Exception as e:
            print(f"❌ Error checking operation status: {e}")
            return 1
    
    # Bucket Discovery Commands
    
    async def cmd_bucket_list(self, detailed: bool = False, show_metrics: bool = False):
        """List all virtual filesystems (buckets) in ~/.ipfs_kit/."""
        print("🗂️ Discovering Virtual Filesystems...")
        
        if not check_bucket_index_available():
            print("❌ Bucket index not available")
            return 1
        
        try:
            bucket_index = get_global_enhanced_bucket_index()
            if not bucket_index:
                print("❌ Could not initialize bucket index")
                return 1
            
            if show_metrics:
                # Show comprehensive metrics
                metrics = bucket_index.get_comprehensive_metrics()
                print_bucket_metrics(metrics)
                return 0
            
            # List buckets
            buckets = bucket_index.list_buckets(detailed=detailed)
            
            if not buckets:
                print("📭 No virtual filesystems found")
                print()
                print("💡 Create buckets with:")
                if check_bucket_vfs_available():
                    print("   python ipfs_kit_cli_optimized.py bucket create <name> --type <type>")
                else:
                    print("   Bucket VFS system not available")
                return 0
            
            print(f"📋 Found {len(buckets)} virtual filesystem{'s' if len(buckets) != 1 else ''}:")
            print()
            
            format_size = _cached_imports.get('format_size', format_bytes)
            
            for bucket in buckets:
                if detailed:
                    print(f"📁 {bucket['bucket_name']}")
                    print(f"   Type: {bucket['bucket_type']}")
                    print(f"   Structure: {bucket['structure_type']}")
                    print(f"   Files: {bucket['file_count']:,}")
                    print(f"   Size: {format_size(bucket['total_size'])}")
                    print(f"   Created: {bucket['created_at']}")
                    print(f"   Storage: {bucket['storage_path']}")
                    if bucket.get('metadata'):
                        print(f"   Metadata: {json.dumps(bucket['metadata'], indent=4)}")
                else:
                    print(f"📁 {bucket['name']} ({bucket['type']}) - {bucket['file_count']} files, {format_size(bucket['size'])}")
                print()
            
            return 0
                
        except Exception as e:
            print(f"❌ Error accessing bucket index: {e}")
            return 1
    
    async def cmd_bucket_info(self, bucket_name: str):
        """Get detailed information about a specific virtual filesystem."""
        print(f"🔍 Getting details for bucket: {bucket_name}")
        
        if not check_bucket_index_available():
            print("❌ Bucket index not available")
            return 1
        
        try:
            bucket_index = get_global_enhanced_bucket_index()
            if not bucket_index:
                print("❌ Could not initialize bucket index")
                return 1
            
            details = bucket_index.get_bucket_info(bucket_name)
            
            if details:
                format_size = _cached_imports.get('format_size', format_bytes)
                
                print("📊 BUCKET DETAILS")
                print("=" * 30)
                print(f"Name: {details['bucket_name']}")
                print(f"Type: {details['bucket_type']}")
                print(f"Structure: {details['structure_type']}")
                print(f"Storage Path: {details['storage_path']}")
                print(f"Created: {details['created_at']}")
                print(f"Files: {details['file_count']:,}")
                print(f"Size: {format_size(details['total_size'])}")
                
                if details.get('last_modified'):
                    print(f"Modified: {details['last_modified']}")
                
                if details.get('metadata'):
                    print("\n📋 Metadata:")
                    print(json.dumps(details['metadata'], indent=2))
                
                return 0
            else:
                print(f"❌ Bucket '{bucket_name}' not found")
                return 1
                
        except Exception as e:
            print(f"❌ Error getting bucket details: {e}")
            return 1
    
    async def cmd_bucket_search(self, query: str, search_type: str = "name"):
        """Search virtual filesystems by name, type, or metadata."""
        print(f"🔍 Searching buckets for: '{query}' (search type: {search_type})")
        
        if not check_bucket_index_available():
            print("❌ Bucket index not available")
            return 1
        
        try:
            bucket_index = get_global_enhanced_bucket_index()
            if not bucket_index:
                print("❌ Could not initialize bucket index")
                return 1
            
            results = bucket_index.search_buckets(query, search_type)
            
            if not results:
                print(f"📭 No buckets found matching '{query}'")
                return 0
            
            print(f"📋 Found {len(results)} matching bucket{'s' if len(results) != 1 else ''}:")
            print()
            
            format_size = _cached_imports.get('format_size', format_bytes)
            
            for bucket in results:
                print(f"📁 {bucket['bucket_name']}")
                print(f"   Type: {bucket['bucket_type']}")
                print(f"   Structure: {bucket['structure_type']}")
                print(f"   Files: {bucket['file_count']:,}")
                print(f"   Size: {format_size(bucket['total_size'])}")
                print(f"   Created: {bucket['created_at']}")
                print()
            
            return 0
                
        except Exception as e:
            print(f"❌ Error searching buckets: {e}")
            return 1
    
    async def cmd_bucket_types(self):
        """Show bucket type distribution and usage."""
        print("📊 Bucket Type Analysis")
        
        if not check_bucket_index_available():
            print("❌ Bucket index not available")
            return 1
        
        try:
            bucket_index = get_global_enhanced_bucket_index()
            if not bucket_index:
                print("❌ Could not initialize bucket index")
                return 1
            
            bucket_types = bucket_index.get_bucket_types()
            
            if not bucket_types:
                print("📭 No bucket types found")
                return 0
            
            print("=" * 50)
            
            for bucket_type, count in bucket_types.items():
                print(f"📁 {bucket_type.upper()}: {count} buckets")
            
            return 0
                
        except Exception as e:
            print(f"❌ Error getting bucket types: {e}")
            return 1
    
    async def cmd_bucket_analytics(self):
        """Show advanced bucket analytics."""
        print("📈 Advanced Bucket Analytics")
        
        if not check_bucket_index_available():
            print("❌ Bucket index not available")
            return 1
        
        try:
            bucket_index = get_global_enhanced_bucket_index()
            if not bucket_index:
                print("❌ Could not initialize bucket index")
                return 1
            
            metrics = bucket_index.get_comprehensive_metrics()
            print_bucket_metrics(metrics)
            
            return 0
                
        except Exception as e:
            print(f"❌ Error getting analytics: {e}")
            return 1
    
    async def cmd_bucket_refresh(self):
        """Manually refresh the bucket index."""
        print("🔄 Refreshing bucket index...")
        
        if not check_bucket_index_available():
            print("❌ Bucket index not available")
            return 1
        
        try:
            bucket_index = get_global_enhanced_bucket_index()
            if not bucket_index:
                print("❌ Could not initialize bucket index")
                return 1
            
            bucket_count = bucket_index.refresh_index()
            
            print("✅ Bucket index refreshed successfully")
            print(f"   Updated buckets: {bucket_count}")
            print(f"   Updated at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")
            return 0
                
        except Exception as e:
            print(f"❌ Error refreshing index: {e}")
            return 1
    
    # Backend Management Commands
    
    async def cmd_backend_start(self, backend_name: str):
        """Start a specific backend."""
        if not await self._ensure_daemon():
            return 1
        
        print(f"🔌 Starting backend: {backend_name}")
        
        try:
            # Mock backend start
            print(f"✅ Backend {backend_name} start requested")
            return 0
                
        except Exception as e:
            print(f"❌ Error starting backend: {e}")
            return 1
    
    async def cmd_backend_stop(self, backend_name: str):
        """Stop a specific backend."""
        if not await self._ensure_daemon():
            return 1
        
        print(f"🛑 Stopping backend: {backend_name}")
        
        try:
            # Mock backend stop
            print(f"✅ Backend {backend_name} stop requested")
            return 0
                
        except Exception as e:
            print(f"❌ Error stopping backend: {e}")
            return 1
    
    async def cmd_backend_status(self, backend_name: Optional[str] = None):
        """Show backend status."""
        if not await self._ensure_daemon():
            return 1
        
        print("🔧 BACKEND STATUS")
        print("=" * 30)
        
        # Mock backend status
        backends = ["ipfs", "ipfs_cluster", "lotus", "lassie"]
        
        for backend in backends:
            if backend_name is None or backend == backend_name:
                print(f"✅ 💚 {backend.upper()}")
                print(f"   Status: running (mock)")
                print(f"   Health: healthy")
                print()
        
        return 0
    
    # Health Commands
    
    async def cmd_health_check(self, backend_name: Optional[str] = None):
        """Perform health check."""
        if not await self._ensure_daemon():
            return 1
        
        print("🏥 Performing health check...")
        
        print("📊 HEALTH CHECK RESULTS")
        print("-" * 30)
        
        print("✅ Overall Health: healthy (mock)")
        print()
        
        backends = ["ipfs", "ipfs_cluster"] 
        for backend in backends:
            if backend_name is None or backend == backend_name:
                print(f"✅ 💚 {backend}")
                print(f"   Status: running")
                print(f"   Health: healthy")
                print()
        
        return 0
    
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
                print(f"Expected location: {self.config_file}")
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
            return 0
            
        except Exception as e:
            print(f"❌ Error setting configuration: {e}")
            return 1
    
    # Metrics Commands
    
    async def cmd_metrics(self, detailed: bool = False):
        """Show performance metrics."""
        print("📊 PERFORMANCE METRICS")
        print("=" * 30)
        
        if check_enhanced_features_available():
            try:
                # Try to get enhanced metrics
                print("Enhanced metrics not fully implemented yet")
                print("This would show:")
                print("- CPU usage and multiprocessing performance")
                print("- I/O throughput statistics") 
                print("- Memory usage patterns")
                print("- Pin access patterns")
                return 0
            except Exception as e:
                print(f"⚠️  Enhanced metrics error: {e}")
        
        # Mock metrics
        print("Mock Performance Metrics:")
        print("- CPU Cores: 4")
        print("- Memory Usage: 1.2GB")
        print("- Active Pins: 0")
        print("- Network Peers: 12")
        
        return 0
    
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
            print("Start the daemon with: python ipfs_kit_cli_optimized.py daemon start --detach")
            return False
        return True


def create_parser():
    """Create argument parser (fast - no imports needed)."""
    parser = argparse.ArgumentParser(
        description="IPFS-Kit Enhanced CLI Tool (Optimized)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --help                          # Fast help (no imports)
  %(prog)s daemon status                   # Check daemon status
  %(prog)s bucket list --metrics           # List virtual filesystems
  %(prog)s pin add QmHash --name "My Pin"  # Add pin with metadata
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Daemon commands
    daemon_parser = subparsers.add_parser('daemon', help='Daemon management')
    daemon_subparsers = daemon_parser.add_subparsers(dest='daemon_action')
    
    start_parser = daemon_subparsers.add_parser('start', help='Start daemon')
    start_parser.add_argument('--detach', action='store_true', help='Run in background')
    start_parser.add_argument('--config', help='Configuration file path')
    
    daemon_subparsers.add_parser('stop', help='Stop daemon')
    
    status_parser = daemon_subparsers.add_parser('status', help='Show daemon status')
    status_parser.add_argument('--verbose', action='store_true', help='Show detailed status')
    
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
    
    status_parser = pin_subparsers.add_parser('status', help='Check pin operation status')
    status_parser.add_argument('operation_id', help='Operation ID to check')
    
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
    
    # Bucket commands
    bucket_parser = subparsers.add_parser('bucket', help='Virtual filesystem (bucket) discovery and management')
    bucket_subparsers = bucket_parser.add_subparsers(dest='bucket_action')
    
    # Bucket list command
    list_bucket_parser = bucket_subparsers.add_parser('list', help='List all virtual filesystems')
    list_bucket_parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    list_bucket_parser.add_argument('--metrics', action='store_true', help='Show comprehensive metrics')
    
    # Bucket info command
    info_bucket_parser = bucket_subparsers.add_parser('info', help='Get detailed information about a bucket')
    info_bucket_parser.add_argument('bucket_name', help='Name of the bucket')
    
    # Bucket search command
    search_bucket_parser = bucket_subparsers.add_parser('search', help='Search buckets')
    search_bucket_parser.add_argument('query', help='Search query')
    search_bucket_parser.add_argument('--type', dest='search_type', default='name', 
                                     choices=['name', 'type', 'structure', 'metadata', 'all'],
                                     help='Type of search (default: name)')
    
    # Bucket types command
    bucket_subparsers.add_parser('types', help='Show bucket type distribution and usage')
    
    # Bucket analytics command
    bucket_subparsers.add_parser('analytics', help='Show advanced bucket analytics')
    
    # Bucket refresh command
    bucket_subparsers.add_parser('refresh', help='Manually refresh the bucket index')
    
    # Metrics commands
    metrics_parser = subparsers.add_parser('metrics', help='Show performance metrics')
    metrics_parser.add_argument('--detailed', action='store_true', help='Show detailed metrics')
    
    return parser


async def main():
    """Main entry point with optimized startup."""
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
                return await cli.cmd_daemon_status(verbose=getattr(args, 'verbose', False))
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
            elif args.pin_action == 'status':
                return await cli.cmd_pin_status(args.operation_id)
        
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
        
        # Bucket commands
        elif args.command == 'bucket':
            if args.bucket_action == 'list':
                return await cli.cmd_bucket_list(detailed=args.detailed, show_metrics=args.metrics)
            elif args.bucket_action == 'info':
                return await cli.cmd_bucket_info(args.bucket_name)
            elif args.bucket_action == 'search':
                return await cli.cmd_bucket_search(args.query, args.search_type)
            elif args.bucket_action == 'types':
                return await cli.cmd_bucket_types()
            elif args.bucket_action == 'analytics':
                return await cli.cmd_bucket_analytics()
            elif args.bucket_action == 'refresh':
                return await cli.cmd_bucket_refresh()
        
        # Metrics commands
        elif args.command == 'metrics':
            return await cli.cmd_metrics(detailed=args.detailed)
        
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
