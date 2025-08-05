#!/usr/bin/env python3
"""
MCP Storage Controller - Mirrors CLI storage commands

This controller provides MCP tools that mirror the CLI storage commands,
allowing MCP clients to manage storage operations with the same functionality
as the command line interface.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..models.mcp_metadata_manager import MCPMetadataManager
from ..services.mcp_daemon_service import MCPDaemonService

logger = logging.getLogger(__name__)


class MCPStorageController:
    """
    MCP Storage Controller that mirrors CLI storage commands
    
    Provides MCP tools for:
    - storage list (mirrors 'ipfs-kit storage list')
    - storage upload (mirrors 'ipfs-kit storage upload')
    - storage download (mirrors 'ipfs-kit storage download')
    """
    
    def __init__(self, metadata_manager: MCPMetadataManager, daemon_service: MCPDaemonService):
        """Initialize the storage controller."""
        self.metadata_manager = metadata_manager
        self.daemon_service = daemon_service
        logger.info("MCP Storage Controller initialized")
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle storage tool calls by routing to appropriate methods."""
        try:
            if tool_name == "storage_list":
                return await self.list_storage(arguments)
            elif tool_name == "storage_upload":
                return await self.upload_content(arguments)
            elif tool_name == "storage_download":
                return await self.download_content(arguments)
            else:
                return {"error": f"Unknown storage tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error handling storage tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def list_storage(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List storage contents (mirrors 'ipfs-kit storage list')
        
        Arguments:
        - backend: Backend to list from
        - path: Path to list
        - recursive: List recursively
        """
        backend = arguments.get("backend")
        path = arguments.get("path", "/")
        recursive = arguments.get("recursive", False)
        
        try:
            if backend:
                # Get pin metadata for specific backend
                pins = await self.metadata_manager.get_pin_metadata(backend_name=backend)
                
                storage_items = []
                for pin in pins:
                    item = {
                        "cid": pin.cid,
                        "backend": pin.backend,
                        "status": pin.status,
                        "created_at": pin.created_at.isoformat(),
                        "car_file_path": pin.car_file_path,
                        "size_bytes": pin.size_bytes
                    }
                    
                    if pin.metadata:
                        item["metadata"] = pin.metadata
                    
                    storage_items.append(item)
                
                return {
                    "backend": backend,
                    "path": path,
                    "recursive": recursive,
                    "items": storage_items,
                    "total_count": len(storage_items)
                }
            else:
                # List all storage across all backends
                all_pins = await self.metadata_manager.get_pin_metadata()
                
                # Group by backend
                backends_storage = {}
                for pin in all_pins:
                    if pin.backend not in backends_storage:
                        backends_storage[pin.backend] = []
                    
                    backends_storage[pin.backend].append({
                        "cid": pin.cid,
                        "status": pin.status,
                        "created_at": pin.created_at.isoformat(),
                        "car_file_path": pin.car_file_path,
                        "size_bytes": pin.size_bytes,
                        "metadata": pin.metadata
                    })
                
                return {
                    "all_backends": True,
                    "path": path,
                    "recursive": recursive,
                    "backends": backends_storage,
                    "total_items": len(all_pins),
                    "backends_count": len(backends_storage)
                }
                
        except Exception as e:
            logger.error(f"Error listing storage: {e}")
            return {"error": str(e)}
    
    async def upload_content(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upload content to storage (mirrors 'ipfs-kit storage upload')
        
        Arguments:
        - file_path: Local file to upload
        - backend: Target backend
        - remote_path: Remote path destination
        """
        file_path = arguments.get("file_path")
        backend = arguments.get("backend")
        remote_path = arguments.get("remote_path")
        
        try:
            if not file_path:
                return {"error": "file_path is required"}
            
            if not backend:
                return {"error": "backend is required"}
            
            # Validate backend exists
            backend_metadata = await self.metadata_manager.get_backend_metadata(backend)
            if not backend_metadata:
                return {"error": f"Backend '{backend}' not found"}
            
            # Note: Actual upload implementation would require backend-specific logic
            # For now, return a placeholder response indicating the operation would be performed
            return {
                "action": "upload_content",
                "file_path": file_path,
                "backend": backend,
                "remote_path": remote_path or f"uploads/{file_path.split('/')[-1]}",
                "status": "simulated",
                "message": "Upload operation would be performed (implementation pending)",
                "backend_type": backend_metadata.type
            }
            
        except Exception as e:
            logger.error(f"Error uploading content: {e}")
            return {"error": str(e)}
    
    async def download_content(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Download content from storage (mirrors 'ipfs-kit storage download')
        
        Arguments:
        - cid: Content ID to download
        - backend: Source backend
        - local_path: Local destination path
        """
        cid = arguments.get("cid")
        backend = arguments.get("backend")
        local_path = arguments.get("local_path")
        
        try:
            if not cid:
                return {"error": "cid is required"}
            
            # Find the CID in pin metadata
            pins = await self.metadata_manager.get_pin_metadata(
                backend_name=backend,
                cid=cid
            )
            
            if not pins:
                if backend:
                    return {"error": f"CID '{cid}' not found in backend '{backend}'"}
                else:
                    return {"error": f"CID '{cid}' not found in any backend"}
            
            # Get the first matching pin
            pin = pins[0]
            
            # Note: Actual download implementation would require backend-specific logic
            # For now, return information about where the content can be found
            return {
                "action": "download_content",
                "cid": cid,
                "backend": pin.backend,
                "local_path": local_path or f"downloads/{cid}",
                "status": "located",
                "car_file_path": pin.car_file_path,
                "size_bytes": pin.size_bytes,
                "pin_status": pin.status,
                "created_at": pin.created_at.isoformat(),
                "message": "Content located (download implementation pending)",
                "metadata": pin.metadata
            }
            
        except Exception as e:
            logger.error(f"Error downloading content: {e}")
            return {"error": str(e)}
