#!/usr/bin/env python3
"""
Filesystem Journal Tools for IPFS Kit Python

This module provides MCP tools for filesystem journal operations, allowing:
1. Tracking of virtual filesystem operations
2. Journal visualization and analysis
3. IPFS-Virtual filesystem synchronization
4. Integration with MCP server architecture
"""

import os
import sys
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='fs_journal_tools.log'
)
logger = logging.getLogger(__name__)

# Add console handler for immediate feedback
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

def register_fs_journal_tools(mcp_server):
    """
    Register all filesystem journal tools with the MCP server.
    
    Args:
        mcp_server: The MCP server instance to register tools with
    """
    try:
        # Import necessary modules
        from ipfs_kit_py.mcp.fs.fs_journal import FSJournal, VirtualFS, FSController
        from ipfs_kit_py.mcp.server import register_tool
        
        # Create or get existing journal and virtual filesystem
        journal_path = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "fs_journal.json")
        os.makedirs(os.path.dirname(journal_path), exist_ok=True)
        
        journal = FSJournal(journal_path)
        virtual_fs = VirtualFS(journal)
        fs_controller = FSController(virtual_fs)
        
        # Register the tools with the MCP server
        # Journal analysis tools
        register_tool(
            "fs_journal_list",
            fs_journal_list,
            "List all filesystem journal entries",
            {"limit": "Maximum number of entries to return (default: 100)", 
             "path": "Filter entries by path (optional)"},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_journal_stats",
            fs_journal_stats,
            "Get statistics about filesystem journal usage",
            {},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_journal_clear",
            fs_journal_clear,
            "Clear the filesystem journal",
            {"confirm": "Set to true to confirm clearing the journal"},
            virtual_fs=virtual_fs
        )
        
        # Virtual filesystem tools
        register_tool(
            "fs_virtual_list",
            fs_virtual_list,
            "List entries in the virtual filesystem",
            {"path": "Path to list (default: /)"},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_virtual_read",
            fs_virtual_read,
            "Read a file from the virtual filesystem",
            {"path": "Path to the file to read"},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_virtual_write",
            fs_virtual_write,
            "Write content to the virtual filesystem",
            {"path": "Path to write to", 
             "content": "Content to write (base64 encoded)",
             "cid": "CID to associate with the file (optional)"},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_virtual_delete",
            fs_virtual_delete,
            "Delete a file or directory in the virtual filesystem",
            {"path": "Path to delete"},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_virtual_mkdir",
            fs_virtual_mkdir,
            "Create a directory in the virtual filesystem",
            {"path": "Path of the directory to create"},
            virtual_fs=virtual_fs
        )
        
        # Synchronization tools
        register_tool(
            "fs_sync_to_ipfs",
            fs_sync_to_ipfs,
            "Synchronize virtual filesystem to IPFS",
            {"path": "Path to synchronize (default: /)", 
             "recursive": "Recursively synchronize subdirectories (default: true)"},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_sync_from_ipfs",
            fs_sync_from_ipfs,
            "Synchronize content from IPFS to virtual filesystem",
            {"cid": "IPFS CID to synchronize", 
             "path": "Destination path in virtual filesystem (default: /)"},
            virtual_fs=virtual_fs
        )
        
        # CID mapping tools
        register_tool(
            "fs_get_paths_for_cid",
            fs_get_paths_for_cid,
            "Get all virtual filesystem paths associated with a CID",
            {"cid": "IPFS CID to look up"},
            virtual_fs=virtual_fs
        )
        
        register_tool(
            "fs_find_duplicate_files",
            fs_find_duplicate_files,
            "Find duplicate files in the virtual filesystem",
            {"path": "Path to search from (default: /)", 
             "content_based": "Compare by content hash rather than CID (default: false)"},
            virtual_fs=virtual_fs
        )
        
        # Visualization tools
        register_tool(
            "fs_journal_visualize",
            fs_journal_visualize,
            "Generate a visualization of filesystem journal activity",
            {"format": "Output format (json, html, text) (default: json)",
             "time_window": "Time window in hours (default: 24)"},
            virtual_fs=virtual_fs
        )
        
        # Statistics and information tools
        register_tool(
            "fs_virtual_stats",
            fs_virtual_stats,
            "Get statistics about the virtual filesystem",
            {"path": "Path to get statistics for (default: /)"},
            virtual_fs=virtual_fs
        )
        
        logger.info(f"Successfully registered {15} filesystem journal tools with MCP server")
        return True
    
    except ImportError as e:
        logger.error(f"Failed to register filesystem journal tools: {e}")
        return False
    except Exception as e:
        logger.error(f"Error registering filesystem journal tools: {e}")
        return False


