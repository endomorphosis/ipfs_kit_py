#!/usr/bin/env python3
"""
VFS Bridge for MCP Server

This module provides a bridge between MCP and virtual filesystem operations.
It includes tools for file management, directory operations, and content manipulation.
"""

import os
import sys
import json
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Configure logging
logger = logging.getLogger("vfs-bridge")

def register_vfs_tools(server):
    """Register virtual filesystem tools with the MCP server."""
    logger.info("Registering VFS tools...")
    registered_tools = []
    
    try:
        # Create a wrapper to handle different registration methods
        def register_tool(name, description):
            def decorator(func):
                if hasattr(server, 'tool'):
                    # Use the decorator pattern
                    return server.tool(name=name, description=description)(func)
                elif hasattr(server, 'register_tool'):
                    # Use the direct registration method
                    server.register_tool(name, description, func)
                    return func
                else:
                    logger.error(f"Server doesn't have tool or register_tool methods")
                    return func  # Return the function unchanged
            return decorator
        
        # Register vfs_list_files tool
        @register_tool(name="vfs_list_files", description="List files in a directory")
        async def vfs_list_files(ctx, path: str = ".", recursive: bool = False):
            """List files in a directory.
            
            Args:
                ctx: The MCP context
                path: Path to the directory to list
                recursive: Whether to list files recursively
                
            Returns:
                A dictionary containing the list of files
            """
            await ctx.info(f"Listing files in {path} (recursive={recursive})")
            
            try:
                # Check if the path exists
                if not os.path.exists(path):
                    await ctx.error(f"Path does not exist: {path}")
                    return {"error": f"Path does not exist: {path}"}
                
                # Check if the path is a directory
                if not os.path.isdir(path):
                    await ctx.error(f"Path is not a directory: {path}")
                    return {"error": f"Path is not a directory: {path}"}
                
                # List files
                file_list = []
                if recursive:
                    for root, dirs, files in os.walk(path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(file_path, path)
                            file_list.append({
                                "path": rel_path,
                                "size": os.path.getsize(file_path),
                                "is_dir": False,
                                "modified": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                            })
                        for dir_name in dirs:
                            dir_path = os.path.join(root, dir_name)
                            rel_path = os.path.relpath(dir_path, path)
                            file_list.append({
                                "path": rel_path,
                                "size": 0,
                                "is_dir": True,
                                "modified": datetime.fromtimestamp(os.path.getmtime(dir_path)).isoformat()
                            })
                else:
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        is_dir = os.path.isdir(item_path)
                        file_list.append({
                            "path": item,
                            "size": 0 if is_dir else os.path.getsize(item_path),
                            "is_dir": is_dir,
                            "modified": datetime.fromtimestamp(os.path.getmtime(item_path)).isoformat()
                        })
                
                await ctx.info(f"Listed {len(file_list)} files/directories")
                return {
                    "files": file_list,
                    "count": len(file_list),
                    "path": path
                }
            
            except Exception as e:
                error_msg = f"Error listing files: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        registered_tools.append('vfs_list_files')
        
        # Register vfs_read_file tool
        @register_tool(name="vfs_read_file", description="Read a file from the filesystem")
        async def vfs_read_file(ctx, path: str):
            """Read a file from the filesystem.
            
            Args:
                ctx: The MCP context
                path: Path to the file to read
                
            Returns:
                A dictionary containing the file content
            """
            await ctx.info(f"Reading file: {path}")
            
            try:
                # Check if the file exists
                if not os.path.exists(path):
                    await ctx.error(f"File does not exist: {path}")
                    return {"error": f"File does not exist: {path}"}
                
                # Check if the path is a file
                if not os.path.isfile(path):
                    await ctx.error(f"Path is not a file: {path}")
                    return {"error": f"Path is not a file: {path}"}
                
                # Read the file
                with open(path, 'rb') as f:
                    content = f.read()
                
                # Try to decode as utf-8 if it seems to be text
                is_text = True
                try:
                    text_content = content.decode('utf-8')
                except UnicodeDecodeError:
                    # It's binary data
                    text_content = content.hex()
                    is_text = False
                
                file_info = {
                    "name": os.path.basename(path),
                    "path": path,
                    "size": os.path.getsize(path),
                    "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
                    "is_text": is_text
                }
                
                await ctx.info(f"Read file: {path} ({file_info['size']} bytes)")
                
                if is_text:
                    return {
                        "content": text_content,
                        "file_info": file_info
                    }
                else:
                    return {
                        "content_hex": text_content,
                        "file_info": file_info
                    }
            
            except Exception as e:
                error_msg = f"Error reading file: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        registered_tools.append('vfs_read_file')
        
        # Register vfs_write_file tool
        @register_tool(name="vfs_write_file", description="Write content to a file")
        async def vfs_write_file(ctx, path: str, content: str, create_dirs: bool = True):
            """Write content to a file.
            
            Args:
                ctx: The MCP context
                path: Path to the file to write
                content: Content to write to the file
                create_dirs: Whether to create parent directories if they don't exist
                
            Returns:
                A dictionary containing the result of the operation
            """
            await ctx.info(f"Writing to file: {path}")
            
            try:
                # Create parent directories if needed
                if create_dirs:
                    dir_path = os.path.dirname(path)
                    if dir_path and not os.path.exists(dir_path):
                        os.makedirs(dir_path)
                        await ctx.info(f"Created directory: {dir_path}")
                
                # Write the file
                content_bytes = content.encode('utf-8') if isinstance(content, str) else content
                with open(path, 'wb') as f:
                    f.write(content_bytes)
                
                file_info = {
                    "name": os.path.basename(path),
                    "path": path,
                    "size": os.path.getsize(path),
                    "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
                }
                
                await ctx.info(f"Wrote {file_info['size']} bytes to file: {path}")
                return {
                    "success": True,
                    "file_info": file_info
                }
            
            except Exception as e:
                error_msg = f"Error writing file: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        registered_tools.append('vfs_write_file')
        
        # Register vfs_delete_file tool
        @register_tool(name="vfs_delete_file", description="Delete a file from the filesystem")
        async def vfs_delete_file(ctx, path: str):
            """Delete a file from the filesystem.
            
            Args:
                ctx: The MCP context
                path: Path to the file to delete
                
            Returns:
                A dictionary containing the result of the operation
            """
            await ctx.info(f"Deleting file: {path}")
            
            try:
                # Check if the file exists
                if not os.path.exists(path):
                    await ctx.error(f"File does not exist: {path}")
                    return {"error": f"File does not exist: {path}"}
                
                # Check if the path is a file
                if not os.path.isfile(path):
                    await ctx.error(f"Path is not a file: {path}")
                    return {"error": f"Path is not a file: {path}"}
                
                # Store file info before deletion
                file_info = {
                    "name": os.path.basename(path),
                    "path": path,
                    "size": os.path.getsize(path),
                    "modified": datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
                }
                
                # Delete the file
                os.remove(path)
                
                await ctx.info(f"Deleted file: {path}")
                return {
                    "success": True,
                    "file_info": file_info
                }
            
            except Exception as e:
                error_msg = f"Error deleting file: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        registered_tools.append('vfs_delete_file')
        
        # Register vfs_create_directory tool
        @register_tool(name="vfs_create_directory", description="Create a directory")
        async def vfs_create_directory(ctx, path: str):
            """Create a directory.
            
            Args:
                ctx: The MCP context
                path: Path to the directory to create
                
            Returns:
                A dictionary containing the result of the operation
            """
            await ctx.info(f"Creating directory: {path}")
            
            try:
                # Check if the directory already exists
                if os.path.exists(path):
                    if os.path.isdir(path):
                        await ctx.warning(f"Directory already exists: {path}")
                        return {
                            "success": True,
                            "already_exists": True,
                            "path": path
                        }
                    else:
                        await ctx.error(f"Path exists but is not a directory: {path}")
                        return {"error": f"Path exists but is not a directory: {path}"}
                
                # Create the directory
                os.makedirs(path)
                
                await ctx.info(f"Created directory: {path}")
                return {
                    "success": True,
                    "already_exists": False,
                    "path": path
                }
            
            except Exception as e:
                error_msg = f"Error creating directory: {str(e)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                await ctx.error(error_msg)
                return {"error": error_msg}
        
        registered_tools.append('vfs_create_directory')
        
        logger.info(f"Registered {len(registered_tools)} VFS tools: {', '.join(registered_tools)}")
        return registered_tools
    except Exception as e:
        logger.error(f"Error registering VFS tools: {e}")
        logger.error(traceback.format_exc())
        return []

if __name__ == "__main__":
    print("This module is not meant to be run directly.")
    print("Import it and call register_vfs_tools(server) to register tools.")
