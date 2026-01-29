#!/usr/bin/env python3
"""
Simplified Bucket Manager for IPFS Kit.

This implements the correct bucket architecture:
- Buckets are just VFS indexes (parquet files)
- File additions append to VFS index with CID and metadata
- File contents go to WAL as parquet files named by CID
- No complex folder structures
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

import pandas as pd

logger = logging.getLogger(__name__)

# Import CID calculation
try:
    from .ipfs_multiformats import ipfs_multiformats_py
    _multiformats = ipfs_multiformats_py()
    CID_AVAILABLE = True
except ImportError:
    logger.warning("ipfs_multiformats not available - CID calculation disabled")
    _multiformats = None
    CID_AVAILABLE = False

# Import CAR WAL Manager
try:
    from .car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    logger.warning("CAR WAL Manager not available - falling back to Parquet WAL")
    CAR_WAL_AVAILABLE = False

# Import config manager
try:
    from .config_manager import get_config_manager
    CONFIG_AVAILABLE = True
    _config_manager = get_config_manager
except ImportError:
    CONFIG_AVAILABLE = False
    _config_manager = None

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
    accelerate_path = PathlibPath(__file__).parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
    logger.info("ipfs_accelerate_py compute layer available")
except ImportError:
    HAS_ACCELERATE = False
    AccelerateCompute = None
    logger.info("ipfs_accelerate_py not available - using default compute")


class SimpleBucketManager:
    """Simplified bucket manager following the correct architecture."""
    
    def __init__(
        self, 
        data_dir: Optional[str] = None,
        enable_dataset_storage: bool = False,
        enable_compute_layer: bool = False,
        ipfs_client=None,
        dataset_batch_size: int = 100
    ):
        """Initialize simple bucket manager."""
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            # Try to get from config manager if available
            if CONFIG_AVAILABLE and _config_manager:
                try:
                    config_manager = _config_manager()
                    self.data_dir = Path(config_manager.get_config_value('data_dir', '~/.ipfs_kit')).expanduser()
                except Exception:
                    self.data_dir = Path('~/.ipfs_kit').expanduser()
            else:
                self.data_dir = Path('~/.ipfs_kit').expanduser()
        
        # Simple directory structure
        self.buckets_dir = self.data_dir / 'buckets'
        
        # WAL directory - use CAR format structure
        if CAR_WAL_AVAILABLE:
            self.wal_dir = self.data_dir / 'wal' / 'car'
        else:
            # Fallback to old structure for compatibility
            self.wal_dir = self.data_dir / 'wal' / 'pins' / 'pending'
        
        # Ensure directories exist
        self.buckets_dir.mkdir(parents=True, exist_ok=True)
        self.wal_dir.mkdir(parents=True, exist_ok=True)
        
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
                logger.info("Simple Bucket Manager dataset storage enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
                self.enable_dataset_storage = False
        
        # Initialize compute layer if enabled
        if self.enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Simple Bucket Manager compute layer enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
                self.enable_compute_layer = False
        
        logger.info(f"SimpleBucketManager initialized with data_dir: {self.data_dir}")
    
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
                temp_file = self.data_dir / f"operations_{int(time.time())}.json"
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
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a new bucket (just a VFS index file) with comprehensive YAML configuration.
        
        Args:
            bucket_name: Name of the bucket
            bucket_type: Type of bucket (general, dataset, etc.)
            vfs_structure: VFS structure type (ignored in simple implementation)
            metadata: Optional metadata
            **kwargs: Additional configuration parameters for comprehensive bucket setup
            
        Returns:
            Result dictionary
        """
        try:
            vfs_index_path = self.buckets_dir / f"{bucket_name}.parquet"
            
            if vfs_index_path.exists():
                return {
                    'success': False,
                    'error': f"Bucket '{bucket_name}' already exists"
                }
            
            # Create empty VFS index
            vfs_data = {
                'bucket_name': [bucket_name],
                'file_path': [''],  # Empty initial entry
                'file_cid': [''],
                'file_size': [0],
                'created_at': [datetime.utcnow().isoformat()],
                'bucket_type': [bucket_type],
                'vfs_structure': [vfs_structure],
                'metadata': [json.dumps(metadata or {})]
            }
            
            df = pd.DataFrame(vfs_data)
            df.to_parquet(vfs_index_path, index=False)
            
            # Generate comprehensive YAML configuration file
            yaml_config_path = await self._generate_bucket_yaml_config(
                bucket_name, bucket_type, vfs_structure, metadata, **kwargs
            )
            
            logger.info(f"Created bucket '{bucket_name}' at {vfs_index_path}")
            logger.info(f"Generated YAML config at {yaml_config_path}")
            
            result = {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'vfs_index_path': str(vfs_index_path),
                    'yaml_config_path': str(yaml_config_path),
                    'bucket_type': bucket_type,
                    'created_at': datetime.utcnow().isoformat()
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
    
    async def _generate_bucket_yaml_config(
        self,
        bucket_name: str,
        bucket_type: str,
        vfs_structure: str,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Path:
        """
        Generate comprehensive YAML configuration file for bucket.
        
        This includes all fields necessary for daemon and replication management.
        """
        # Create bucket configs directory
        bucket_configs_dir = self.data_dir / 'bucket_configs'
        bucket_configs_dir.mkdir(parents=True, exist_ok=True)
        
        # Comprehensive bucket configuration with all required fields
        config = {
            # Basic bucket metadata
            'bucket_name': bucket_name,
            'type': bucket_type,
            'description': kwargs.get('description', f'{bucket_type.title()} bucket for {bucket_name}'),
            'created_at': datetime.utcnow().isoformat(),
            'version': '2.0',
            'schema_version': '1.0',
            
            # VFS Structure
            'vfs': {
                'structure': vfs_structure,
                'index_path': str(self.buckets_dir / f"{bucket_name}.parquet"),
                'encoding': 'parquet',
                'compression': 'snappy'
            },
            
            # Daemon Management Fields
            'daemon': {
                'managed': True,
                'auto_start': kwargs.get('daemon_auto_start', True),
                'health_check_interval': kwargs.get('health_check_interval', 30),
                'restart_policy': kwargs.get('restart_policy', 'always'),
                'log_level': kwargs.get('log_level', 'INFO'),
                'monitoring_enabled': kwargs.get('monitoring_enabled', True)
            },
            
            # Backend Bindings and Storage
            'backend_bindings': kwargs.get('backend_bindings', []),
            'storage': {
                'wal_enabled': True,
                'wal_format': 'car',
                'compression_enabled': kwargs.get('compression_enabled', True),
                'deduplication_enabled': kwargs.get('deduplication_enabled', True),
                'encryption_enabled': kwargs.get('encryption_enabled', False)
            },
            
            # Comprehensive Replication Configuration
            'replication': {
                'enabled': kwargs.get('replication_enabled', True),
                'min_replicas': max(2, kwargs.get('replication_min', 2)),
                'target_replicas': kwargs.get('replication_target', 3),
                'max_replicas': kwargs.get('replication_max', 5),
                'policy': kwargs.get('replication_policy', 'balanced'),
                'geographic_distribution': kwargs.get('geographic_distribution', True),
                'priority': kwargs.get('replication_priority', 'normal'),
                'auto_replication': kwargs.get('auto_replication', True),
                'emergency_backup_enabled': kwargs.get('emergency_backup_enabled', True),
                'consistency_model': kwargs.get('consistency_model', 'eventual'),
                'conflict_resolution': kwargs.get('conflict_resolution', 'timestamp'),
                'preferred_regions': kwargs.get('preferred_regions', []),
                'avoid_regions': kwargs.get('avoid_regions', [])
            },
            
            # Backup and Disaster Recovery
            'backup': {
                'enabled': kwargs.get('backup_enabled', True),
                'frequency': kwargs.get('backup_frequency', 'daily'),
                'retention_days': kwargs.get('retention_days', 365),
                'destinations': kwargs.get('backend_bindings', []),
                'incremental_enabled': kwargs.get('incremental_backup', True),
                'compression_enabled': kwargs.get('backup_compression', True),
                'encryption_enabled': kwargs.get('backup_encryption', False),
                'verification_enabled': kwargs.get('backup_verification', True)
            },
            
            # Disaster Recovery
            'disaster_recovery': {
                'tier': kwargs.get('dr_tier', 'standard'),
                'rpo_minutes': kwargs.get('rpo_minutes', 60),  # Recovery Point Objective
                'rto_minutes': kwargs.get('rto_minutes', 30),  # Recovery Time Objective
                'zones': kwargs.get('dr_zones', []),
                'backup_frequency': kwargs.get('dr_backup_frequency', 'daily'),
                'cross_region_backup': kwargs.get('cross_region_backup', True),
                'automated_failover': kwargs.get('automated_failover', False)
            },
            
            # Cache Configuration
            'cache': {
                'enabled': kwargs.get('cache_enabled', True),
                'policy': kwargs.get('cache_policy', 'lru'),
                'size_mb': kwargs.get('cache_size_mb', 512),
                'max_entries': kwargs.get('cache_max_entries', 10000),
                'ttl_seconds': kwargs.get('cache_ttl', 3600),
                'priority': kwargs.get('cache_priority', 'normal'),
                'write_through': kwargs.get('cache_write_through', False),
                'compression_enabled': kwargs.get('cache_compression', True)
            },
            
            # Performance and Throughput
            'performance': {
                'throughput_mode': kwargs.get('throughput_mode', 'balanced'),
                'concurrent_ops': kwargs.get('concurrent_ops', 5),
                'max_connection_pool': kwargs.get('max_connections', 20),
                'timeout_seconds': kwargs.get('timeout_seconds', 30),
                'retry_attempts': kwargs.get('retry_attempts', 3),
                'batch_size': kwargs.get('batch_size', 100),
                'optimization_tier': kwargs.get('performance_tier', 'balanced')
            },
            
            # Lifecycle Management
            'lifecycle': {
                'policy': kwargs.get('lifecycle_policy', 'none'),
                'archive_after_days': kwargs.get('archive_after_days'),
                'delete_after_days': kwargs.get('delete_after_days'),
                'auto_cleanup_enabled': kwargs.get('auto_cleanup', False),
                'version_retention': kwargs.get('version_retention', 10)
            },
            
            # Access Control and Security
            'access': {
                'public_read': kwargs.get('public_read', False),
                'api_access': kwargs.get('api_access', True),
                'web_interface': kwargs.get('web_interface', True),
                'authentication_required': kwargs.get('auth_required', False),
                'encryption_at_rest': kwargs.get('encryption_at_rest', False),
                'encryption_in_transit': kwargs.get('encryption_in_transit', True)
            },
            
            # Monitoring and Observability
            'monitoring': {
                'metrics_enabled': kwargs.get('metrics_enabled', True),
                'logging_enabled': kwargs.get('logging_enabled', True),
                'tracing_enabled': kwargs.get('tracing_enabled', False),
                'alert_on_failures': kwargs.get('alert_on_failures', True),
                'health_check_enabled': kwargs.get('health_check_enabled', True),
                'performance_monitoring': kwargs.get('performance_monitoring', True),
                'retention_days': kwargs.get('monitoring_retention_days', 30)
            },
            
            # Resource Limits
            'limits': {
                'max_file_size_gb': kwargs.get('max_file_size_gb', 10),
                'max_total_size_gb': kwargs.get('max_total_size_gb', 1000),
                'max_files': kwargs.get('max_files', 100000),
                'rate_limit_rps': kwargs.get('rate_limit_rps', 100),
                'bandwidth_limit_mbps': kwargs.get('bandwidth_limit_mbps')
            },
            
            # Quality of Service
            'qos': {
                'priority_class': kwargs.get('priority_class', 'normal'),
                'guaranteed_bandwidth': kwargs.get('guaranteed_bandwidth'),
                'burst_bandwidth': kwargs.get('burst_bandwidth'),
                'latency_requirements': kwargs.get('latency_requirements', 'standard')
            },
            
            # Integration Settings
            'integrations': {
                'mcp_enabled': kwargs.get('mcp_enabled', True),
                'api_gateway_enabled': kwargs.get('api_gateway_enabled', True),
                'webhook_notifications': kwargs.get('webhook_enabled', False),
                'external_indexing': kwargs.get('external_indexing', False)
            },
            
            # Custom metadata and tags
            'metadata': metadata or {},
            'tags': kwargs.get('tags', []),
            'labels': kwargs.get('labels', {}),
            
            # Operational metadata
            'operational': {
                'last_modified': datetime.utcnow().isoformat(),
                'modified_by': kwargs.get('created_by', 'system'),
                'version_history': [],
                'maintenance_windows': kwargs.get('maintenance_windows', [])
            }
        }
        
        # Save YAML configuration
        yaml_config_path = bucket_configs_dir / f"{bucket_name}.yaml"
        
        try:
            import yaml
            with open(yaml_config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=True, indent=2)
            
            logger.info(f"Generated comprehensive YAML config for bucket {bucket_name}")
            return yaml_config_path
            
        except ImportError:
            # Fallback to JSON if YAML not available
            json_config_path = bucket_configs_dir / f"{bucket_name}.json"
            with open(json_config_path, 'w') as f:
                json.dump(config, f, indent=2, sort_keys=True)
            
            logger.warning(f"YAML not available, saved config as JSON: {json_config_path}")
            return json_config_path
    
    async def list_buckets(self) -> Dict[str, Any]:
        """List all buckets (parquet files in buckets directory)."""
        try:
            buckets = []
            
            for parquet_file in self.buckets_dir.glob('*.parquet'):
                try:
                    # Read VFS index to get bucket info
                    df = pd.read_parquet(parquet_file)
                    
                    if len(df) > 0:
                        # Get bucket metadata from first row
                        first_row = df.iloc[0]
                        bucket_info = {
                            'name': first_row.get('bucket_name', parquet_file.stem),
                            'type': first_row.get('bucket_type', 'general'),
                            'vfs_structure': first_row.get('vfs_structure', 'hybrid'),
                            'created_at': first_row.get('created_at', 'unknown'),
                            'file_count': len(df) - 1,  # Subtract empty initial entry
                            'size_bytes': df['file_size'].sum(),
                            'vfs_index': str(parquet_file)
                        }
                        buckets.append(bucket_info)
                        
                except Exception as e:
                    logger.warning(f"Error reading bucket file {parquet_file}: {e}")
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
    
    async def add_file_to_bucket(
        self,
        bucket_name: str,
        file_path: str,
        content: Union[bytes, str, None] = None,
        content_file: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a file to a bucket.
        
        Args:
            bucket_name: Name of the bucket
            file_path: Virtual path within bucket
            content: File content (bytes or string)
            content_file: Path to file to read content from
            metadata: Optional metadata
            
        Returns:
            Result dictionary
        """
        try:
            vfs_index_path = self.buckets_dir / f"{bucket_name}.parquet"
            
            if not vfs_index_path.exists():
                return {
                    'success': False,
                    'error': f"Bucket '{bucket_name}' does not exist"
                }
            
            # Get content
            if content is None and content_file:
                with open(content_file, 'rb') as f:
                    content = f.read()
            elif isinstance(content, str):
                content = content.encode('utf-8')
            
            if content is None:
                return {
                    'success': False,
                    'error': "No content provided"
                }
            
            # Calculate CID
            file_cid = None
            if CID_AVAILABLE and _multiformats:
                try:
                    file_cid = _multiformats.get_cid(content)
                    logger.info(f"Calculated CID for {file_path}: {file_cid}")
                except Exception as e:
                    logger.warning(f"Failed to calculate CID: {e}")
                    file_cid = f"no-cid-{hash(content) % 1000000}"
            else:
                file_cid = f"no-cid-{hash(content) % 1000000}"
            
            # Store content in WAL as parquet file named by CID
            await self._store_content_to_wal(file_cid, content, file_path, metadata)
            
            # Append to VFS index
            await self._append_to_vfs_index(
                vfs_index_path, 
                bucket_name, 
                file_path, 
                file_cid, 
                len(content),
                metadata
            )
            
            result = {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'file_path': file_path,
                    'file_cid': file_cid,
                    'file_size': len(content),
                    'wal_stored': True
                }
            }
            
            # Store operation to dataset
            self._store_operation_to_dataset("add_file", bucket_name, {
                "file_path": file_path,
                "file_size": len(content),
                "file_cid": file_cid
            }, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error adding file to bucket: {e}")
            return {
                'success': False,
                'error': f"Failed to add file: {str(e)}"
            }
    
    async def _store_content_to_wal(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store file content to WAL using CAR format instead of Parquet."""
        try:
            if CAR_WAL_AVAILABLE:
                # Use new CAR-based WAL manager
                car_wal_manager = get_car_wal_manager()
                result = await car_wal_manager.store_content_to_wal(
                    file_cid, content, file_path, metadata
                )
                
                if result.get("success"):
                    logger.info(f"Stored content to CAR WAL: {result.get('wal_file')}")
                else:
                    logger.error(f"CAR WAL storage failed: {result.get('error')}")
                    raise Exception(f"CAR WAL storage failed: {result.get('error')}")
            else:
                # Fallback to old Parquet WAL (for compatibility)
                await self._store_content_to_parquet_wal(file_cid, content, file_path, metadata)
                
        except Exception as e:
            logger.error(f"Error storing content to WAL: {e}")
            raise
    
    async def _store_content_to_parquet_wal(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Legacy Parquet WAL storage (fallback only)."""
        try:
            # WAL entry as parquet file named by CID
            wal_file_path = self.wal_dir / f"{file_cid}.parquet"
            
            # Create WAL entry data
            wal_data = {
                'operation_id': [f"file-add-{file_cid}"],
                'operation_type': ['file_add'],
                'file_cid': [file_cid],
                'file_path': [file_path],
                'content_size': [len(content)],
                'created_at_iso': [datetime.utcnow().isoformat()],
                'status': ['pending'],
                'content_hash': [hash(content)],  # Simple hash for verification
                'metadata': [json.dumps(metadata or {})]
            }
            
            # Store as parquet
            df = pd.DataFrame(wal_data)
            df.to_parquet(wal_file_path, index=False)
            
            # Also store the actual content in a separate file for the daemon to process
            content_file_path = self.wal_dir / f"{file_cid}.content"
            with open(content_file_path, 'wb') as f:
                f.write(content)
            
            logger.info(f"Stored content to Parquet WAL (fallback): {wal_file_path}")
            
        except Exception as e:
            logger.error(f"Error storing content to Parquet WAL: {e}")
            raise
    
    async def _append_to_vfs_index(
        self,
        vfs_index_path: Path,
        bucket_name: str,
        file_path: str,
        file_cid: str,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Append new file entry to VFS index."""
        try:
            # Read existing VFS index
            df_existing = pd.read_parquet(vfs_index_path)
            
            # Create new entry
            new_entry = {
                'bucket_name': bucket_name,
                'file_path': file_path,
                'file_cid': file_cid,
                'file_size': file_size,
                'created_at': datetime.utcnow().isoformat(),
                'bucket_type': df_existing.iloc[0]['bucket_type'] if len(df_existing) > 0 else 'general',
                'vfs_structure': df_existing.iloc[0]['vfs_structure'] if len(df_existing) > 0 else 'hybrid',
                'metadata': json.dumps(metadata or {})
            }
            
            # Append new entry
            df_new = pd.DataFrame([new_entry])
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            
            # Remove empty initial entry if it exists
            if len(df_combined) > 1 and df_combined.iloc[0]['file_path'] == '':
                df_combined = df_combined.iloc[1:].reset_index(drop=True)
            
            # Save updated VFS index
            df_combined.to_parquet(vfs_index_path, index=False)
            
            logger.info(f"Appended file entry to VFS index: {file_path} -> {file_cid}")
            
        except Exception as e:
            logger.error(f"Error appending to VFS index: {e}")
            raise
    
    async def get_bucket_files(self, bucket_name: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get files in a bucket from VFS index."""
        try:
            vfs_index_path = self.buckets_dir / f"{bucket_name}.parquet"
            
            if not vfs_index_path.exists():
                return {
                    'success': False,
                    'error': f"Bucket '{bucket_name}' does not exist"
                }
            
            # Read VFS index
            df = pd.read_parquet(vfs_index_path)
            
            # Filter out empty entries
            df = df[df['file_path'] != '']
            
            if limit:
                df = df.head(limit)
            
            files = []
            for _, row in df.iterrows():
                file_info = {
                    'file_path': row['file_path'],
                    'file_cid': row['file_cid'],
                    'file_size': row['file_size'],
                    'created_at': row['created_at'],
                    'metadata': json.loads(row.get('metadata', '{}'))
                }
                files.append(file_info)
            
            return {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'files': files,
                    'total_files': len(files)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting bucket files: {e}")
            return {
                'success': False,
                'error': f"Failed to get bucket files: {str(e)}"
            }
    
    async def delete_bucket(self, bucket_name: str, force: bool = False) -> Dict[str, Any]:
        """Delete a bucket (remove VFS index file)."""
        try:
            vfs_index_path = self.buckets_dir / f"{bucket_name}.parquet"
            
            if not vfs_index_path.exists():
                return {
                    'success': False,
                    'error': f"Bucket '{bucket_name}' does not exist"
                }
            
            # Remove VFS index file
            vfs_index_path.unlink()
            
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


# Global instance
_global_simple_bucket_manager = None

def get_simple_bucket_manager(data_dir: Optional[str] = None) -> SimpleBucketManager:
    """Get global simple bucket manager instance."""
    global _global_simple_bucket_manager
    
    if _global_simple_bucket_manager is None:
        _global_simple_bucket_manager = SimpleBucketManager(data_dir)
    
    return _global_simple_bucket_manager