# Tool implementations

def fs_journal_list(limit: int = 100, path: Optional[str] = None, virtual_fs=None):
    """
    List filesystem journal entries.
    
    Args:
        limit: Maximum number of entries to return
        path: Filter entries by path (optional)
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with journal entries and metadata
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        if path:
            entries = virtual_fs.journal.get_operations_for_path(path)
            return {"entries": entries[:limit], "total": len(entries), "filtered_by_path": path}
        else:
            entries = virtual_fs.journal.operations
            return {"entries": entries[-limit:], "total": len(entries)}
    
    except Exception as e:
        return {"error": f"Failed to list journal entries: {str(e)}"}


def fs_journal_stats(virtual_fs=None):
    """
    Get statistics about filesystem journal usage.
    
    Args:
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with journal statistics
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        operations = virtual_fs.journal.operations
        
        if not operations:
            return {"total_operations": 0, "message": "No journal entries found"}
        
        # Calculate statistics
        op_types = {}
        paths = set()
        success_count = 0
        failed_count = 0
        first_timestamp = float('inf')
        last_timestamp = 0
        
        for op in operations:
            # Count operation types
            op_type = op.get("op_type")
            op_types[op_type] = op_types.get(op_type, 0) + 1
            
            # Count unique paths
            paths.add(op.get("path"))
            
            # Count successes and failures
            if op.get("success", False):
                success_count += 1
            else:
                failed_count += 1
            
            # Track time range
            timestamp = op.get("timestamp", 0)
            first_timestamp = min(first_timestamp, timestamp)
            last_timestamp = max(last_timestamp, timestamp)
        
        # Calculate time span
        time_span_seconds = last_timestamp - first_timestamp if first_timestamp < last_timestamp else 0
        time_span_hours = time_span_seconds / 3600
        time_span_days = time_span_hours / 24
        
        return {
            "total_operations": len(operations),
            "operation_types": op_types,
            "unique_paths": len(paths),
            "success_count": success_count,
            "failure_count": failed_count,
            "success_rate": success_count / len(operations) if operations else 0,
            "time_span_seconds": time_span_seconds,
            "time_span_hours": time_span_hours,
            "time_span_days": time_span_days,
            "first_operation": datetime.fromtimestamp(first_timestamp).isoformat() if first_timestamp < float('inf') else None,
            "last_operation": datetime.fromtimestamp(last_timestamp).isoformat() if last_timestamp > 0 else None
        }
    
    except Exception as e:
        return {"error": f"Failed to calculate journal statistics: {str(e)}"}


def fs_journal_clear(confirm: bool = False, virtual_fs=None):
    """
    Clear the filesystem journal.
    
    Args:
        confirm: Set to true to confirm clearing the journal
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with result of the operation
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    if not confirm:
        return {"error": "Clearing journal requires confirmation. Set confirm=true to proceed."}
    
    try:
        count = len(virtual_fs.journal.operations)
        virtual_fs.journal.clear()
        return {"success": True, "message": f"Cleared {count} journal entries"}
    
    except Exception as e:
        return {"error": f"Failed to clear journal: {str(e)}"}


def fs_virtual_list(path: str = "/", virtual_fs=None):
    """
    List entries in the virtual filesystem.
    
    Args:
        path: Path to list
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with directory contents or error
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        entries = virtual_fs.list(path)
        if entries is None:
            return {"error": "Directory not found or not a directory"}
        
        # Get stats for each entry
        result = []
        for name in entries:
            entry_path = os.path.join(path, name).replace("\\", "/")
            if entry_path.startswith("//"):
                entry_path = entry_path[1:]
            
            stats = virtual_fs.get_stats(entry_path)
            if stats:
                result.append(stats)
        
        return {"path": path, "entries": result, "count": len(result)}
    
    except Exception as e:
        return {"error": f"Failed to list directory: {str(e)}"}


