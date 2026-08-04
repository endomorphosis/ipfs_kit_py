"""
VFS (Virtual File System) for IPFS Kit (MCP Wrapper).

This module acts as a thin wrapper around the centralized VFSManager
from the ipfs_kit_py library, ensuring the MCP layer uses the core VFS functionalities.
"""

import logging
import json
import threading
import tempfile
import os
from collections.abc import Mapping
from typing import Dict, Any
from datetime import datetime
from uuid import uuid4

try:
    # Primary import path for when the package is installed
    from ipfs_kit_py.vfs_manager import get_global_vfs_manager
except ImportError:
    # Fallback for development environments
    import sys
    import os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from ipfs_kit_py.vfs_manager import get_global_vfs_manager

logger = logging.getLogger(__name__)

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
    import sys
    from pathlib import Path
    accelerate_path = Path(__file__).parent.parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute acceleration available")
except ImportError:
    logger.info("ipfs_accelerate_py not available - using standard compute")

class VFSManager:
    """
    MCP Wrapper for the centralized VFSManager.
    Delegates all VFS tasks to the centralized library component.
    """

    def __init__(self, 
                 enable_dataset_storage: bool = False,
                 enable_compute_layer: bool = False,
                 ipfs_client = None,
                 dataset_batch_size: int = 100):
        """Initializes the wrapper and the underlying VFSManager."""
        logger.info("=== MCP VFSManager Wrapper initializing ===")
        try:
            self.vfs_manager = get_global_vfs_manager()
            logger.info("✓ Centralized VFSManager initialized for MCP operations.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize VFSManager: {e}", exc_info=True)
            self.vfs_manager = None
        
        # Dataset storage integration
        self.enable_dataset_storage = enable_dataset_storage
        self.enable_compute_layer = enable_compute_layer
        self.dataset_manager = None
        self.compute_layer = None
        self._operation_buffer = []
        self._buffer_lock = threading.Lock()
        self.dataset_batch_size = max(1, int(dataset_batch_size))
        
        if HAS_DATASETS and enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(
                    enable=True,
                    ipfs_client=ipfs_client
                )
                logger.info("Dataset storage enabled for VFS operations")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
        
        if HAS_ACCELERATE and enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Compute acceleration enabled for VFS operations")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
        
        logger.info("=== MCP VFSManager Wrapper initialization complete ===")

    async def execute_vfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Executes a VFS operation by delegating to the centralized VFSManager.
        """
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}

        try:
            result = await self.vfs_manager.execute_vfs_operation(operation, **kwargs)
            if not isinstance(result, Mapping):
                return {
                    "success": False,
                    "error": "central VFS manager returned an invalid result",
                    "operation": operation,
                }
            result = dict(result)
            if not self._is_committed_result(result):
                # A malformed response that claims success while carrying an
                # error is not allowed to reach MCP callers as a success.
                result["success"] = False
                return result

            # Only canonical committed operations are eligible for eventual
            # dataset publication.
            operation_data = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "kwargs": kwargs,
                "success": True,
                "result": result
            }
            self._store_operation_to_dataset(operation_data)
            
            return result
        except Exception as e:
            logger.error(f"❌ VFS operation '{operation}' failed in MCP wrapper: {e}", exc_info=True)
            return {"success": False, "error": str(e), "operation": operation}

    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """Get VFS statistics from the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.get_vfs_statistics()
        except Exception as e:
            logger.error(f"❌ Failed to get VFS statistics: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def get_vfs_journal(self, backend_filter=None, search_query=None, limit=100):
        """Get VFS journal entries from the centralized VFSManager."""
        if not self.vfs_manager:
            return []
        
        try:
            return await self.vfs_manager.get_vfs_journal(
                backend_filter=backend_filter,
                search_query=search_query,
                limit=limit
            )
        except Exception as e:
            logger.error(f"❌ Failed to get VFS journal: {e}", exc_info=True)
            return []

    async def list_files(self, path="/"):
        """List files using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.list_files(path)
        except Exception as e:
            logger.error(f"❌ Failed to list files: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def create_folder(self, path, name):
        """Create folder using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.create_folder(path, name)
        except Exception as e:
            logger.error(f"❌ Failed to create folder: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def delete_item(self, path):
        """Delete item using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.delete_item(path)
        except Exception as e:
            logger.error(f"❌ Failed to delete item: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def rename_item(self, old_path, new_name):
        """Rename item using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.rename_item(old_path, new_name)
        except Exception as e:
            logger.error(f"❌ Failed to rename item: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def move_item(self, source_path, target_path):
        """Move item using the centralized VFSManager."""
        if not self.vfs_manager:
            return {"success": False, "error": "VFSManager not initialized."}
        
        try:
            return await self.vfs_manager.move_item(source_path, target_path)
        except Exception as e:
            logger.error(f"❌ Failed to move item: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def cleanup(self):
        """Cleans up resources if the underlying VFSManager has a cleanup method."""
        if self.vfs_manager:
            logger.info("Cleaning up MCP VFSManager wrapper...")
            
            # Flush any pending operations to dataset
            if self.enable_dataset_storage:
                self.flush_to_dataset()
            
            # The actual cleanup is handled by the centralized VFSManager
            # We just need to release our reference
            self.vfs_manager = None
            logger.info("✓ MCP VFSManager wrapper cleaned up.")
    
    @staticmethod
    def _is_committed_result(result: Mapping[str, Any] | Any) -> bool:
        if not (
            isinstance(result, Mapping)
            and result.get("success") is True
            and not result.get("error")
        ):
            return False

        nested_result = result.get("result")
        return not (
            isinstance(nested_result, Mapping)
            and (
                nested_result.get("success") is False
                or bool(nested_result.get("error"))
            )
        )

    def _store_operation_to_dataset(self, operation_data: dict) -> bool:
        """Buffer a committed operation with a collision-safe identity."""
        if not self.enable_dataset_storage or not self.dataset_manager:
            return False

        record = dict(operation_data)
        # Never rely on a timestamp as a batch identity: concurrent operations
        # can share one.  Always assign the wrapper's own unique record id.
        record["dataset_operation_id"] = f"mcp-vfs-operation-{uuid4().hex}"
        with self._buffer_lock:
            self._operation_buffer.append(record)
            should_flush = len(self._operation_buffer) >= self.dataset_batch_size
        if should_flush:
            return self._flush_operations_to_dataset()
        return True
            
    def _flush_operations_to_dataset(self) -> bool:
        """Flush one snapshot, retaining all records until storage commits."""
        if not self.enable_dataset_storage or not self.dataset_manager:
            return False
        is_available = getattr(self.dataset_manager, "is_available", None)
        try:
            available = callable(is_available) and is_available()
        except Exception as exc:
            logger.warning("Unable to determine dataset availability: %s", exc)
            return False
        if not available:
            return False
        with self._buffer_lock:
            snapshot = list(self._operation_buffer)
        if not snapshot:
            return False

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                for op in snapshot:
                    f.write(json.dumps(op) + '\n')
                temp_path = f.name
            result = self.dataset_manager.store(
                temp_path,
                metadata={
                    "type": "vfs_operations",
                    "operation_count": len(snapshot),
                    "timestamp": datetime.now().isoformat(),
                    "component": self.__class__.__name__,
                },
            )
            if not self._is_committed_result(result):
                return False
            snapshot_ids = {operation["dataset_operation_id"] for operation in snapshot}
            with self._buffer_lock:
                self._operation_buffer = [
                    operation for operation in self._operation_buffer
                    if operation.get("dataset_operation_id") not in snapshot_ids
                ]
            logger.info(
                "Stored %s VFS operations to dataset: %s",
                len(snapshot), result.get("cid", "N/A"),
            )
            return True
        except Exception as e:
            logger.error(f"Failed to flush operations to dataset: {e}")
            return False
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass
    
    def flush_to_dataset(self) -> bool:
        """Manually flush pending operations to dataset storage."""
        if not self.enable_dataset_storage:
            return False
        return self._flush_operations_to_dataset()
