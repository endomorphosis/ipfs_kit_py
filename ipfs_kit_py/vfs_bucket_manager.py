#!/usr/bin/env python3
"""
VFS-Based Bucket Manager

This module implements the new bucket architecture where:
- Each bucket is a VFS index directory
- Central bucket registry tracks all buckets
- Bucket configurations stored in YAML files
- No redundant bucket directory structure
"""

import os
import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class VFSBucketManager:
    """Manages buckets using VFS indices directly."""
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the VFS bucket manager.
        
        Args:
            base_path: Base path for IPFS Kit data (defaults to ~/.ipfs_kit)
        """
        self.base_path = base_path or Path.home() / '.ipfs_kit'
        self.vfs_indices_path = self.base_path / 'vfs_indices'
        self.bucket_configs_path = self.base_path / 'bucket_configs'
        self.registry_path = self.base_path / 'bucket_registry.yaml'
        
        # Ensure directories exist
        self.vfs_indices_path.mkdir(parents=True, exist_ok=True)
        self.bucket_configs_path.mkdir(parents=True, exist_ok=True)
        
    def load_registry(self) -> Dict[str, Any]:
        """Load the bucket registry from YAML file.
        
        Returns:
            Dictionary containing bucket registry data
        """
        if not self.registry_path.exists():
            return {
                'buckets': {},
                'statistics': {
                    'total_buckets': 0,
                    'total_files': 0,
                    'total_size': '0B',
                    'last_updated': datetime.now().isoformat()
                }
            }
        
        try:
            with open(self.registry_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading bucket registry: {e}")
            return {'buckets': {}, 'statistics': {}}
    
    def save_registry(self, registry: Dict[str, Any]) -> bool:
        """Save the bucket registry to YAML file.
        
        Args:
            registry: Registry data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update statistics
            registry['statistics']['last_updated'] = datetime.now().isoformat()
            
            with open(self.registry_path, 'w') as f:
                yaml.dump(registry, f, default_flow_style=False, sort_keys=True)
            return True
        except Exception as e:
            logger.error(f"Error saving bucket registry: {e}")
            return False
    
    def create_bucket(self, bucket_name: str, bucket_type: str = 'general', 
                     backend_bindings: Optional[List[str]] = None,
                     **kwargs) -> bool:
        """Create a new bucket using VFS index.
        
        Args:
            bucket_name: Name of the bucket to create
            bucket_type: Type of bucket (general, dataset, media, etc.)
            backend_bindings: List of backend storage bindings
            **kwargs: Additional bucket metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create VFS index directory
            vfs_path = self.vfs_indices_path / bucket_name
            vfs_path.mkdir(parents=True, exist_ok=True)
            
            # Create initial VFS index files
            self._create_vfs_index_files(vfs_path)
            
            # Create bucket configuration
            config = {
                'bucket_name': bucket_name,
                'type': bucket_type,
                'created_at': datetime.now().isoformat(),
                'backup': {
                    'enabled': True,
                    'frequency': 'daily',
                    'retention_days': 365,
                    'destinations': backend_bindings or []
                },
                'replication': {
                    'min_replicas': 2,
                    'max_replicas': 5,
                    'geographic_distribution': True
                },
                'cache': {
                    'enabled': True,
                    'policy': 'lru',
                    'size_mb': 512,
                    'ttl_seconds': 3600
                },
                'access': {
                    'public_read': False,
                    'api_access': True,
                    'web_interface': True
                }
            }
            
            # Add any additional config from kwargs
            config.update(kwargs)
            
            # Save bucket configuration
            config_path = self.bucket_configs_path / f"{bucket_name}.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Update bucket registry
            registry = self.load_registry()
            registry['buckets'][bucket_name] = {
                'type': bucket_type,
                'vfs_index': bucket_name,
                'created_at': datetime.now().isoformat(),
                'backend_bindings': backend_bindings or [],
                'total_files': 0,
                'total_size': '0B',
                'last_sync': datetime.now().isoformat()
            }
            
            # Update statistics
            registry['statistics']['total_buckets'] = len(registry['buckets'])
            
            self.save_registry(registry)
            
            logger.info(f"Created bucket: {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating bucket {bucket_name}: {e}")
            return False
    
    def _create_vfs_index_files(self, vfs_path: Path):
        """Create initial VFS index files for a new bucket.
        
        Args:
            vfs_path: Path to VFS index directory
        """
        # Create index.parquet (core file mappings)
        index_df = pd.DataFrame(columns=[
            'file_path', 'ipfs_cid', 'file_size', 'modified_time', 
            'content_type', 'checksum_sha256'
        ])
        index_df.to_parquet(vfs_path / 'index.parquet', index=False)
        
        # Create metadata.parquet (extended metadata)
        metadata_df = pd.DataFrame(columns=[
            'file_path', 'tags', 'description', 'custom_metadata', 'search_keywords'
        ])
        metadata_df.to_parquet(vfs_path / 'metadata.parquet', index=False)
    
    def list_buckets(self, bucket_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all buckets or filter by type.
        
        Args:
            bucket_type: Optional bucket type filter
            
        Returns:
            List of bucket information dictionaries
        """
        registry = self.load_registry()
        buckets = []
        
        for bucket_name, bucket_data in registry.get('buckets', {}).items():
            if bucket_type is None or bucket_data.get('type') == bucket_type:
                # Add configuration data
                config = self.get_bucket_config(bucket_name)
                bucket_info = {
                    'name': bucket_name,
                    **bucket_data,
                    'config': config
                }
                buckets.append(bucket_info)
        
        return buckets
    
    def get_bucket_config(self, bucket_name: str) -> Dict[str, Any]:
        """Get bucket configuration from YAML file.
        
        Args:
            bucket_name: Name of the bucket
            
        Returns:
            Bucket configuration dictionary
        """
        config_path = self.bucket_configs_path / f"{bucket_name}.yaml"
        if not config_path.exists():
            return {}
        
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Error loading config for bucket {bucket_name}: {e}")
            return {}
    
    def update_bucket_config(self, bucket_name: str, config_updates: Dict[str, Any]) -> bool:
        """Update bucket configuration.
        
        Args:
            bucket_name: Name of the bucket
            config_updates: Configuration updates to apply
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config = self.get_bucket_config(bucket_name)
            
            # Deep merge config updates
            self._deep_merge(config, config_updates)
            
            # Save updated configuration
            config_path = self.bucket_configs_path / f"{bucket_name}.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False)
            
            logger.info(f"Updated config for bucket: {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating config for bucket {bucket_name}: {e}")
            return False
    
    def _deep_merge(self, target: Dict, source: Dict):
        """Deep merge two dictionaries.
        
        Args:
            target: Target dictionary to merge into
            source: Source dictionary to merge from
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value
    
    def add_file_to_bucket(self, bucket_name: str, file_path: str, ipfs_cid: str,
                          file_size: int = 0, content_type: str = '',
                          metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Add a file to a bucket's VFS index.
        
        Args:
            bucket_name: Name of the bucket
            file_path: Virtual file path within bucket
            ipfs_cid: IPFS Content ID
            file_size: File size in bytes
            content_type: MIME type
            metadata: Additional metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            vfs_path = self.vfs_indices_path / bucket_name
            if not vfs_path.exists():
                logger.error(f"Bucket {bucket_name} does not exist")
                return False
            
            # Read existing index
            index_path = vfs_path / 'index.parquet'
            if index_path.exists():
                index_df = pd.read_parquet(index_path)
            else:
                index_df = pd.DataFrame(columns=[
                    'file_path', 'ipfs_cid', 'file_size', 'modified_time', 
                    'content_type', 'checksum_sha256'
                ])
            
            # Add new file entry
            new_entry = pd.DataFrame([{
                'file_path': file_path,
                'ipfs_cid': ipfs_cid,
                'file_size': file_size,
                'modified_time': datetime.now(),
                'content_type': content_type,
                'checksum_sha256': ''  # Will be calculated later
            }])
            
            # Remove existing entry if it exists (update)
            index_df = index_df[index_df['file_path'] != file_path]
            index_df = pd.concat([index_df, new_entry], ignore_index=True)
            
            # Save updated index
            index_df.to_parquet(index_path, index=False)
            
            # Add metadata if provided
            if metadata:
                self._add_file_metadata(vfs_path, file_path, metadata)
            
            # Update bucket statistics
            self._update_bucket_statistics(bucket_name)
            
            logger.info(f"Added file {file_path} to bucket {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding file to bucket {bucket_name}: {e}")
            return False
    
    def _add_file_metadata(self, vfs_path: Path, file_path: str, metadata: Dict[str, Any]):
        """Add metadata for a file in the bucket.
        
        Args:
            vfs_path: Path to VFS index directory
            file_path: Virtual file path
            metadata: Metadata to add
        """
        metadata_path = vfs_path / 'metadata.parquet'
        
        if metadata_path.exists():
            metadata_df = pd.read_parquet(metadata_path)
        else:
            metadata_df = pd.DataFrame(columns=[
                'file_path', 'tags', 'description', 'custom_metadata', 'search_keywords'
            ])
        
        # Create metadata entry
        new_metadata = pd.DataFrame([{
            'file_path': file_path,
            'tags': metadata.get('tags', []),
            'description': metadata.get('description', ''),
            'custom_metadata': json.dumps(metadata.get('custom', {})),
            'search_keywords': metadata.get('keywords', '')
        }])
        
        # Remove existing metadata if it exists
        metadata_df = metadata_df[metadata_df['file_path'] != file_path]
        metadata_df = pd.concat([metadata_df, new_metadata], ignore_index=True)
        
        # Save updated metadata
        metadata_df.to_parquet(metadata_path, index=False)
    
    def _update_bucket_statistics(self, bucket_name: str):
        """Update bucket statistics in the registry.
        
        Args:
            bucket_name: Name of the bucket
        """
        try:
            vfs_path = self.vfs_indices_path / bucket_name
            index_path = vfs_path / 'index.parquet'
            
            if not index_path.exists():
                return
            
            # Read index to calculate statistics
            index_df = pd.read_parquet(index_path)
            total_files = len(index_df)
            total_size = index_df['file_size'].sum()
            
            # Update registry
            registry = self.load_registry()
            if bucket_name in registry['buckets']:
                registry['buckets'][bucket_name]['total_files'] = total_files
                registry['buckets'][bucket_name]['total_size'] = self._format_size(total_size)
                registry['buckets'][bucket_name]['last_sync'] = datetime.now().isoformat()
            
            # Update global statistics
            total_bucket_files = sum(bucket.get('total_files', 0) for bucket in registry['buckets'].values())
            registry['statistics']['total_files'] = total_bucket_files
            
            self.save_registry(registry)
            
        except Exception as e:
            logger.error(f"Error updating statistics for bucket {bucket_name}: {e}")
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        size = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f}{unit}"
            size /= 1024.0
        return f"{size:.1f}PB"
    
    def list_bucket_files(self, bucket_name: str, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """List files in a bucket.
        
        Args:
            bucket_name: Name of the bucket
            include_metadata: Whether to include extended metadata
            
        Returns:
            List of file information dictionaries
        """
        try:
            vfs_path = self.vfs_indices_path / bucket_name
            index_path = vfs_path / 'index.parquet'
            
            if not index_path.exists():
                return []
            
            # Read index
            index_df = pd.read_parquet(index_path)
            files = [dict(row) for _, row in index_df.iterrows()]
            
            # Add metadata if requested
            if include_metadata:
                metadata_path = vfs_path / 'metadata.parquet'
                if metadata_path.exists():
                    metadata_df = pd.read_parquet(metadata_path)
                    metadata_dict = metadata_df.set_index('file_path').to_dict('index')
                    
                    for file_info in files:
                        file_path = file_info['file_path']
                        if file_path in metadata_dict:
                            file_info['metadata'] = metadata_dict[file_path]
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing files for bucket {bucket_name}: {e}")
            return []
    
    def delete_bucket(self, bucket_name: str, force: bool = False) -> bool:
        """Delete a bucket and all its data.
        
        Args:
            bucket_name: Name of the bucket to delete
            force: Force deletion without confirmation
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not force:
                response = input(f"⚠️  Delete bucket '{bucket_name}' and all its data? [y/N]: ")
                if response.lower() != 'y':
                    print("❌ Deletion cancelled")
                    return False
            
            # Remove VFS index directory
            vfs_path = self.vfs_indices_path / bucket_name
            if vfs_path.exists():
                import shutil
                shutil.rmtree(vfs_path)
            
            # Remove configuration file
            config_path = self.bucket_configs_path / f"{bucket_name}.yaml"
            if config_path.exists():
                config_path.unlink()
            
            # Update registry
            registry = self.load_registry()
            if bucket_name in registry['buckets']:
                del registry['buckets'][bucket_name]
                registry['statistics']['total_buckets'] = len(registry['buckets'])
                self.save_registry(registry)
            
            logger.info(f"Deleted bucket: {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting bucket {bucket_name}: {e}")
            return False
    
    def get_bucket_info(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive information about a bucket.
        
        Args:
            bucket_name: Name of the bucket
            
        Returns:
            Bucket information dictionary or None if not found
        """
        registry = self.load_registry()
        if bucket_name not in registry['buckets']:
            return None
        
        bucket_data = registry['buckets'][bucket_name]
        config = self.get_bucket_config(bucket_name)
        files = self.list_bucket_files(bucket_name, include_metadata=True)
        
        return {
            'name': bucket_name,
            'registry_data': bucket_data,
            'configuration': config,
            'files': files,
            'file_count': len(files),
            'vfs_path': str(self.vfs_indices_path / bucket_name)
        }
    
    def migrate_legacy_bucket(self, legacy_bucket_path: Path) -> bool:
        """Migrate a legacy bucket to the new VFS-based structure.
        
        Args:
            legacy_bucket_path: Path to legacy bucket directory
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bucket_name = legacy_bucket_path.name
            
            # Read legacy bucket registry if it exists
            legacy_registry_path = legacy_bucket_path / 'bucket_registry.json'
            if legacy_registry_path.exists():
                with open(legacy_registry_path, 'r') as f:
                    legacy_data = json.load(f)
                    
                bucket_type = legacy_data.get(bucket_name, {}).get('type', 'general')
            else:
                bucket_type = 'general'
            
            # Create new bucket
            if not self.create_bucket(bucket_name, bucket_type):
                return False
            
            # Migrate files if they exist
            # This would need to be implemented based on the legacy structure
            
            logger.info(f"Migrated legacy bucket: {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error migrating legacy bucket: {e}")
            return False