def fs_virtual_read(path: str, virtual_fs=None):
    """
    Read a file from the virtual filesystem.
    
    Args:
        path: Path to the file to read
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with file content and metadata
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        content = virtual_fs.read_file(path)
        if content is None:
            return {"error": "File not found or not a file"}
        
        import base64
        content_b64 = base64.b64encode(content).decode('utf-8')
        
        stats = virtual_fs.get_stats(path)
        
        return {
            "path": path,
            "size": len(content),
            "content_base64": content_b64,
            "stats": stats
        }
    
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}


def fs_virtual_write(path: str, content: str, cid: Optional[str] = None, virtual_fs=None):
    """
    Write content to the virtual filesystem.
    
    Args:
        path: Path to write to
        content: Base64 encoded content to write
        cid: CID to associate with the file (optional)
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with result of the operation
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        import base64
        content_bytes = base64.b64decode(content)
        
        success = virtual_fs.write_file(path, content_bytes, cid)
        if success:
            return {"success": True, "path": path, "size": len(content_bytes), "cid": cid}
        else:
            return {"error": "Failed to write file"}
    
    except Exception as e:
        return {"error": f"Failed to write file: {str(e)}"}


def fs_virtual_delete(path: str, virtual_fs=None):
    """
    Delete a file or directory in the virtual filesystem.
    
    Args:
        path: Path to delete
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with result of the operation
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        success = virtual_fs.delete(path)
        if success:
            return {"success": True, "path": path}
        else:
            return {"error": "Path not found or could not be deleted"}
    
    except Exception as e:
        return {"error": f"Failed to delete path: {str(e)}"}


def fs_virtual_mkdir(path: str, virtual_fs=None):
    """
    Create a directory in the virtual filesystem.
    
    Args:
        path: Path of the directory to create
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with result of the operation
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        success = virtual_fs.mkdir(path)
        if success:
            return {"success": True, "path": path}
        else:
            return {"error": "Failed to create directory (may already exist)"}
    
    except Exception as e:
        return {"error": f"Failed to create directory: {str(e)}"}


