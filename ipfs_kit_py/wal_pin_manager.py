#!/usr/bin/env python3
"""
Write-Ahead Log (WAL) Manager for IPFS-Kit Pin Operations

This module manages pending pin operations that will be processed by the daemon
and replicated across virtual filesystem backends.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
from datetime import datetime


class WALPinManager:
    """Manages write-ahead log for pin operations."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or Path.home() / '.ipfs_kit'
        self.wal_path = self.base_path / 'wal' / 'pins'
        self.pending_path = self.wal_path / 'pending'
        self.processing_path = self.wal_path / 'processing'
        self.completed_path = self.wal_path / 'completed'
        
        # Ensure directories exist
        for path in [self.pending_path, self.processing_path, self.completed_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def add_pin_to_wal(self, cid: str, name: Optional[str] = None, 
                       recursive: bool = True, file_path: Optional[str] = None) -> Dict[str, Any]:
        """Add a pin operation to the write-ahead log."""
        try:
            # Generate unique operation ID
            operation_id = str(uuid.uuid4())
            timestamp = time.time()
            
            # Create WAL entry
            wal_entry = {
                'operation_id': operation_id,
                'operation_type': 'pin_add',
                'cid': cid,
                'name': name or f'pin_{cid[:12]}',
                'recursive': recursive,
                'file_path': file_path,
                'created_at': timestamp,
                'created_at_iso': datetime.fromtimestamp(timestamp).isoformat(),
                'status': 'pending',
                'backends': [],  # Will be populated by daemon
                'metadata': {
                    'size_bytes': 0,  # Will be populated by daemon
                    'content_type': None,  # Will be populated by daemon
                    'priority': 'normal',
                    'replication_factor': 1,
                    'storage_tiers': ['local']  # Default, can be extended
                }
            }
            
            # Save to pending operations
            wal_file = self.pending_path / f'{operation_id}.json'
            with open(wal_file, 'w') as f:
                json.dump(wal_entry, f, indent=2)
            
            # Update WAL index
            self._update_wal_index(wal_entry)
            
            return {
                'success': True,
                'operation_id': operation_id,
                'status': 'pending',
                'wal_file': str(wal_file),
                'message': f'Pin operation queued for processing by daemon'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'WAL add error: {e}',
                'operation_id': None
            }
    
    def get_pending_pins(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Get pending pin operations from WAL."""
        try:
            pending_files = list(self.pending_path.glob('*.json'))
            
            if not pending_files:
                return {
                    'success': True,
                    'operations': [],
                    'total_count': 0,
                    'source': 'wal_pending'
                }
            
            operations = []
            for file_path in sorted(pending_files):
                try:
                    with open(file_path, 'r') as f:
                        operation = json.load(f)
                        operations.append(operation)
                except Exception as e:
                    print(f"⚠️  Error reading WAL file {file_path}: {e}")
                    continue
            
            # Sort by creation time (oldest first for processing)
            operations.sort(key=lambda x: x.get('created_at', 0))
            
            # Apply limit if specified
            if limit:
                operations = operations[:limit]
            
            return {
                'success': True,
                'operations': operations,
                'total_count': len(operations),
                'source': 'wal_pending',
                'method': 'wal_direct'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'WAL read error: {e}',
                'operations': []
            }
    
    def get_wal_status(self) -> Dict[str, Any]:
        """Get overall WAL status for pin operations."""
        try:
            pending_count = len(list(self.pending_path.glob('*.json')))
            processing_count = len(list(self.processing_path.glob('*.json')))
            completed_count = len(list(self.completed_path.glob('*.json')))
            
            return {
                'success': True,
                'pending_operations': pending_count,
                'processing_operations': processing_count,
                'completed_operations': completed_count,
                'total_operations': pending_count + processing_count + completed_count,
                'wal_path': str(self.wal_path)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': f'WAL status error: {e}'
            }
    
    def _update_wal_index(self, wal_entry: Dict[str, Any]):
        """Update the WAL index for quick queries."""
        try:
            index_file = self.wal_path / 'pin_wal_index.parquet'
            
            # Create DataFrame from entry
            df_new = pd.DataFrame([{
                'operation_id': wal_entry['operation_id'],
                'operation_type': wal_entry['operation_type'],
                'cid': wal_entry['cid'],
                'name': wal_entry['name'],
                'status': wal_entry['status'],
                'created_at': wal_entry['created_at'],
                'updated_at': wal_entry['created_at'],
                'file_path': wal_entry.get('file_path', ''),
                'recursive': wal_entry['recursive'],
                'priority': wal_entry['metadata'].get('priority', 'normal')
            }])
            
            # If index exists, append to it
            if index_file.exists():
                try:
                    df_existing = pd.read_parquet(index_file)
                    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                except Exception:
                    # If reading fails, start fresh
                    df_combined = df_new
            else:
                df_combined = df_new
            
            # Save updated index
            df_combined.to_parquet(index_file, index=False)
            
        except Exception as e:
            print(f"⚠️  Error updating WAL index: {e}")
    
    def mark_operation_processing(self, operation_id: str) -> bool:
        """Mark a pending operation as processing (daemon use)."""
        try:
            pending_file = self.pending_path / f'{operation_id}.json'
            processing_file = self.processing_path / f'{operation_id}.json'
            
            if pending_file.exists():
                # Load operation
                with open(pending_file, 'r') as f:
                    operation = json.load(f)
                
                # Update status
                operation['status'] = 'processing'
                operation['updated_at'] = time.time()
                
                # Move to processing directory
                with open(processing_file, 'w') as f:
                    json.dump(operation, f, indent=2)
                
                # Remove from pending
                pending_file.unlink()
                
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Error marking operation as processing: {e}")
            return False
    
    def mark_operation_completed(self, operation_id: str, backends: List[str], 
                                size_bytes: int = 0) -> bool:
        """Mark a processing operation as completed (daemon use)."""
        try:
            processing_file = self.processing_path / f'{operation_id}.json'
            completed_file = self.completed_path / f'{operation_id}.json'
            
            if processing_file.exists():
                # Load operation
                with open(processing_file, 'r') as f:
                    operation = json.load(f)
                
                # Update status
                operation['status'] = 'completed'
                operation['updated_at'] = time.time()
                operation['completed_at'] = time.time()
                operation['backends'] = backends
                operation['metadata']['size_bytes'] = size_bytes
                
                # Move to completed directory
                with open(completed_file, 'w') as f:
                    json.dump(operation, f, indent=2)
                
                # Remove from processing
                processing_file.unlink()
                
                return True
            
            return False
            
        except Exception as e:
            print(f"⚠️  Error marking operation as completed: {e}")
            return False


def get_wal_pin_manager() -> WALPinManager:
    """Get global WAL pin manager instance."""
    return WALPinManager()
