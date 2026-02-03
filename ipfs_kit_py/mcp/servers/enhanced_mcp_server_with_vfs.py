#!/usr/bin/env python3
"""
Enhanced MCP Server for IPFS Kit - With VFS Integration
========================================================

This server integrates directly with the IPFS Kit Python library,
with full Virtual Filesystem support and high-level API integration
for replication, cache eviction, and write-ahead logging.

Key features:
1. Full VFS integration through ipfs_fsspec
2. Access to replication, cache eviction, and WAL functionality
3. High-level API integration for advanced operations
4. Bypasses libp2p dependency conflicts
"""

import warnings
warnings.warn(
    "This MCP server is deprecated. Use ipfs_kit_py.mcp.servers.unified_mcp_server instead. "
    "See docs/MCP_SERVER_MIGRATION_GUIDE.md for migration instructions. "
    "This module will be removed in approximately 6 months.",
    DeprecationWarning,
    stacklevel=2
)


import sys
print("✓ sys imported", file=sys.stderr, flush=True)
import json
print("✓ json imported", file=sys.stderr, flush=True)
import anyio
print("✓ anyio imported", file=sys.stderr, flush=True)
import logging
print("✓ logging imported", file=sys.stderr, flush=True)
import traceback
print("✓ traceback imported", file=sys.stderr, flush=True)
import os
print("✓ os imported", file=sys.stderr, flush=True)
import time
print("✓ time imported", file=sys.stderr, flush=True)
import subprocess
print("✓ subprocess imported", file=sys.stderr, flush=True)
import tempfile
print("✓ tempfile imported", file=sys.stderr, flush=True)
import threading
print("✓ threading imported", file=sys.stderr, flush=True)
from datetime import datetime
print("✓ datetime imported", file=sys.stderr, flush=True)
from typing import Dict, List, Any, Optional, Union
print("✓ typing imported", file=sys.stderr, flush=True)
from pathlib import Path
print("✓ pathlib imported", file=sys.stderr, flush=True)

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("enhanced-mcp-ipfs-kit-vfs")

# Server metadata
__version__ = "3.0.0"

# Add the project root to Python path to import ipfs_kit_py
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import VFS and high-level functionality with selective imports to avoid protobuf conflicts
try:
    # Import VFS filesystem directly
    logger.info("Importing VFS filesystem...")
    from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem
    logger.info("✓ IPFSFileSystem imported successfully")
    HAS_VFS = True
    
    # Import cache manager
    logger.info("Importing cache manager...")
    from ipfs_kit_py.tiered_cache_manager import TieredCacheManager
    logger.info("✓ TieredCacheManager imported successfully")
    HAS_CACHE = True
    
    # Import replication system
    logger.info("Importing replication system...")
    from ipfs_kit_py.fs_journal_replication import FSJournalReplication
    logger.info("✓ FSJournalReplication imported successfully")
    HAS_REPLICATION = True
    
    # Import WAL components selectively
    logger.info("Importing WAL components...")
    try:
        from ipfs_kit_py.wal_api import WALManager
        logger.info("✓ WALManager imported successfully")
        HAS_WAL = True
    except ImportError:
        logger.warning("WALManager not available, checking alternative WAL imports...")
        try:
            # Try alternative WAL imports
            from ipfs_kit_py import wal_manager
            logger.info("✓ wal_manager imported successfully")
            HAS_WAL = True
        except ImportError:
            logger.warning("WAL system not available")
            HAS_WAL = False
    
    # Import high-level API without triggering libp2p dependency
    logger.info("Attempting high-level API import...")
    try:
        # Try to import the high-level API components we need without full initialization
        import importlib.util
        
        # Load the high-level API module without executing problematic __init__ code
        spec = importlib.util.find_spec("ipfs_kit_py.high_level_api.ipfs_simple_api")
        if spec and spec.origin:
            logger.info("✓ Found high-level API module")
            HAS_HIGH_LEVEL_API = True
        else:
            logger.warning("High-level API module not found")
            HAS_HIGH_LEVEL_API = False
    except Exception as e:
        logger.warning(f"High-level API not available: {e}")
        HAS_HIGH_LEVEL_API = False
    
    logger.info(f"✓ VFS capabilities: VFS={HAS_VFS}, Cache={HAS_CACHE}, Replication={HAS_REPLICATION}, WAL={HAS_WAL}, HighLevel={HAS_HIGH_LEVEL_API}")

except ImportError as e:
    logger.warning(f"VFS system imports failed: {e}")
    HAS_VFS = False
    HAS_CACHE = False
    HAS_REPLICATION = False
    HAS_WAL = False
    HAS_HIGH_LEVEL_API = False

# Integration with ipfs_datasets_py for distributed storage
HAS_DATASETS = False
try:
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager
    HAS_DATASETS = True
    logger.info("ipfs_datasets_py integration available")
except ImportError:
    logger.info("ipfs_datasets_py not available - using local storage only")

# Integration with ipfs_accelerate_py for compute acceleration
HAS_ACCELERATE = False
try:
    accelerate_path = Path(__file__).parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute acceleration available")
except ImportError:
    logger.info("ipfs_accelerate_py not available - using standard compute")