def fs_sync_to_ipfs(path: str = "/", recursive: bool = True, virtual_fs=None):
    """
    Synchronize virtual filesystem to IPFS.
    
    Args:
        path: Path to synchronize
        recursive: Recursively synchronize subdirectories
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with synchronization results
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Import necessary IPFS modules
        try:
            from ipfs_kit_py.core import IPFSClient
            client = IPFSClient()
        except ImportError:
            return {"error": "IPFS client not available"}
        except Exception as e:
            return {"error": f"Failed to create IPFS client: {str(e)}"}
        
        # Check if path exists
        if not virtual_fs.exists(path):
            return {"error": f"Path {path} does not exist in virtual filesystem"}
        
        # Synchronization results
        synced_files = []
        failed_files = []
        total_size = 0
        
        # Helper function for recursive sync
        def sync_path(current_path):
            nonlocal synced_files, failed_files, total_size
            
            # Handle directory
            if virtual_fs.is_dir(current_path):
                # Create a temporary directory to hold files
                import tempfile
                import shutil
                temp_dir = tempfile.mkdtemp()
                
                try:
                    # Process entries in the directory
                    entries = virtual_fs.list(current_path) or []
                    for name in entries:
                        entry_path = os.path.join(current_path, name).replace("\\", "/")
                        if entry_path.startswith("//"):
                            entry_path = entry_path[1:]
                        
                        if recursive and virtual_fs.is_dir(entry_path):
                            sync_path(entry_path)
                        elif virtual_fs.is_file(entry_path):
                            # Write file to temp directory for adding to IPFS
                            content = virtual_fs.read_file(entry_path)
                            if content is not None:
                                local_path = os.path.join(temp_dir, name)
                                with open(local_path, 'wb') as f:
                                    f.write(content)
                                
                                # Add file to IPFS
                                try:
                                    result = client.add(local_path, quiet=True)
                                    cid = result.get("Hash")
                                    if cid:
                                        # Update the CID in the virtual filesystem
                                        virtual_fs.write_file(entry_path, content, cid)
                                        synced_files.append({
                                            "path": entry_path,
                                            "cid": cid,
                                            "size": len(content)
                                        })
                                        total_size += len(content)
                                    else:
                                        failed_files.append({
                                            "path": entry_path,
                                            "error": "No CID returned from IPFS"
                                        })
                                except Exception as e:
                                    failed_files.append({
                                        "path": entry_path,
                                        "error": str(e)
                                    })
                
                finally:
                    # Clean up the temporary directory
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
            # Handle file
            elif virtual_fs.is_file(current_path):
                content = virtual_fs.read_file(current_path)
                if content is not None:
                    # Write to temporary file for adding to IPFS
                    with tempfile.NamedTemporaryFile(delete=False) as temp:
                        temp.write(content)
                        temp_path = temp.name
                    
                    try:
                        # Add file to IPFS
                        result = client.add(temp_path, quiet=True)
                        os.unlink(temp_path)  # Clean up
                        
                        cid = result.get("Hash")
                        if cid:
                            # Update the CID in the virtual filesystem
                            virtual_fs.write_file(current_path, content, cid)
                            synced_files.append({
                                "path": current_path,
                                "cid": cid,
                                "size": len(content)
                            })
                            total_size += len(content)
                        else:
                            failed_files.append({
                                "path": current_path,
                                "error": "No CID returned from IPFS"
                            })
                    
                    except Exception as e:
                        os.unlink(temp_path)  # Clean up
                        failed_files.append({
                            "path": current_path,
                            "error": str(e)
                        })
        
        # Start synchronization from the given path
        sync_path(path)
        
        return {
            "success": len(failed_files) == 0,
            "synced_files": synced_files,
            "failed_files": failed_files,
            "total_synced": len(synced_files),
            "total_failed": len(failed_files),
            "total_size_bytes": total_size
        }
    
    except Exception as e:
        return {"error": f"Synchronization failed: {str(e)}"}


def fs_sync_from_ipfs(cid: str, path: str = "/", virtual_fs=None):
    """
    Synchronize content from IPFS to virtual filesystem.
    
    Args:
        cid: IPFS CID to synchronize
        path: Destination path in virtual filesystem
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with synchronization results
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Import necessary IPFS modules
        try:
            from ipfs_kit_py.core import IPFSClient
            client = IPFSClient()
        except ImportError:
            return {"error": "IPFS client not available"}
        except Exception as e:
            return {"error": f"Failed to create IPFS client: {str(e)}"}
        
        # Try to retrieve the content from IPFS
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Get the content from IPFS
                result = client.get(cid, target=temp_dir)
                
                # Process the retrieved content
                retrieved_files = []
                failed_files = []
                total_size = 0
                
                # Helper function to process retrieved files
                def process_directory(dir_path, virtual_path):
                    nonlocal retrieved_files, failed_files, total_size
                    
                    for root, dirs, files in os.walk(dir_path):
                        # Calculate relative path
                        rel_path = os.path.relpath(root, dir_path)
                        if rel_path == '.':
                            rel_path = ''
                        
                        # Create directories
                        for dir_name in dirs:
                            dir_virtual_path = os.path.join(virtual_path, rel_path, dir_name).replace("\\", "/")
                            if dir_virtual_path.startswith('//'):
                                dir_virtual_path = dir_virtual_path[1:]
                            
                            try:
                                virtual_fs.mkdir(dir_virtual_path)
                            except Exception as e:
                                failed_files.append({
                                    "path": dir_virtual_path,
                                    "error": f"Failed to create directory: {str(e)}"
                                })
                        
                        # Process files
                        for file_name in files:
                            file_path = os.path.join(root, file_name)
                            file_virtual_path = os.path.join(virtual_path, rel_path, file_name).replace("\\", "/")
                            if file_virtual_path.startswith('//'):
                                file_virtual_path = file_virtual_path[1:]
                            
                            try:
                                with open(file_path, 'rb') as f:
                                    content = f.read()
                                
                                # Calculate CID for the individual file
                                file_result = client.add(file_path, only_hash=True, quiet=True)
                                file_cid = file_result.get("Hash") if file_result else None
                                
                                # Write to virtual filesystem
                                if virtual_fs.write_file(file_virtual_path, content, file_cid):
                                    retrieved_files.append({
                                        "path": file_virtual_path,
                                        "cid": file_cid,
                                        "size": len(content)
                                    })
                                    total_size += len(content)
                                else:
                                    failed_files.append({
                                        "path": file_virtual_path,
                                        "error": "Failed to write to virtual filesystem"
                                    })
                            
                            except Exception as e:
                                failed_files.append({
                                    "path": file_virtual_path,
                                    "error": str(e)
                                })
                
                # Get the main directory containing the retrieved content
                retrieved_dir = os.path.join(temp_dir, cid)
                if not os.path.exists(retrieved_dir):
                    # Some IPFS implementations don't use CID as directory name
                    entries = os.listdir(temp_dir)
                    if entries:
                        retrieved_dir = os.path.join(temp_dir, entries[0])
                
                # Process the content
                if os.path.isdir(retrieved_dir):
                    process_directory(retrieved_dir, path)
                elif os.path.isfile(retrieved_dir):
                    # Handle single file retrieval
                    try:
                        with open(retrieved_dir, 'rb') as f:
                            content = f.read()
                        
                        file_name = os.path.basename(path) or cid
                        file_path = path if os.path.basename(path) else os.path.join(path, file_name)
                        file_path = file_path.replace("\\", "/")
                        
                        if virtual_fs.write_file(file_path, content, cid):
                            retrieved_files.append({
                                "path": file_path,
                                "cid": cid,
                                "size": len(content)
                            })
                            total_size += len(content)
                        else:
                            failed_files.append({
                                "path": file_path,
                                "error": "Failed to write to virtual filesystem"
                            })
                    
                    except Exception as e:
                        failed_files.append({
                            "path": path,
                            "error": str(e)
                        })
                
                return {
                    "success": len(failed_files) == 0,
                    "retrieved_files": retrieved_files,
                    "failed_files": failed_files,
                    "total_retrieved": len(retrieved_files),
                    "total_failed": len(failed_files),
                    "total_size_bytes": total_size,
                    "cid": cid
                }
            
            except Exception as e:
                return {"error": f"Failed to retrieve content from IPFS: {str(e)}"}
    
    except Exception as e:
        return {"error": f"Synchronization failed: {str(e)}"}


