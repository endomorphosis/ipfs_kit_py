"""
Filecoin Pin MCP Controller.

This module provides MCP tools for interacting with the Filecoin Pin backend,
exposing pin operations via the MCP protocol.
"""

import logging
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Pydantic models for request validation
class FilecoinPinAddRequest(BaseModel):
    """Request model for adding a pin."""
    content: str = Field(..., description="File path or CID to pin")
    name: Optional[str] = Field(None, description="Human-readable name for the pin")
    description: Optional[str] = Field(None, description="Description for the pin")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    replication: Optional[int] = Field(3, description="Number of replicas")
    api_key: Optional[str] = Field(None, description="Filecoin Pin API key")


class FilecoinPinListRequest(BaseModel):
    """Request model for listing pins."""
    status: Optional[str] = Field(None, description="Filter by status (queued, pinning, pinned, failed)")
    limit: Optional[int] = Field(100, description="Maximum number of results")
    api_key: Optional[str] = Field(None, description="Filecoin Pin API key")


class FilecoinPinStatusRequest(BaseModel):
    """Request model for checking pin status."""
    cid: str = Field(..., description="Content ID to check")
    api_key: Optional[str] = Field(None, description="Filecoin Pin API key")


class FilecoinPinRemoveRequest(BaseModel):
    """Request model for removing a pin."""
    cid: str = Field(..., description="Content ID to unpin")
    api_key: Optional[str] = Field(None, description="Filecoin Pin API key")


class FilecoinPinGetRequest(BaseModel):
    """Request model for retrieving content."""
    cid: str = Field(..., description="Content ID to retrieve")
    api_key: Optional[str] = Field(None, description="Filecoin Pin API key")


class FilecoinPinController:
    """MCP Controller for Filecoin Pin operations."""
    
    def __init__(self):
        """Initialize the Filecoin Pin controller."""
        self.logger = logger
        self._backend_cache: Optional[Any] = None
    
    def _get_backend(self, api_key: Optional[str] = None):
        """Get or create Filecoin Pin backend instance."""
        from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend
        
        # Use provided API key or environment variable
        key = api_key or os.getenv('FILECOIN_PIN_API_KEY')
        
        # Create backend
        resources = {
            "api_key": key,
            "timeout": 60
        }
        
        metadata = {
            "default_replication": 3,
            "auto_renew": True,
            "deal_duration_days": 540
        }
        
        return FilecoinPinBackend(resources, metadata)
    
    async def pin_add(self, request: FilecoinPinAddRequest) -> Dict[str, Any]:
        """
        Pin content to Filecoin Pin service.
        
        Args:
            request: Pin add request with content and metadata
        
        Returns:
            Dictionary with pin result including CID, status, and deal info
        """
        try:
            from pathlib import Path
            
            backend = self._get_backend(request.api_key)
            
            # Determine if input is file or CID
            is_file = Path(request.content).exists()
            
            if is_file:
                self.logger.info(f"Pinning file: {request.content}")
                content = request.content
            else:
                self.logger.info(f"Pinning CID: {request.content}")
                # For CID, we encode it as bytes (simplified)
                content = request.content.encode('utf-8')
            
            # Prepare metadata
            pin_metadata = {
                "name": request.name or f"pin-{request.content[:12]}",
                "description": request.description or "",
                "tags": request.tags.split(',') if request.tags else [],
                "replication": request.replication
            }
            
            # Pin content
            result = backend.add_content(content, pin_metadata)
            
            return {
                "success": result.get('success', False),
                "cid": result.get('cid'),
                "status": result.get('status'),
                "request_id": result.get('request_id'),
                "deal_ids": result.get('deal_ids', []),
                "size": result.get('size', 0),
                "replication": result.get('replication', 0),
                "error": result.get('error'),
                "backend": "filecoin_pin"
            }
            
        except Exception as e:
            self.logger.error(f"Error pinning content: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "backend": "filecoin_pin"
            }
    
    async def pin_list(self, request: FilecoinPinListRequest) -> Dict[str, Any]:
        """
        List pins on Filecoin Pin service.
        
        Args:
            request: Pin list request with optional filters
        
        Returns:
            Dictionary with list of pins
        """
        try:
            backend = self._get_backend(request.api_key)
            
            result = backend.list_pins(
                status=request.status,
                limit=request.limit
            )
            
            return {
                "success": result.get('success', False),
                "pins": result.get('pins', []),
                "count": result.get('count', 0),
                "error": result.get('error'),
                "backend": "filecoin_pin"
            }
            
        except Exception as e:
            self.logger.error(f"Error listing pins: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "backend": "filecoin_pin"
            }
    
    async def pin_status(self, request: FilecoinPinStatusRequest) -> Dict[str, Any]:
        """
        Get pin status and metadata.
        
        Args:
            request: Pin status request with CID
        
        Returns:
            Dictionary with pin status and deal information
        """
        try:
            backend = self._get_backend(request.api_key)
            
            result = backend.get_metadata(request.cid)
            
            return {
                "success": result.get('success', False),
                "cid": result.get('cid'),
                "status": result.get('status'),
                "deals": result.get('deals', []),
                "created": result.get('created'),
                "size": result.get('size', 0),
                "replication": result.get('replication', 0),
                "error": result.get('error'),
                "backend": "filecoin_pin"
            }
            
        except Exception as e:
            self.logger.error(f"Error getting pin status: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "backend": "filecoin_pin"
            }
    
    async def pin_remove(self, request: FilecoinPinRemoveRequest) -> Dict[str, Any]:
        """
        Remove a pin from Filecoin Pin service.
        
        Args:
            request: Pin remove request with CID
        
        Returns:
            Dictionary with removal result
        """
        try:
            backend = self._get_backend(request.api_key)
            
            result = backend.remove_content(request.cid)
            
            return {
                "success": result.get('success', False),
                "cid": result.get('cid'),
                "error": result.get('error'),
                "backend": "filecoin_pin"
            }
            
        except Exception as e:
            self.logger.error(f"Error removing pin: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "backend": "filecoin_pin"
            }
    
    async def pin_get(self, request: FilecoinPinGetRequest) -> Dict[str, Any]:
        """
        Retrieve pinned content.
        
        Args:
            request: Pin get request with CID
        
        Returns:
            Dictionary with content data and retrieval info
        """
        try:
            backend = self._get_backend(request.api_key)
            
            result = backend.get_content(request.cid)
            
            # Convert bytes to base64 for JSON serialization
            if result.get('success') and 'data' in result:
                import base64
                data_bytes = result['data']
                result['data'] = base64.b64encode(data_bytes).decode('utf-8')
                result['data_encoding'] = 'base64'
            
            return {
                "success": result.get('success', False),
                "cid": result.get('cid'),
                "data": result.get('data'),
                "data_encoding": result.get('data_encoding', 'base64'),
                "source": result.get('source'),
                "size": result.get('size', 0),
                "error": result.get('error'),
                "backend": "filecoin_pin"
            }
            
        except Exception as e:
            self.logger.error(f"Error retrieving content: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "backend": "filecoin_pin"
            }


