"""
VFS (Virtual File System) Manager for IPFS Kit

This module provides comprehensive VFS management functionality that is shared
between the CLI, MCP server, and other components. It consolidates all VFS
operations, index management, analytics, and filesystem operations.

Key Features:
- Unified VFS operations for all IPFS-Kit components
- Index management and synchronization
- Performance monitoring and analytics
- Filesystem change tracking and journaling
- Cache management and optimization
"""

import anyio
import sniffio
import logging
import time
import shutil
import os
import stat
import json
import threading
import inspect
import mimetypes
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING
from pathlib import Path

logger = logging.getLogger(__name__)


def _run_async_from_sync(async_fn, *args, **kwargs):
    """Run an async callable from sync code.

    - If called from an AnyIO worker thread, uses `anyio.from_thread.run`.
    - If called from plain sync code, uses `anyio.run`.
    - If called while an async library is running in this thread, runs the
      call in a dedicated helper thread.
    """
    async def _invoke():
        return await async_fn(*args, **kwargs)

    try:
        return anyio.from_thread.run(_invoke)
    except RuntimeError:
        pass

    try:
        sniffio.current_async_library()
    except sniffio.AsyncLibraryNotFoundError:
        return anyio.run(_invoke)

    result: List[Any] = []
    error: List[BaseException] = []

    def _thread_main() -> None:
        try:
            result.append(anyio.run(_invoke))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    t = threading.Thread(target=_thread_main, daemon=True)
    t.start()
    t.join()
    if error:
        raise error[0]
    return result[0] if result else None

if TYPE_CHECKING:
    from .high_level_api import IPFSSimpleAPI  # noqa: F401

ARROW_IPC_AVAILABLE = False
get_global_pin_metadata_index = None
get_cli_pin_metrics = None
FilesystemJournal = None
ArrowIPCDaemonInterface = None
get_global_arrow_ipc_interface = None
get_pin_index_zero_copy = None
get_metrics_zero_copy = None

_CORE_IMPORTS_READY = False


def _ensure_core_imports() -> bool:
    """Lazily import core IPFS Kit components to avoid circular imports."""
    global ARROW_IPC_AVAILABLE
    global get_global_pin_metadata_index, get_cli_pin_metrics
    global FilesystemJournal
    global ArrowIPCDaemonInterface, get_global_arrow_ipc_interface
    global get_pin_index_zero_copy, get_metrics_zero_copy
    global _CORE_IMPORTS_READY

    if _CORE_IMPORTS_READY:
        return True

    try:
        from .pin_metadata_index import get_global_pin_metadata_index as _get_global_pin_metadata_index
        from .filesystem_journal import FilesystemJournal as _FilesystemJournal
        from .pin_metadata_index import get_cli_pin_metrics as _get_cli_pin_metrics
        from .arrow_ipc_daemon_interface import (
            ArrowIPCDaemonInterface as _ArrowIPCDaemonInterface,
            get_global_arrow_ipc_interface as _get_global_arrow_ipc_interface,
            get_pin_index_zero_copy as _get_pin_index_zero_copy,
            get_metrics_zero_copy as _get_metrics_zero_copy,
        )
        get_global_pin_metadata_index = _get_global_pin_metadata_index
        FilesystemJournal = _FilesystemJournal
        get_cli_pin_metrics = _get_cli_pin_metrics
        ArrowIPCDaemonInterface = _ArrowIPCDaemonInterface
        get_global_arrow_ipc_interface = _get_global_arrow_ipc_interface
        get_pin_index_zero_copy = _get_pin_index_zero_copy
        get_metrics_zero_copy = _get_metrics_zero_copy
        ARROW_IPC_AVAILABLE = True
        _CORE_IMPORTS_READY = True
        return True
    except ImportError as e:
        logger.error(f"Failed to import core IPFS Kit components: {e}")
        ARROW_IPC_AVAILABLE = False
        return False

# Optional imports for advanced features
try:
    from .arrow_metadata_index import ArrowMetadataIndex
    from .metadata_sync_handler import MetadataSyncHandler
    ARROW_METADATA_AVAILABLE = True
except ImportError:
    ARROW_METADATA_AVAILABLE = False
    logger.warning("Arrow metadata index not available")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available for resource monitoring")

# Import ipfs_datasets_py integration with fallback
try:
    from .ipfs_datasets_integration import get_ipfs_datasets_manager
    HAS_DATASETS = True
except ImportError:
    HAS_DATASETS = False
    get_ipfs_datasets_manager = None
    logger.info("ipfs_datasets_py not available - dataset storage disabled")

# Import ipfs_accelerate_py for compute acceleration
try:
    import sys
    from pathlib import Path as PathlibPath
    accelerate_path = PathlibPath(__file__).parent.parent / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute layer available")
except ImportError:
    HAS_ACCELERATE = False
    AccelerateCompute = None
    logger.info("ipfs_accelerate_py not available - using default compute")