def fs_get_paths_for_cid(cid: str, virtual_fs=None):
    """
    Get all virtual filesystem paths associated with a CID.
    
    Args:
        cid: IPFS CID to look up
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with paths associated with the CID
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        paths = virtual_fs.get_paths_for_cid(cid)
        return {"cid": cid, "paths": paths, "count": len(paths)}
    
    except Exception as e:
        return {"error": f"Failed to get paths for CID: {str(e)}"}


def fs_find_duplicate_files(path: str = "/", content_based: bool = False, virtual_fs=None):
    """
    Find duplicate files in the virtual filesystem.
    
    Args:
        path: Path to search from
        content_based: Compare by content hash rather than CID
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with duplicate files grouped by CID or content hash
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Dictionary to track files by CID or content hash
        file_groups = {}
        
        # Helper function to process a directory recursively
        def process_directory(dir_path):
            entries = virtual_fs.list(dir_path)
            if entries is None:
                return
            
            for name in entries:
                entry_path = os.path.join(dir_path, name).replace("\\", "/")
                if entry_path.startswith("//"):
                    entry_path = entry_path[1:]
                
                if virtual_fs.is_dir(entry_path):
                    # Recursively process subdirectory
                    process_directory(entry_path)
                
                elif virtual_fs.is_file(entry_path):
                    content = virtual_fs.read_file(entry_path)
                    if content is not None:
                        if content_based:
                            # Use content hash for grouping
                            import hashlib
                            content_hash = hashlib.sha256(content).hexdigest()
                            key = content_hash
                        else:
                            # Use CID for grouping
                            cid = virtual_fs.get_cid(entry_path)
                            if cid is None:
                                continue
                            key = cid
                        
                        # Add to the appropriate group
                        if key not in file_groups:
                            file_groups[key] = []
                        
                        file_groups[key].append({
                            "path": entry_path,
                            "size": len(content),
                            "cid": virtual_fs.get_cid(entry_path)
                        })
        
        # Start processing from the specified path
        process_directory(path)
        
        # Filter groups with more than one file (duplicates)
        duplicate_groups = {k: v for k, v in file_groups.items() if len(v) > 1}
        
        # Calculate statistics
        total_duplicates = sum(len(group) - 1 for group in duplicate_groups.values())
        total_wasted_bytes = sum(
            group[0]["size"] * (len(group) - 1)
            for group in duplicate_groups.values()
        )
        
        return {
            "duplicate_groups": duplicate_groups,
            "group_count": len(duplicate_groups),
            "total_duplicates": total_duplicates,
            "total_wasted_bytes": total_wasted_bytes,
            "comparison_method": "content_hash" if content_based else "cid"
        }
    
    except Exception as e:
        return {"error": f"Failed to find duplicate files: {str(e)}"}


