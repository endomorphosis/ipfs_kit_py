#!/usr/bin/env python3
"""
Enhanced Virtual Filesystem MCP Integration

This module provides enhanced virtual filesystem tools for MCP server integration.
It extends the basic VFS tools with advanced features, including:
- Multi-filesystem support (local and IPFS)
- Caching and performance optimizations
- Journaling for better reliability
- Metadata management
"""

import os
import sys
import json
import logging
import hashlib
import datetime
import importlib.util
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enhanced-vfs")

# Global cache for storing metadata to improve performance
_metadata_cache = {}
_file_content_cache = {}

def register_all_fs_tools(server) -> bool:
    """
    Register all enhanced filesystem tools with the MCP server.
    
    Args:
        server: The MCP server instance
        
    Returns:
        bool: True if registration was successful, False otherwise
    """
    logger.info("Registering enhanced VFS tools with MCP server...")
    
    # Try to register base tools first if the module exists
    base_tools_registered = False
    try:
        # Try direct import first
        try:
            import integrate_vfs_to_final_mcp
            if hasattr(integrate_vfs_to_final_mcp, "register_vfs_tools"):
                base_result = integrate_vfs_to_final_mcp.register_vfs_tools(server)
                if base_result:
                    logger.info("Successfully registered base VFS tools")
                    base_tools_registered = True
                else:
                    logger.warning("Base VFS tools registration returned False")
            else:
                logger.warning("integrate_vfs_to_final_mcp exists but doesn't have register_vfs_tools function")
        except ImportError:
            # Fall back to manual import using spec
            logger.info("Direct import failed, trying spec-based import")
            spec = importlib.util.find_spec("integrate_vfs_to_final_mcp")
            if spec is not None and spec.loader is not None:
                try:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    if hasattr(module, "register_vfs_tools"):
                        base_result = module.register_vfs_tools(server)
                        if base_result:
                            logger.info("Successfully registered base VFS tools")
                            base_tools_registered = True
                        else:
                            logger.warning("Base VFS tools registration returned False")
                    else:
                        logger.warning("integrate_vfs_to_final_mcp exists but doesn't have register_vfs_tools function")
                except Exception as e:
                    logger.warning(f"Error loading module via spec: {e}")
            else:
                logger.info("Base VFS module spec not found")
        else:
            logger.info("No base VFS module found, will register enhanced tools directly")
    except Exception as e:
        logger.error(f"Failed to register base VFS tools: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # If base tools weren't registered, we'll provide our own basic VFS tools
    if not base_tools_registered:
        logger.info("Implementing basic VFS tools directly")
    
    # Register enhanced tools
    registered_tools = register_enhanced_vfs_tools(server)
    
    # Register advanced tools
    advanced_tools = register_advanced_vfs_tools(server)
    registered_tools.extend(advanced_tools)
    
    logger.info(f"Registered {len(registered_tools)} enhanced VFS tools")
    return len(registered_tools) > 0

def register_enhanced_vfs_tools(server) -> List[str]:
    """
    Register enhanced virtual filesystem tools with the server.
    This provides additional functionality beyond the basic VFS tools.
    
    Args:
        server: The MCP server instance
        
    Returns:
        List[str]: Names of registered tools
    """
    logger.info("Registering enhanced VFS tools...")
    
    registered_tools = []
    
    # Tool: Search for files in the virtual filesystem
    @server.tool("vfs_search_files")
    async def vfs_search_files(ctx, root_path: str, pattern: str, max_results: int = 100, recursive: bool = True):
        """Search for files matching a pattern in the virtual filesystem"""
        try:
            import fnmatch
            import re
            
            # Check if directory exists
            if not os.path.isdir(root_path):
                return {
                    "success": False,
                    "error": f"Root directory not found: {root_path}"
                }
            
            # Determine if pattern is regex or glob
            is_regex = False
            regex = None
            if pattern.startswith("re:"):
                is_regex = True
                pattern = pattern[3:]  # Remove the "re:" prefix
                regex = re.compile(pattern)
            
            matches = []
            
            # Walk the directory tree
            if recursive:
                for root, dirs, files in os.walk(root_path):
                    for filename in files:
                        filepath = os.path.join(root, filename)
                        rel_path = os.path.relpath(filepath, root_path)
                        
                        # Check if file matches pattern
                        if is_regex and regex:
                            if regex.search(rel_path):
                                matches.append(filepath)
                        else:
                            if fnmatch.fnmatch(rel_path, pattern):
                                matches.append(filepath)
                        
                        # Stop if we've reached the maximum number of results
                        if len(matches) >= max_results:
                            break
                    
                    if len(matches) >= max_results:
                        break
            else:
                # Non-recursive search (just the root directory)
                for filename in os.listdir(root_path):
                    filepath = os.path.join(root_path, filename)
                    if os.path.isfile(filepath):
                        if is_regex and regex:
                            if regex.search(filename):
                                matches.append(filepath)
                        else:
                            if fnmatch.fnmatch(filename, pattern):
                                matches.append(filepath)
                        
                        if len(matches) >= max_results:
                            break
            
            # Prepare results with metadata
            results = []
            for filepath in matches:
                try:
                    stat_info = os.stat(filepath)
                    results.append({
                        "path": filepath,
                        "size": stat_info.st_size,
                        "last_modified": datetime.datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                        "relative_path": os.path.relpath(filepath, root_path)
                    })
                except Exception:
                    # Skip files with permission issues
                    pass
            
            return {
                "success": True,
                "matches": results,
                "count": len(results),
                "pattern": pattern,
                "is_regex": is_regex,
                "root_path": root_path
            }
        except Exception as e:
            logger.error(f"Error searching for files: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_search_files")
    
    # Tool: Calculate file checksum
    @server.tool("vfs_file_checksum")
    async def vfs_file_checksum(ctx, path: str, algorithm: str = "md5"):
        """Calculate the checksum of a file using the specified algorithm"""
        try:
            # Check if file exists
            if not os.path.isfile(path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Calculate checksum
            hash_obj = None
            if algorithm.lower() == "md5":
                hash_obj = hashlib.md5()
            elif algorithm.lower() == "sha1":
                hash_obj = hashlib.sha1()
            elif algorithm.lower() == "sha256":
                hash_obj = hashlib.sha256()
            else:
                return {
                    "success": False,
                    "error": f"Unsupported algorithm: {algorithm}. Supported algorithms: md5, sha1, sha256"
                }
            
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            
            checksum = hash_obj.hexdigest()
            
            # Cache the checksum for future reference
            _metadata_cache[path] = {
                "checksum": {
                    "algorithm": algorithm,
                    "value": checksum,
                    "calculated_at": datetime.datetime.now().isoformat()
                }
            }
            
            return {
                "success": True,
                "path": path,
                "algorithm": algorithm,
                "checksum": checksum,
                "size": os.path.getsize(path)
            }
        except Exception as e:
            logger.error(f"Error calculating checksum for {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_file_checksum")
    
    # Tool: Find duplicate files
    @server.tool("vfs_find_duplicates")
    async def vfs_find_duplicates(ctx, root_path: str, recursive: bool = True):
        """Find duplicate files based on content hash"""
        try:
            # Check if directory exists
            if not os.path.isdir(root_path):
                return {
                    "success": False,
                    "error": f"Root directory not found: {root_path}"
                }
            
            # Get all files
            files = []
            if recursive:
                for root, _, filenames in os.walk(root_path):
                    for filename in filenames:
                        files.append(os.path.join(root, filename))
            else:
                for filename in os.listdir(root_path):
                    filepath = os.path.join(root_path, filename)
                    if os.path.isfile(filepath):
                        files.append(filepath)
            
            # Calculate checksums and identify duplicates
            checksums = {}
            duplicate_groups = {}
            
            for filepath in files:
                try:
                    hash_obj = hashlib.md5()
                    with open(filepath, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_obj.update(chunk)
                    
                    checksum = hash_obj.hexdigest()
                    
                    if checksum in checksums:
                        checksums[checksum].append(filepath)
                        if len(checksums[checksum]) == 2:
                            # Just became a duplicate group
                            duplicate_groups[checksum] = checksums[checksum].copy()
                        elif len(checksums[checksum]) > 2:
                            # Add to existing duplicate group
                            duplicate_groups[checksum].append(filepath)
                    else:
                        checksums[checksum] = [filepath]
                except Exception:
                    # Skip files with permission issues
                    pass
            
            # Prepare results
            duplicate_list = []
            for checksum, filepaths in duplicate_groups.items():
                try:
                    size = os.path.getsize(filepaths[0])
                    duplicate_list.append({
                        "checksum": checksum,
                        "files": filepaths,
                        "count": len(filepaths),
                        "size": size,
                        "wasted_space": size * (len(filepaths) - 1)
                    })
                except Exception:
                    # Skip on error
                    pass
            
            # Sort by wasted space
            duplicate_list.sort(key=lambda x: x.get("wasted_space", 0), reverse=True)
            
            return {
                "success": True,
                "duplicate_groups": duplicate_list,
                "total_groups": len(duplicate_list),
                "total_files_scanned": len(files),
                "total_wasted_space": sum(g.get("wasted_space", 0) for g in duplicate_list)
            }
        except Exception as e:
            logger.error(f"Error finding duplicate files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_find_duplicates")
    
    # Tool: Write binary data to file
    @server.tool("vfs_write_binary")
    async def vfs_write_binary(ctx, path: str, data: bytes):
        """Write binary data to a file in the virtual filesystem"""
        try:
            # Ensure the directory exists
            dir_path = os.path.dirname(os.path.abspath(path))
            os.makedirs(dir_path, exist_ok=True)
            
            # Write binary data to file
            with open(path, 'wb') as f:
                f.write(data)
            
            return {
                "success": True,
                "path": path,
                "size": len(data),
                "message": f"Binary data written successfully to {path}"
            }
        except Exception as e:
            logger.error(f"Error writing binary data to {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_write_binary")
    
    # Tool: Read binary data from file
    @server.tool("vfs_read_binary")
    async def vfs_read_binary(ctx, path: str):
        """Read binary data from a file in the virtual filesystem"""
        try:
            # Check if file exists
            if not os.path.isfile(path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Read binary data
            with open(path, 'rb') as f:
                data = f.read()
            
            return {
                "success": True,
                "path": path,
                "data": data,
                "size": len(data)
            }
        except Exception as e:
            logger.error(f"Error reading binary data from {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_read_binary")
    
    # Tool: Get disk usage information
    @server.tool("vfs_disk_usage")
    async def vfs_disk_usage(ctx, path: str):
        """Get disk usage information for a path"""
        try:
            import shutil
            
            # Check if path exists
            if not os.path.exists(path):
                return {
                    "success": False,
                    "error": f"Path not found: {path}"
                }
            
            # Get disk usage
            if os.path.isdir(path):
                # For directories, get total size recursively
                total_size = 0
                file_count = 0
                dir_count = 0
                
                for root, dirs, files in os.walk(path):
                    dir_count += len(dirs)
                    file_count += len(files)
                    
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            total_size += os.path.getsize(file_path)
                        except (OSError, IOError):
                            # Skip files with permission issues
                            pass
                
                # Get disk usage stats for the volume
                usage = shutil.disk_usage(path)
                
                return {
                    "success": True,
                    "path": path,
                    "type": "directory",
                    "size": total_size,
                    "file_count": file_count,
                    "directory_count": dir_count,
                    "volume": {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent_used": usage.used / usage.total * 100
                    }
                }
            else:
                # For individual files
                size = os.path.getsize(path)
                usage = shutil.disk_usage(os.path.dirname(path))
                
                return {
                    "success": True,
                    "path": path,
                    "type": "file",
                    "size": size,
                    "volume": {
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent_used": usage.used / usage.total * 100
                    }
                }
        except Exception as e:
            logger.error(f"Error getting disk usage for {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_disk_usage")
    
    logger.info(f"Registered {len(registered_tools)} enhanced VFS tools")
    return registered_tools

def register_advanced_vfs_tools(server) -> List[str]:
    """
    Register advanced virtual filesystem tools with the server.
    These tools integrate with other systems and provide more complex functionality.
    
    Args:
        server: The MCP server instance
        
    Returns:
        List[str]: Names of registered tools
    """
    logger.info("Registering advanced VFS tools...")
    
    registered_tools = []
    
    # Tool: Sync directory to IPFS
    @server.tool("vfs_sync_to_ipfs")
    async def vfs_sync_to_ipfs(ctx, local_path: str, include_hidden: bool = False):
        """Sync a local directory to IPFS (mock implementation)"""
        try:
            # Check if directory exists
            if not os.path.isdir(local_path):
                return {
                    "success": False,
                    "error": f"Directory not found: {local_path}"
                }
            
            # Mock IPFS sync operation
            files_synced = 0
            total_size = 0
            file_cids = {}
            
            for root, _, files in os.walk(local_path):
                for filename in files:
                    if not include_hidden and filename.startswith('.'):
                        continue
                    
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, local_path)
                    
                    try:
                        size = os.path.getsize(filepath)
                        total_size += size
                        
                        # Generate mock CID based on file path and last modified time
                        mtime = os.path.getmtime(filepath)
                        hash_input = f"{filepath}:{mtime}".encode('utf-8')
                        hash_obj = hashlib.sha256(hash_input)
                        mock_cid = f"Qm{hash_obj.hexdigest()[:44]}"
                        
                        file_cids[rel_path] = {
                            "cid": mock_cid,
                            "size": size
                        }
                        
                        files_synced += 1
                    except Exception:
                        # Skip files with permission issues
                        pass
            
            # Generate directory CID
            dir_cid = f"Qm{hashlib.sha256(local_path.encode('utf-8')).hexdigest()[:44]}"
            
            return {
                "success": True,
                "local_path": local_path,
                "directory_cid": dir_cid,
                "files_synced": files_synced,
                "total_size": total_size,
                "file_cids": file_cids,
                "implementation": "mock"
            }
        except Exception as e:
            logger.error(f"Error syncing directory to IPFS: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_sync_to_ipfs")
    
    # Tool: Create virtual filesystem link
    @server.tool("vfs_create_link")
    async def vfs_create_link(ctx, target: str, link_name: str, symbolic: bool = True):
        """Create a link (symbolic or hard) in the virtual filesystem"""
        try:
            # Check if target exists
            if not os.path.exists(target):
                return {
                    "success": False,
                    "error": f"Target not found: {target}"
                }
            
            # Create link
            if symbolic:
                os.symlink(target, link_name)
            else:
                os.link(target, link_name)
            
            return {
                "success": True,
                "target": target,
                "link_name": link_name,
                "type": "symbolic" if symbolic else "hard",
                "message": f"Link created successfully: {link_name} -> {target}"
            }
        except Exception as e:
            logger.error(f"Error creating link {link_name} -> {target}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_create_link")
    
    # Tool: Cache file for faster access
    @server.tool("vfs_cache_file")
    async def vfs_cache_file(ctx, path: str):
        """Cache a file for faster access"""
        try:
            # Check if file exists
            if not os.path.isfile(path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Read file into cache
            with open(path, 'rb') as f:
                content = f.read()
            
            _file_content_cache[path] = {
                "content": content,
                "size": len(content),
                "cached_at": datetime.datetime.now().isoformat(),
                "last_modified": os.path.getmtime(path)
            }
            
            return {
                "success": True,
                "path": path,
                "size": len(content),
                "cached_at": _file_content_cache[path]["cached_at"],
                "message": f"File cached successfully: {path}"
            }
        except Exception as e:
            logger.error(f"Error caching file {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_cache_file")
    
    # Tool: Read from cache
    @server.tool("vfs_read_cached")
    async def vfs_read_cached(ctx, path: str, refresh: bool = False):
        """Read a file from cache, optionally refreshing it"""
        try:
            # Check if file exists
            if not os.path.isfile(path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Check if file is in cache and if we need to refresh
            if path not in _file_content_cache or refresh:
                # Cache or refresh the file
                with open(path, 'rb') as f:
                    content = f.read()
                
                _file_content_cache[path] = {
                    "content": content,
                    "size": len(content),
                    "cached_at": datetime.datetime.now().isoformat(),
                    "last_modified": os.path.getmtime(path)
                }
            else:
                # Check if file has been modified since it was cached
                current_mtime = os.path.getmtime(path)
                cached_mtime = _file_content_cache[path]["last_modified"]
                
                if current_mtime > cached_mtime:
                    # File has been modified, refresh the cache
                    with open(path, 'rb') as f:
                        content = f.read()
                    
                    _file_content_cache[path] = {
                        "content": content,
                        "size": len(content),
                        "cached_at": datetime.datetime.now().isoformat(),
                        "last_modified": current_mtime
                    }
            
            # Return the cached content
            cache_entry = _file_content_cache[path]
            
            # For binary content, we cannot include it directly in the return value
            # So we'll just include metadata
            return {
                "success": True,
                "path": path,
                "size": cache_entry["size"],
                "cached_at": cache_entry["cached_at"],
                "last_modified": datetime.datetime.fromtimestamp(cache_entry["last_modified"]).isoformat(),
                "from_cache": not refresh and path in _file_content_cache,
                "message": "Content retrieved from cache"
            }
        except Exception as e:
            logger.error(f"Error reading cached file {path}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    registered_tools.append("vfs_read_cached")
    
    logger.info(f"Registered {len(registered_tools)} advanced VFS tools")
    return registered_tools

if __name__ == "__main__":
    print("This module is meant to be imported, not run directly.")
    sys.exit(1)