def create_filecoin_pin_router():
    """Create FastAPI router for Filecoin Pin MCP tools."""
    try:
        from fastapi import APIRouter, HTTPException
        
        router = APIRouter(prefix="/filecoin-pin", tags=["filecoin-pin"])
        controller = FilecoinPinController()
        
        @router.post("/add")
        async def filecoin_pin_add(request: FilecoinPinAddRequest):
            """Pin content to Filecoin Pin service."""
            result = await controller.pin_add(request)
            if not result.get('success'):
                raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
            return result
        
        @router.post("/list")
        async def filecoin_pin_list(request: FilecoinPinListRequest):
            """List pins on Filecoin Pin service."""
            result = await controller.pin_list(request)
            if not result.get('success'):
                raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
            return result
        
        @router.post("/status")
        async def filecoin_pin_status(request: FilecoinPinStatusRequest):
            """Get pin status and metadata."""
            result = await controller.pin_status(request)
            if not result.get('success'):
                raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
            return result
        
        @router.post("/remove")
        async def filecoin_pin_remove(request: FilecoinPinRemoveRequest):
            """Remove a pin from Filecoin Pin service."""
            result = await controller.pin_remove(request)
            if not result.get('success'):
                raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
            return result
        
        @router.post("/get")
        async def filecoin_pin_get(request: FilecoinPinGetRequest):
            """Retrieve pinned content."""
            result = await controller.pin_get(request)
            if not result.get('success'):
                raise HTTPException(status_code=500, detail=result.get('error', 'Unknown error'))
            return result
        
        return router
        
    except ImportError:
        logger.warning("FastAPI not available, router creation skipped")
        return None


# MCP Tool Definitions
def get_filecoin_pin_tools():
    """Get MCP tool definitions for Filecoin Pin operations."""
    return [
        {
            "name": "filecoin_pin_add",
            "description": "Pin content to Filecoin Pin service (unified IPFS + Filecoin storage)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "File path or CID to pin"
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable name for the pin"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description for the pin"
                    },
                    "tags": {
                        "type": "string",
                        "description": "Comma-separated tags for categorization"
                    },
                    "replication": {
                        "type": "integer",
                        "description": "Number of replicas (default: 3)"
                    },
                    "api_key": {
                        "type": "string",
                        "description": "Filecoin Pin API key (optional, uses env var if not provided)"
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "filecoin_pin_list",
            "description": "List all pins on Filecoin Pin service",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["queued", "pinning", "pinned", "failed"],
                        "description": "Filter by pin status"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 100)"
                    },
                    "api_key": {
                        "type": "string",
                        "description": "Filecoin Pin API key (optional)"
                    }
                }
            }
        },
        {
            "name": "filecoin_pin_status",
            "description": "Get detailed status information for a pin",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "Content ID to check"
                    },
                    "api_key": {
                        "type": "string",
                        "description": "Filecoin Pin API key (optional)"
                    }
                },
                "required": ["cid"]
            }
        },
        {
            "name": "filecoin_pin_remove",
            "description": "Remove a pin from Filecoin Pin service",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "Content ID to unpin"
                    },
                    "api_key": {
                        "type": "string",
                        "description": "Filecoin Pin API key (optional)"
                    }
                },
                "required": ["cid"]
            }
        },
        {
            "name": "filecoin_pin_get",
            "description": "Retrieve pinned content from Filecoin Pin via gateways",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "Content ID to retrieve"
                    },
                    "api_key": {
                        "type": "string",
                        "description": "Filecoin Pin API key (optional)"
                    }
                },
                "required": ["cid"]
            }
        }
    ]