def fs_journal_visualize(format: str = "json", time_window: int = 24, virtual_fs=None):
    """
    Generate a visualization of filesystem journal activity.
    
    Args:
        format: Output format (json, html, text)
        time_window: Time window in hours
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with visualization data
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        operations = virtual_fs.journal.operations
        
        if not operations:
            return {"message": "No journal entries found for visualization"}
        
        # Filter operations by time window
        current_time = time.time()
        cutoff_time = current_time - (time_window * 3600)
        filtered_ops = [op for op in operations if op.get("timestamp", 0) >= cutoff_time]
        
        # Group operations by hour
        hourly_activity = {}
        op_types_count = {}
        paths_activity = {}
        
        for op in filtered_ops:
            timestamp = op.get("timestamp", 0)
            op_type = op.get("op_type")
            path = op.get("path")
            success = op.get("success", False)
            
            # Round to the nearest hour
            hour = int(timestamp / 3600) * 3600
            hour_iso = datetime.fromtimestamp(hour).isoformat(timespec='hours')
            
            # Count by hour
            if hour_iso not in hourly_activity:
                hourly_activity[hour_iso] = {"total": 0, "success": 0, "failure": 0}
            
            hourly_activity[hour_iso]["total"] += 1
            if success:
                hourly_activity[hour_iso]["success"] += 1
            else:
                hourly_activity[hour_iso]["failure"] += 1
            
            # Count by operation type
            if op_type not in op_types_count:
                op_types_count[op_type] = {"total": 0, "success": 0, "failure": 0}
            
            op_types_count[op_type]["total"] += 1
            if success:
                op_types_count[op_type]["success"] += 1
            else:
                op_types_count[op_type]["failure"] += 1
            
            # Count by path
            if path not in paths_activity:
                paths_activity[path] = {"total": 0, "success": 0, "failure": 0}
            
            paths_activity[path]["total"] += 1
            if success:
                paths_activity[path]["success"] += 1
            else:
                paths_activity[path]["failure"] += 1
        
        # Prepare visualization data
        visualization_data = {
            "time_window_hours": time_window,
            "total_operations": len(filtered_ops),
            "hourly_activity": hourly_activity,
            "operation_types": op_types_count,
            "paths_activity": paths_activity
        }
        
        # Generate the appropriate format
        if format.lower() == "json":
            return visualization_data
        
        elif format.lower() == "html":
            try:
                import json
                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Filesystem Journal Visualization</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; }}
                        h1, h2 {{ color: #333; }}
                        .chart {{ margin: 20px 0; padding: 10px; border: 1px solid #ddd; border-radius: 5px; }}
                        .bar {{ background-color: #4CAF50; height: 20px; margin: 2px 0; }}
                        .failure {{ background-color: #f44336; }}
                    </style>
                    <script>
                        // Visualization data
                        const data = {json.dumps(visualization_data)};
                        
                        // Add charts when the page loads
                        window.onload = function() {{
                            // Create hourly activity chart
                            const hourlyDiv = document.getElementById('hourly-chart');
                            const hours = Object.keys(data.hourly_activity).sort();
                            let maxHourlyOps = 0;
                            for (let hour of hours) {{
                                maxHourlyOps = Math.max(maxHourlyOps, data.hourly_activity[hour].total);
                            }}
                            
                            for (let hour of hours) {{
                                const activity = data.hourly_activity[hour];
                                const successWidth = (activity.success / maxHourlyOps) * 100;
                                const failureWidth = (activity.failure / maxHourlyOps) * 100;
                                
                                hourlyDiv.innerHTML += `
                                    <div style="margin-bottom: 10px;">
                                        <div style="display: flex; align-items: center;">
                                            <div style="width: 150px;">${hour}</div>
                                            <div style="flex-grow: 1;">
                                                <div class="bar" style="width: ${successWidth}%"></div>
                                                <div class="bar failure" style="width: ${failureWidth}%"></div>
                                            </div>
                                            <div style="width: 100px; text-align: right;">
                                                ${activity.total} ops
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }}
                            
                            // Create operation types chart
                            const opTypesDiv = document.getElementById('op-types-chart');
                            const opTypes = Object.keys(data.operation_types);
                            let maxTypeOps = 0;
                            for (let type of opTypes) {{
                                maxTypeOps = Math.max(maxTypeOps, data.operation_types[type].total);
                            }}
                            
                            for (let type of opTypes) {{
                                const typeData = data.operation_types[type];
                                const successWidth = (typeData.success / maxTypeOps) * 100;
                                const failureWidth = (typeData.failure / maxTypeOps) * 100;
                                
                                opTypesDiv.innerHTML += `
                                    <div style="margin-bottom: 10px;">
                                        <div style="display: flex; align-items: center;">
                                            <div style="width: 150px;">${type}</div>
                                            <div style="flex-grow: 1;">
                                                <div class="bar" style="width: ${successWidth}%"></div>
                                                <div class="bar failure" style="width: ${failureWidth}%"></div>
                                            </div>
                                            <div style="width: 100px; text-align: right;">
                                                ${typeData.total} ops
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }}
                            
                            // Create top paths chart (top 10 most active)
                            const pathsDiv = document.getElementById('paths-chart');
                            const paths = Object.keys(data.paths_activity)
                                .map(path => ({{path, ...data.paths_activity[path]}}))
                                .sort((a, b) => b.total - a.total)
                                .slice(0, 10);
                            
                            let maxPathOps = 0;
                            for (let pathData of paths) {{
                                maxPathOps = Math.max(maxPathOps, pathData.total);
                            }}
                            
                            for (let pathData of paths) {{
                                const successWidth = (pathData.success / maxPathOps) * 100;
                                const failureWidth = (pathData.failure / maxPathOps) * 100;
                                
                                pathsDiv.innerHTML += `
                                    <div style="margin-bottom: 10px;">
                                        <div style="display: flex; align-items: center;">
                                            <div style="width: 250px; overflow: hidden; text-overflow: ellipsis;">
                                                ${pathData.path}
                                            </div>
                                            <div style="flex-grow: 1;">
                                                <div class="bar" style="width: ${successWidth}%"></div>
                                                <div class="bar failure" style="width: ${failureWidth}%"></div>
                                            </div>
                                            <div style="width: 100px; text-align: right;">
                                                ${pathData.total} ops
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }}
                        }};
                    </script>
                </head>
                <body>
                    <h1>Filesystem Journal Visualization</h1>
                    <p>Time window: {time_window} hours, Total operations: {len(filtered_ops)}</p>
                    
                    <h2>Activity by Hour</h2>
                    <div id="hourly-chart" class="chart"></div>
                    
                    <h2>Activity by Operation Type</h2>
                    <div id="op-types-chart" class="chart"></div>
                    
                    <h2>Top 10 Most Active Paths</h2>
                    <div id="paths-chart" class="chart"></div>
                    
                    <p>Generated on: {datetime.now().isoformat()}</p>
                </body>
                </html>
                """
                
                # Save the HTML to a temp file
                with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w') as f:
                    f.write(html)
                    html_path = f.name
                
                return {
                    "format": "html",
                    "file_path": html_path,
                    "visualization_data": visualization_data
                }
            
            except ImportError:
                return {"error": "HTML visualization requires additional libraries"}
        
        elif format.lower() == "text":
            # Generate a text-based visualization
            text_output = []
            
            text_output.append(f"Filesystem Journal Visualization")
            text_output.append(f"Time window: {time_window} hours")
            text_output.append(f"Total operations: {len(filtered_ops)}")
            text_output.append("")
            
            # Activity by hour
            text_output.append("Activity by Hour:")
            sorted_hours = sorted(hourly_activity.keys())
            for hour in sorted_hours:
                activity = hourly_activity[hour]
                text_output.append(f"  {hour}: {activity['total']} operations ({activity['success']} success, {activity['failure']} failure)")
            text_output.append("")
            
            # Activity by operation type
            text_output.append("Activity by Operation Type:")
            sorted_types = sorted(op_types_count.keys())
            for op_type in sorted_types:
                counts = op_types_count[op_type]
                text_output.append(f"  {op_type}: {counts['total']} operations ({counts['success']} success, {counts['failure']} failure)")
            text_output.append("")
            
            # Top 10 most active paths
            text_output.append("Top 10 Most Active Paths:")
            sorted_paths = sorted(paths_activity.items(), key=lambda x: x[1]["total"], reverse=True)[:10]
            for path, counts in sorted_paths:
                text_output.append(f"  {path}: {counts['total']} operations ({counts['success']} success, {counts['failure']} failure)")
            
            return {
                "format": "text",
                "text_visualization": "\n".join(text_output),
                "visualization_data": visualization_data
            }
        
        else:
            return {"error": f"Unsupported format: {format}. Supported formats are json, html, text"}
    
    except Exception as e:
        return {"error": f"Failed to generate visualization: {str(e)}"}


