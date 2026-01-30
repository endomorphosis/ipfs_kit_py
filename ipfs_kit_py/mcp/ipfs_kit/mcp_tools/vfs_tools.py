"""
VFS tools for MCP server.
"""

from typing import Dict, Any
import logging
import threading
import tempfile
import json
import os
from datetime import datetime

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
    from pathlib import Path as PathLib
    accelerate_path = PathLib(__file__).parent.parent.parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute acceleration available")
except ImportError:
    logger.info("ipfs_accelerate_py not available - using standard compute")


class VFSTools:
    """Tools for VFS operations."""
    
    def __init__(self, backend_monitor, 
                 enable_dataset_storage: bool = False,
                 enable_compute_layer: bool = False,
                 ipfs_client = None,
                 dataset_batch_size: int = 100):
        self.backend_monitor = backend_monitor
        
        # Dataset storage integration
        self.enable_dataset_storage = enable_dataset_storage
        self.enable_compute_layer = enable_compute_layer
        self.dataset_manager = None
        self.compute_layer = None
        self._operation_buffer = []
        self._buffer_lock = threading.Lock()
        self.dataset_batch_size = dataset_batch_size
        
        if HAS_DATASETS and enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(
                    enable=True,
                    ipfs_client=ipfs_client
                )
                logger.info("Dataset storage enabled for VFS tools")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
        
        if HAS_ACCELERATE and enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Compute acceleration enabled for VFS tools")
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
                        "type": "vfs_tool_invocations",
                        "operation_count": len(self._operation_buffer),
                        "timestamp": datetime.now().isoformat(),
                        "component": "VFSTools"
                    }
                )
                
                if result.get("success"):
                    logger.info(f"Stored {len(self._operation_buffer)} VFS tool operations to dataset: {result.get('cid', 'N/A')}")
                
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
    
    async def get_vfs_statistics(self) -> Dict[str, Any]:
        """Get VFS statistics."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                result = await self.backend_monitor.vfs_observer.get_vfs_statistics()
            else:
                result = {
                    "cache_hit_rate": 0,
                    "cache_size": 0,
                    "total_files": 0,
                    "total_size": 0,
                    "error": "VFS observer not available"
                }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_statistics",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": result
            })
            
            return result
        except Exception as e:
            error_result = {"error": str(e)}
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_statistics",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": error_result
            })
            return error_result
    
    async def get_vfs_cache(self) -> Dict[str, Any]:
        """Get VFS cache information."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                result = await self.backend_monitor.vfs_observer.get_cache_statistics()
            else:
                result = {
                    "cache_entries": 0,
                    "cache_size_mb": 0,
                    "cache_hit_rate": 0,
                    "error": "VFS observer not available"
                }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_cache",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": result
            })
            
            return result
        except Exception as e:
            error_result = {"error": str(e)}
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_cache",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": error_result
            })
            return error_result
    
    async def get_vfs_vector_index(self) -> Dict[str, Any]:
        """Get VFS vector index information."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                result = await self.backend_monitor.vfs_observer.get_vector_index_statistics()
            else:
                result = {
                    "vector_count": 0,
                    "dimensions": 0,
                    "index_size_mb": 0,
                    "error": "VFS observer not available"
                }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_vector_index",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": result
            })
            
            return result
        except Exception as e:
            error_result = {"error": str(e)}
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_vector_index",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": error_result
            })
            return error_result
    
    async def get_vfs_knowledge_base(self) -> Dict[str, Any]:
        """Get VFS knowledge base information."""
        try:
            if hasattr(self.backend_monitor, 'vfs_observer'):
                result = await self.backend_monitor.vfs_observer.get_knowledge_base_statistics()
            else:
                result = {
                    "kb_nodes": 0,
                    "kb_relationships": 0,
                    "kb_size_mb": 0,
                    "error": "VFS observer not available"
                }
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_knowledge_base",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": result
            })
            
            return result
        except Exception as e:
            error_result = {"error": str(e)}
            self._store_operation_to_dataset({
                "tool_name": "get_vfs_knowledge_base",
                "timestamp": datetime.now().isoformat(),
                "parameters": {},
                "result": error_result
            })
            return error_result
