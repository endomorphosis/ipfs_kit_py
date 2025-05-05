#!/usr/bin/env python3
"""
MCP VFS Configuration

Centralized configuration and registration for Virtual File System tools 
in the MCP server. This module consolidates all VFS-related functionality
and provides a single interface for registering VFS tools with the MCP server.
"""

import os
import sys
import time
import logging
import importlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("vfs-mcp-config")

# Global registry to track registered tools
registered_tools = set()

def try_import(module_name):
    """Try to import a module and return None if not available."""
    try:
        return importlib.import_module(module_name)
    except ImportError:
        logger.warning(f"Module {module_name} not available")
        return None

# Try to import the various VFS modules
fs_journal_module = try_import("fs_journal_tools")
ipfs_fs_integration_module = try_import("ipfs_mcp_fs_integration")
multi_backend_fs_module = try_import("multi_backend_fs_integration")

def register_vfs_tools(mcp_server):
    """
    Register all Virtual File System tools with the MCP server.
    
    This is the main entry point for VFS tool registration.
    
    Args:
        mcp_server: The MCP server instance to register tools with
    
    Returns:
        bool: True if registration was successful
    """
    logger.info("Registering VFS tools with MCP server")
    
    # Register basic VFS tools
    register_basic_vfs_tools(mcp_server)
    
    # Register FS journal tools
    register_fs_journal_tools(mcp_server)
    
    # Register IPFS-FS integration tools
    register_ipfs_fs_tools(mcp_server)
    
    # Register multi-backend FS tools
    register_multi_backend_tools(mcp_server)
    
    logger.info(f"VFS tool registration complete. Registered {len(registered_tools)} tools.")
    return True

def register_basic_vfs_tools(mcp_server):
    """Register basic virtual filesystem tools with the MCP server."""
    logger.info("Registering basic VFS tools...")
    
    # List files tool
    register_tool(
        mcp_server,
        "vfs_list_files",
        "List files in a directory",
        basic_list_files,
        {
            "path": "Path to the directory to list",
            "recursive": "Whether to list files recursively (default: False)"
        }
    )
    
    # Read file tool
    register_tool(
        mcp_server,
        "vfs_read_file",
        "Read the contents of a file",
        basic_read_file,
        {
            "path": "Path to the file to read"
        }
    )
    
    # Write file tool
    register_tool(
        mcp_server,
        "vfs_write_file",
        "Write content to a file",
        basic_write_file,
        {
            "path": "Path to the file to write",
            "content": "Content to write to the file",
            "append": "Whether to append to the file (default: False)"
        }
    )
    
    # Delete file tool
    register_tool(
        mcp_server,
        "vfs_delete_file",
        "Delete a file",
        basic_delete_file,
        {
            "path": "Path to the file to delete"
        }
    )
    
    # Check if file exists tool
    register_tool(
        mcp_server,
        "vfs_file_exists",
        "Check if a file exists",
        basic_file_exists,
        {
            "path": "Path to check"
        }
    )
    
    # File info tool
    register_tool(
        mcp_server,
        "vfs_get_file_info",
        "Get information about a file",
        basic_get_file_info,
        {
            "path": "Path to the file"
        }
    )
    
    # Create directory tool
    register_tool(
        mcp_server,
        "vfs_create_directory",
        "Create a new directory",
        basic_create_directory,
        {
            "path": "Path to the directory to create",
            "exist_ok": "Whether to ignore if the directory already exists (default: True)"
        }
    )
    
    # Remove directory tool
    register_tool(
        mcp_server,
        "vfs_remove_directory",
        "Remove a directory",
        basic_remove_directory,
        {
            "path": "Path to the directory to remove",
            "recursive": "Whether to remove recursively (default: False)"
        }
    )
    
    # Count files tool
    register_tool(
        mcp_server,
        "vfs_count_files",
        "Count files in a directory",
        basic_count_files,
        {
            "path": "Path to the directory",
            "recursive": "Whether to count recursively (default: False)",
            "pattern": "Optional file pattern (e.g., '*.py') to filter files"
        }
    )
    
    # Search files tool
    register_tool(
        mcp_server,
        "vfs_search_files",
        "Search for files matching a pattern",
        basic_search_files,
        {
            "path": "Path to the directory to search in",
            "pattern": "File pattern to search for (e.g., '*.py')",
            "recursive": "Whether to search recursively (default: True)"
        }
    )
    
    logger.info("✅ Successfully registered basic VFS tools")
    return True

