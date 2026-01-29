#!/usr/bin/env python3
"""
REST API controller for Filesystem Journal functionality.

This module provides API endpoints for interacting with the Filesystem Journal
through the MCP server.
"""

import logging
import time
import sys
import os
import json
import threading
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

# Integration with ipfs_datasets_py for distributed storage
HAS_DATASETS = False
try:
    from ipfs_kit_py.ipfs_datasets_integration import get_ipfs_datasets_manager
    HAS_DATASETS = True
except ImportError:
    pass

# Integration with ipfs_accelerate_py for compute acceleration
HAS_ACCELERATE = False
try:
    from pathlib import Path as PathLib
    accelerate_path = PathLib(__file__).parent.parent.parent / "external" / "ipfs_accelerate_py"
    if accelerate_path.exists():
        sys.path.insert(0, str(accelerate_path))
    from ipfs_accelerate_py import AccelerateCompute
    HAS_ACCELERATE = True
except ImportError:
    pass

try:
    from fastapi import APIRouter, Depends, Query, Path, Body
    from pydantic import BaseModel, Field
except ImportError:
    # For testing without FastAPI
    class APIRouter:
        def add_api_route(self, *args, **kwargs):
            pass

    class BaseModel:
        pass

    def Field(*args, **kwargs):
        return None

    def Query(*args, **kwargs):
        return None

    def Path(*args, **kwargs):
        return None

    def Body(*args, **kwargs):
        return None

# Configure logger
logger = logging.getLogger(__name__)

class FileSystemOperationRequest(BaseModel):
    """Base model for file system operations."""
    path: str = Field(..., description="Path to the file or directory")
    recursive: bool = Field(False, description="Whether to perform the operation recursively")

