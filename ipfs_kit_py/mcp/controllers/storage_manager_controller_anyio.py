"""
Storage Manager Controller for AnyIO compatibility.
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Body, Query

logger = logging.getLogger(__name__)

class StorageManagerControllerAnyIO:
    """
    Controller for Storage Manager operations using AnyIO.
    
    Handles HTTP requests related to storage operations.
    """
    
    def __init__(self, storage_manager):
        """
        Initialize the Storage Manager Controller.
        
        Args:
            storage_manager: The storage manager instance to use
        """
        self.storage_manager = storage_manager
        logger.info("Storage Manager Controller AnyIO initialized")
        
    def register_routes(self, router: APIRouter):
        """
        Register routes with a FastAPI router.
        
        Args:
            router: FastAPI router to register routes with
        """
        # Add storage endpoints
        router.add_api_route(
            "/storage/backends",
            self.list_backends,
            methods=["GET"],
            summary="List storage backends",
            description="List available storage backends and their status",
        )
        
        logger.info("Storage Manager Controller AnyIO routes registered")
        
    async def list_backends(self) -> Dict[str, Any]:
        """
        List available storage backends.
        
        Returns:
            Dictionary with backend information
        """
        try:
            # Return mock data for testing
            return {
                "success": True,
                "backends": [
                    {"name": "ipfs", "status": "active", "type": "distributed"},
                    {"name": "local", "status": "active", "type": "local"}
                ]
            }
        except Exception as e:
            logger.error(f"Error listing backends: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error listing backends: {str(e)}")
