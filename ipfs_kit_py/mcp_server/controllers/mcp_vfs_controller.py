#!/usr/bin/env python3
"""
MCP VFS Controller - Mirrors CLI VFS commands

This controller provides MCP tools that mirror the CLI VFS (Virtual File System)
commands, allowing MCP clients to manage VFS operations with the same functionality
as the command line interface.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.mcp_metadata_manager import MCPMetadataManager
from ..services.mcp_daemon_service import MCPDaemonService

logger = logging.getLogger(__name__)


class MCPVFSController:
    """
    MCP VFS Controller that mirrors CLI VFS commands
    
    Provides MCP tools for:
    - vfs list (mirrors 'ipfs-kit vfs list')
    - vfs create (mirrors 'ipfs-kit vfs create')
    - vfs add (mirrors 'ipfs-kit vfs add')
    """
    
    def __init__(self, metadata_manager: MCPMetadataManager, daemon_service: MCPDaemonService):
        """Initialize the VFS controller."""
        self.metadata_manager = metadata_manager
        self.daemon_service = daemon_service
        self.vfs_root = self.metadata_manager.data_dir / "vfs"
        logger.info("MCP VFS Controller initialized")
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle VFS tool calls by routing to appropriate methods."""
        try:
            if tool_name == "vfs_list":
                return await self.list_vfs(arguments)
            elif tool_name == "vfs_create":
                return await self.create_vfs_directory(arguments)
            elif tool_name == "vfs_add":
                return await self.add_to_vfs(arguments)
            elif tool_name == "vfs_remove":
                return await self.remove_vfs_path(arguments)
            else:
                return {"error": f"Unknown VFS tool: {tool_name}"}
        except Exception as e:
            logger.error(f"Error handling VFS tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def list_vfs(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        List VFS contents (mirrors 'ipfs-kit vfs list')
        
        Arguments:
        - path: VFS path to list
        - recursive: List recursively
        """
        vfs_path = arguments.get("path", "/")
        recursive = arguments.get("recursive", False)
        
        try:
            # Normalize VFS path
            if vfs_path.startswith("/"):
                vfs_path = vfs_path[1:]
            
            full_path = self.vfs_root / vfs_path
            
            if not full_path.exists():
                return {
                    "path": vfs_path,
                    "exists": False,
                    "message": f"VFS path '{vfs_path}' does not exist"
                }
            
            items = []
            
            if full_path.is_file():
                # Single file
                stat_info = full_path.stat()
                items.append({
                    "name": full_path.name,
                    "type": "file",
                    "size_bytes": stat_info.st_size,
                    "modified": stat_info.st_mtime,
                    "path": str(full_path.relative_to(self.vfs_root))
                })
            else:
                # Directory listing
                try:
                    if recursive:
                        # Recursive listing
                        for item_path in full_path.rglob("*"):
                            if item_path == full_path:
                                continue
                            
                            stat_info = item_path.stat()
                            items.append({
                                "name": item_path.name,
                                "type": "directory" if item_path.is_dir() else "file",
                                "size_bytes": stat_info.st_size if item_path.is_file() else 0,
                                "modified": stat_info.st_mtime,
                                "path": str(item_path.relative_to(self.vfs_root)),
                                "relative_path": str(item_path.relative_to(full_path))
                            })
                    else:
                        # Single level listing
                        for item_path in full_path.iterdir():
                            stat_info = item_path.stat()
                            items.append({
                                "name": item_path.name,
                                "type": "directory" if item_path.is_dir() else "file",
                                "size_bytes": stat_info.st_size if item_path.is_file() else 0,
                                "modified": stat_info.st_mtime,
                                "path": str(item_path.relative_to(self.vfs_root))
                            })
                    
                    # Sort items by name
                    items.sort(key=lambda x: (x["type"] == "file", x["name"]))
                    
                except PermissionError:
                    return {
                        "path": vfs_path,
                        "error": "Permission denied",
                        "message": f"Cannot access VFS path '{vfs_path}'"
                    }
            
            return {
                "path": vfs_path,
                "exists": True,
                "recursive": recursive,
                "items": items,
                "total_count": len(items),
                "directories": len([i for i in items if i["type"] == "directory"]),
                "files": len([i for i in items if i["type"] == "file"]),
                "total_size_bytes": sum(i["size_bytes"] for i in items)
            }
            
        except Exception as e:
            logger.error(f"Error listing VFS: {e}")
            return {"error": str(e)}
    
    async def create_vfs_directory(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create VFS directory (mirrors 'ipfs-kit vfs create')
        
        Arguments:
        - path: VFS path to create
        - parents: Create parent directories
        """
        vfs_path = arguments.get("path")
        parents = arguments.get("parents", False)
        
        try:
            if not vfs_path:
                return {"error": "path is required"}
            
            # Normalize VFS path
            if vfs_path.startswith("/"):
                vfs_path = vfs_path[1:]
            
            full_path = self.vfs_root / vfs_path
            
            if full_path.exists():
                if full_path.is_dir():
                    return {
                        "action": "create_vfs_directory",
                        "path": vfs_path,
                        "status": "already_exists",
                        "message": f"VFS directory '{vfs_path}' already exists"
                    }
                else:
                    return {
                        "action": "create_vfs_directory",
                        "path": vfs_path,
                        "error": "path_exists_as_file",
                        "message": f"VFS path '{vfs_path}' already exists as a file"
                    }
            
            try:
                full_path.mkdir(parents=parents, exist_ok=False)
                
                return {
                    "action": "create_vfs_directory",
                    "path": vfs_path,
                    "status": "created",
                    "message": f"VFS directory '{vfs_path}' created successfully",
                    "full_path": str(full_path),
                    "parents_created": parents
                }
                
            except FileNotFoundError:
                return {
                    "action": "create_vfs_directory",
                    "path": vfs_path,
                    "error": "parent_not_found",
                    "message": f"Parent directory for '{vfs_path}' does not exist (use parents=true to create)"
                }
            except PermissionError:
                return {
                    "action": "create_vfs_directory",
                    "path": vfs_path,
                    "error": "permission_denied",
                    "message": f"Permission denied creating VFS directory '{vfs_path}'"
                }
                
        except Exception as e:
            logger.error(f"Error creating VFS directory: {e}")
            return {"error": str(e)}
    
    async def add_to_vfs(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add file to VFS (mirrors 'ipfs-kit vfs add')
        
        Arguments:
        - local_path: Local file to add
        - vfs_path: VFS destination path
        """
        local_path = arguments.get("local_path")
        vfs_path = arguments.get("vfs_path")
        
        try:
            if not local_path:
                return {"error": "local_path is required"}
            
            if not vfs_path:
                return {"error": "vfs_path is required"}
            
            # Validate local file exists
            local_file = Path(local_path)
            if not local_file.exists():
                return {
                    "action": "add_to_vfs",
                    "local_path": local_path,
                    "error": "local_file_not_found",
                    "message": f"Local file '{local_path}' does not exist"
                }
            
            if not local_file.is_file():
                return {
                    "action": "add_to_vfs",
                    "local_path": local_path,
                    "error": "not_a_file",
                    "message": f"'{local_path}' is not a file"
                }
            
            # Normalize VFS path
            if vfs_path.startswith("/"):
                vfs_path = vfs_path[1:]
            
            full_vfs_path = self.vfs_root / vfs_path
            
            # Create parent directories if needed
            full_vfs_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if destination already exists
            if full_vfs_path.exists():
                return {
                    "action": "add_to_vfs",
                    "local_path": local_path,
                    "vfs_path": vfs_path,
                    "error": "destination_exists",
                    "message": f"VFS path '{vfs_path}' already exists"
                }
            
            # Copy file to VFS
            import shutil
            shutil.copy2(local_file, full_vfs_path)
            
            # Get file info
            stat_info = full_vfs_path.stat()
            
            return {
                "action": "add_to_vfs",
                "local_path": local_path,
                "vfs_path": vfs_path,
                "status": "added",
                "message": f"File '{local_path}' added to VFS as '{vfs_path}'",
                "size_bytes": stat_info.st_size,
                "full_vfs_path": str(full_vfs_path)
            }
            
        except Exception as e:
            logger.error(f"Error adding to VFS: {e}")
            return {"error": str(e)}

    async def remove_vfs_path(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """        Remove VFS path (mirrors 'ipfs-kit vfs rm')
        
        Arguments:
        - path: VFS path to remove
        - recursive: Remove recursively
        """
        vfs_path = arguments.get("path")
        recursive = arguments.get("recursive", False)

        try:
            if not vfs_path:
                return {"error": "path is required"}

            # Normalize VFS path
            if vfs_path.startswith("/"):
                vfs_path = vfs_path[1:]

            full_path = self.vfs_root / vfs_path

            if not full_path.exists():
                return {
                    "action": "remove_vfs_path",
                    "path": vfs_path,
                    "error": "path_not_found",
                    "message": f"VFS path '{vfs_path}' does not exist"
                }

            if full_path.is_dir() and not recursive:
                return {
                    "action": "remove_vfs_path",
                    "path": vfs_path,
                    "error": "is_a_directory",
                    "message": f"VFS path '{vfs_path}' is a directory (use recursive=true to remove)"
                }

            try:
                if full_path.is_dir():
                    import shutil
                    shutil.rmtree(full_path)
                else:
                    full_path.unlink()

                return {
                    "action": "remove_vfs_path",
                    "path": vfs_path,
                    "status": "removed",
                    "message": f"VFS path '{vfs_path}' removed successfully"
                }
            except OSError as e:
                return {
                    "action": "remove_vfs_path",
                    "path": vfs_path,
                    "error": "os_error",
                    "message": str(e)
                }

        except Exception as e:
            logger.error(f"Error removing VFS path: {e}")
            return {"error": str(e)}
