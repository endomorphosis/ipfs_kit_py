#!/usr/bin/env python3
"""
Simplified Bucket Manager for IPFS Kit.

This implements the simplified bucket architecture:
- Buckets as VFS indices (parquet files)
- Central bucket registry
- YAML configuration files for policies
- Integration with ipfs_datasets_py and ipfs_accelerate_py
"""

import anyio
import json
import logging
import os
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, asdict

import pandas as pd

logger = logging.getLogger(__name__)

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


@dataclass
class BucketConfig:
    """Bucket configuration."""
    name: str
    bucket_type: str = 'general'
    vfs_structure: str = 'hybrid'
    created_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SimplifiedBucketManager:
    """Simplified bucket manager with dataset and compute layer integration."""
    
    def __init__(
        self, 
        base_path: Optional[str] = None,
        enable_dataset_storage: bool = False,
        enable_compute_layer: bool = False,
        ipfs_client=None,
        dataset_batch_size: int = 100
    ):
        """
        Initialize simplified bucket manager.
        
        Args:
            base_path: Base directory for buckets
            enable_dataset_storage: Enable ipfs_datasets_py integration
            enable_compute_layer: Enable ipfs_accelerate_py compute acceleration
            ipfs_client: IPFS client instance
            dataset_batch_size: Batch size for dataset operations
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path('~/.ipfs_kit').expanduser()
        
        # Directory structure
        self.vfs_indices_dir = self.base_path / 'vfs_indices'
        self.bucket_configs_dir = self.base_path / 'bucket_configs'
        self.bucket_registry_file = self.base_path / 'bucket_registry.parquet'
        
        # Ensure directories exist
        self.vfs_indices_dir.mkdir(parents=True, exist_ok=True)
        self.bucket_configs_dir.mkdir(parents=True, exist_ok=True)
        
        # Dataset storage configuration
        self.enable_dataset_storage = enable_dataset_storage and HAS_DATASETS
        self.dataset_batch_size = dataset_batch_size
        self.dataset_manager = None
        self.ipfs_client = ipfs_client
        self._operation_buffer = []
        self._buffer_lock = threading.Lock()
        
        # Compute layer configuration
        self.enable_compute_layer = enable_compute_layer and HAS_ACCELERATE
        self.compute_layer = None
        
        # Initialize dataset manager if enabled
        if self.enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(enable=True, ipfs_client=ipfs_client)
                logger.info("Simplified Bucket Manager dataset storage enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
                self.enable_dataset_storage = False
        
        # Initialize compute layer if enabled
        if self.enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Simplified Bucket Manager compute layer enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
                self.enable_compute_layer = False
        
        logger.info(f"SimplifiedBucketManager initialized at {self.base_path}")
    
    def __del__(self):
        """Cleanup method to flush buffers on deletion."""
        try:
            self.flush_to_dataset()
        except Exception as e:
            logger.warning(f"Error flushing buffer during cleanup: {e}")
    
    def _store_operation_to_dataset(self, operation: str, bucket_name: str, details: Dict[str, Any], result: Dict[str, Any]):
        """Buffer operation for dataset storage."""
        if not self.enable_dataset_storage:
            return
        
        operation_data = {
            "operation": operation,
            "timestamp": time.time(),
            "bucket_name": bucket_name,
            "details": details,
            "result": result
        }
        
        with self._buffer_lock:
            self._operation_buffer.append(operation_data)
            
            # Flush buffer if it reaches batch size
            if len(self._operation_buffer) >= self.dataset_batch_size:
                self._flush_operations_to_dataset()
    
    def _flush_operations_to_dataset(self):
        """Flush buffered operations to dataset storage."""
        if not self.enable_dataset_storage or not self._operation_buffer:
            return
        
        with self._buffer_lock:
            if not self._operation_buffer:
                return
            
            try:
                # Write operations to temp file
                temp_file = self.base_path / f"operations_{int(time.time())}.json"
                with open(temp_file, 'w') as f:
                    json.dump(self._operation_buffer, f)
                
                # Store in dataset manager
                if self.dataset_manager and self.dataset_manager.is_available():
                    self.dataset_manager.store(temp_file, metadata={
                        "type": "bucket_operations",
                        "count": len(self._operation_buffer),
                        "timestamp": time.time()
                    })
                
                # Clear buffer
                self._operation_buffer.clear()
                
                # Clean up temp file
                if temp_file.exists():
                    temp_file.unlink()
                    
            except Exception as e:
                logger.warning(f"Failed to flush operations to dataset: {e}")
    
    def flush_to_dataset(self):
        """Public method to manually flush operations to dataset storage."""
        self._flush_operations_to_dataset()
    
    async def create_bucket(
        self, 
        bucket_name: str, 
        bucket_type: str = 'general',
        vfs_structure: str = 'hybrid',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new bucket with VFS index.
        
        Args:
            bucket_name: Name of the bucket
            bucket_type: Type of bucket (general, dataset, etc.)
            vfs_structure: VFS structure type (unixfs, graph, vector, hybrid)
            metadata: Optional metadata
            
        Returns:
            Result dictionary
        """
        try:
            vfs_index_path = self.vfs_indices_dir / f"{bucket_name}.parquet"
            
            if vfs_index_path.exists():
                return {
                    'success': False,
                    'error': f"Bucket '{bucket_name}' already exists"
                }
            
            # Create VFS index
            vfs_data = {
                'path': [''],  # Root entry
                'cid': [''],
                'size': [0],
                'mime_type': [''],
                'created_at': [datetime.utcnow().isoformat()],
                'modified_at': [datetime.utcnow().isoformat()],
                'attributes': [json.dumps({})]
            }
            
            df = pd.DataFrame(vfs_data)
            df.to_parquet(vfs_index_path, index=False)
            
            # Create YAML config
            config = BucketConfig(
                name=bucket_name,
                bucket_type=bucket_type,
                vfs_structure=vfs_structure,
                created_at=datetime.utcnow().isoformat(),
                metadata=metadata or {}
            )
            
            config_path = self.bucket_configs_dir / f"{bucket_name}.yaml"
            try:
                import yaml
                with open(config_path, 'w') as f:
                    yaml.dump(asdict(config), f, default_flow_style=False)
            except ImportError:
                # Fallback to JSON if YAML not available
                config_path = self.bucket_configs_dir / f"{bucket_name}.json"
                with open(config_path, 'w') as f:
                    json.dump(asdict(config), f, indent=2)
            
            # Update bucket registry
            await self._update_bucket_registry(bucket_name, vfs_index_path)
            
            logger.info(f"Created bucket '{bucket_name}' at {vfs_index_path}")
            
            result = {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'vfs_index_path': str(vfs_index_path),
                    'config_path': str(config_path),
                    'bucket_type': bucket_type,
                    'created_at': config.created_at
                }
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset("create_bucket", bucket_name, {
                "bucket_type": bucket_type,
                "vfs_structure": vfs_structure,
                "metadata": metadata
            }, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating bucket '{bucket_name}': {e}")
            return {
                'success': False,
                'error': f"Failed to create bucket: {str(e)}"
            }
    
    async def list_buckets(self) -> Dict[str, Any]:
        """List all buckets."""
        try:
            buckets = []
            
            for vfs_file in self.vfs_indices_dir.glob('*.parquet'):
                try:
                    bucket_name = vfs_file.stem
                    df = pd.read_parquet(vfs_file)
                    
                    bucket_info = {
                        'name': bucket_name,
                        'vfs_index_path': str(vfs_file),
                        'file_count': len(df) - 1,  # Subtract root entry
                        'size_bytes': df['size'].sum(),
                        'created_at': df.iloc[0]['created_at'] if len(df) > 0 else None
                    }
                    buckets.append(bucket_info)
                    
                except Exception as e:
                    logger.warning(f"Error reading bucket file {vfs_file}: {e}")
                    continue
            
            result = {
                'success': True,
                'data': {
                    'buckets': buckets,
                    'total_count': len(buckets)
                }
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset("list_buckets", "", {}, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error listing buckets: {e}")
            return {
                'success': False,
                'error': f"Failed to list buckets: {str(e)}"
            }
    
    async def delete_bucket(self, bucket_name: str, force: bool = False) -> Dict[str, Any]:
        """Delete a bucket."""
        try:
            vfs_index_path = self.vfs_indices_dir / f"{bucket_name}.parquet"
            
            if not vfs_index_path.exists():
                return {
                    'success': False,
                    'error': f"Bucket '{bucket_name}' does not exist"
                }
            
            # Check if bucket has files (unless force=True)
            if not force:
                df = pd.read_parquet(vfs_index_path)
                if len(df) > 1:  # More than just root entry
                    return {
                        'success': False,
                        'error': f"Bucket '{bucket_name}' contains files. Use force=True to delete."
                    }
            
            # Remove VFS index
            vfs_index_path.unlink()
            
            # Remove config file
            for ext in ['.yaml', '.json']:
                config_path = self.bucket_configs_dir / f"{bucket_name}{ext}"
                if config_path.exists():
                    config_path.unlink()
            
            logger.info(f"Deleted bucket '{bucket_name}'")
            
            result = {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'deleted_at': datetime.utcnow().isoformat()
                }
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset("delete_bucket", bucket_name, {"force": force}, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error deleting bucket: {e}")
            return {
                'success': False,
                'error': f"Failed to delete bucket: {str(e)}"
            }
    
    async def _update_bucket_registry(self, bucket_name: str, vfs_index_path: Path):
        """Update the central bucket registry."""
        try:
            registry_data = []
            
            # Load existing registry if it exists
            if self.bucket_registry_file.exists():
                existing_df = pd.read_parquet(self.bucket_registry_file)
                registry_data = existing_df.to_dict('records')
                # Remove existing entry for this bucket if any
                registry_data = [r for r in registry_data if r['bucket_name'] != bucket_name]
            
            # Add new entry
            registry_data.append({
                'bucket_name': bucket_name,
                'vfs_index_path': str(vfs_index_path),
                'updated_at': datetime.utcnow().isoformat()
            })
            
            # Save registry
            df = pd.DataFrame(registry_data)
            df.to_parquet(self.bucket_registry_file, index=False)
            
        except Exception as e:
            logger.warning(f"Failed to update bucket registry: {e}")


# Global instance
_global_simplified_bucket_manager = None

def get_global_simplified_bucket_manager(
    base_path: Optional[str] = None,
    enable_dataset_storage: bool = False,
    enable_compute_layer: bool = False,
    ipfs_client=None,
    dataset_batch_size: int = 100
) -> SimplifiedBucketManager:
    """Get global simplified bucket manager instance."""
    global _global_simplified_bucket_manager
    
    if _global_simplified_bucket_manager is None:
        _global_simplified_bucket_manager = SimplifiedBucketManager(
            base_path=base_path,
            enable_dataset_storage=enable_dataset_storage,
            enable_compute_layer=enable_compute_layer,
            ipfs_client=ipfs_client,
            dataset_batch_size=dataset_batch_size
        )
    
    return _global_simplified_bucket_manager
