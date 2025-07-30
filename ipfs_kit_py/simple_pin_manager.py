#!/usr/bin/env python3
"""
Simplified PIN Manager for IPFS Kit.

This implements the correct PIN architecture matching the bucket system:
- PIN operations append to VFS index (parquet files)
- File additions store content in CAR WAL using CAR format
- CID calculation using ipfs_multiformats.py BEFORE metadata addition
- Simple append-only operations using CAR WAL manager
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

# Import config manager
try:
    from .config_manager import get_config_manager
    CONFIG_AVAILABLE = True
    _config_manager = get_config_manager
except ImportError:
    CONFIG_AVAILABLE = False
    _config_manager = None

# Import CAR WAL manager
try:
    from .car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    logger.warning("get_car_wal_manager not available - falling back to Parquet WAL")
    CAR_WAL_AVAILABLE = False


class SimplePinManager:
    """Simplified PIN manager following the correct architecture with CAR WAL."""
    
    def __init__(self, data_dir: Optional[str] = None):
        """Initialize simple PIN manager."""
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
        
        # Simple directory structure - match bucket architecture
        self.pin_metadata_dir = self.data_dir / 'pin_metadata'
        
        # Use CAR WAL manager for PIN operations (same directory as buckets)
        if CAR_WAL_AVAILABLE:
            self.car_wal_manager = get_car_wal_manager()
            self.use_car_wal = True
            logger.info("Using CAR WAL manager for PIN operations")
        else:
            # Fallback to old system
            self.wal_dir = self.data_dir / 'wal' / 'pins' / 'pending'
            self.wal_dir.mkdir(parents=True, exist_ok=True)
            self.use_car_wal = False
            logger.warning("CAR WAL not available - using fallback Parquet WAL")
        
        # Ensure directories exist
        self.pin_metadata_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"SimplePinManager initialized with data_dir: {self.data_dir}")
        logger.info(f"Using CAR WAL: {self.use_car_wal}")
    
    async def add_pin_operation(
        self, 
        cid_or_file: str,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        source_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a PIN operation.
        
        Args:
            cid_or_file: CID string or file path to pin
            name: Optional name for the pin
            recursive: Whether to pin recursively
            metadata: Optional metadata
            source_file: Path to source file (for file-based pins)
            
        Returns:
            Result dictionary
        """
        try:
            # Determine if it's a file or CID
            is_file = os.path.exists(cid_or_file) or source_file
            
            if is_file:
                # File-based pin - calculate CID from content
                file_path = source_file or cid_or_file
                
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                # Calculate CID using ipfs_multiformats BEFORE metadata
                if CID_AVAILABLE and _multiformats:
                    try:
                        file_cid = _multiformats.get_cid(content)
                        logger.info(f"Calculated CID for {file_path}: {file_cid}")
                    except Exception as e:
                        logger.warning(f"Failed to calculate CID: {e}")
                        file_cid = f"no-cid-{hash(content) % 1000000}"
                else:
                    file_cid = f"no-cid-{hash(content) % 1000000}"
                
                # Store content in CAR WAL
                await self._store_content_to_wal(
                    file_cid, content, file_path, name, recursive, metadata
                )
                
                # Append to PIN index
                await self._append_to_pin_index(
                    file_cid, name or Path(file_path).name, recursive, 
                    len(content), metadata, source_file=file_path
                )
                
                return {
                    'success': True,
                    'data': {
                        'cid': file_cid,
                        'name': name or Path(file_path).name,
                        'source_file': file_path,
                        'file_size': len(content),
                        'recursive': recursive,
                        'wal_stored': True
                    }
                }
                
            else:
                # Direct CID pin
                cid = cid_or_file
                
                # Store CID pin operation in CAR WAL
                await self._store_cid_pin_to_wal(cid, name, recursive, metadata)
                
                # Append to PIN index  
                await self._append_to_pin_index(
                    cid, name or cid, recursive, 0, metadata, source_file=None
                )
                
                return {
                    'success': True,
                    'data': {
                        'cid': cid,
                        'name': name or cid,
                        'source_file': None,
                        'file_size': 0,
                        'recursive': recursive,
                        'wal_stored': True
                    }
                }
                
        except Exception as e:
            logger.error(f"Error adding PIN operation: {e}")
            return {
                'success': False,
                'error': f"Failed to add PIN operation: {str(e)}"
            }
    
    async def _store_content_to_wal(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        name: Optional[str],
        recursive: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store file content to CAR WAL."""
        try:
            if self.use_car_wal:
                # Use CAR WAL manager
                operation_metadata = {
                    'operation_type': 'pin_add',
                    'target_cid': file_cid,
                    'pin_name': name,
                    'source_file': file_path,
                    'recursive': recursive,
                    'content_size': len(content),
                    'created_at_iso': datetime.utcnow().isoformat(),
                    'status': 'pending',
                    'metadata': metadata or {}
                }
                
                # Store to CAR WAL
                result = await self.car_wal_manager.store_content_to_wal(
                    file_cid=file_cid,
                    content=content,
                    file_path=file_path,
                    metadata=operation_metadata
                )
                
                if not result.get('success'):
                    raise Exception(f"CAR WAL storage failed: {result.get('error')}")
                
                logger.info(f"Stored file content to CAR WAL: {file_cid}")
                
            else:
                # Fallback to old Parquet system
                await self._store_content_to_wal_parquet(
                    file_cid, content, file_path, name, recursive, metadata
                )
            
        except Exception as e:
            logger.error(f"Error storing content to WAL: {e}")
            raise
    
    async def _store_cid_pin_to_wal(
        self, 
        cid: str,
        name: Optional[str],
        recursive: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store CID pin operation to CAR WAL."""
        try:
            if self.use_car_wal:
                # Use CAR WAL manager for CID-only pins
                operation_metadata = {
                    'operation_type': 'pin_add_cid',
                    'target_cid': cid,
                    'pin_name': name,
                    'source_file': None,
                    'recursive': recursive,
                    'content_size': 0,
                    'created_at_iso': datetime.utcnow().isoformat(),
                    'status': 'pending',
                    'metadata': metadata or {}
                }
                
                # For CID-only pins, store empty content with rich metadata
                empty_content = b''
                result = await self.car_wal_manager.store_content_to_wal(
                    file_cid=cid,
                    content=empty_content,
                    file_path='',  # Empty file path for CID-only pins
                    metadata=operation_metadata
                )
                
                if not result.get('success'):
                    raise Exception(f"CAR WAL storage failed: {result.get('error')}")
                
                logger.info(f"Stored CID pin operation to CAR WAL: {cid}")
                
            else:
                # Fallback to old Parquet system
                await self._store_cid_pin_to_wal_parquet(cid, name, recursive, metadata)
            
        except Exception as e:
            logger.error(f"Error storing CID pin to WAL: {e}")
            raise
    
    async def _append_to_pin_index(
        self,
        cid: str,
        name: str,
        recursive: bool,
        file_size: int,
        metadata: Optional[Dict[str, Any]] = None,
        source_file: Optional[str] = None
    ):
        """Append new PIN entry to PIN index."""
        try:
            # Pin index file
            pin_index_path = self.pin_metadata_dir / 'pins.parquet'
            
            # Create new entry
            new_entry = {
                'cid': cid,
                'name': name,
                'recursive': recursive,
                'file_size': file_size,
                'source_file': source_file,
                'created_at': datetime.utcnow().isoformat(),
                'status': 'pending',
                'metadata': json.dumps(metadata or {})
            }
            
            if pin_index_path.exists():
                # Read existing PIN index
                df_existing = pd.read_parquet(pin_index_path)
                
                # Append new entry
                df_new = pd.DataFrame([new_entry])
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                # Create new PIN index
                df_combined = pd.DataFrame([new_entry])
            
            # Save updated PIN index
            df_combined.to_parquet(pin_index_path, index=False)
            
            logger.info(f"Appended PIN entry to index: {name} -> {cid}")
            
        except Exception as e:
            logger.error(f"Error appending to PIN index: {e}")
            raise
    
    async def list_pins(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """List all pins from PIN index."""
        try:
            pin_index_path = self.pin_metadata_dir / 'pins.parquet'
            
            if not pin_index_path.exists():
                return {
                    'success': True,
                    'data': {
                        'pins': [],
                        'total_pins': 0
                    }
                }
            
            # Read PIN index
            df = pd.read_parquet(pin_index_path)
            
            if limit:
                df = df.head(limit)
            
            pins = []
            for _, row in df.iterrows():
                pin_info = {
                    'cid': row['cid'],
                    'name': row['name'],
                    'recursive': row['recursive'],
                    'file_size': row['file_size'],
                    'source_file': row.get('source_file'),
                    'created_at': row['created_at'],
                    'status': row.get('status', 'unknown'),
                    'metadata': json.loads(row.get('metadata', '{}'))
                }
                pins.append(pin_info)
            
            return {
                'success': True,
                'data': {
                    'pins': pins,
                    'total_pins': len(pins)
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing pins: {e}")
            return {
                'success': False,
                'error': f"Failed to list pins: {str(e)}"
            }
    
    async def get_pending_operations(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get pending PIN operations from CAR WAL."""
        try:
            if self.use_car_wal:
                # Use CAR WAL manager to list entries (not async)
                result = self.car_wal_manager.list_wal_entries()
                
                if not result.get('success'):
                    return {
                        'success': False,
                        'error': f"Failed to list CAR WAL entries: {result.get('error')}"
                    }
                
                operations = []
                entries = result.get('data', {}).get('entries', [])
                
                for entry in entries:
                    metadata = entry.get('metadata', {})
                    
                    # Only include PIN operations
                    if metadata.get('operation_type', '').startswith('pin_'):
                        operation_info = {
                            'operation_id': f"pin-{entry.get('content_id')}",
                            'operation_type': metadata.get('operation_type'),
                            'target_cid': metadata.get('target_cid'),
                            'pin_name': metadata.get('pin_name'),
                            'source_file': metadata.get('source_file'),
                            'recursive': metadata.get('recursive'),
                            'content_size': metadata.get('content_size'),
                            'created_at': metadata.get('created_at_iso'),
                            'status': metadata.get('status'),
                            'wal_file': entry.get('file_path')
                        }
                        operations.append(operation_info)
                
                # Sort by creation time (newest first)
                operations.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                
                if limit:
                    operations = operations[:limit]
                
                return {
                    'success': True,
                    'data': {
                        'operations': operations,
                        'total_operations': len(operations)
                    }
                }
                
            else:
                # Fallback to old Parquet system
                return await self._get_pending_operations_parquet(limit)
            
        except Exception as e:
            logger.error(f"Error getting pending operations: {e}")
            return {
                'success': False,
                'error': f"Failed to get pending operations: {str(e)}"
            }
    
    async def remove_pin(self, cid: str) -> Dict[str, Any]:
        """Remove a PIN from the index."""
        try:
            pin_index_path = self.pin_metadata_dir / 'pins.parquet'
            
            if not pin_index_path.exists():
                return {
                    'success': False,
                    'error': f"PIN index does not exist"
                }
            
            # Read PIN index
            df = pd.read_parquet(pin_index_path)
            
            # Check if PIN exists
            pin_exists = df['cid'].eq(cid).any()
            if not pin_exists:
                return {
                    'success': False,
                    'error': f"PIN with CID '{cid}' not found"
                }
            
            # Remove PIN from index
            df_filtered = df[df['cid'] != cid]
            
            # Save updated index
            df_filtered.to_parquet(pin_index_path, index=False)
            
            logger.info(f"Removed PIN from index: {cid}")
            
            return {
                'success': True,
                'data': {
                    'cid': cid,
                    'removed_at': datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error removing PIN: {e}")
            return {
                'success': False,
                'error': f"Failed to remove PIN: {str(e)}"
            }
    
    # Fallback methods for Parquet WAL system
    async def _store_content_to_wal_parquet(
        self, 
        file_cid: str, 
        content: bytes, 
        file_path: str,
        name: Optional[str],
        recursive: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store file content to WAL as parquet file named by CID (fallback)."""
        try:
            # WAL entry as parquet file named by CID
            wal_file_path = self.wal_dir / f"{file_cid}.parquet"
            
            # Create WAL entry data
            wal_data = {
                'operation_id': [f"pin-add-{file_cid}"],
                'operation_type': ['pin_add'],
                'target_cid': [file_cid],
                'pin_name': [name],
                'source_file': [file_path],
                'recursive': [recursive],
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
            
            logger.info(f"Stored file content to Parquet WAL: {wal_file_path}")
            
        except Exception as e:
            logger.error(f"Error storing content to Parquet WAL: {e}")
            raise
    
    async def _store_cid_pin_to_wal_parquet(
        self, 
        cid: str,
        name: Optional[str],
        recursive: bool,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store CID pin operation to WAL as parquet file named by CID (fallback)."""
        try:
            # WAL entry as parquet file named by CID
            wal_file_path = self.wal_dir / f"{cid}.parquet"
            
            # Create WAL entry data for CID pin
            wal_data = {
                'operation_id': [f"pin-add-{cid}"],
                'operation_type': ['pin_add_cid'],
                'target_cid': [cid],
                'pin_name': [name],
                'source_file': [None],  # No source file for direct CID pins
                'recursive': [recursive],
                'content_size': [0],  # Unknown size for CID pins
                'created_at_iso': [datetime.utcnow().isoformat()],
                'status': ['pending'],
                'content_hash': [None],  # No content hash for CID pins
                'metadata': [json.dumps(metadata or {})]
            }
            
            # Store as parquet
            df = pd.DataFrame(wal_data)
            df.to_parquet(wal_file_path, index=False)
            
            logger.info(f"Stored CID pin operation to Parquet WAL: {wal_file_path}")
            
        except Exception as e:
            logger.error(f"Error storing CID pin to Parquet WAL: {e}")
            raise
    
    async def _get_pending_operations_parquet(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get pending PIN operations from Parquet WAL (fallback)."""
        try:
            operations = []
            
            # List all parquet files in WAL directory
            for wal_file in self.wal_dir.glob('*.parquet'):
                try:
                    df = pd.read_parquet(wal_file)
                    if len(df) > 0:
                        row = df.iloc[0]
                        operation_info = {
                            'operation_id': row.get('operation_id'),
                            'operation_type': row.get('operation_type'),
                            'target_cid': row.get('target_cid'),
                            'pin_name': row.get('pin_name'),
                            'source_file': row.get('source_file'),
                            'recursive': bool(row.get('recursive', False)),
                            'content_size': int(row.get('content_size', 0)),
                            'created_at': row.get('created_at_iso'),
                            'status': row.get('status'),
                            'wal_file': str(wal_file)
                        }
                        operations.append(operation_info)
                        
                except Exception as e:
                    logger.warning(f"Error reading WAL file {wal_file}: {e}")
                    continue
            
            # Sort by creation time (newest first)
            operations.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            if limit:
                operations = operations[:limit]
            
            return {
                'success': True,
                'data': {
                    'operations': operations,
                    'total_operations': len(operations)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting pending operations from Parquet WAL: {e}")
            return {
                'success': False,
                'error': f"Failed to get pending operations: {str(e)}"
            }


# Global instance
_global_simple_pin_manager = None

def get_simple_pin_manager(data_dir: Optional[str] = None) -> SimplePinManager:
    """Get global simple PIN manager instance."""
    global _global_simple_pin_manager
    
    if _global_simple_pin_manager is None:
        _global_simple_pin_manager = SimplePinManager(data_dir)
    
    return _global_simple_pin_manager