class VFSManager:
    """
    Comprehensive VFS Manager for IPFS Kit.
    
    This class provides all VFS management functionality including:
    - File and directory operations
    - Index management and synchronization
    - Performance monitoring and analytics
    - Cache management
    - Journal operations
    """
    
    def __init__(
        self,
        enable_dataset_storage: bool = False,
        enable_compute_layer: bool = False,
        dataset_batch_size: int = 100,
        storage_path: Optional[Union[str, Path]] = None,
    ):
        """
        Initialize the VFS Manager.
        
        Args:
            enable_dataset_storage: Enable ipfs_datasets_py integration
            enable_compute_layer: Enable ipfs_accelerate_py compute acceleration
            dataset_batch_size: Batch size for dataset operations
            storage_path: Optional filesystem root for VFS operations
        """
        self.storage_path: Optional[Path] = Path(storage_path) if storage_path else None
        if self.storage_path is not None:
            try:
                self.storage_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"Could not create storage_path {self.storage_path}: {e}")

        self.api = None
        self.pin_index = None
        self.arrow_metadata_index = None
        self.filesystem_journal = None
        self.initialized = False
        self.last_init_attempt = 0
        self.init_retry_interval = 30  # Retry every 30 seconds
        
        # Dataset storage configuration
        self.enable_dataset_storage = enable_dataset_storage and HAS_DATASETS
        self.dataset_batch_size = dataset_batch_size
        self.dataset_manager = None
        self._operation_buffer = []
        
        # Compute layer configuration
        self.enable_compute_layer = enable_compute_layer and HAS_ACCELERATE
        self.compute_layer = None

        # Optional VFS GraphRAG indexing state. These components are initialized
        # lazily so the manager remains usable without GraphRAG dependencies.
        self.graphrag_indexing_enabled = False
        self.graphrag_namespace = "default"
        self.graphrag_index_path: Optional[Path] = None
        self.graphrag_index = None
        self.graphrag_indexer = None
        self.graphrag_adapters = None
        self.graphrag_use_mocks = True
        
        # Initialize dataset manager if enabled
        if self.enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(enable=True)
                logger.info("VFS Manager dataset storage enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
                self.enable_dataset_storage = False
        
        # Initialize compute layer if enabled
        if self.enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("VFS Manager compute layer enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
                self.enable_compute_layer = False
        
        # Cache for frequently accessed data
        self.metrics_cache = {}
        self.cache_ttl = 10  # Cache for 10 seconds
        self.last_cache_update = 0
        
        logger.info("VFS Manager initialized")
    
    def __del__(self):
        """Cleanup method to flush buffers on deletion."""
        try:
            self._flush_operation_buffer()
        except Exception as e:
            logger.warning(f"Error flushing buffer during cleanup: {e}")
    
    async def initialize(self) -> bool:
        """
        Initialize the VFS Manager with all components.
        
        Returns:
            True if initialization successful, False otherwise
        """
        current_time = time.time()
        
        # Rate limit initialization attempts
        if current_time - self.last_init_attempt < self.init_retry_interval:
            return self.initialized
        
        self.last_init_attempt = current_time
        
        if not _ensure_core_imports():
            return False

        try:
            # Initialize IPFS API
            await self._initialize_ipfs_api()
            
            # Initialize enhanced pin index
            await self._initialize_enhanced_pin_index()
            
            # Initialize arrow metadata index
            await self._initialize_arrow_metadata_index()
            
            # Initialize filesystem journal
            await self._initialize_filesystem_journal()
            
            self.initialized = True
            logger.info("✓ VFS Manager fully initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize VFS Manager: {e}")
            return False
    
    async def _initialize_ipfs_api(self):
        """Initialize the IPFS API."""
        try:
            # Import lazily to avoid circular imports during package/module initialization.
            from .high_level_api import IPFSSimpleAPI as _IPFSSimpleAPI
        except Exception as e:
            logger.warning(f"IPFS API import failed (high_level_api not ready?): {e}")
            self.api = None
            return

        try:
            self.api = await anyio.to_thread.run_sync(_IPFSSimpleAPI)
            logger.info("✓ IPFS Simple API initialized")
        except Exception as e:
            logger.warning(f"IPFS API initialization failed: {e}")
            self.api = None
    
    async def _initialize_enhanced_pin_index(self):
        """Initialize the enhanced pin metadata index."""
        try:
            if not _ensure_core_imports() or get_global_pin_metadata_index is None:
                logger.warning("Pin metadata index unavailable; skipping initialization")
                self.pin_index = None
                return
            if self.api and hasattr(self.api, 'fs'):
                self.pin_index = await anyio.to_thread.run_sync(lambda: get_global_pin_metadata_index(ipfs_filesystem=self.api.fs)
                )
            else:
                self.pin_index = await anyio.to_thread.run_sync(get_global_pin_metadata_index)
            
            # Start background services if available
            if hasattr(self.pin_index, 'start_background_services'):
                try:
                    await self.pin_index.start_background_services()
                except Exception as e:
                    logger.warning(f"Could not start enhanced pin index background services: {e}")
            
            logger.info("✓ Enhanced pin metadata index initialized")
            
        except Exception as e:
            logger.warning(f"Enhanced pin index initialization failed: {e}")
            self.pin_index = None
    
    async def _initialize_arrow_metadata_index(self):
        """Initialize the arrow metadata index."""
        if not ARROW_METADATA_AVAILABLE:
            return
        
        try:
            self.arrow_metadata_index = await anyio.to_thread.run_sync(ArrowMetadataIndex)
            logger.info("✓ Arrow metadata index initialized")
        except Exception as e:
            logger.warning(f"Arrow metadata index initialization failed: {e}")
            self.arrow_metadata_index = None
    
    async def _initialize_filesystem_journal(self):
        """Initialize the filesystem journal."""
        try:
            if not _ensure_core_imports() or FilesystemJournal is None:
                logger.warning("Filesystem journal unavailable; skipping initialization")
                self.filesystem_journal = None
                return
            self.filesystem_journal = await anyio.to_thread.run_sync(FilesystemJournal)
            logger.info("✓ Filesystem journal initialized")
        except Exception as e:
            logger.warning(f"Filesystem journal initialization failed: {e}")
            self.filesystem_journal = None
    
    def _track_vfs_operation(self, operation: str, path: str, metadata: Optional[Dict[str, Any]] = None):
        """Track VFS operation to dataset storage if enabled."""
        if not self.enable_dataset_storage:
            return
        
        operation_data = {
            "operation": operation,
            "path": path,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
        
        self._operation_buffer.append(operation_data)
        
        # Flush buffer if it reaches batch size
        if len(self._operation_buffer) >= self.dataset_batch_size:
            self._flush_operation_buffer()
    
    def _flush_operation_buffer(self):
        """Flush buffered operations to dataset storage."""
        if not self.enable_dataset_storage or not self._operation_buffer:
            return
        
        try:
            import tempfile
            # Write operations to temp file
            temp_file = Path(tempfile.gettempdir()) / f"vfs_operations_{int(time.time())}.json"
            with open(temp_file, 'w') as f:
                json.dump(self._operation_buffer, f)
            
            # Store in dataset manager
            if self.dataset_manager and self.dataset_manager.is_available():
                self.dataset_manager.store(temp_file, metadata={
                    "type": "vfs_operations",
                    "count": len(self._operation_buffer),
                    "timestamp": time.time()
                })
            
            # Clear buffer
            self._operation_buffer.clear()
            
            # Clean up temp file
            if temp_file.exists():
                temp_file.unlink()
                
        except Exception as e:
            logger.warning(f"Failed to flush operation buffer to dataset: {e}")
    
    # =================================================================
    # ARROW IPC ZERO-COPY ACCESS
    # =================================================================
    
    async def get_pin_index_zero_copy(self, limit: Optional[int] = None, 
                                      filters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Get pin index data using zero-copy Arrow IPC.
        
        This method provides efficient access to pin index data without database locks
        by using Apache Arrow IPC for communication with the daemon.
        
        Args:
            limit: Maximum number of rows to return
            filters: Dictionary of filters to apply
            
        Returns:
            Dictionary with pin data or None if not available
        """
        if not _ensure_core_imports() or not ARROW_IPC_AVAILABLE:
            logger.warning("Arrow IPC not available, falling back to traditional access")
            return await self._get_pin_index_fallback(limit, filters)
        
        try:
            # Get Arrow table from daemon via IPC
            arrow_table = await get_pin_index_zero_copy(limit, filters)
            
            if arrow_table is not None:
                # Convert Arrow table to dictionary format
                arrow_ipc_interface = get_global_arrow_ipc_interface()
                pin_data = arrow_ipc_interface.table_to_dict(arrow_table)
                
                logger.info(f"✓ Retrieved {len(pin_data)} pins via Arrow IPC")
                return {
                    "success": True,
                    "pins": pin_data,
                    "source": "arrow_ipc_daemon",
                    "method": "zero_copy",
                    "timestamp": time.time()
                }
            else:
                logger.warning("No Arrow IPC data received, falling back")
                return await self._get_pin_index_fallback(limit, filters)
                
        except Exception as e:
            logger.error(f"Error getting pin index via Arrow IPC: {e}")
            return await self._get_pin_index_fallback(limit, filters)
    
    async def get_metrics_zero_copy(self, metric_types: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Get metrics data using zero-copy Arrow IPC.
        
        Args:
            metric_types: List of metric types to include
            
        Returns:
            Dictionary with metrics data or None if not available
        """
        if not _ensure_core_imports() or not ARROW_IPC_AVAILABLE:
            logger.warning("Arrow IPC not available, falling back to traditional access")
            return await self._get_metrics_fallback(metric_types)
        
        try:
            # Get Arrow table from daemon via IPC
            arrow_table = await get_metrics_zero_copy(metric_types)
            
            if arrow_table is not None:
                # Convert Arrow table to dictionary format
                arrow_ipc_interface = get_global_arrow_ipc_interface()
                metrics_data = arrow_ipc_interface.table_to_dict(arrow_table)
                
                logger.info(f"✓ Retrieved {len(metrics_data)} metrics via Arrow IPC")
                return {
                    "success": True,
                    "metrics": metrics_data,
                    "source": "arrow_ipc_daemon",
                    "method": "zero_copy",
                    "timestamp": time.time()
                }
            else:
                logger.warning("No Arrow IPC metrics received, falling back")
                return await self._get_metrics_fallback(metric_types)
                
        except Exception as e:
            logger.error(f"Error getting metrics via Arrow IPC: {e}")
            return await self._get_metrics_fallback(metric_types)
    
    async def _get_pin_index_fallback(self, limit: Optional[int] = None, 
                                      filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fallback method to get pin index without Arrow IPC."""
        try:
            # Ensure components are initialized
            if not await self.initialize():
                return {"success": False, "error": "VFS Manager not initialized"}
            
            # Try to get data from pin index directly
            if self.pin_index:
                # This would normally access the pin index but might hit database locks
                logger.warning("Attempting direct pin index access (may encounter database locks)")
                pins_data = await anyio.to_thread.run_sync(lambda: [])  # Placeholder - actual implementation would query pin index
                
                return {
                    "success": True,
                    "pins": pins_data,
                    "source": "direct_pin_index",
                    "method": "traditional",
                    "timestamp": time.time(),
                    "warning": "Database locks may affect performance"
                }
            else:
                return {"success": False, "error": "Pin index not available"}
                
        except Exception as e:
            logger.error(f"Fallback pin index access failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _get_metrics_fallback(self, metric_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fallback method to get metrics without Arrow IPC."""
        try:
            # Use existing metrics collection methods
            metrics = await self.get_analytics_data()
            
            # Filter by metric types if specified
            if metric_types and "metrics" in metrics:
                filtered_metrics = []
                for metric in metrics["metrics"]:
                    if metric.get("type") in metric_types:
                        filtered_metrics.append(metric)
                metrics["metrics"] = filtered_metrics
            
            return {
                "success": True,
                "metrics": metrics.get("metrics", []),
                "source": "vfs_manager_analytics",
                "method": "traditional",
                "timestamp": time.time()
            }
            
        except Exception as e:
            logger.error(f"Fallback metrics access failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_pin_index_zero_copy_sync(self, limit: Optional[int] = None, 
                                     filters: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for CLI use - handles both sync and async contexts."""
        try:
            return _run_async_from_sync(self.get_pin_index_zero_copy, limit, filters)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_metrics_zero_copy_sync(self, metric_types: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Synchronous wrapper for CLI use - handles both sync and async contexts."""
        try:
            return _run_async_from_sync(self.get_metrics_zero_copy, metric_types)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # =================================================================
    # VFS OPERATIONS
    # =================================================================
    
    async def execute_vfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a VFS operation by delegating to the appropriate component.
        
        Args:
            operation: The operation to execute (e.g., 'ls', 'cat', 'write', 'mkdir', 'rm')
            **kwargs: Operation-specific arguments
            
        Returns:
            Dictionary with operation results
        """
        if not await self.initialize():
            return {"success": False, "error": "VFS Manager not initialized"}
        
        if not self.api:
            return {"success": False, "error": "IPFS API not available"}
        
        # Handle special operations
        if operation == 'cache_stats':
            return await self.get_cache_statistics()
        elif operation == 'performance_metrics':
            return await self.get_performance_metrics()
        elif operation == 'index_status':
            return await self.get_index_status()
        
        # Map operation to API method
        op_name = operation
        if operation in ['ls', 'cat', 'write', 'mkdir', 'rm', 'info']:
            if hasattr(self.api, f"vfs_{operation}"):
                op_name = f"vfs_{operation}"
            elif hasattr(self.api.fs, operation):
                # Use filesystem directly
                try:
                    method = getattr(self.api.fs, operation)
                    if inspect.iscoroutinefunction(method):
                        return await method(**kwargs)
                    else:
                        return await anyio.to_thread.run_sync(lambda: method(**kwargs))
                except Exception as e:
                    logger.error(f"VFS operation '{operation}' failed: {e}")
                    return {"success": False, "error": str(e), "operation": operation}
        
        # Try to execute on API
        if not hasattr(self.api, op_name):
            logger.error(f"VFS operation '{op_name}' not found in IPFSSimpleAPI")
            return {"success": False, "error": f"Unknown VFS operation: {op_name}"}
        
        try:
            method = getattr(self.api, op_name)
            
            if inspect.iscoroutinefunction(method):
                return await method(**kwargs)
            else:
                return await anyio.to_thread.run_sync(lambda: method(**kwargs))
                
        except Exception as e:
            logger.error(f"VFS operation '{operation}' failed: {e}")
            return {"success": False, "error": str(e), "operation": operation}
    
    # =================================================================
    # FILE SYSTEM OPERATIONS
    # =================================================================
    
    async def list_files(self, path: str = "/") -> Dict[str, Any]:
        """List files and directories at the specified path."""
        try:
            result = await self.execute_vfs_operation('ls', path=path)
            if result.get("success", True) and "error" not in result:
                return {
                    "success": True,
                    "path": path,
                    "items": result.get("items", []),
                    "timestamp": time.time()
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "path": path
                }
        except Exception as e:
            logger.error(f"Error listing files at {path}: {e}")
            return {"success": False, "error": str(e), "path": path}
    
    async def create_folder(self, path: str, name: str) -> Dict[str, Any]:
        """Create a new folder at the specified path."""
        try:
            full_path = f"{path.rstrip('/')}/{name}"
            result = await self.execute_vfs_operation('mkdir', path=full_path)
            
            # Log to filesystem journal
            if self.filesystem_journal:
                await anyio.to_thread.run_sync(lambda: self.filesystem_journal.log_operation(
                        "mkdir", full_path, {"parent": path, "name": name})
                )
            
            # Track operation in dataset
            self._track_vfs_operation("create_folder", full_path, {"parent": path, "name": name})
            
            return {
                "success": result.get("success", True),
                "path": full_path,
                "error": result.get("error"),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error creating folder {name} at {path}: {e}")
            return {"success": False, "error": str(e), "path": path}
    
    async def delete_item(self, path: str) -> Dict[str, Any]:
        """Delete a file or directory at the specified path."""
        try:
            result = await self.execute_vfs_operation('rm', path=path)
            
            # Log to filesystem journal
            if self.filesystem_journal:
                await anyio.to_thread.run_sync(lambda: self.filesystem_journal.log_operation(
                        "rm", path, {"action": "delete"})
                )
            
            # Track operation in dataset
            self._track_vfs_operation("delete_item", path)
            
            return {
                "success": result.get("success", True),
                "path": path,
                "error": result.get("error"),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error deleting item at {path}: {e}")
            return {"success": False, "error": str(e), "path": path}
    
    async def rename_item(self, old_path: str, new_name: str) -> Dict[str, Any]:
        """Rename a file or directory."""
        try:
            parent_path = str(Path(old_path).parent)
            new_path = f"{parent_path}/{new_name}"
            
            # This would need to be implemented as copy + delete
            # For now, return a placeholder implementation
            
            # Log to filesystem journal
            if self.filesystem_journal:
                await anyio.to_thread.run_sync(lambda: self.filesystem_journal.log_operation(
                        "rename", old_path, {"new_name": new_name, "new_path": new_path})
                )
            
            return {
                "success": True,  # Placeholder
                "old_path": old_path,
                "new_path": new_path,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error renaming item {old_path} to {new_name}: {e}")
            return {"success": False, "error": str(e), "old_path": old_path}
    
    async def move_item(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Move a file or directory from source to target path."""
        try:
            # This would need to be implemented as copy + delete
            # For now, return a placeholder implementation
            
            # Log to filesystem journal
            if self.filesystem_journal:
                await anyio.to_thread.run_sync(lambda: self.filesystem_journal.log_operation(
                        "move", source_path, {"target_path": target_path})
                )
            
            return {
                "success": True,  # Placeholder
                "source_path": source_path,
                "target_path": target_path,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Error moving item from {source_path} to {target_path}: {e}")
            return {"success": False, "error": str(e), "source_path": source_path}
    
    # =================================================================
    # ANALYTICS AND METRICS
    # =================================================================
    
    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive VFS statistics.
        
        Returns:
            Dictionary with VFS statistics and metrics
        """
        if not await self.initialize():
            return self._get_fallback_statistics()
        
        try:
            # Check cache first
            current_time = time.time()
            if (current_time - self.last_cache_update < self.cache_ttl and 
                'vfs_statistics' in self.metrics_cache):
                return self.metrics_cache['vfs_statistics']
            
            # Get fresh statistics
            stats = await self._collect_vfs_statistics()
            
            # Update cache
            self.metrics_cache['vfs_statistics'] = stats
            self.last_cache_update = current_time
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting VFS statistics: {e}")
            return self._get_fallback_statistics()
    
    async def _collect_vfs_statistics(self) -> Dict[str, Any]:
        """Collect comprehensive VFS statistics from all sources."""
        stats = {
            "timestamp": time.time(),
            "status": "active",
            "source": "ipfs_kit_vfs_manager"
        }
        
        # Get enhanced pin metrics
        if self.pin_index:
            try:
                if not _ensure_core_imports() or get_cli_pin_metrics is None:
                    raise RuntimeError("Pin metrics function unavailable")
                cli_metrics = await anyio.to_thread.run_sync(get_cli_pin_metrics)
                
                if 'error' not in cli_metrics:
                    stats.update({
                        "pin_metrics": cli_metrics.get("traffic_metrics", {}),
                        "performance_metrics": cli_metrics.get("performance_metrics", {}),
                        "vfs_analytics": cli_metrics.get("vfs_analytics", {}),
                    })
                    
                    # Extract key metrics for dashboard
                    traffic = cli_metrics.get("traffic_metrics", {})
                    stats.update({
                        "filesystem_status": {
                            "total_pins": traffic.get("total_pins", 0),
                            "total_size_bytes": traffic.get("total_size_bytes", 0),
                            "total_size_human": traffic.get("total_size_human", "0 B"),
                            "vfs_mounts": traffic.get("vfs_mounts", 0),
                            "directory_pins": traffic.get("directory_pins", 0),
                            "file_pins": traffic.get("file_pins", 0)
                        },
                        "cache_performance": {
                            "cache_efficiency": traffic.get("cache_efficiency", 0.0),
                            "hot_pins": len(traffic.get("hot_pins", [])),
                            "verified_pins": traffic.get("verified_pins", 0),
                            "corrupted_pins": traffic.get("corrupted_pins", 0)
                        }
                    })
                    
            except Exception as e:
                logger.warning(f"Could not get enhanced pin metrics: {e}")
        
        # Get resource utilization
        stats["resource_utilization"] = await self._get_resource_utilization()
        
        # Get storage tier information
        if self.pin_index:
            stats["storage_tiers"] = await self._get_storage_tier_info()
        
        return stats
    
    async def _get_resource_utilization(self) -> Dict[str, Any]:
        """Get system resource utilization."""
        if not PSUTIL_AVAILABLE:
            return {
                "memory_usage": {"system_used_percent": 0},
                "disk_usage": {"used_percent": 0}
            }
        
        try:
            # Get memory usage
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "memory_usage": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "system_used_percent": memory.percent
                },
                "disk_usage": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "used_percent": round((disk.used / disk.total) * 100, 1)
                }
            }
            
        except Exception as e:
            logger.warning(f"Error getting resource utilization: {e}")
            return {
                "memory_usage": {"system_used_percent": 0},
                "disk_usage": {"used_percent": 0}
            }
    
    async def _get_storage_tier_info(self) -> Dict[str, Any]:
        """Get storage tier distribution and analytics."""
        try:
            if not self.pin_index:
                return {}
            
            # Get tier analytics from enhanced pin index
            if hasattr(self.pin_index, 'get_comprehensive_metrics'):
                tier_info = await anyio.to_thread.run_sync(lambda: self.pin_index.get_comprehensive_metrics()
                )
                
                return {
                    "tier_distribution": getattr(tier_info, 'tier_distribution', {}),
                    "replication_stats": getattr(tier_info, 'replication_stats', {}),
                    "storage_recommendations": getattr(tier_info, 'storage_recommendations', {})
                }
            
            return {}
            
        except Exception as e:
            logger.warning(f"Error getting storage tier info: {e}")
            return {}
    
    def _get_fallback_statistics(self) -> Dict[str, Any]:
        """Get fallback statistics when initialization fails."""
        return {
            "timestamp": time.time(),
            "status": "fallback",
            "source": "vfs_manager_fallback",
            "filesystem_status": {
                "total_pins": 0,
                "total_size_bytes": 0,
                "total_size_human": "0 B",
                "vfs_mounts": 0
            },
            "cache_performance": {
                "cache_efficiency": 0.0,
                "hot_pins": 0,
                "verified_pins": 0,
                "corrupted_pins": 0
            },
            "resource_utilization": {
                "memory_usage": {"system_used_percent": 0},
                "disk_usage": {"used_percent": 0}
            }
        }
    
    async def get_cache_statistics(self) -> Dict[str, Any]:
        """Get VFS cache performance statistics."""
        if not await self.initialize():
            return {"success": False, "error": "VFS Manager not initialized"}
        
        try:
            if self.pin_index and hasattr(self.pin_index, 'get_performance_metrics'):
                metrics = await anyio.to_thread.run_sync(lambda: self.pin_index.get_performance_metrics()
                )
                return {"success": True, "cache_stats": metrics}
            else:
                return {"success": False, "error": "Pin index not available"}
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        if not await self.initialize():
            return {"success": False, "error": "VFS Manager not initialized"}
        
        try:
            metrics = await self.get_vfs_statistics()
            return {
                "success": True,
                "performance_metrics": metrics.get("performance_metrics", {}),
                "cache_performance": metrics.get("cache_performance", {}),
                "resource_utilization": metrics.get("resource_utilization", {})
            }
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {"success": False, "error": str(e)}

    async def enable_graphrag_indexing(
        self,
        *,
        index_path: Optional[Union[str, Path]] = None,
        namespace: str = "default",
        indexer: Optional[Any] = None,
        use_mocks: bool = True,
        storage_format: str = "jsonl",
        adapter_config: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Enable optional VFS GraphRAG indexing for this manager.

        A supplied ``indexer`` may be a mock or production object exposing any
        subset of the manager lifecycle/search methods. Without one, the
        dependency-free ``VFSGraphRAGIndex`` and mock adapters are used by
        default.
        """

        try:
            if index_path is None:
                base_path = self.storage_path or Path.cwd()
                index_root = base_path / ".vfs_graphrag_index"
            else:
                index_root = Path(index_path)

            self.graphrag_namespace = namespace
            self.graphrag_index_path = index_root
            self.graphrag_use_mocks = use_mocks

            if indexer is not None:
                self.graphrag_indexer = indexer
                self.graphrag_index = indexer
                self.graphrag_adapters = None
            else:
                from .vfs_graphrag_index import (
                    VFSGraphRAGAdapterConfig,
                    VFSGraphRAGIndex,
                    create_vfs_graphrag_adapters,
                )

                self.graphrag_index = VFSGraphRAGIndex(
                    index_root,
                    namespace=namespace,
                    storage_format=storage_format,
                )
                config = adapter_config or VFSGraphRAGAdapterConfig(
                    namespace=namespace,
                    use_mocks=use_mocks,
                )
                self.graphrag_adapters = create_vfs_graphrag_adapters(config)
                self.graphrag_indexer = self.graphrag_index

            self.graphrag_indexing_enabled = True
            delegated = await self._call_graphrag_method(
                "enable_graphrag_indexing",
                index_path=str(index_root),
                namespace=namespace,
                use_mocks=use_mocks,
                storage_format=storage_format,
            )
            if delegated is not None:
                return self._success_result(delegated)

            return {
                "success": True,
                "enabled": True,
                "namespace": namespace,
                "index_path": str(index_root),
                "use_mocks": use_mocks,
                "storage_format": getattr(self.graphrag_index, "format", storage_format),
            }
        except Exception as e:
            logger.error(f"Failed to enable VFS GraphRAG indexing: {e}")
            self.graphrag_indexing_enabled = False
            return {"success": False, "error": str(e), "enabled": False}

    async def index_path(
        self,
        path: Union[str, Path],
        *,
        namespace: Optional[str] = None,
        backend: str = "vfs",
        protocol: str = "file",
        content: Optional[Union[str, bytes]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        recursive: bool = False,
        extract_content: bool = True,
    ) -> Dict[str, Any]:
        """Index one VFS path into the configured GraphRAG index."""

        if not self.graphrag_indexing_enabled:
            enabled = await self.enable_graphrag_indexing(namespace=namespace or self.graphrag_namespace)
            if not enabled.get("success"):
                return enabled

        delegated = await self._call_graphrag_method(
            "index_path",
            path=path,
            namespace=namespace,
            backend=backend,
            protocol=protocol,
            content=content,
            metadata=metadata,
            tags=tags,
            recursive=recursive,
            extract_content=extract_content,
        )
        if delegated is not None:
            return self._success_result(delegated)

        try:
            from .vfs_graphrag_schema import VFSObjectRecord

            records = []
            paths = self._expand_index_paths(Path(path), recursive=recursive)
            for item_path in paths:
                info = self._local_path_info(item_path)
                object_content = content if len(paths) == 1 else None
                if object_content is None and extract_content and info.get("object_type") == "file":
                    object_content = self._read_indexable_text(item_path)

                record = VFSObjectRecord(
                    namespace=namespace or self.graphrag_namespace,
                    backend=backend,
                    protocol=protocol,
                    path=str(item_path),
                    content_id=info.get("content_id"),
                    content_hash=info.get("content_hash"),
                    mime_type=info.get("mime_type") or "application/octet-stream",
                    size_bytes=int(info.get("size_bytes") or 0),
                    object_type=info.get("object_type", "file"),
                    modified_at=info.get("modified_at"),
                    tags=list(tags or []),
                    metadata={
                        "source": "vfs_manager",
                        "event": "index_path",
                        **dict(metadata or {}),
                    },
                )
                stored = await anyio.to_thread.run_sync(lambda r=record: self.graphrag_index.upsert_object(r))
                records.append(stored)

                if object_content is not None:
                    await self._index_text_derivatives(stored, object_content)

            return {
                "success": True,
                "indexed": len(records),
                "records": [record.to_dict() for record in records],
                "namespace": namespace or self.graphrag_namespace,
            }
        except Exception as e:
            logger.error(f"Failed to index VFS path {path}: {e}")
            return {"success": False, "error": str(e), "path": str(path)}

    async def index_namespace(
        self,
        namespace: Optional[str] = None,
        *,
        root_path: Optional[Union[str, Path]] = None,
        backend: str = "vfs",
        protocol: str = "file",
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Index all discoverable paths for a namespace."""

        target_namespace = namespace or self.graphrag_namespace
        if not self.graphrag_indexing_enabled:
            enabled = await self.enable_graphrag_indexing(namespace=target_namespace)
            if not enabled.get("success"):
                return enabled

        delegated = await self._call_graphrag_method(
            "index_namespace",
            namespace=target_namespace,
            root_path=root_path,
            backend=backend,
            protocol=protocol,
            recursive=recursive,
            metadata=metadata,
        )
        if delegated is not None:
            return self._success_result(delegated)

        path = Path(root_path) if root_path is not None else self.storage_path
        if path is None:
            return {
                "success": True,
                "indexed": 0,
                "namespace": target_namespace,
                "warning": "No root_path or storage_path configured",
            }
        result = await self.index_path(
            path,
            namespace=target_namespace,
            backend=backend,
            protocol=protocol,
            recursive=recursive,
            metadata={"namespace_index": True, **dict(metadata or {})},
        )
        result["namespace"] = target_namespace
        return result

    async def search(
        self,
        query: str = "",
        *,
        namespaces: Optional[List[str]] = None,
        backends: Optional[List[str]] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        search_type: str = "hybrid",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Search the configured VFS GraphRAG index."""

        if not self.graphrag_indexing_enabled:
            return {"success": False, "error": "VFS GraphRAG indexing is not enabled"}

        delegated = await self._call_graphrag_method(
            "search",
            query=query,
            namespaces=namespaces,
            backends=backends,
            metadata_filters=metadata_filters,
            top_k=top_k,
            search_type=search_type,
            **kwargs,
        )
        if delegated is not None:
            return self._success_result(delegated)

        try:
            optimized_query = query
            processor_result = None
            if self.graphrag_adapters is not None:
                optimizer_result = self.graphrag_adapters.query_optimizer.optimize(query)
                optimized_query = optimizer_result.get("optimized_query") or query
                processor_result = self.graphrag_adapters.processor.query(
                    optimized_query,
                    namespaces=namespaces,
                    backends=backends,
                    top_k=top_k,
                    search_type=search_type,
                    **kwargs,
                )

            filters = dict(metadata_filters or {})
            query_lower = optimized_query.lower()
            records = await anyio.to_thread.run_sync(lambda: self.graphrag_index.query_objects())
            matching_chunk_parents = set()
            if query_lower:
                chunks = await anyio.to_thread.run_sync(lambda: self.graphrag_index.query_chunks())
                matching_chunk_parents = {
                    chunk.parent_record_id
                    for chunk in chunks
                    if query_lower in str(chunk.text or "").lower()
                }
            results = []
            namespace_set = set(namespaces or [])
            backend_set = set(backends or [])
            for record in records:
                data = record.to_dict()
                if namespace_set and data.get("namespace") not in namespace_set:
                    continue
                if backend_set and data.get("backend") not in backend_set:
                    continue
                if not self._metadata_filters_match(data, filters):
                    continue
                searchable = " ".join(
                    str(value)
                    for value in (
                        data.get("path"),
                        data.get("normalized_path"),
                        data.get("content_id"),
                        data.get("mime_type"),
                        data.get("metadata"),
                        data.get("tags"),
                    )
                ).lower()
                if query_lower and query_lower not in searchable and data.get("record_id") not in matching_chunk_parents:
                    continue
                results.append({"record": data, "score": 1.0 if query_lower else None})
                if len(results) >= top_k:
                    break

            return {
                "success": True,
                "query": query,
                "optimized_query": optimized_query,
                "search_type": search_type,
                "results": results,
                "graphrag": processor_result or {},
                "total": len(results),
            }
        except Exception as e:
            logger.error(f"VFS GraphRAG search failed: {e}")
            return {"success": False, "error": str(e), "query": query}

    async def export_index(
        self,
        destination: Optional[Union[str, Path]] = None,
        *,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export the configured GraphRAG index as a portable JSON bundle."""

        if not self.graphrag_indexing_enabled:
            return {"success": False, "error": "VFS GraphRAG indexing is not enabled"}

        delegated = await self._call_graphrag_method("export_index", destination=destination, namespace=namespace)
        if delegated is not None:
            return self._success_result(delegated)

        try:
            bundle = await anyio.to_thread.run_sync(lambda: self._build_index_export(namespace=namespace))
            if destination is not None:
                dest_path = Path(destination)
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                await anyio.to_thread.run_sync(
                    lambda: dest_path.write_text(json.dumps(bundle, sort_keys=True, indent=2), encoding="utf-8")
                )
                bundle["path"] = str(dest_path)
            return {"success": True, "export": bundle}
        except Exception as e:
            logger.error(f"VFS GraphRAG export failed: {e}")
            return {"success": False, "error": str(e)}

    async def import_index(
        self,
        source: Union[str, Path, Dict[str, Any]],
        *,
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import a JSON bundle produced by ``export_index``."""

        if not self.graphrag_indexing_enabled:
            enabled = await self.enable_graphrag_indexing(namespace=namespace or self.graphrag_namespace)
            if not enabled.get("success"):
                return enabled

        delegated = await self._call_graphrag_method("import_index", source=source, namespace=namespace)
        if delegated is not None:
            return self._success_result(delegated)

        try:
            if isinstance(source, dict):
                bundle = source
            else:
                bundle = json.loads(Path(source).read_text(encoding="utf-8"))
            count = await anyio.to_thread.run_sync(lambda: self._import_index_bundle(bundle, namespace=namespace))
            return {"success": True, "imported": count, "namespace": namespace or self.graphrag_namespace}
        except Exception as e:
            logger.error(f"VFS GraphRAG import failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_index_status(self) -> Dict[str, Any]:
        """Get status of all VFS indices."""
        status = {
            "timestamp": time.time(),
            "pin_index": {
                "initialized": self.pin_index is not None,
                "available": bool(self.pin_index)
            },
            "arrow_metadata_index": {
                "initialized": self.arrow_metadata_index is not None,
                "available": ARROW_METADATA_AVAILABLE
            },
            "filesystem_journal": {
                "initialized": self.filesystem_journal is not None,
                "available": bool(self.filesystem_journal)
            },
            "ipfs_api": {
                "initialized": self.api is not None,
                "available": bool(self.api)
            },
            "graphrag": {
                "enabled": self.graphrag_indexing_enabled,
                "initialized": self.graphrag_index is not None,
                "available": self.graphrag_index is not None,
                "namespace": self.graphrag_namespace,
                "index_path": str(self.graphrag_index_path) if self.graphrag_index_path else None,
                "use_mocks": self.graphrag_use_mocks,
            }
        }

        delegated = await self._call_graphrag_method("get_index_status")
        if delegated is not None:
            status["graphrag"]["indexer_status"] = delegated
        elif self.graphrag_index is not None and hasattr(self.graphrag_index, "stats"):
            try:
                status["graphrag"]["stats"] = await anyio.to_thread.run_sync(self.graphrag_index.stats)
            except Exception as e:
                status["graphrag"]["stats_error"] = str(e)
        
        return {"success": True, "index_status": status}

    def enable_graphrag_indexing_sync(self, **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper for ``enable_graphrag_indexing``."""

        return _run_async_from_sync(self.enable_graphrag_indexing, **kwargs)

    def index_path_sync(self, path: Union[str, Path], **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper for ``index_path``."""

        return _run_async_from_sync(self.index_path, path, **kwargs)

    def index_namespace_sync(self, namespace: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper for ``index_namespace``."""

        return _run_async_from_sync(self.index_namespace, namespace, **kwargs)

    def search_sync(self, query: str = "", **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper for ``search``."""

        return _run_async_from_sync(self.search, query, **kwargs)

    def export_index_sync(self, destination: Optional[Union[str, Path]] = None, **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper for ``export_index``."""

        return _run_async_from_sync(self.export_index, destination, **kwargs)

    def import_index_sync(self, source: Union[str, Path, Dict[str, Any]], **kwargs: Any) -> Dict[str, Any]:
        """Synchronous wrapper for ``import_index``."""

        return _run_async_from_sync(self.import_index, source, **kwargs)

    def get_index_status_sync(self) -> Dict[str, Any]:
        """Synchronous wrapper for ``get_index_status``."""

        return _run_async_from_sync(self.get_index_status)

    async def _call_graphrag_method(self, method_name: str, **kwargs: Any) -> Optional[Any]:
        """Call a method on an injected GraphRAG indexer when it is distinct."""

        indexer = self.graphrag_indexer
        if indexer is None or indexer is self:
            return None
        if indexer is self.graphrag_index and type(indexer).__name__ == "VFSGraphRAGIndex":
            return None
        method = getattr(indexer, method_name, None)
        if not callable(method):
            return None
        filtered = {key: value for key, value in kwargs.items() if value is not None}
        try:
            result = method(**filtered)
        except TypeError:
            result = method(*filtered.values())
        if inspect.isawaitable(result):
            result = await result
        return result

    def _success_result(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value if "success" in value else {"success": True, **value}
        return {"success": True, "result": value}

    def _expand_index_paths(self, path: Path, *, recursive: bool) -> List[Path]:
        if path.exists() and path.is_dir() and recursive:
            return [path, *sorted(child for child in path.rglob("*"))]
        return [path]

    def _local_path_info(self, path: Path) -> Dict[str, Any]:
        info: Dict[str, Any] = {
            "object_type": "directory" if path.exists() and path.is_dir() else "file",
            "mime_type": mimetypes.guess_type(str(path))[0],
            "size_bytes": 0,
        }
        try:
            stat_result = path.stat()
            info["size_bytes"] = stat_result.st_size
            info["modified_at"] = str(stat_result.st_mtime)
        except OSError:
            return info
        if info["object_type"] == "file":
            try:
                import hashlib

                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                info["content_hash"] = f"sha256:{digest}"
            except OSError:
                pass
        return info

    def _read_indexable_text(self, path: Path, *, max_bytes: int = 1_000_000) -> Optional[str]:
        mime_type = mimetypes.guess_type(str(path))[0] or ""
        if not (
            mime_type.startswith("text/")
            or path.suffix.lower() in {".md", ".json", ".yaml", ".yml", ".csv", ".py", ".js", ".ts", ".txt"}
        ):
            return None
        try:
            data = path.read_bytes()[:max_bytes]
            return data.decode("utf-8", errors="replace")
        except OSError:
            return None

    async def _index_text_derivatives(self, record: Any, content: Union[str, bytes]) -> None:
        if self.graphrag_adapters is None:
            return
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
        if not text:
            return

        def _index() -> None:
            chunks = self.graphrag_adapters.chunking.chunk_text(
                text,
                parent_record_id=record.record_id,
                path=record.path,
                content_id=record.content_id,
            )
            if chunks:
                self.graphrag_index.put_records(chunks)
                embeddings, vectors = self.graphrag_adapters.embeddings.embed_chunks(
                    chunks,
                    parent_record_id=record.record_id,
                    vector_store_id=getattr(self.graphrag_adapters.vector_store, "store_id", None),
                )
                embeddings = self.graphrag_adapters.vector_store.add_embeddings(embeddings, vectors)
                self.graphrag_index.put_records(embeddings)
            entities, relationships = self.graphrag_adapters.knowledge_graph.extract(
                text,
                source_record_ids=[record.record_id],
                source_chunk_ids=[chunk.chunk_id for chunk in chunks],
            )
            self.graphrag_index.put_records([*entities, *relationships])

        await anyio.to_thread.run_sync(_index)

    def _metadata_filters_match(self, record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        metadata = record.get("metadata") or {}
        for key, expected in filters.items():
            if key in record:
                actual = record.get(key)
            else:
                actual = metadata.get(key)
            if actual != expected:
                return False
        return True

    def _build_index_export(self, *, namespace: Optional[str] = None) -> Dict[str, Any]:
        kinds = ("objects", "chunks", "embeddings", "entities", "relationships", "snapshots", "checkpoints")
        records: Dict[str, List[Dict[str, Any]]] = {}
        for kind in kinds:
            rows = [record.to_dict() for record in self.graphrag_index.query_records(kind)]
            if namespace is not None and rows and "namespace" in rows[0]:
                rows = [row for row in rows if row.get("namespace") == namespace]
            records[kind] = rows
        return {
            "schema": "ipfs_kit_py.vfs.graphrag.export.v1",
            "namespace": namespace or self.graphrag_namespace,
            "created_at": time.time(),
            "records": records,
            "counts": {kind: len(rows) for kind, rows in records.items()},
        }

    def _import_index_bundle(self, bundle: Dict[str, Any], *, namespace: Optional[str] = None) -> int:
        from .vfs_graphrag_schema import record_from_dict

        count = 0
        for rows in (bundle.get("records") or {}).values():
            for row in rows:
                data = dict(row)
                if namespace is not None and "namespace" in data:
                    data["namespace"] = namespace
                self.graphrag_index.put_record(record_from_dict(data))
                count += 1
        return count
    
    # =================================================================
    # JOURNAL OPERATIONS
    # =================================================================
    
    async def get_vfs_journal(self, backend_filter: Optional[str] = None, 
                             search_query: Optional[str] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get VFS journal entries.
        
        Args:
            backend_filter: Optional backend to filter by
            search_query: Optional search query
            limit: Maximum number of entries to return
            
        Returns:
            List of journal entries
        """
        if not await self.initialize():
            return []
        
        try:
            entries = []
            
            # Get entries from filesystem journal
            if self.filesystem_journal:
                journal_entries = await anyio.to_thread.run_sync(lambda: self.filesystem_journal.get_recent_entries(limit=limit)
                )
                entries.extend(journal_entries)
            
            # Get entries from pin index journal if available
            if self.pin_index and hasattr(self.pin_index, 'journal'):
                journal = self.pin_index.journal
                if journal:
                    pin_entries = await anyio.to_thread.run_sync(lambda: journal.get_recent_entries(limit=limit)
                    )
                    entries.extend(pin_entries)
            
            # Apply filters
            filtered_entries = []
            for entry in entries:
                if backend_filter and entry.get('backend') != backend_filter:
                    continue
                if search_query and search_query.lower() not in str(entry).lower():
                    continue
                filtered_entries.append(entry)
            
            # Sort by timestamp (most recent first) and limit
            filtered_entries.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return filtered_entries[:limit]
            
        except Exception as e:
            logger.error(f"Error getting VFS journal: {e}")
            return []
    
    # =================================================================
    # CLEANUP AND LIFECYCLE
    # =================================================================
    
    async def cleanup(self):
        """Clean up resources and stop background services."""
        try:
            if self.pin_index and hasattr(self.pin_index, 'stop_background_services'):
                await self.pin_index.stop_background_services()
            
            if self.filesystem_journal and hasattr(self.filesystem_journal, 'close'):
                await anyio.to_thread.run_sync(self.filesystem_journal.close)
            
            self.initialized = False
            logger.info("VFS Manager cleaned up")
            
        except Exception as e:
            logger.error(f"Error during VFS Manager cleanup: {e}")


# =================================================================
# GLOBAL INSTANCE MANAGEMENT
# =================================================================

_global_vfs_manager: Optional[VFSManager] = None


def get_global_vfs_manager() -> VFSManager:
    """Get or create the global VFS Manager instance."""
    global _global_vfs_manager
    
    if _global_vfs_manager is None:
        _global_vfs_manager = VFSManager()
    
    return _global_vfs_manager


async def initialize_global_vfs_manager() -> bool:
    """Initialize the global VFS Manager."""
    manager = get_global_vfs_manager()
    return await manager.initialize()


async def cleanup_global_vfs_manager():
    """Clean up the global VFS Manager."""
    global _global_vfs_manager
    
    if _global_vfs_manager:
        await _global_vfs_manager.cleanup()
        _global_vfs_manager = None


# =================================================================
# SYNCHRONOUS HELPERS FOR CLI
# =================================================================


def get_vfs_manager_sync() -> VFSManager:
    """Get the global VFS Manager for synchronous use (CLI)."""
    return get_global_vfs_manager()


def execute_vfs_operation_sync(operation: str, **kwargs) -> Dict[str, Any]:
    """Execute a VFS operation synchronously for CLI use."""
    manager = get_global_vfs_manager()

    return _run_async_from_sync(manager.execute_vfs_operation, operation, **kwargs)


def get_vfs_statistics_sync() -> Dict[str, Any]:
    """Get VFS statistics synchronously for CLI use."""
    manager = get_global_vfs_manager()

    return _run_async_from_sync(manager.get_vfs_statistics)