def register_fs_journal_tools(mcp_server):
    """Register filesystem journal tools with the MCP server."""
    logger.info("Registering filesystem journal tools...")
    
    # Check if the fs_journal_tools module is available
    if fs_journal_module and hasattr(fs_journal_module, "register_tools"):
        # If available, use its registration function
        try:
            fs_journal_module.register_tools(mcp_server)
            logger.info("✅ Successfully registered FS journal tools from module")
            return True
        except Exception as e:
            logger.error(f"Error registering FS journal tools from module: {e}")
            # Fall back to basic implementation
    
    # Implement basic journal functionality if module not available
    logger.info("Using basic FS journal tools implementation")
    
    # In-memory journal storage
    journal_db = {}
    
    # Register journal record tool
    register_tool(
        mcp_server,
        "fs_journal_record",
        "Record a filesystem operation in the journal",
        lambda operation, path, metadata=None: _journal_record(journal_db, operation, path, metadata),
        {
            "operation": "Operation performed (create, read, update, delete)",
            "path": "Path to the file or directory",
            "metadata": "Additional metadata about the operation"
        }
    )
    
    # Register journal get history tool
    register_tool(
        mcp_server,
        "fs_journal_get_history",
        "Get the history of operations for a file or directory",
        lambda path: _journal_get_history(journal_db, path),
        {
            "path": "Path to the file or directory"
        }
    )
    
    # Register journal clear tool
    register_tool(
        mcp_server,
        "fs_journal_clear",
        "Clear the journal for a specific path or all paths",
        lambda path=None: _journal_clear(journal_db, path),
        {
            "path": "Path to clear journal for (if None, clears all)"
        }
    )
    
    # Register journal stats tool
    register_tool(
        mcp_server,
        "fs_journal_stats",
        "Get statistics about the journal",
        lambda: _journal_stats(journal_db),
        {}
    )
    
    logger.info("✅ Successfully registered basic FS journal tools")
    return True

def register_ipfs_fs_tools(mcp_server):
    """Register IPFS-FS bridge tools with the MCP server."""
    logger.info("Registering IPFS-FS bridge tools...")
    
    # Check if the ipfs_mcp_fs_integration module is available
    if ipfs_fs_integration_module and hasattr(ipfs_fs_integration_module, "register_integration_tools"):
        # If available, use its registration function
        try:
            ipfs_fs_integration_module.register_integration_tools(mcp_server)
            logger.info("✅ Successfully registered IPFS-FS bridge tools from module")
            return True
        except Exception as e:
            logger.error(f"Error registering IPFS-FS bridge tools from module: {e}")
            # Fall back to stub implementation
    
    # Implement stub IPFS-FS functionality if module not available
    logger.info("Using stub IPFS-FS bridge tools implementation")
    
    # Register IPFS-FS pin file tool
    register_tool(
        mcp_server,
        "ipfs_fs_pin_file",
        "Pin a file to IPFS and return the CID",
        lambda path: {
            "success": False,
            "error": "IPFS-FS integration not available",
            "path": path
        },
        {
            "path": "Path to the file to pin"
        }
    )
    
    # Register IPFS-FS get file tool
    register_tool(
        mcp_server,
        "ipfs_fs_get_file",
        "Get a file from IPFS by CID and save it to the local filesystem",
        lambda cid, path: {
            "success": False,
            "error": "IPFS-FS integration not available",
            "cid": cid,
            "path": path
        },
        {
            "cid": "IPFS CID of the file",
            "path": "Path to save the file"
        }
    )
    
    # Register IPFS-FS status tool
    register_tool(
        mcp_server,
        "ipfs_fs_status",
        "Get the status of the IPFS-FS bridge",
        lambda: {
            "available": False,
            "error": "IPFS-FS integration not available"
        },
        {}
    )
    
    logger.info("✅ Successfully registered IPFS-FS bridge stub tools")
    return True

