#!/usr/bin/env python3
"""
IPFS-FS Bridge Integration for IPFS Kit

This module provides integration between IPFS and the local filesystem,
enabling seamless operations across both systems.
"""

import os
import sys
import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global mapping between IPFS paths and filesystem paths
_path_mappings: Dict[str, Dict[str, Any]] = {}

def register_integration_tools(mcp_server) -> bool:
    """
    Register IPFS-FS Bridge tools with the MCP server.
    
    Args:
        mcp_server: The MCP server instance
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    logger.info("Registering IPFS-FS Bridge tools with MCP server...")
    
    async def ipfs_fs_bridge_status() -> Dict[str, Any]:
        """Get status of the IPFS-FS bridge"""
        logger.info("MCP Tool call: ipfs_fs_bridge_status()")
        
        try:
            # Count mappings by type
            dir_mappings = 0
            file_mappings = 0
            
            for mapping_info in _path_mappings.values():
                if mapping_info.get("is_directory", False):
                    dir_mappings += 1
                else:
                    file_mappings += 1
            
            return {
                "success": True,
                "active": True,
                "mappings_count": len(_path_mappings),
                "directory_mappings": dir_mappings,
                "file_mappings": file_mappings,
                "last_sync": _get_last_sync_time()
            }
                
        except Exception as e:
            logger.error(f"Error getting bridge status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def ipfs_fs_bridge_map(fs_path: str, ipfs_path: Optional[str] = None, 
                               recursive: bool = False) -> Dict[str, Any]:
        """Map a filesystem path to an IPFS path"""
        logger.info(f"MCP Tool call: ipfs_fs_bridge_map(fs_path={fs_path}, ipfs_path={ipfs_path}, recursive={recursive})")
        
        try:
            abs_fs_path = os.path.abspath(fs_path)
            
            if not os.path.exists(abs_fs_path):
                return {
                    "success": False,
                    "error": f"Filesystem path does not exist: {fs_path}"
                }
            
            # Generate IPFS path if not provided
            if ipfs_path is None:
                base_name = os.path.basename(abs_fs_path)
                ipfs_path = f"/ipfs-fs/{base_name}"
            
            # Normalize IPFS path
            if not ipfs_path.startswith("/"):
                ipfs_path = f"/{ipfs_path}"
            
            # Create mapping
            is_dir = os.path.isdir(abs_fs_path)
            mapping_key = abs_fs_path
            
            _path_mappings[mapping_key] = {
                "fs_path": abs_fs_path,
                "ipfs_path": ipfs_path,
                "is_directory": is_dir,
                "mapped_at": asyncio.get_event_loop().time(),
                "last_sync": None,
                "recursive": recursive
            }
            
            mapped_paths = [mapping_key]
            
            # If recursive and path is a directory, map all children
            if recursive and is_dir:
                for root, dirs, files in os.walk(abs_fs_path):
                    rel_path = os.path.relpath(root, abs_fs_path)
                    if rel_path == ".":
                        rel_path = ""
                    
                    # Map directories
                    for dir_name in dirs:
                        dir_fs_path = os.path.join(root, dir_name)
                        dir_ipfs_path = os.path.join(ipfs_path, rel_path, dir_name).replace("\\", "/")
                        
                        _path_mappings[dir_fs_path] = {
                            "fs_path": dir_fs_path,
                            "ipfs_path": dir_ipfs_path,
                            "is_directory": True,
                            "mapped_at": asyncio.get_event_loop().time(),
                            "last_sync": None,
                            "recursive": False,  # Only top-level is marked recursive
                            "parent": abs_fs_path
                        }
                        mapped_paths.append(dir_fs_path)
                    
                    # Map files
                    for file_name in files:
                        file_fs_path = os.path.join(root, file_name)
                        file_ipfs_path = os.path.join(ipfs_path, rel_path, file_name).replace("\\", "/")
                        
                        _path_mappings[file_fs_path] = {
                            "fs_path": file_fs_path,
                            "ipfs_path": file_ipfs_path,
                            "is_directory": False,
                            "mapped_at": asyncio.get_event_loop().time(),
                            "last_sync": None,
                            "recursive": False,  # Only top-level is marked recursive
                            "parent": abs_fs_path
                        }
                        mapped_paths.append(file_fs_path)
            
            logger.info(f"Mapped {len(mapped_paths)} paths")
            
            return {
                "success": True,
                "fs_path": fs_path,
                "ipfs_path": ipfs_path,
                "is_directory": is_dir,
                "recursive": recursive,
                "mapped_paths": len(mapped_paths)
            }
                
        except Exception as e:
            logger.error(f"Error mapping path: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def ipfs_fs_bridge_unmap(fs_path: str, recursive: bool = True) -> Dict[str, Any]:
        """Unmap a filesystem path from IPFS"""
        logger.info(f"MCP Tool call: ipfs_fs_bridge_unmap(fs_path={fs_path}, recursive={recursive})")
        
        try:
            abs_fs_path = os.path.abspath(fs_path)
            
            if abs_fs_path not in _path_mappings:
                return {
                    "success": False,
                    "error": f"Path is not mapped: {fs_path}"
                }
            
            # Get mapping info
            mapping_info = _path_mappings[abs_fs_path]
            is_dir = mapping_info.get("is_directory", False)
            
            # Remove this mapping
            del _path_mappings[abs_fs_path]
            unmapped_paths = 1
            
            # If recursive, remove all child mappings
            if recursive and is_dir:
                child_paths = []
                for path, info in list(_path_mappings.items()):
                    if info.get("parent") == abs_fs_path:
                        child_paths.append(path)
                
                for path in child_paths:
                    del _path_mappings[path]
                    unmapped_paths += 1
            
            logger.info(f"Unmapped {unmapped_paths} paths")
            
            return {
                "success": True,
                "fs_path": fs_path,
                "ipfs_path": mapping_info.get("ipfs_path"),
                "unmapped_paths": unmapped_paths
            }
                
        except Exception as e:
            logger.error(f"Error unmapping path: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def ipfs_fs_bridge_list_mappings(include_children: bool = False) -> Dict[str, Any]:
        """List all mapped paths"""
        logger.info(f"MCP Tool call: ipfs_fs_bridge_list_mappings(include_children={include_children})")
        
        try:
            mappings = []
            
            for fs_path, info in _path_mappings.items():
                # Skip child mappings if not requested
                if not include_children and "parent" in info:
                    continue
                
                mapping = {
                    "fs_path": fs_path,
                    "ipfs_path": info.get("ipfs_path"),
                    "is_directory": info.get("is_directory", False),
                    "mapped_at": info.get("mapped_at"),
                    "last_sync": info.get("last_sync")
                }
                
                if "parent" in info:
                    mapping["parent"] = info["parent"]
                
                mappings.append(mapping)
            
            return {
                "success": True,
                "mappings": mappings,
                "count": len(mappings)
            }
                
        except Exception as e:
            logger.error(f"Error listing mappings: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def ipfs_fs_bridge_sync(fs_path: Optional[str] = None) -> Dict[str, Any]:
        """Synchronize filesystem changes to IPFS"""
        if fs_path:
            logger.info(f"MCP Tool call: ipfs_fs_bridge_sync(fs_path={fs_path})")
        else:
            logger.info("MCP Tool call: ipfs_fs_bridge_sync()")
        
        try:
            # If path specified, sync only that path
            if fs_path:
                abs_fs_path = os.path.abspath(fs_path)
                
                if abs_fs_path not in _path_mappings:
                    return {
                        "success": False,
                        "error": f"Path is not mapped: {fs_path}"
                    }
                
                paths_to_sync = [abs_fs_path]
                
                # If this is a directory with recursive mapping, include all children
                mapping_info = _path_mappings[abs_fs_path]
                if mapping_info.get("is_directory", False) and mapping_info.get("recursive", False):
                    for path, info in _path_mappings.items():
                        if info.get("parent") == abs_fs_path:
                            paths_to_sync.append(path)
            else:
                # Sync all mapped paths (only top-level ones with recursive flag)
                paths_to_sync = []
                for path, info in _path_mappings.items():
                    if not info.get("parent"):  # Only top-level mappings
                        paths_to_sync.append(path)
            
            # Mock sync operation - in a real implementation, this would:
            # 1. Check for changes in the filesystem
            # 2. Upload changed files to IPFS
            # 3. Update the IPFS directory structure
            # 4. Update last_sync timestamp
            
            sync_time = asyncio.get_event_loop().time()
            sync_results = {}
            
            for path in paths_to_sync:
                if path in _path_mappings:  # Check again in case it was unmapped during sync
                    _path_mappings[path]["last_sync"] = sync_time
                    sync_results[path] = "synced"
            
            logger.info(f"Synchronized {len(sync_results)} paths")
            
            return {
                "success": True,
                "synced_paths": len(sync_results),
                "details": sync_results
            }
                
        except Exception as e:
            logger.error(f"Error synchronizing paths: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Register all tools with the MCP server
    try:
        mcp_server.add_tool(ipfs_fs_bridge_status, name="ipfs_fs_bridge_status")
        mcp_server.add_tool(ipfs_fs_bridge_map, name="ipfs_fs_bridge_map")
        mcp_server.add_tool(ipfs_fs_bridge_unmap, name="ipfs_fs_bridge_unmap")
        mcp_server.add_tool(ipfs_fs_bridge_list_mappings, name="ipfs_fs_bridge_list_mappings")
        mcp_server.add_tool(ipfs_fs_bridge_sync, name="ipfs_fs_bridge_sync")
        
        logger.info("✅ Successfully registered IPFS-FS Bridge tools")
        return True
    except Exception as e:
        logger.error(f"Error registering IPFS-FS Bridge tools: {e}")
        return False

# Alias function for compatibility with the MCP server
def register_with_mcp_server(mcp_server) -> bool:
    """
    Register IPFS-FS Bridge tools with the MCP server.
    This is an alias for register_integration_tools() to match server expectations.
    
    Args:
        mcp_server: The MCP server instance to register tools with
        
    Returns:
        bool: True if registration successful, False otherwise
    """
    return register_integration_tools(mcp_server)

def _get_last_sync_time() -> Optional[float]:
    """Get the timestamp of the last sync across all mappings"""
    if not _path_mappings:
        return None
    
    # Explicitly filter to float values only
    sync_times: List[float] = []
    for info in _path_mappings.values():
        sync_time = info.get("last_sync")
        if isinstance(sync_time, (int, float)) and sync_time is not None:
            sync_times.append(float(sync_time))
    
    if not sync_times:
        return None
    
    return max(sync_times)

if __name__ == "__main__":
    print("This module should be imported and used with an MCP server, not run directly.")
    sys.exit(1)
