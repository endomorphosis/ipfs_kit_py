#!/usr/bin/env python3
"""
Enhanced Pin Write-Ahead Log (WAL) system with CAR format support.

This module provides a specialized WAL for pin operations using CAR files
instead of JSON files for better IPFS integration and performance.
"""

import asyncio
import json
import os
import time
import uuid
import logging
import aiofiles
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from datetime import datetime

# Import CAR WAL manager
try:
    from .car_wal_manager import get_car_wal_manager
    CAR_WAL_AVAILABLE = True
except ImportError:
    CAR_WAL_AVAILABLE = False

logger = logging.getLogger(__name__)

class PinOperationType(str, Enum):
    """Types of pin operations supported by the WAL."""
    ADD = "add"
    REMOVE = "remove"
    UPDATE = "update"
    METADATA_UPDATE = "metadata_update"

class PinOperationStatus(str, Enum):
    """Status values for pin operations in the WAL."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class EnhancedPinWAL:
    """
    Enhanced Write-Ahead Log for pin operations using CAR format.
    
    This uses CAR files instead of JSON for better IPFS integration
    and more efficient storage/processing.
    """
    
    def __init__(self, base_path: str = "/tmp/ipfs_kit_wal"):
        self.base_path = Path(base_path)
        self.use_car_format = CAR_WAL_AVAILABLE
        
        # Initialize appropriate WAL backend
        if self.use_car_format:
            self.car_wal_manager = get_car_wal_manager(self.base_path / "car")
            logger.info("Using CAR-based PIN WAL")
        else:
            # Fallback to original JSON implementation
            self._init_json_wal()
            logger.info("Using JSON-based PIN WAL (fallback)")
    
    def _init_json_wal(self):
        """Initialize JSON-based WAL (fallback)."""
        self.pending_dir = self.base_path / "pending"
        self.processing_dir = self.base_path / "processing"
        self.completed_dir = self.base_path / "completed"
        self.failed_dir = self.base_path / "failed"
        
        for directory in [self.pending_dir, self.processing_dir, 
                         self.completed_dir, self.failed_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    async def add_pin_operation(
        self,
        cid: str,
        operation_type: PinOperationType,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """Add a pin operation to the WAL."""
        
        if self.use_car_format:
            return await self._add_pin_operation_car(
                cid, operation_type, name, recursive, metadata, priority
            )
        else:
            return await self._add_pin_operation_json(
                cid, operation_type, name, recursive, metadata, priority
            )
    
    async def _add_pin_operation_car(
        self,
        cid: str,
        operation_type: PinOperationType,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """Add pin operation using CAR format."""
        
        operation_id = str(uuid.uuid4())
        
        # Create pin operation metadata
        pin_metadata = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "target_cid": cid,
            "pin_name": name,
            "recursive": recursive,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "status": PinOperationStatus.PENDING.value,
            "retry_count": 0,
            "user_metadata": metadata or {}
        }
        
        # Store using CAR WAL manager
        result = await self.car_wal_manager.store_content_to_wal(
            file_cid=f"pin-op-{operation_id}",
            content=json.dumps(pin_metadata).encode(),
            file_path=f"/pins/{operation_type.value}/{cid}",
            metadata=pin_metadata
        )
        
        if result.get("success"):
            logger.info(f"Added PIN operation {operation_id} to CAR WAL")
            return operation_id
        else:
            logger.error(f"Failed to add PIN operation to CAR WAL: {result.get('error')}")
            raise Exception(f"PIN WAL storage failed: {result.get('error')}")
    
    async def _add_pin_operation_json(
        self,
        cid: str,
        operation_type: PinOperationType,
        name: Optional[str] = None,
        recursive: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
        priority: int = 0
    ) -> str:
        """Add pin operation using JSON format (fallback)."""
        
        operation_id = str(uuid.uuid4())
        timestamp = time.time()
        
        operation = {
            "operation_id": operation_id,
            "operation_type": operation_type.value,
            "cid": cid,
            "name": name,
            "recursive": recursive,
            "metadata": metadata or {},
            "priority": priority,
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "status": PinOperationStatus.PENDING.value,
            "retry_count": 0,
            "last_error": None
        }
        
        # Write to pending directory
        pending_file = self.pending_dir / f"{timestamp:.6f}_{priority:03d}_{operation_id}.json"
        
        async with aiofiles.open(pending_file, 'w') as f:
            await f.write(json.dumps(operation, indent=2))
        
        logger.info(f"Added pin operation {operation_id} for CID {cid}")
        return operation_id
    
    async def get_pending_operations(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending operations."""
        
        if self.use_car_format:
            return await self._get_pending_operations_car(limit)
        else:
            return await self._get_pending_operations_json(limit)
    
    async def _get_pending_operations_car(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending operations from CAR WAL."""
        
        # Get WAL entries from CAR manager
        wal_status = self.car_wal_manager.list_wal_entries()
        
        if not wal_status.get("success"):
            logger.error(f"Failed to list CAR WAL entries: {wal_status.get('error')}")
            return []
        
        # Convert WAL entries to pin operations format
        operations = []
        for entry in wal_status.get("wal_entries", []):
            if entry.get("file_cid", "").startswith("pin-op-"):
                operations.append({
                    "operation_id": entry.get("file_cid", "").replace("pin-op-", ""),
                    "timestamp": entry.get("timestamp"),
                    "status": "pending",
                    "wal_file": entry.get("wal_file"),
                    "size_bytes": entry.get("size_bytes")
                })
        
        return operations[:limit]
    
    async def _get_pending_operations_json(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get pending operations from JSON WAL (fallback)."""
        
        try:
            pending_files = list(self.pending_dir.glob("*.json"))
            pending_files.sort()
            
            operations = []
            for file_path in pending_files[:limit]:
                try:
                    async with aiofiles.open(file_path, 'r') as f:
                        content = await f.read()
                        operation = json.loads(content)
                        operations.append(operation)
                except Exception as e:
                    logger.error(f"Failed to read operation file {file_path}: {e}")
            
            return operations
            
        except Exception as e:
            logger.error(f"Failed to get pending operations: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get WAL statistics."""
        
        if self.use_car_format:
            wal_status = self.car_wal_manager.list_wal_entries()
            
            if wal_status.get("success"):
                return {
                    "format": "CAR",
                    "pending": wal_status.get("pending_count", 0),
                    "processed": wal_status.get("processed_count", 0),
                    "total_operations": wal_status.get("pending_count", 0) + wal_status.get("processed_count", 0)
                }
            else:
                return {"format": "CAR", "error": wal_status.get("error")}
        else:
            try:
                pending_count = len(list(self.pending_dir.glob("*.json")))
                processing_count = len(list(self.processing_dir.glob("*.json")))
                completed_count = len(list(self.completed_dir.glob("*.json")))
                failed_count = len(list(self.failed_dir.glob("*.json")))
                
                return {
                    "format": "JSON",
                    "pending": pending_count,
                    "processing": processing_count,
                    "completed": completed_count,
                    "failed": failed_count,
                    "total_operations": pending_count + processing_count + completed_count + failed_count
                }
            except Exception as e:
                logger.error(f"Failed to get WAL stats: {e}")
                return {"format": "JSON", "error": str(e)}


# Global enhanced PIN WAL instance
_global_enhanced_pin_wal: Optional[EnhancedPinWAL] = None

def get_global_pin_wal() -> EnhancedPinWAL:
    """Get or create the global Enhanced Pin WAL instance."""
    global _global_enhanced_pin_wal
    if _global_enhanced_pin_wal is None:
        _global_enhanced_pin_wal = EnhancedPinWAL()
    return _global_enhanced_pin_wal

# Convenience functions remain the same but use enhanced WAL
async def add_pin_to_wal(
    cid: str,
    name: Optional[str] = None,
    recursive: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 0
) -> str:
    """Convenience function to add a pin operation to the global enhanced WAL."""
    wal = get_global_pin_wal()
    return await wal.add_pin_operation(
        cid=cid,
        operation_type=PinOperationType.ADD,
        name=name,
        recursive=recursive,
        metadata=metadata,
        priority=priority
    )

async def remove_pin_from_wal(
    cid: str,
    metadata: Optional[Dict[str, Any]] = None,
    priority: int = 0
) -> str:
    """Convenience function to add a pin removal operation to the global enhanced WAL."""
    wal = get_global_pin_wal()
    return await wal.add_pin_operation(
        cid=cid,
        operation_type=PinOperationType.REMOVE,
        metadata=metadata,
        priority=priority
    )