def register_multi_backend_tools(mcp_server):
    """Register multi-backend filesystem tools with the MCP server."""
    logger.info("Registering multi-backend filesystem tools...")
    
    # Check if the multi_backend_fs_integration module is available
    if multi_backend_fs_module and hasattr(multi_backend_fs_module, "register_multi_backend_tools"):
        # If available, use its registration function
        try:
            multi_backend_fs_module.register_multi_backend_tools(mcp_server)
            logger.info("✅ Successfully registered multi-backend FS tools from module")
            return True
        except Exception as e:
            logger.error(f"Error registering multi-backend FS tools from module: {e}")
            # Fall back to stub implementation
    
    # Skip registration if module not available
    logger.info("Multi-backend FS module not available, skipping")
    return True

# --- Helper functions for tool registration ---

def register_tool(mcp_server, name, description, function, parameter_descriptions=None):
    """
    Register a tool with the MCP server.
    
    Args:
        mcp_server: The MCP server instance
        name: Tool name
        description: Tool description
        function: Tool implementation function
        parameter_descriptions: Tool parameter descriptions
    """
    try:
        # Check if the tool is already registered
        if name in registered_tools:
            logger.warning(f"Tool {name} already registered, skipping")
            return False
        
        # Register the tool
        if parameter_descriptions:
            mcp_server.register_tool(
                name=name,
                description=description,
                function=function,
                parameter_descriptions=parameter_descriptions
            )
        else:
            mcp_server.register_tool(
                name=name,
                description=description,
                function=function
            )
            
        # Add to registry
        registered_tools.add(name)
        logger.debug(f"Registered tool: {name}")
        return True
    except Exception as e:
        logger.error(f"Error registering tool {name}: {e}")
        return False

# --- Basic VFS tool implementations ---

def basic_list_files(path, recursive=False):
    """List files in a directory."""
    try:
        if not os.path.exists(path):
            return {"error": f"Path {path} does not exist"}
        
        if os.path.isfile(path):
            return {"error": f"Path {path} is a file, not a directory"}
        
        if recursive:
            files = []
            dirs = []
            for root, directories, filenames in os.walk(path):
                for directory in directories:
                    dirs.append(os.path.join(root, directory))
                for filename in filenames:
                    files.append(os.path.join(root, filename))
            return {
                "files": files,
                "directories": dirs,
                "count": len(files) + len(dirs)
            }
        else:
            all_items = os.listdir(path)
            files = [f for f in all_items if os.path.isfile(os.path.join(path, f))]
            dirs = [d for d in all_items if os.path.isdir(os.path.join(path, d))]
            return {
                "files": files,
                "directories": dirs,
                "count": len(files) + len(dirs)
            }
    except Exception as e:
        return {"error": str(e)}

def basic_read_file(path):
    """Read the contents of a file."""
    try:
        if not os.path.exists(path):
            return {"error": f"File {path} does not exist"}
        
        if not os.path.isfile(path):
            return {"error": f"Path {path} is not a file"}
        
        with open(path, 'r') as f:
            content = f.read()
        
        return {
            "content": content,
            "size": os.path.getsize(path),
            "last_modified": os.path.getmtime(path)
        }
    except Exception as e:
        return {"error": str(e)}

