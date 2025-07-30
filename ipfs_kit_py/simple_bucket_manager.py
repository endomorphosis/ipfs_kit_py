#!/usr/bin/env python3
"""
Simplified Bucket Manager for IPFS Kit.

This implements the correct bucket architecture:
- Buckets are just VFS indexes (parquet files)
- File additions append to VFS index with CID and metadata
- File contents go to WAL as parquet files named by CID
- No complex folder structures
"""

import asyncio
import json
import logging
import os
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


class SimpleBucketManager:
    """Simplified bucket manager following the correct architecture."""
    
    def __init__(self, data_dir: Optional[str] = None):
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
        
        logger.info(f"SimpleBucketManager initialized with data_dir: {self.data_dir}")
    
    async def create_bucket(
        self, 
        bucket_name: str, 
        bucket_type: str = 'general',
        vfs_structure: str = 'hybrid',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new bucket (just a VFS index file).
        
        Args:
            bucket_name: Name of the bucket
            bucket_type: Type of bucket (general, dataset, etc.)
            vfs_structure: VFS structure type (ignored in simple implementation)
            metadata: Optional metadata
            
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
            
            logger.info(f"Created bucket '{bucket_name}' at {vfs_index_path}")
            
            return {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'vfs_index_path': str(vfs_index_path),
                    'bucket_type': bucket_type,
                    'created_at': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error creating bucket '{bucket_name}': {e}")
            return {
                'success': False,
                'error': f"Failed to create bucket: {str(e)}"
            }
    
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
            
            return {
                'success': True,
                'data': {
                    'buckets': buckets,
                    'total_count': len(buckets)
                }
            }
            
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
            
            return {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'file_path': file_path,
                    'file_cid': file_cid,
                    'file_size': len(content),
                    'wal_stored': True
                }
            }
            
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
            
            return {
                'success': True,
                'data': {
                    'bucket_name': bucket_name,
                    'deleted_at': datetime.utcnow().isoformat()
                }
            }
            
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
