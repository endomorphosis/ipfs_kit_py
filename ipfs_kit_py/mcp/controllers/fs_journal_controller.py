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
from typing import Dict, Any, Optional, List

# Add the parent directory to sys.path to allow importing mcp_error_handling
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import mcp_error_handling

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
    
    def __init__(self, fs_journal_model):
        """
        Initialize the Filesystem Journal controller.
        
        Args:
            fs_journal_model: Model for handling filesystem journal operations
        """
        self.fs_journal_model = fs_journal_model
        logger.info("Filesystem Journal Controller initialized")
    
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
        try:
            logger.info(f"Creating journal entry for path: {request.path}")
            
            # Call the model's create_journal_entry method
            result = self.fs_journal_model.create_journal_entry(
                path=request.path,
                recursive=request.recursive
            )
            
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
        try:
            logger.info(f"Listing journal entries (limit: {limit})")
            
            # Call the model's list_journal_entries method
            result = self.fs_journal_model.list_journal_entries(limit=limit)
            
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
        try:
            logger.info(f"Getting journal entry: {entry_id}")
            
            # Call the model's get_journal_entry method
            result = self.fs_journal_model.get_journal_entry(entry_id=entry_id)
            
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
            return {
                "success": False,
                "message": f"Internal error: {str(e)}",
                "path": "",
                "entry_id": entry_id
            }