def fs_virtual_stats(path: str = "/", virtual_fs=None):
    """
    Get statistics about the virtual filesystem.
    
    Args:
        path: Path to get statistics for
        virtual_fs: The virtual filesystem instance
        
    Returns:
        Dictionary with filesystem statistics
    """
    if virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Check if path exists
        if not virtual_fs.exists(path):
            return {"error": f"Path {path} does not exist"}
        
        # Statistics to collect
        file_count = 0
        dir_count = 0
        total_size = 0
        cids = set()
        max_depth = 0
        path_lengths = []
        
        # Helper function for recursive statistics gathering
        def collect_stats(current_path, depth=0):
            nonlocal file_count, dir_count, total_size, max_depth
            
            # Update max depth
            max_depth = max(max_depth, depth)
            
            # Get entry stats
            stats = virtual_fs.get_stats(current_path)
            if stats is None:
                return
            
            # Check if it's a directory
            is_directory = stats.get("is_directory", False)
            
            if is_directory:
                dir_count += 1
                
                # Process entries in the directory
                entries = virtual_fs.list(current_path) or []
                for name in entries:
                    entry_path = os.path.join(current_path, name).replace("\\", "/")
                    if entry_path.startswith("//"):
                        entry_path = entry_path[1:]
                    
                    path_lengths.append(len(entry_path))
                    collect_stats(entry_path, depth + 1)
            
            else:
                # It's a file
                file_count += 1
                path_lengths.append(len(current_path))
                
                # Get the file size
                size = stats.get("size", 0)
                total_size += size
                
                # Track CID if available
                cid = stats.get("cid")
                if cid:
                    cids.add(cid)
        
        # Start collecting statistics from the given path
        collect_stats(path)
        
        # Calculate additional statistics
        avg_path_length = sum(path_lengths) / len(path_lengths) if path_lengths else 0
        
        return {
            "path": path,
            "file_count": file_count,
            "directory_count": dir_count,
            "total_entries": file_count + dir_count,
            "total_size_bytes": total_size,
            "unique_cids": len(cids),
            "max_depth": max_depth,
            "average_path_length": avg_path_length,
            "stats": virtual_fs.get_stats(path)
        }
    
    except Exception as e:
        return {"error": f"Failed to get filesystem statistics: {str(e)}"}


# Main entry point for the module
def main():
    """
    Main entry point for the script when run directly.
    
    Registers filesystem journal tools with a running MCP server.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Register filesystem journal tools with MCP server"
    )
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("MCP_PORT", "9994")),
        help="Port where the MCP server is running (default: 9994)"
    )
    parser.add_argument(
        "--host", type=str, default="localhost",
        help="Host where the MCP server is running (default: localhost)"
    )
    args = parser.parse_args()
    
    logger.info(f"Registering filesystem journal tools with MCP server at {args.host}:{args.port}")
    
    try:
        # Try to import and connect to MCP server
        from ipfs_kit_py.mcp.server_bridge import MCPServerClient
        
        client = MCPServerClient(host=args.host, port=args.port)
        
        # Register the tools
        result = register_fs_journal_tools(client)
        
        if result:
            logger.info("Successfully registered filesystem journal tools")
            return 0
        else:
            logger.error("Failed to register filesystem journal tools")
            return 1
    
    except ImportError:
        logger.error("Could not import necessary modules for MCP server integration")
        return 1
    except Exception as e:
        logger.error(f"Error registering tools: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