class FileSystemOperationResponse(BaseModel):
    """Base model for file system operation responses."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field("", description="Error message if operation failed")
    path: str = Field(..., description="Path that was operated on")

class FsJournalController:
    """
    Controller for Filesystem Journal operations.
    
    This controller handles HTTP requests related to filesystem journal operations and
    delegates business logic to the appropriate model.
    """
    
    def __init__(self, 
                 fs_journal_model,
                 enable_dataset_storage: bool = False,
                 enable_compute_layer: bool = False,
                 ipfs_client = None,
                 dataset_batch_size: int = 100):
        """
        Initialize the Filesystem Journal controller.
        
        Args:
            fs_journal_model: Model for handling filesystem journal operations
            enable_dataset_storage: Enable ipfs_datasets_py integration for distributed storage
            enable_compute_layer: Enable ipfs_accelerate_py for compute acceleration
            ipfs_client: Optional IPFS client instance for dataset operations
            dataset_batch_size: Number of operations to buffer before flushing to dataset
        """
        self.fs_journal_model = fs_journal_model
        
        # Dataset storage integration
        self.enable_dataset_storage = enable_dataset_storage
        self.enable_compute_layer = enable_compute_layer
        self.dataset_manager = None
        self.compute_layer = None
        self._operation_buffer = []
        self._buffer_lock = threading.Lock()
        self.dataset_batch_size = dataset_batch_size
        
        # Initialize dataset storage
        self._initialize_dataset_storage(ipfs_client)
        
        # Initialize compute layer
        self._initialize_compute_layer()
        
        logger.info("Filesystem Journal Controller initialized")
    
    def _initialize_dataset_storage(self, ipfs_client):
        """Initialize dataset storage if enabled."""
        if HAS_DATASETS and self.enable_dataset_storage:
            try:
                self.dataset_manager = get_ipfs_datasets_manager(
                    enable=True,
                    ipfs_client=ipfs_client
                )
                logger.info("Dataset storage enabled for journal operations")
            except Exception as e:
                logger.warning(f"Failed to initialize dataset storage: {e}")
    
    def _initialize_compute_layer(self):
        """Initialize compute layer if enabled."""
        if HAS_ACCELERATE and self.enable_compute_layer:
            try:
                self.compute_layer = AccelerateCompute()
                logger.info("Compute acceleration enabled for journal operations")
            except Exception as e:
                logger.warning(f"Failed to initialize compute layer: {e}")
    
    def _store_operation_to_dataset(self, operation_data: dict):
        """Store journal controller operation to dataset if enabled."""
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
                        "type": "fs_journal_controller_operations",
                        "operation_count": len(self._operation_buffer),
                        "timestamp": datetime.now().isoformat(),
                        "component": "FsJournalController"
                    }
                )
                
                if result.get("success"):
                    logger.info(f"Stored {len(self._operation_buffer)} journal controller operations to dataset: {result.get('cid', 'N/A')}")
                
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
    
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Create journal entry
        router.add_api_route(
            "/create",
            self.create_journal_entry,
            methods=["POST"],
            response_model=FileSystemOperationResponse,
            summary="Create a filesystem journal entry",
            description="Create an entry in the filesystem journal"
        )
        
        # List journal entries
        router.add_api_route(
            "/list",
            self.list_journal_entries,
            methods=["GET"],
            summary="List filesystem journal entries",
            description="List entries in the filesystem journal"
        )
        
        # Get journal entry details
        router.add_api_route(
            "/get/{entry_id}",
            self.get_journal_entry,
            methods=["GET"],
            response_model=FileSystemOperationResponse,
            summary="Get filesystem journal entry",
            description="Get details of a specific filesystem journal entry"
        )
        
        logger.info("Filesystem Journal Controller routes registered")
    
    async def create_journal_entry(self, request: FileSystemOperationRequest) -> Dict[str, Any]:
        """
        Create a filesystem journal entry.
        
        Args:
            request: Journal entry creation request
            
        Returns:
            Dictionary with operation results
        """
        start_time = time.time()
        try:
            logger.info(f"Creating journal entry for path: {request.path}")
            
            # Call the model's create_journal_entry method
            result = self.fs_journal_model.create_journal_entry(
                path=request.path,
                recursive=request.recursive
            )
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "controller_action": "create_journal_entry",
                "timestamp": datetime.now().isoformat(),
                "journal_operation": "create",
                "parameters": {
                    "path": request.path,
                    "recursive": request.recursive
                },
                "result": {
                    "success": result.get("success", False),
                    "entry_id": result.get("entry_id"),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            })
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error creating journal entry: {error_msg}")
                return {
                    "success": False,
                    "message": f"Failed to create journal entry: {error_msg}",
                    "path": request.path
                }
            
            return {
                "success": True,
                "message": "Journal entry created successfully",
                "path": request.path,
                "entry_id": result.get("entry_id")
            }
            
        except Exception as e:
            logger.error(f"Error creating journal entry: {e}")
            # Store error to dataset
            self._store_operation_to_dataset({
                "controller_action": "create_journal_entry",
                "timestamp": datetime.now().isoformat(),
                "journal_operation": "create",
                "parameters": {
                    "path": request.path,
                    "recursive": request.recursive
                },
                "result": {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            })
            return {
                "success": False,
                "message": f"Internal error: {str(e)}",
                "path": request.path
            }
    
    async def list_journal_entries(self, limit: int = Query(100, description="Maximum number of entries to return")) -> Dict[str, Any]:
        """
        List filesystem journal entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            Dictionary with operation results
        """
        start_time = time.time()
        try:
            logger.info(f"Listing journal entries (limit: {limit})")
            
            # Call the model's list_journal_entries method
            result = self.fs_journal_model.list_journal_entries(limit=limit)
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "controller_action": "list_journal_entries",
                "timestamp": datetime.now().isoformat(),
                "journal_operation": "list",
                "parameters": {
                    "limit": limit
                },
                "result": {
                    "success": result.get("success", False),
                    "entry_count": len(result.get("entries", [])),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            })
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error listing journal entries: {error_msg}")
                return {
                    "success": False,
                    "message": f"Failed to list journal entries: {error_msg}",
                    "entries": []
                }
            
            return {
                "success": True,
                "message": f"Retrieved {len(result.get('entries', []))} journal entries",
                "entries": result.get("entries", [])
            }
            
        except Exception as e:
            logger.error(f"Error listing journal entries: {e}")
            # Store error to dataset
            self._store_operation_to_dataset({
                "controller_action": "list_journal_entries",
                "timestamp": datetime.now().isoformat(),
                "journal_operation": "list",
                "parameters": {
                    "limit": limit
                },
                "result": {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            })
            return {
                "success": False,
                "message": f"Internal error: {str(e)}",
                "entries": []
            }
    
    async def get_journal_entry(self, entry_id: str = Path(..., description="Journal entry ID")) -> Dict[str, Any]:
        """
        Get filesystem journal entry details.
        
        Args:
            entry_id: Journal entry ID
            
        Returns:
            Dictionary with operation results
        """
        start_time = time.time()
        try:
            logger.info(f"Getting journal entry: {entry_id}")
            
            # Call the model's get_journal_entry method
            result = self.fs_journal_model.get_journal_entry(entry_id=entry_id)
            
            # Store operation to dataset
            self._store_operation_to_dataset({
                "controller_action": "get_journal_entry",
                "timestamp": datetime.now().isoformat(),
                "journal_operation": "get",
                "parameters": {
                    "entry_id": entry_id
                },
                "result": {
                    "success": result.get("success", False),
                    "path": result.get("path", ""),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            })
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Error getting journal entry: {error_msg}")
                return {
                    "success": False,
                    "message": f"Failed to get journal entry: {error_msg}",
                    "path": "",
                    "entry_id": entry_id
                }
            
            return {
                "success": True,
                "message": "Journal entry retrieved successfully",
                "path": result.get("path", ""),
                "entry_id": entry_id,
                "timestamp": result.get("timestamp"),
                "details": result.get("details", {})
            }
            
        except Exception as e:
            logger.error(f"Error getting journal entry: {e}")
            # Store error to dataset
            self._store_operation_to_dataset({
                "controller_action": "get_journal_entry",
                "timestamp": datetime.now().isoformat(),
                "journal_operation": "get",
                "parameters": {
                    "entry_id": entry_id
                },
                "result": {
                    "success": False,
                    "error": str(e),
                    "duration_ms": (time.time() - start_time) * 1000
                }
            })
            return {
                "success": False,
                "message": f"Internal error: {str(e)}",
                "path": "",
                "entry_id": entry_id
            }