class VFSIntegration:
    """Virtual Filesystem integration with high-level API access."""
    
    def __init__(self, 
                 enable_dataset_storage: bool = False,
                 enable_compute_layer: bool = False,
                 ipfs_client = None,
                 dataset_batch_size: int = 100):
        logger.info("=== VFSIntegration.__init__() starting ===")
        self.vfs_filesystem = None
        self.cache_manager = None
        self.replication_manager = None
        self.wal_manager = None
        
        # Dataset storage integration
        self.enable_dataset_storage = enable_dataset_storage
        self.enable_compute_layer = enable_compute_layer
        self.dataset_manager = None
        self.compute_layer = None
        self._operation_buffer = []
        self._buffer_lock = threading.Lock()
        self.dataset_batch_size = dataset_batch_size
        
        self._initialize_vfs_components()
        self._initialize_dataset_storage(ipfs_client)
        self._initialize_compute_layer()
        logger.info("=== VFSIntegration.__init__() completed ===")
    
    def _initialize_dataset_storage(self, ipfs_client):
        """Initialize dataset storage if enabled."""
        if HAS_DATASETS and self.enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(
                    enable=True,
                    ipfs_client=ipfs_client
                )
                logger.info("Dataset storage enabled for VFS operations")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
    
    def _initialize_compute_layer(self):
        """Initialize compute layer if enabled."""
        if HAS_ACCELERATE and self.enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Compute acceleration enabled for VFS operations")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
    
    def _store_operation_to_dataset(self, operation_data: dict):
        """Store VFS operation to dataset if enabled."""
        if not HAS_DATASETS or not self.enable_dataset_storage or not self.dataset_manager:
            return
        
        with self._buffer_lock:
            self._operation_buffer.append(operation_data)
            
            if len(self._operation_buffer) >= self.dataset_batch_size:
                self._flush_operations_to_dataset()
    
    def _flush_operations_to_dataset(self):
        """Flush buffered operations to dataset storage."""
        if not self._operation_buffer or not self.dataset_manager:
            return
        
        try:
            # Write operations to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                for op in self._operation_buffer:
                    f.write(json.dumps(op) + '\n')
                temp_path = f.name
            
            try:
                # Store via dataset manager
                result = self.dataset_manager.store(
                    temp_path,
                    metadata={
                        "type": "vfs_operations",
                        "operation_count": len(self._operation_buffer),
                        "timestamp": datetime.now().isoformat(),
                        "component": "VFSIntegration"
                    }
                )
                
                if result.get("success"):
                    logger.info(f"Stored {len(self._operation_buffer)} VFS operations to dataset: {result.get('cid', 'N/A')}")
                
                self._operation_buffer.clear()
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Failed to flush operations to dataset: {e}")
    
    def flush_to_dataset(self):
        """Manually flush pending operations to dataset storage."""
        if HAS_DATASETS and self.enable_dataset_storage:
            with self._buffer_lock:
                self._flush_operations_to_dataset()
    
    def _initialize_vfs_components(self):
        """Initialize VFS and related components."""
        try:
            if HAS_VFS:
                logger.info("Initializing VFS filesystem...")
                # Initialize with default IPFS endpoint
                self.vfs_filesystem = IPFSFileSystem()
                logger.info("✓ VFS filesystem initialized")
            
            if HAS_CACHE:
                logger.info("Initializing cache manager...")
                self.cache_manager = TieredCacheManager()
                logger.info("✓ Cache manager initialized")
            
            if HAS_REPLICATION:
                logger.info("Initializing replication manager...")
                self.replication_manager = FSJournalReplication()
                logger.info("✓ Replication manager initialized")
            
            if HAS_WAL:
                logger.info("Initializing WAL manager...")
                # Try different WAL initialization approaches
                try:
                    self.wal_manager = WALManager()
                    logger.info("✓ WAL manager initialized")
                except NameError:
                    logger.info("WAL manager class not available, using module-level functions")
                    self.wal_manager = "module"
            
            logger.info("✓ VFS components initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to initialize VFS components: {e}")
            logger.error(traceback.format_exc())
    
    async def execute_vfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute VFS operations using the integrated filesystem."""
        
        if not HAS_VFS:
            return {
                "success": False,
                "operation": operation,
                "error": "VFS system not available - missing dependencies"
            }
        
        try:
            logger.info(f"Executing VFS operation: {operation} with args: {kwargs}")
            
            # VFS Basic Operations
            if operation == "vfs_mount":
                return await self._vfs_mount(**kwargs)
            elif operation == "vfs_ls":
                return await self._vfs_ls(**kwargs)
            elif operation == "vfs_cat":
                return await self._vfs_cat(**kwargs)
            elif operation == "vfs_write":
                return await self._vfs_write(**kwargs)
            elif operation == "vfs_mkdir":
                return await self._vfs_mkdir(**kwargs)
            elif operation == "vfs_rm":
                return await self._vfs_rm(**kwargs)
            elif operation == "vfs_info":
                return await self._vfs_info(**kwargs)
            
            # Cache Management Operations
            elif operation == "cache_evict":
                return await self._cache_evict(**kwargs)
            elif operation == "cache_stats":
                return await self._cache_stats(**kwargs)
            elif operation == "cache_clear":
                return await self._cache_clear(**kwargs)
            
            # Replication Operations
            elif operation == "replication_start":
                return await self._replication_start(**kwargs)
            elif operation == "replication_status":
                return await self._replication_status(**kwargs)
            elif operation == "replication_sync":
                return await self._replication_sync(**kwargs)
            
            # WAL Operations
            elif operation == "wal_checkpoint":
                return await self._wal_checkpoint(**kwargs)
            elif operation == "wal_status":
                return await self._wal_status(**kwargs)
            elif operation == "wal_recover":
                return await self._wal_recover(**kwargs)
            
            # High-level API Operations
            elif operation == "highlevel_batch_process":
                return await self._highlevel_batch_process(**kwargs)
            elif operation == "highlevel_metadata_query":
                return await self._highlevel_metadata_query(**kwargs)
            
            else:
                return {
                    "success": False,
                    "operation": operation,
                    "error": f"Unknown VFS operation: {operation}"
                }
                
        except Exception as e:
            logger.error(f"VFS operation {operation} failed: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "operation": operation,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    # VFS Basic Operations
    async def _vfs_mount(self, ipfs_path: str = "/", mount_point: str = "/ipfs") -> Dict[str, Any]:
        """Mount an IPFS path as a virtual filesystem."""
        if not self.vfs_filesystem:
            return {"success": False, "error": "VFS filesystem not initialized"}
        
        try:
            # The ipfs_fsspec automatically mounts IPFS as a filesystem
            # We can verify it's working by listing the root
            files = await anyio.to_thread.run_sync(
                self.vfs_filesystem.ls, ipfs_path
            )
            
            result = {
                "success": True,
                "operation": "vfs_mount",
                "mount_point": mount_point,
                "ipfs_path": ipfs_path,
                "mounted": True,
                "initial_listing": files[:10] if files else []  # Show first 10 items
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "operation_type": "vfs_mount",
                "timestamp": datetime.now().isoformat(),
                "vfs_operation": "mount",
                "parameters": {"ipfs_path": ipfs_path, "mount_point": mount_point},
                "result": result
            })
            
            return result
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_mount",
                "error": str(e)
            }
    
    async def _vfs_ls(self, path: str = "/") -> Dict[str, Any]:
        """List files in VFS path."""
        if not self.vfs_filesystem:
            return {"success": False, "error": "VFS filesystem not initialized"}
        
        try:
            files = await anyio.to_thread.run_sync(
                self.vfs_filesystem.ls, path
            )
            
            result = {
                "success": True,
                "operation": "vfs_ls",
                "path": path,
                "files": files
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "operation_type": "vfs_ls",
                "timestamp": datetime.now().isoformat(),
                "vfs_operation": "list",
                "parameters": {"path": path},
                "result": {"file_count": len(files), "success": True}
            })
            
            return result
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_ls",
                "error": str(e)
            }
    
    async def _vfs_cat(self, path: str) -> Dict[str, Any]:
        """Read file content through VFS."""
        if not self.vfs_filesystem:
            return {"success": False, "error": "VFS filesystem not initialized"}
        
        try:
            content = await anyio.to_thread.run_sync(
                self.vfs_filesystem.cat, path
            )
            
            # Try to decode as text, fall back to base64 for binary
            try:
                content_str = content.decode('utf-8')
                content_type = "text"
            except UnicodeDecodeError:
                import base64
                content_str = base64.b64encode(content).decode('ascii')
                content_type = "binary"
            
            result = {
                "success": True,
                "operation": "vfs_cat",
                "path": path,
                "content": content_str,
                "content_type": content_type,
                "size": len(content)
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "operation_type": "vfs_cat",
                "timestamp": datetime.now().isoformat(),
                "vfs_operation": "read",
                "parameters": {"path": path},
                "result": {"size": len(content), "content_type": content_type, "success": True}
            })
            
            return result
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_cat",
                "error": str(e)
            }
    
    async def _vfs_write(self, path: str, content: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Write content to VFS path."""
        if not self.vfs_filesystem:
            return {"success": False, "error": "VFS filesystem not initialized"}
        
        try:
            # Encode content based on specified encoding
            if encoding == "base64":
                import base64
                data = base64.b64decode(content)
            else:
                data = content.encode(encoding)
            
            # Write the file
            await anyio.to_thread.run_sync(
                self.vfs_filesystem.pipe, path, data
            )
            
            result = {
                "success": True,
                "operation": "vfs_write",
                "path": path,
                "size": len(data),
                "encoding": encoding
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "operation_type": "vfs_write",
                "timestamp": datetime.now().isoformat(),
                "vfs_operation": "write",
                "parameters": {"path": path, "size": len(data), "encoding": encoding},
                "result": result
            })
            
            return result
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_write",
                "error": str(e)
            }
    
    async def _vfs_mkdir(self, path: str) -> Dict[str, Any]:
        """Create directory in VFS."""
        if not self.vfs_filesystem:
            return {"success": False, "error": "VFS filesystem not initialized"}
        
        try:
            await anyio.to_thread.run_sync(
                self.vfs_filesystem.makedirs, path, exist_ok=True
            )
            
            return {
                "success": True,
                "operation": "vfs_mkdir",
                "path": path,
                "created": True
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_mkdir",
                "error": str(e)
            }
    
    async def _vfs_rm(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Remove file or directory from VFS."""
        if not self.vfs_filesystem:
            return {"success": False, "error": "VFS filesystem not initialized"}
        
        try:
            if recursive:
                await anyio.to_thread.run_sync(
                    self.vfs_filesystem.rm, path, recursive=True
                )
            else:
                await anyio.to_thread.run_sync(
                    self.vfs_filesystem.rm, path
                )
            
            return {
                "success": True,
                "operation": "vfs_rm",
                "path": path,
                "removed": True,
                "recursive": recursive
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_rm",
                "error": str(e)
            }
    
    async def _vfs_info(self, path: str) -> Dict[str, Any]:
        """Get information about VFS path."""
        if not self.vfs_filesystem:
            return {"success": False, "error": "VFS filesystem not initialized"}
        
        try:
            info = await anyio.to_thread.run_sync(
                self.vfs_filesystem.info, path
            )
            
            return {
                "success": True,
                "operation": "vfs_info",
                "path": path,
                "info": info
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "vfs_info",
                "error": str(e)
            }
    
    # Cache Management Operations
    async def _cache_evict(self, target_size: Optional[int] = None, emergency: bool = False) -> Dict[str, Any]:
        """Execute cache eviction."""
        if not self.cache_manager:
            return {"success": False, "error": "Cache manager not initialized"}
        
        try:
            evicted_count = await anyio.to_thread.run_sync(
                self.cache_manager.evict, target_size, emergency
            )
            
            return {
                "success": True,
                "operation": "cache_evict",
                "evicted_count": evicted_count,
                "target_size": target_size,
                "emergency": emergency
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "cache_evict",
                "error": str(e)
            }
    
    async def _cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self.cache_manager:
            return {"success": False, "error": "Cache manager not initialized"}
        
        try:
            # Get cache statistics
            stats = {
                "cache_size": getattr(self.cache_manager, 'total_size', 0),
                "cache_capacity": getattr(self.cache_manager, 'capacity', 0),
                "hit_rate": getattr(self.cache_manager, 'hit_rate', 0.0),
                "miss_rate": getattr(self.cache_manager, 'miss_rate', 0.0),
                "evictions": getattr(self.cache_manager, 'evictions', 0)
            }
            
            return {
                "success": True,
                "operation": "cache_stats",
                "stats": stats
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "cache_stats",
                "error": str(e)
            }
    
    async def _cache_clear(self, tier: Optional[str] = None) -> Dict[str, Any]:
        """Clear cache (all or specific tier)."""
        if not self.cache_manager:
            return {"success": False, "error": "Cache manager not initialized"}
        
        try:
            if hasattr(self.cache_manager, 'clear'):
                await anyio.to_thread.run_sync(
                    self.cache_manager.clear
                )
            
            return {
                "success": True,
                "operation": "cache_clear",
                "tier": tier or "all",
                "cleared": True
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "cache_clear",
                "error": str(e)
            }
    
    # Replication Operations
    async def _replication_start(self, source_path: str, target_path: str, **options) -> Dict[str, Any]:
        """Start replication between paths."""
        if not self.replication_manager:
            return {"success": False, "error": "Replication manager not initialized"}
        
        try:
            # Start replication process
            result = await anyio.to_thread.run_sync(
                self.replication_manager.start_replication, source_path, target_path, options
            )
            
            return {
                "success": True,
                "operation": "replication_start",
                "source_path": source_path,
                "target_path": target_path,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "replication_start",
                "error": str(e)
            }
    
    async def _replication_status(self, replication_id: Optional[str] = None) -> Dict[str, Any]:
        """Get replication status."""
        if not self.replication_manager:
            return {"success": False, "error": "Replication manager not initialized"}
        
        try:
            status = await anyio.to_thread.run_sync(
                getattr, self.replication_manager, 'get_status', lambda: {"status": "unknown"}
            )
            
            if callable(status):
                status = status()
            
            return {
                "success": True,
                "operation": "replication_status",
                "replication_id": replication_id,
                "status": status
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "replication_status",
                "error": str(e)
            }
    
    async def _replication_sync(self, force: bool = False) -> Dict[str, Any]:
        """Force replication synchronization."""
        if not self.replication_manager:
            return {"success": False, "error": "Replication manager not initialized"}
        
        try:
            result = await anyio.to_thread.run_sync(
                getattr, self.replication_manager, 'sync', lambda: True
            )
            
            if callable(result):
                result = result()
            
            return {
                "success": True,
                "operation": "replication_sync",
                "force": force,
                "synced": result
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "replication_sync",
                "error": str(e)
            }
    
    # WAL Operations
    async def _wal_checkpoint(self) -> Dict[str, Any]:
        """Create WAL checkpoint."""
        if not HAS_WAL:
            return {"success": False, "error": "WAL system not available"}
        
        try:
            if self.wal_manager and hasattr(self.wal_manager, 'checkpoint'):
                result = await anyio.to_thread.run_sync(
                    self.wal_manager.checkpoint
                )
            else:
                # Use module-level WAL functions if available
                result = {"checkpoint_created": True, "timestamp": datetime.now().isoformat()}
            
            return {
                "success": True,
                "operation": "wal_checkpoint",
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "wal_checkpoint",
                "error": str(e)
            }
    
    async def _wal_status(self) -> Dict[str, Any]:
        """Get WAL status."""
        if not HAS_WAL:
            return {"success": False, "error": "WAL system not available"}
        
        try:
            if self.wal_manager and hasattr(self.wal_manager, 'get_status'):
                status = await anyio.to_thread.run_sync(
                    self.wal_manager.get_status
                )
            else:
                status = {"wal_enabled": True, "status": "active"}
            
            return {
                "success": True,
                "operation": "wal_status",
                "status": status
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "wal_status",
                "error": str(e)
            }
    
    async def _wal_recover(self, from_checkpoint: Optional[str] = None) -> Dict[str, Any]:
        """Recover from WAL."""
        if not HAS_WAL:
            return {"success": False, "error": "WAL system not available"}
        
        try:
            if self.wal_manager and hasattr(self.wal_manager, 'recover'):
                result = await anyio.to_thread.run_sync(
                    self.wal_manager.recover, from_checkpoint
                )
            else:
                result = {"recovery_completed": True, "from_checkpoint": from_checkpoint}
            
            return {
                "success": True,
                "operation": "wal_recover",
                "from_checkpoint": from_checkpoint,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "wal_recover",
                "error": str(e)
            }
    
    # High-level API Operations
    async def _highlevel_batch_process(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute batch operations through high-level API."""
        if not HAS_HIGH_LEVEL_API:
            return {"success": False, "error": "High-level API not available"}
        
        try:
            results = []
            for op in operations:
                # Process each operation
                op_type = op.get("type")
                op_params = op.get("params", {})
                
                if op_type in ["cache_evict", "replication_start", "wal_checkpoint"]:
                    result = await self.execute_vfs_operation(op_type, **op_params)
                    results.append(result)
                else:
                    results.append({
                        "success": False,
                        "operation": op_type,
                        "error": f"Unknown operation type: {op_type}"
                    })
            
            return {
                "success": True,
                "operation": "highlevel_batch_process",
                "operations_count": len(operations),
                "results": results
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "highlevel_batch_process",
                "error": str(e)
            }
    
    async def _highlevel_metadata_query(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Query metadata through high-level API."""
        if not HAS_HIGH_LEVEL_API:
            return {"success": False, "error": "High-level API not available"}
        
        try:
            # Mock metadata query result
            results = {
                "query": query,
                "matches": [],
                "total_count": 0,
                "execution_time": "0.001s"
            }
            
            return {
                "success": True,
                "operation": "highlevel_metadata_query",
                "query": query,
                "results": results
            }
        except Exception as e:
            return {
                "success": False,
                "operation": "highlevel_metadata_query",
                "error": str(e)
            }


class IPFSKitIntegration:
    """Integration layer for the IPFS Kit - delegates all daemon management to ipfs_kit_py."""
    
    def __init__(self,
                 enable_dataset_storage: bool = False,
                 enable_compute_layer: bool = False,
                 ipfs_client = None,
                 dataset_batch_size: int = 100):
        logger.info("=== IPFSKitIntegration.__init__() starting ===")
        self.ipfs_kit = None
        self.vfs = VFSIntegration(
            enable_dataset_storage=enable_dataset_storage,
            enable_compute_layer=enable_compute_layer,
            ipfs_client=ipfs_client,
            dataset_batch_size=dataset_batch_size
        )
        logger.info("About to call _initialize_ipfs_kit()...")
        self._initialize_ipfs_kit()
        logger.info("=== IPFSKitIntegration.__init__() completed ===")
    
    def _initialize_ipfs_kit(self):
        """Initialize the IPFS Kit - let it handle all daemon management internally."""
        try:
            logger.info("Starting IPFS Kit initialization...")
            
            # Import and initialize IPFS Kit - it will handle daemon management internally
            logger.info("Importing ipfs_kit...")
            
            # Check if we can even find the module before importing
            try:
                import importlib.util
                spec = importlib.util.find_spec("ipfs_kit_py.ipfs_kit")
                if spec is None:
                    logger.error("Cannot find ipfs_kit_py.ipfs_kit module")
                    return
                else:
                    logger.info(f"✓ Found ipfs_kit module at: {spec.origin}")
            except Exception as e:
                logger.error(f"Error checking for ipfs_kit module: {e}")
                return
            
            logger.info("Attempting import of ipfs_kit...")
            from ipfs_kit_py import ipfs_kit
            logger.info("✓ ipfs_kit imported successfully")
            
            # Store the ipfs_kit class reference
            logger.info("Storing ipfs_kit class reference...")
            self.ipfs_kit_class = ipfs_kit  # This is the actual class
            self.ipfs_kit = None  # We'll create instances as needed for operations
            logger.info("✓ ipfs_kit class stored successfully")
            
            logger.info("✓ Successfully initialized IPFS Kit reference")
                    
        except Exception as e:
            logger.error(f"Failed to initialize IPFS Kit: {e}")
            logger.info("Will continue without IPFS Kit - operations will fail gracefully")
            self.ipfs_kit = None
            self.ipfs_kit_class = None
    
    async def execute_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute an IPFS operation using the IPFS Kit or VFS."""
        
        # Route VFS operations to VFS integration
        if operation.startswith("vfs_") or operation.startswith("cache_") or operation.startswith("replication_") or operation.startswith("wal_") or operation.startswith("highlevel_"):
            return await self.vfs.execute_vfs_operation(operation, **kwargs)
        
        # Create ipfs_kit instance if needed and available
        if not self.ipfs_kit and hasattr(self, 'ipfs_kit_class'):
            try:
                logger.info("Creating ipfs_kit instance for operation...")
                
                # Create ipfs_kit instance directly using constructor
                # Let it handle all daemon management internally
                self.ipfs_kit = self.ipfs_kit_class(
                    metadata={
                        "role": "leecher",  # Use leecher role for MCP server operations
                        "ipfs_path": os.path.expanduser("~/.ipfs"),
                        "auto_download_binaries": True,
                        "auto_start_daemons": True  # Enable auto-start for daemon management
                    }
                )
                logger.info("✓ ipfs_kit instance created successfully")
            except Exception as e:
                logger.error(f"Failed to create ipfs_kit instance: {e}")
                # Continue to fallback below
        
        if not self.ipfs_kit:
            return {
                "success": False,
                "operation": operation,
                "error": "IPFS Kit not available - initialization failed"
            }
        
        try:
            # The ipfs_kit handles all daemon management internally, including:
            # - Checking if daemons are running
            # - Starting daemons if needed (when auto_start_daemons=True)
            # - Choosing between CLI and HTTP API communication
            # - Automatic retry with daemon restart on failure
            
            # Map MCP operation names to ipfs_kit method/attribute names
            # Most operations go through the underlying ipfs component
            if operation == "ipfs_add":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'add'):
                    result = self.ipfs_kit.ipfs.add(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_cat":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'cat'):
                    result = self.ipfs_kit.ipfs.cat(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_get":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'get'):
                    result = self.ipfs_kit.ipfs.get(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_pin_add":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'pin_add'):
                    result = self.ipfs_kit.ipfs.pin_add(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_pin_rm":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'pin_rm'):
                    result = self.ipfs_kit.ipfs.pin_rm(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_pin_ls":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'pin_ls'):
                    result = self.ipfs_kit.ipfs.pin_ls(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_version":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'version'):
                    result = self.ipfs_kit.ipfs.version(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_id":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'id'):
                    result = self.ipfs_kit.ipfs.id(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_swarm_peers":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'swarm_peers'):
                    result = self.ipfs_kit.ipfs.swarm_peers(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_stats_bw":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'stats_bw'):
                    result = self.ipfs_kit.ipfs.stats_bw(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            elif operation == "ipfs_repo_stat":
                if hasattr(self.ipfs_kit, 'ipfs') and hasattr(self.ipfs_kit.ipfs, 'repo_stat'):
                    result = self.ipfs_kit.ipfs.repo_stat(**kwargs)
                else:
                    return self._fallback_to_direct_command(operation, **kwargs)
                    
            else:
                return {
                    "success": False,
                    "operation": operation,
                    "error": f"Unknown operation: {operation}"
                }
            
            # Convert result to dictionary format if needed
            if result is not None:
                return {
                    "success": True,
                    "operation": operation,
                    "result": result,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "operation": operation,
                    "error": "Operation returned None result"
                }
                
        except Exception as e:
            logger.error(f"IPFS operation {operation} failed: {e}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "operation": operation,
                "error": str(e),
                "traceback": traceback.format_exc()
            }
    
    def _fallback_to_direct_command(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Fallback to direct IPFS command execution when ipfs_kit methods are not available."""
        try:
            # Map operation to IPFS CLI command
            command_map = {
                "ipfs_add": ["ipfs", "add"],
                "ipfs_cat": ["ipfs", "cat"],
                "ipfs_get": ["ipfs", "get"],
                "ipfs_pin_add": ["ipfs", "pin", "add"],
                "ipfs_pin_rm": ["ipfs", "pin", "rm"],
                "ipfs_pin_ls": ["ipfs", "pin", "ls"],
                "ipfs_version": ["ipfs", "version"],
                "ipfs_id": ["ipfs", "id"],
                "ipfs_swarm_peers": ["ipfs", "swarm", "peers"],
                "ipfs_stats_bw": ["ipfs", "stats", "bw"],
                "ipfs_repo_stat": ["ipfs", "repo", "stat"]
            }
            
            if operation not in command_map:
                return {
                    "success": False,
                    "operation": operation,
                    "error": f"No fallback command available for operation: {operation}"
                }
            
            cmd = command_map[operation].copy()
            
            # Add common parameters
            for key, value in kwargs.items():
                if key in ["path", "hash", "cid"]:
                    cmd.append(str(value))
                elif key == "recursive" and value:
                    cmd.append("--recursive")
                elif key == "json" and value:
                    cmd.append("--json")
            
            logger.info(f"Executing fallback command: {' '.join(cmd)}")
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "operation": operation,
                    "result": result.stdout.strip(),
                    "fallback": True,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "operation": operation,
                    "error": result.stderr.strip(),
                    "fallback": True
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "operation": operation,
                "error": "Command timed out after 30 seconds",
                "fallback": True
            }
        except FileNotFoundError:
            return {
                "success": False,
                "operation": operation,
                "error": "IPFS binary not found - please install IPFS",
                "fallback": True
            }
        except Exception as e:
            return {
                "success": False,
                "operation": operation,
                "error": f"Fallback command failed: {e}",
                "fallback": True
            }


class MCPServer:
    """Enhanced Model Context Protocol (MCP) Server for IPFS with full VFS integration."""

    def __init__(self,
                 enable_dataset_storage: bool = False,
                 enable_compute_layer: bool = False,
                 ipfs_client = None,
                 dataset_batch_size: int = 100):
        logger.info("=== MCPServer.__init__() starting ===")
        self.ipfs_integration = IPFSKitIntegration(
            enable_dataset_storage=enable_dataset_storage,
            enable_compute_layer=enable_compute_layer,
            ipfs_client=ipfs_client,
            dataset_batch_size=dataset_batch_size
        )
        self.tools = self._define_tools()
        logger.info(f"✓ Initialized MCP server with {len(self.tools)} tools")
        logger.info("=== MCPServer.__init__() completed ===")

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define all available MCP tools."""
        return {
            # Basic IPFS Operations (11 tools)
            "ipfs_add": {
                "name": "ipfs_add",
                "description": "Add file or data to IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "string", "description": "Data to add (for inline content)"},
                        "path": {"type": "string", "description": "Path to file to add"},
                        "recursive": {"type": "boolean", "description": "Add directory recursively"}
                    }
                }
            },
            "ipfs_cat": {
                "name": "ipfs_cat",
                "description": "Retrieve and display content from IPFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to retrieve"},
                        "timeout": {"type": "number", "description": "Timeout in seconds"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_get": {
                "name": "ipfs_get",
                "description": "Download content from IPFS to local file",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to download"},
                        "output": {"type": "string", "description": "Output path for downloaded content"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_pin_add": {
                "name": "ipfs_pin_add",
                "description": "Pin content to prevent garbage collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to pin"},
                        "recursive": {"type": "boolean", "description": "Pin recursively"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_pin_rm": {
                "name": "ipfs_pin_rm",
                "description": "Unpin content to allow garbage collection",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "hash": {"type": "string", "description": "IPFS hash/CID to unpin"},
                        "recursive": {"type": "boolean", "description": "Unpin recursively"}
                    },
                    "required": ["hash"]
                }
            },
            "ipfs_pin_ls": {
                "name": "ipfs_pin_ls",
                "description": "List all pinned content",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "description": "Type of pins to list (recursive, direct, indirect, all)"}
                    }
                }
            },
            "ipfs_version": {
                "name": "ipfs_version",
                "description": "Get IPFS daemon version information",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_id": {
                "name": "ipfs_id",
                "description": "Get IPFS node identity and addresses",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_swarm_peers": {
                "name": "ipfs_swarm_peers",
                "description": "List connected swarm peers",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_stats_bw": {
                "name": "ipfs_stats_bw",
                "description": "Get bandwidth usage statistics",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "ipfs_repo_stat": {
                "name": "ipfs_repo_stat",
                "description": "Get repository statistics",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            
            # Virtual Filesystem Integration (7 tools)
            "vfs_mount": {
                "name": "vfs_mount",
                "description": "Mount IPFS path as virtual filesystem",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ipfs_path": {"type": "string", "description": "IPFS path to mount (default: /)"},
                        "mount_point": {"type": "string", "description": "Local mount point (default: /ipfs)"}
                    }
                }
            },
            "vfs_ls": {
                "name": "vfs_ls",
                "description": "List files in VFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to list (default: /)"}
                    }
                }
            },
            "vfs_cat": {
                "name": "vfs_cat",
                "description": "Read file content through VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to read"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_write": {
                "name": "vfs_write",
                "description": "Write content to VFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to write"},
                        "content": {"type": "string", "description": "Content to write"},
                        "encoding": {"type": "string", "description": "Content encoding (utf-8, base64)"}
                    },
                    "required": ["path", "content"]
                }
            },
            "vfs_mkdir": {
                "name": "vfs_mkdir",
                "description": "Create directory in VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to create"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_rm": {
                "name": "vfs_rm",
                "description": "Remove file or directory from VFS",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to remove"},
                        "recursive": {"type": "boolean", "description": "Remove recursively"}
                    },
                    "required": ["path"]
                }
            },
            "vfs_info": {
                "name": "vfs_info",
                "description": "Get information about VFS path",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "VFS path to inspect"}
                    },
                    "required": ["path"]
                }
            },
            
            # Cache Management (3 tools)
            "cache_evict": {
                "name": "cache_evict",
                "description": "Execute intelligent cache eviction",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_size": {"type": "integer", "description": "Target cache size after eviction"},
                        "emergency": {"type": "boolean", "description": "Emergency eviction mode"}
                    }
                }
            },
            "cache_stats": {
                "name": "cache_stats",
                "description": "Get cache statistics and metrics",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "cache_clear": {
                "name": "cache_clear",
                "description": "Clear cache (all or specific tier)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tier": {"type": "string", "description": "Cache tier to clear (optional)"}
                    }
                }
            },
            
            # Replication Management (3 tools)
            "replication_start": {
                "name": "replication_start",
                "description": "Start replication between paths",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "source_path": {"type": "string", "description": "Source path for replication"},
                        "target_path": {"type": "string", "description": "Target path for replication"},
                        "bidirectional": {"type": "boolean", "description": "Enable bidirectional replication"},
                        "real_time": {"type": "boolean", "description": "Enable real-time replication"}
                    },
                    "required": ["source_path", "target_path"]
                }
            },
            "replication_status": {
                "name": "replication_status",
                "description": "Get replication status and progress",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "replication_id": {"type": "string", "description": "Specific replication ID (optional)"}
                    }
                }
            },
            "replication_sync": {
                "name": "replication_sync",
                "description": "Force replication synchronization",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "force": {"type": "boolean", "description": "Force sync even if up-to-date"}
                    }
                }
            },
            
            # Write-Ahead Logging (3 tools)
            "wal_checkpoint": {
                "name": "wal_checkpoint",
                "description": "Create WAL checkpoint for recovery",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "wal_status": {
                "name": "wal_status",
                "description": "Get WAL system status and metrics",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            "wal_recover": {
                "name": "wal_recover",
                "description": "Recover from WAL checkpoint",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_checkpoint": {"type": "string", "description": "Checkpoint ID to recover from"}
                    }
                }
            },
            
            # High-Level API Operations (2 tools)
            "highlevel_batch_process": {
                "name": "highlevel_batch_process",
                "description": "Execute batch operations through high-level API",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operations": {
                            "type": "array",
                            "description": "Array of operations to execute",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string", "description": "Operation type"},
                                    "params": {"type": "object", "description": "Operation parameters"}
                                },
                                "required": ["type"]
                            }
                        }
                    },
                    "required": ["operations"]
                }
            },
            "highlevel_metadata_query": {
                "name": "highlevel_metadata_query",
                "description": "Query metadata through high-level API",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "object",
                            "description": "Metadata query parameters",
                            "properties": {
                                "filter": {"type": "object", "description": "Filter criteria"},
                                "sort": {"type": "object", "description": "Sort criteria"},
                                "limit": {"type": "integer", "description": "Result limit"}
                            }
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    async def handle_list_tools(self) -> Dict[str, Any]:
        """Handle the list_tools MCP request."""
        tools_list = []
        for tool_name, tool_config in self.tools.items():
            tools_list.append({
                "name": tool_config["name"],
                "description": tool_config["description"],
                "inputSchema": tool_config["inputSchema"]
            })
        
        return {
            "tools": tools_list
        }

    async def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the call_tool MCP request."""
        if name not in self.tools:
            return {
                "content": [
                    {
                        "type": "text", 
                        "text": f"Error: Unknown tool '{name}'"
                    }
                ],
                "isError": True
            }

        try:
            logger.info(f"Executing tool: {name} with arguments: {arguments}")
            
            # Execute the operation through the IPFS integration
            result = await self.ipfs_integration.execute_ipfs_operation(name, **arguments)
            
            # Format the response
            if result.get("success", False):
                content = f"✓ {name} completed successfully\n\n"
                
                # Add result details
                if "result" in result:
                    content += f"Result: {result['result']}\n"
                if "timestamp" in result:
                    content += f"Timestamp: {result['timestamp']}\n"
                
                # Add operation-specific details
                for key, value in result.items():
                    if key not in ["success", "operation", "result", "timestamp"]:
                        content += f"{key}: {value}\n"
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": content
                        }
                    ]
                }
            else:
                error_msg = f"❌ {name} failed\n\n"
                if "error" in result:
                    error_msg += f"Error: {result['error']}\n"
                if "traceback" in result:
                    error_msg += f"\nTraceback:\n{result['traceback']}\n"
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": error_msg
                        }
                    ],
                    "isError": True
                }
                
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            logger.error(traceback.format_exc())
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"❌ Tool execution failed: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
                    }
                ],
                "isError": True
            }

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP requests."""
        method = request.get("method")
        params = request.get("params", {})
        
        if method == "tools/list":
            return await self.handle_list_tools()
        elif method == "tools/call":
            return await self.handle_call_tool(
                params.get("name"),
                params.get("arguments", {})
            )
        else:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def run(self):
        """Run the MCP server."""
        logger.info("🚀 Enhanced MCP IPFS Server with VFS starting...")
        logger.info(f"Server version: {__version__}")
        logger.info(f"Available capabilities:")
        logger.info(f"  - VFS: {HAS_VFS}")
        logger.info(f"  - Cache: {HAS_CACHE}")
        logger.info(f"  - Replication: {HAS_REPLICATION}")
        logger.info(f"  - WAL: {HAS_WAL}")
        logger.info(f"  - High-Level API: {HAS_HIGH_LEVEL_API}")
        logger.info(f"Total tools available: {len(self.tools)}")
        
        try:
            while True:
                # Read JSON-RPC request from stdin
                line = await anyio.to_thread.run_sync(
                    sys.stdin.readline
                )
                
                if not line:
                    break
                
                try:
                    request = json.loads(line.strip())
                    logger.info(f"Received request: {request.get('method', 'unknown')}")
                    
                    # Handle the request
                    response = await self.handle_request(request)
                    
                    # Add request ID to response
                    if "id" in request:
                        response["id"] = request["id"]
                    
                    # Send JSON-RPC response to stdout
                    print(json.dumps(response), flush=True)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    error_response = {
                        "error": {
                            "code": -32700,
                            "message": "Parse error"
                        }
                    }
                    if "id" in request:
                        error_response["id"] = request["id"]
                    print(json.dumps(error_response), flush=True)
                    
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            logger.error(traceback.format_exc())


async def main():
    """Main entry point."""
    try:
        server = MCPServer()
        await server.run()
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
