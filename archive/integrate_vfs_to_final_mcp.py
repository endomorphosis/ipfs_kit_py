#!/usr/bin/env python3
"""
Virtual Filesystem Integration Module

This module provides functions to register virtual filesystem tools with an MCP server.
It bridges the gap between the filesystem and IPFS, allowing for seamless operations.
"""

import os
import sys
import json
import logging
import importlib.util
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vfs-integration")

def register_vfs_tools(server) -> bool:
    """
    Register virtual filesystem tools with the MCP server.
    
    Args:
        server: The MCP server instance
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    logger.info("Registering virtual filesystem tools with MCP server...")
    
    # Try importing fs_journal_tools as a backup
    try:
        import fs_journal_tools
        journal_result = fs_journal_tools.register_tools(server)
        if journal_result:
            logger.info("Successfully registered filesystem journal tools")
    except Exception as e:
        logger.error(f"Failed to register filesystem journal tools: {e}")
    
    # Register virtual filesystem basic tools
    registered_tools = register_basic_vfs_tools(server)
    
    logger.info(f"Registered {len(registered_tools)} virtual filesystem tools")
    return len(registered_tools) > 0

def register_basic_vfs_tools(server) -> List[str]:
    """
    Register basic virtual filesystem tools with the server.
    This provides core VFS functionality.
    
    Args:
        server: The MCP server instance
        
    Returns:
        List[str]: Names of registered tools
    """
    logger.info("Registering basic virtual filesystem tools...")
    
    registered_tools = []
    
    # Tool: Create a file in the virtual filesystem
    @server.tool("vfs_create_file")
    async def vfs_create_file(ctx, path: str, content: str):
        """Create a file in the virtual filesystem"""
        try:
            # Ensure the directory exists
            dir_path = os.path.dirname(os.path.abspath(path))
            os.makedirs(dir_path, exist_ok=True)
            
            # Write content to file
            with open(path, 'w') as f:
                f.write(content)
            
            return {
                "success": True,
                "path": path,
                "size": len(content),
                "message": f"File created successfully at {path}"
            }
        except Exception as e:
            logger.error(f"Error creating file {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_create_file")
    
    # Tool: Read a file from the virtual filesystem
    @server.tool("vfs_read_file")
    async def vfs_read_file(ctx, path: str):
        """Read a file from the virtual filesystem"""
        try:
            # Check if file exists
            if not os.path.isfile(path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Read file content
            with open(path, 'r') as f:
                content = f.read()
            
            return {
                "success": True,
                "path": path,
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_read_file")
    
    # Tool: Delete a file from the virtual filesystem
    @server.tool("vfs_delete_file")
    async def vfs_delete_file(ctx, path: str):
        """Delete a file from the virtual filesystem"""
        try:
            # Check if file exists
            if not os.path.isfile(path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Delete the file
            os.remove(path)
            
            return {
                "success": True,
                "path": path,
                "message": f"File deleted successfully: {path}"
            }
        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_delete_file")
    
    # Tool: List directory contents
    @server.tool("vfs_list_directory")
    async def vfs_list_directory(ctx, path: str, recursive: bool = False):
        """List contents of a directory in the virtual filesystem"""
        try:
            # Check if directory exists
            if not os.path.isdir(path):
                return {
                    "success": False,
                    "error": f"Directory not found: {path}"
                }
            
            if recursive:
                # Recursive listing
                file_list = []
                dir_list = []
                
                for root, dirs, files in os.walk(path):
                    # Add directories with relative paths
                    for d in dirs:
                        dir_path = os.path.join(root, d)
                        rel_path = os.path.relpath(dir_path, path)
                        dir_list.append({
                            "path": rel_path,
                            "type": "directory",
                            "full_path": dir_path
                        })
                    
                    # Add files with relative paths
                    for f in files:
                        file_path = os.path.join(root, f)
                        rel_path = os.path.relpath(file_path, path)
                        try:
                            file_size = os.path.getsize(file_path)
                        except:
                            file_size = 0
                        
                        file_list.append({
                            "path": rel_path,
                            "type": "file",
                            "size": file_size,
                            "full_path": file_path
                        })
                
                return {
                    "success": True,
                    "path": path,
                    "directories": dir_list,
                    "files": file_list,
                    "count": len(dir_list) + len(file_list)
                }
            else:
                # Non-recursive listing
                dir_list = []
                file_list = []
                
                for entry in os.listdir(path):
                    entry_path = os.path.join(path, entry)
                    
                    if os.path.isdir(entry_path):
                        dir_list.append({
                            "name": entry,
                            "type": "directory",
                            "path": entry_path
                        })
                    else:
                        try:
                            file_size = os.path.getsize(entry_path)
                        except:
                            file_size = 0
                        
                        file_list.append({
                            "name": entry,
                            "type": "file",
                            "size": file_size,
                            "path": entry_path
                        })
                
                return {
                    "success": True,
                    "path": path,
                    "directories": dir_list,
                    "files": file_list,
                    "count": len(dir_list) + len(file_list)
                }
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_list_directory")
    
    # Tool: Create a directory in the virtual filesystem
    @server.tool("vfs_create_directory")
    async def vfs_create_directory(ctx, path: str):
        """Create a directory in the virtual filesystem"""
        try:
            # Create the directory
            os.makedirs(path, exist_ok=True)
            
            return {
                "success": True,
                "path": path,
                "message": f"Directory created successfully: {path}"
            }
        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_create_directory")
    
    # Tool: Copy a file or directory
    @server.tool("vfs_copy")
    async def vfs_copy(ctx, source: str, destination: str):
        """Copy a file or directory in the virtual filesystem"""
        try:
            import shutil
            
            # Check if source exists
            if not os.path.exists(source):
                return {
                    "success": False,
                    "error": f"Source not found: {source}"
                }
            
            # Create destination directory if needed
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            
            if os.path.isdir(source):
                # Copy directory
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                # Copy file
                shutil.copy2(source, destination)
            
            return {
                "success": True,
                "source": source,
                "destination": destination,
                "message": f"Successfully copied {source} to {destination}"
            }
        except Exception as e:
            logger.error(f"Error copying {source} to {destination}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_copy")
    
    # Tool: Move a file or directory
    @server.tool("vfs_move")
    async def vfs_move(ctx, source: str, destination: str):
        """Move a file or directory in the virtual filesystem"""
        try:
            import shutil
            
            # Check if source exists
            if not os.path.exists(source):
                return {
                    "success": False,
                    "error": f"Source not found: {source}"
                }
            
            # Create destination directory if needed
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            
            # Move file or directory
            shutil.move(source, destination)
            
            return {
                "success": True,
                "source": source,
                "destination": destination,
                "message": f"Successfully moved {source} to {destination}"
            }
        except Exception as e:
            logger.error(f"Error moving {source} to {destination}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_move")
    
    # Tool: Get file metadata
    @server.tool("vfs_get_metadata")
    async def vfs_get_metadata(ctx, path: str):
        """Get metadata for a file or directory"""
        try:
            # Check if path exists
            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path not found: {path}"
                }
            
            # Gather metadata
            stat_info = os.stat(path)
            
            metadata = {
                "path": path,
                "type": "directory" if os.path.isdir(path) else "file",
                "size": stat_info.st_size,
                "creation_time": stat_info.st_ctime,
                "last_modified": stat_info.st_mtime,
                "last_accessed": stat_info.st_atime,
                "exists": True
            }
            
            if not os.path.isdir(path):
                # Additional file-specific metadata
                metadata["extension"] = os.path.splitext(path)[1]
                metadata["filename"] = os.path.basename(path)
            
            return {
                "success": True,
                "metadata": metadata
            }
        except Exception as e:
            logger.error(f"Error getting metadata for {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_get_metadata")
    
    logger.info(f"Registered {len(registered_tools)} basic VFS tools")
    return registered_tools

if __name__ == "__main__":
    print("This module is meant to be imported, not run directly.")
    sys.exit(1)