def basic_write_file(path, content, append=False):
    """Write content to a file."""
    try:
        # Create parent directory if it doesn't exist
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        
        # Write content to file
        mode = 'a' if append else 'w'
        with open(path, mode) as f:
            f.write(content)
        
        return {
            "success": True,
            "path": path,
            "size": os.path.getsize(path),
            "append": append
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

def basic_delete_file(path):
    """Delete a file."""
    try:
        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"File {path} does not exist",
                "path": path
            }
        
        if not os.path.isfile(path):
            return {
                "success": False,
                "error": f"Path {path} is not a file",
                "path": path
            }
        
        os.remove(path)
        
        return {
            "success": True,
            "path": path,
            "exists_after": os.path.exists(path)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

def basic_file_exists(path):
    """Check if a file exists."""
    try:
        exists = os.path.exists(path)
        
        result = {
            "exists": exists,
            "path": path
        }
        
        if exists:
            result.update({
                "is_file": os.path.isfile(path),
                "is_directory": os.path.isdir(path),
                "is_symlink": os.path.islink(path),
                "size": os.path.getsize(path) if os.path.isfile(path) else None,
                "last_modified": os.path.getmtime(path)
            })
        
        return result
    except Exception as e:
        return {
            "error": str(e),
            "path": path
        }

def basic_get_file_info(path):
    """Get information about a file."""
    try:
        if not os.path.exists(path):
            return {
                "error": f"Path {path} does not exist",
                "path": path
            }
        
        is_file = os.path.isfile(path)
        is_dir = os.path.isdir(path)
        is_link = os.path.islink(path)
        
        stat_info = os.stat(path)
        
        info = {
            "path": path,
            "exists": True,
            "is_file": is_file,
            "is_directory": is_dir,
            "is_symlink": is_link,
            "size": stat_info.st_size,
            "created": stat_info.st_ctime,
            "last_modified": stat_info.st_mtime,
            "last_accessed": stat_info.st_atime,
            "mode": stat_info.st_mode
        }
        
        if is_file:
            _, extension = os.path.splitext(path)
            info["extension"] = extension
        
        if is_dir:
            info["contents"] = os.listdir(path)
            info["item_count"] = len(info["contents"])
        
        return info
    except Exception as e:
        return {
            "error": str(e),
            "path": path
        }

def basic_create_directory(path, exist_ok=True):
    """Create a new directory."""
    try:
        os.makedirs(path, exist_ok=exist_ok)
        
        return {
            "success": True,
            "path": path,
            "exists": os.path.exists(path),
            "is_directory": os.path.isdir(path)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

def basic_remove_directory(path, recursive=False):
    """Remove a directory."""
    try:
        if not os.path.exists(path):
            return {
                "success": False,
                "error": f"Directory {path} does not exist",
                "path": path
            }
        
        if not os.path.isdir(path):
            return {
                "success": False,
                "error": f"Path {path} is not a directory",
                "path": path
            }
        
        if recursive:
            import shutil
            shutil.rmtree(path)
        else:
            os.rmdir(path)
        
        return {
            "success": True,
            "path": path,
            "exists_after": os.path.exists(path)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

def basic_count_files(path, recursive=False, pattern=None):
    """Count files in a directory."""
    try:
        import fnmatch
        
        if not os.path.exists(path):
            return {
                "error": f"Path {path} does not exist",
                "path": path
            }
        
        if not os.path.isdir(path):
            return {
                "error": f"Path {path} is not a directory",
                "path": path
            }
        
        file_count = 0
        dir_count = 0
        
        if recursive:
            for root, dirs, files in os.walk(path):
                dir_count += len(dirs)
                
                if pattern:
                    file_count += sum(1 for f in files if fnmatch.fnmatch(f, pattern))
                else:
                    file_count += len(files)
        else:
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                
                if os.path.isdir(item_path):
                    dir_count += 1
                elif os.path.isfile(item_path):
                    if pattern and not fnmatch.fnmatch(item, pattern):
                        continue
                    file_count += 1
        
        return {
            "path": path,
            "file_count": file_count,
            "directory_count": dir_count,
            "total_count": file_count + dir_count,
            "recursive": recursive,
            "pattern": pattern
        }
    except Exception as e:
        return {
            "error": str(e),
            "path": path
        }

def basic_search_files(path, pattern, recursive=True):
    """Search for files matching a pattern."""
    try:
        import fnmatch
        
        if not os.path.exists(path):
            return {
                "error": f"Path {path} does not exist",
                "path": path
            }
        
        if not os.path.isdir(path):
            return {
                "error": f"Path {path} is not a directory",
                "path": path
            }
        
        matches = []
        
        if recursive:
            for root, dirnames, filenames in os.walk(path):
                for filename in fnmatch.filter(filenames, pattern):
                    matches.append(os.path.join(root, filename))
        else:
            for item in os.listdir(path):
                if fnmatch.fnmatch(item, pattern):
                    matches.append(os.path.join(path, item))
        
        return {
            "path": path,
            "pattern": pattern,
            "matches": matches,
            "count": len(matches),
            "recursive": recursive
        }
    except Exception as e:
        return {
            "error": str(e),
            "path": path
        }

# --- Journal functions ---

def _journal_record(journal_db, operation, path, metadata=None):
    """Record an operation in the journal."""
    if metadata is None:
        metadata = {}
    
    entry = {
        "operation": operation,
        "timestamp": time.time(),
        "datetime": datetime.now().isoformat(),
        "metadata": metadata
    }
    
    if path not in journal_db:
        journal_db[path] = []
    
    journal_db[path].append(entry)
    
    return {
        "success": True,
        "operation": operation,
        "path": path,
        "entry_count": len(journal_db[path]),
        "timestamp": entry["timestamp"]
    }

def _journal_get_history(journal_db, path):
    """Get the history of operations for a path."""
    if path not in journal_db:
        return {
            "path": path,
            "history": [],
            "count": 0
        }
    
    return {
        "path": path,
        "history": journal_db[path],
        "count": len(journal_db[path])
    }

def _journal_clear(journal_db, path=None):
    """Clear the journal for a path or all paths."""
    if path is None:
        # Clear all
        count = sum(len(entries) for entries in journal_db.values())
        journal_db.clear()
        return {
            "success": True,
            "cleared_all": True,
            "entry_count": count
        }
    else:
        # Clear specific path
        if path not in journal_db:
            return {
                "success": False,
                "error": f"No journal entries for path {path}",
                "path": path
            }
        
        count = len(journal_db[path])
        del journal_db[path]
        
        return {
            "success": True,
            "path": path,
            "entry_count": count
        }

def _journal_stats(journal_db):
    """Get statistics about the journal."""
    paths = list(journal_db.keys())
    total_entries = sum(len(entries) for entries in journal_db.values())
    
    operations = {}
    for path, entries in journal_db.items():
        for entry in entries:
            op = entry["operation"]
            operations[op] = operations.get(op, 0) + 1
    
    return {
        "path_count": len(paths),
        "entry_count": total_entries,
        "paths": paths,
        "operations": operations
    }

# --- Main entry point for testing ---
if __name__ == "__main__":
    # For testing, create a mock MCP server
    class MockMCPServer:
        def __init__(self):
            self.tools = {}
        
        def register_tool(self, name, description, function, parameter_descriptions=None):
            self.tools[name] = {
                "description": description,
                "function": function,
                "parameter_descriptions": parameter_descriptions
            }
            print(f"Registered tool: {name}")
    
    # Create a mock server
    mock_server = MockMCPServer()
    
    # Register VFS tools
    register_vfs_tools(mock_server)
    
    # Print registered tools
    print(f"Total registered tools: {len(mock_server.tools)}")
    for name, tool in mock_server.tools.items():
        print(f"- {name}: {tool['description']}")
