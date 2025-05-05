#!/usr/bin/env python3
"""
Enhanced IPFS Virtual Filesystem MCP Integration

This module enhances the Model Context Protocol (MCP) server with comprehensive
virtual filesystem capabilities from the ipfs_kit_py project.

It integrates:
1. Filesystem Journal - for tracking file operations
2. IPFS-FS Bridge - for mapping between IPFS and local filesystem
3. Multi-backend storage - for using multiple storage backends
4. Virtual filesystem operations - for working with the virtual filesystem
"""

import os
import sys
import json
import logging
import asyncio
import traceback
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Component availability checks ---

# Check for filesystem journal availability
try:
    from ipfs_kit_py.mcp.fs.fs_journal import (
        VirtualFS, FSJournal, FSOperation, FSOperationType, FSController, 
        integrate_fs_with_mcp
    )
    FS_JOURNAL_AVAILABLE = True
    logger.info("✅ Filesystem journal functionality is available")
except ImportError:
    FS_JOURNAL_AVAILABLE = False
    logger.warning("⚠️ Filesystem journal functionality is not available")

# Check for IPFS-FS bridge availability
try:
    from ipfs_kit_py.mcp.fs.fs_ipfs_bridge import (
        IPFSFSBridge, create_fs_ipfs_bridge
    )
    IPFS_FS_BRIDGE_AVAILABLE = True
    logger.info("✅ IPFS-FS bridge functionality is available")
except ImportError:
    IPFS_FS_BRIDGE_AVAILABLE = False
    logger.warning("⚠️ IPFS-FS bridge functionality is not available")

# Check for multi-backend storage availability
try:
    from ipfs_kit_py.mcp.storage_manager.manager import UnifiedStorageManager
    MULTI_BACKEND_AVAILABLE = True
    logger.info("✅ Multi-backend storage functionality is available")
except ImportError:
    MULTI_BACKEND_AVAILABLE = False
    logger.warning("⚠️ Multi-backend storage functionality is not available")

# --- Global instances for components ---
fs_journal = None
virtual_fs = None
fs_controller = None
ipfs_fs_bridge = None
unified_storage = None

# --- Component initialization ---
def initialize_components(mcp_server=None):
    """Initialize all filesystem and storage components"""
    global fs_journal, virtual_fs, fs_controller, ipfs_fs_bridge, unified_storage
    
    # Initialize journal and virtual filesystem
    if FS_JOURNAL_AVAILABLE:
        try:
            # Create journal path
            journal_path = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "fs_journal.json")
            os.makedirs(os.path.dirname(journal_path), exist_ok=True)
            
            # Create journal and virtual filesystem
            fs_journal = FSJournal(journal_path)
            virtual_fs = VirtualFS(fs_journal)
            fs_controller = FSController(virtual_fs)
            
            logger.info("Initialized filesystem journal and virtual filesystem")
            
            # If MCP server is provided, integrate with it
            if mcp_server and hasattr(mcp_server, 'app'):
                router = fs_controller.create_router()
                if router:
                    prefix = getattr(mcp_server, 'api_prefix', '/api/v0')
                    mcp_server.app.include_router(router, prefix=prefix)
                    logger.info(f"Registered filesystem controller router with MCP server at {prefix}")
        except Exception as e:
            logger.error(f"Error initializing filesystem journal: {e}")
            logger.error(traceback.format_exc())
    
    # Initialize IPFS-FS bridge
    if IPFS_FS_BRIDGE_AVAILABLE and fs_controller:
        try:
            # Get IPFS controller and model from global registry if available
            ipfs_controller = None
            ipfs_model = None
            
            if mcp_server:
                if hasattr(mcp_server, 'controllers') and 'ipfs' in mcp_server.controllers:
                    ipfs_controller = mcp_server.controllers['ipfs']
                if hasattr(mcp_server, 'models') and 'ipfs' in mcp_server.models:
                    ipfs_model = mcp_server.models['ipfs']
            
            # Create bridge
            ipfs_fs_bridge = IPFSFSBridge(fs_controller, ipfs_model, ipfs_controller)
            
            logger.info("Initialized IPFS-FS bridge")
            
            # Patch IPFS model to track operations in journal
            if ipfs_model:
                if ipfs_fs_bridge.patch_ipfs_model():
                    logger.info("Patched IPFS model to track operations in filesystem journal")
                else:
                    logger.warning("Could not patch IPFS model")
        except Exception as e:
            logger.error(f"Error initializing IPFS-FS bridge: {e}")
            logger.error(traceback.format_exc())
    
    # Initialize unified storage manager
    if MULTI_BACKEND_AVAILABLE:
        try:
            # Configuration for unified storage
            config = {
                "content_registry_path": os.path.expanduser("~/.ipfs_kit/content_registry.json"),
                "storage_backends": {
                    "ipfs": {
                        "type": "ipfs",
                        "enabled": True
                    },
                    "local": {
                        "type": "local",
                        "enabled": True,
                        "path": os.path.expanduser("~/.ipfs_kit/local_storage")
                    }
                }
            }
            
            # Create directory for local storage
            os.makedirs(os.path.expanduser("~/.ipfs_kit/local_storage"), exist_ok=True)
            
            # Initialize unified storage manager
            unified_storage = UnifiedStorageManager(config)
            
            logger.info("Initialized unified storage manager")
        except Exception as e:
            logger.error(f"Error initializing unified storage manager: {e}")
            logger.error(traceback.format_exc())
    
    return {
        "fs_journal_available": FS_JOURNAL_AVAILABLE and fs_journal is not None,
        "ipfs_fs_bridge_available": IPFS_FS_BRIDGE_AVAILABLE and ipfs_fs_bridge is not None,
        "unified_storage_available": MULTI_BACKEND_AVAILABLE and unified_storage is not None
    }

# --- FS Journal Tool Implementations ---
async def fs_journal_get_history(path=None, limit=100, operation_type="all"):
    """Get operation history for a path from the filesystem journal"""
    if not FS_JOURNAL_AVAILABLE or fs_journal is None:
        return {"error": "Filesystem journal not available"}
    
    try:
        if path:
            # Get operations for a specific path
            operations = fs_journal.get_operations_for_path(path)
            
            # Filter by operation type if specified
            if operation_type != "all":
                operations = [op for op in operations if op.op_type.name.lower() == operation_type.lower()]
            
            # Limit the number of results
            operations = operations[:limit]
            
            # Convert operations to dictionaries
            result = []
            for op in operations:
                result.append({
                    "timestamp": op.timestamp,
                    "operation_type": op.op_type.name,
                    "path": op.path,
                    "success": op.success,
                    "error_message": op.error_message
                })
            
            return {
                "operations": result,
                "total": len(operations),
                "path": path
            }
        else:
            # Get all operations
            operations = fs_journal.operations
            
            # Filter by operation type if specified
            if operation_type != "all":
                operations = [op for op in operations if op.op_type.name.lower() == operation_type.lower()]
            
            # Limit the number of results
            operations = operations[-limit:]
            
            # Convert operations to dictionaries
            result = []
            for op in operations:
                result.append({
                    "timestamp": op.timestamp,
                    "operation_type": op.op_type.name,
                    "path": op.path,
                    "success": op.success,
                    "error_message": op.error_message
                })
            
            return {
                "operations": result,
                "total": len(fs_journal.operations)
            }
    except Exception as e:
        logger.error(f"Error getting journal history: {e}")
        return {"error": str(e)}

async def fs_journal_sync(path="/"):
    """Force synchronization between virtual filesystem and actual storage"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Synchronize path with storage
        result = virtual_fs.sync(path)
        return {
            "success": result,
            "path": path,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error syncing filesystem: {e}")
        return {"error": str(e)}

async def fs_journal_track(path):
    """Start tracking operations on a path in the filesystem"""
    if not FS_JOURNAL_AVAILABLE or fs_journal is None:
        return {"error": "Filesystem journal not available"}
    
    try:
        fs_journal.track_path(path)
        return {
            "success": True,
            "path": path,
            "message": f"Now tracking operations on {path}"
        }
    except Exception as e:
        logger.error(f"Error tracking path: {e}")
        return {"error": str(e)}

async def fs_journal_untrack(path):
    """Stop tracking operations on a path in the filesystem"""
    if not FS_JOURNAL_AVAILABLE or fs_journal is None:
        return {"error": "Filesystem journal not available"}
    
    try:
        fs_journal.untrack_path(path)
        return {
            "success": True,
            "path": path,
            "message": f"Stopped tracking operations on {path}"
        }
    except Exception as e:
        logger.error(f"Error untracking path: {e}")
        return {"error": str(e)}

async def fs_journal_status():
    """Get the status of the filesystem journal"""
    if not FS_JOURNAL_AVAILABLE or fs_journal is None:
        return {"error": "Filesystem journal not available"}
    
    try:
        # Get status information
        num_operations = len(fs_journal.operations)
        tracked_paths = fs_journal.tracked_paths
        
        return {
            "status": "active",
            "operations_count": num_operations,
            "tracked_paths": tracked_paths,
            "journal_path": fs_journal.journal_path
        }
    except Exception as e:
        logger.error(f"Error getting journal status: {e}")
        return {"error": str(e)}

# --- IPFS-FS Bridge Tool Implementations ---
async def ipfs_fs_bridge_status():
    """Get the status of the IPFS-FS bridge"""
    if not IPFS_FS_BRIDGE_AVAILABLE or ipfs_fs_bridge is None:
        return {"error": "IPFS-FS bridge not available"}
    
    try:
        # Get mappings
        cid_to_path = ipfs_fs_bridge.cid_to_path_map
        path_to_cid = ipfs_fs_bridge.path_to_cid_map
        
        return {
            "status": "active",
            "patched": ipfs_fs_bridge.is_patched,
            "mappings_count": len(path_to_cid),
            "cids_count": len(cid_to_path)
        }
    except Exception as e:
        logger.error(f"Error getting bridge status: {e}")
        return {"error": str(e)}

async def ipfs_fs_bridge_sync(path="/", direction="both"):
    """Sync between IPFS and virtual filesystem"""
    if not IPFS_FS_BRIDGE_AVAILABLE or ipfs_fs_bridge is None:
        return {"error": "IPFS-FS bridge not available"}
    
    try:
        if direction == "ipfs_to_fs" or direction == "both":
            # For each CID in our mapping, import to virtual filesystem
            success_count = 0
            fail_count = 0
            
            for cid, paths in ipfs_fs_bridge.cid_to_path_map.items():
                for path in paths:
                    try:
                        result = await ipfs_fs_bridge.import_ipfs_to_vfs(cid, path)
                        if result:
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as e:
                        logger.error(f"Error importing {cid} to {path}: {e}")
                        fail_count += 1
            
            if direction == "ipfs_to_fs":
                return {
                    "success": fail_count == 0,
                    "direction": "ipfs_to_fs",
                    "success_count": success_count,
                    "fail_count": fail_count
                }
        
        if direction == "fs_to_ipfs" or direction == "both":
            # For each path in our mapping, export to IPFS
            success_count = 0
            fail_count = 0
            
            for fs_path, cid in ipfs_fs_bridge.path_to_cid_map.items():
                try:
                    new_cid = await ipfs_fs_bridge.export_vfs_to_ipfs(fs_path)
                    if new_cid:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logger.error(f"Error exporting {fs_path}: {e}")
                    fail_count += 1
            
            if direction == "fs_to_ipfs":
                return {
                    "success": fail_count == 0,
                    "direction": "fs_to_ipfs",
                    "success_count": success_count,
                    "fail_count": fail_count
                }
        
        if direction == "both":
            return {
                "success": fail_count == 0,
                "direction": "both",
                "success_count": success_count,
                "fail_count": fail_count
            }
        
        return {"error": f"Invalid direction: {direction}"}
    except Exception as e:
        logger.error(f"Error syncing: {e}")
        return {"error": str(e)}

async def ipfs_fs_bridge_map(ipfs_path, fs_path):
    """Map an IPFS path to a filesystem path"""
    if not IPFS_FS_BRIDGE_AVAILABLE or ipfs_fs_bridge is None:
        return {"error": "IPFS-FS bridge not available"}
    
    try:
        # Extract CID from IPFS path
        if ipfs_path.startswith("/ipfs/"):
            cid = ipfs_path.split("/")[2]
        else:
            cid = ipfs_path
        
        # Map CID to path
        ipfs_fs_bridge.map_cid_to_path(cid, fs_path)
        
        return {
            "success": True,
            "cid": cid,
            "fs_path": fs_path,
            "message": f"Mapped {cid} to {fs_path}"
        }
    except Exception as e:
        logger.error(f"Error mapping: {e}")
        return {"error": str(e)}

async def ipfs_fs_bridge_unmap(fs_path):
    """Remove a mapping between IPFS and filesystem"""
    if not IPFS_FS_BRIDGE_AVAILABLE or ipfs_fs_bridge is None:
        return {"error": "IPFS-FS bridge not available"}
    
    try:
        # Get CID for path
        cid = ipfs_fs_bridge.get_cid_for_path(fs_path)
        if not cid:
            return {
                "success": False,
                "error": f"No mapping found for {fs_path}"
            }
        
        # Remove mapping
        if cid in ipfs_fs_bridge.cid_to_path_map and fs_path in ipfs_fs_bridge.cid_to_path_map[cid]:
            ipfs_fs_bridge.cid_to_path_map[cid].remove(fs_path)
            if len(ipfs_fs_bridge.cid_to_path_map[cid]) == 0:
                del ipfs_fs_bridge.cid_to_path_map[cid]
        
        if fs_path in ipfs_fs_bridge.path_to_cid_map:
            del ipfs_fs_bridge.path_to_cid_map[fs_path]
        
        return {
            "success": True,
            "fs_path": fs_path,
            "cid": cid,
            "message": f"Unmapped {fs_path} from {cid}"
        }
    except Exception as e:
        logger.error(f"Error unmapping: {e}")
        return {"error": str(e)}

async def ipfs_fs_bridge_list_mappings():
    """List all mappings between IPFS and filesystem"""
    if not IPFS_FS_BRIDGE_AVAILABLE or ipfs_fs_bridge is None:
        return {"error": "IPFS-FS bridge not available"}
    
    try:
        # Get mappings
        mappings = []
        for fs_path, cid in ipfs_fs_bridge.path_to_cid_map.items():
            mappings.append({
                "fs_path": fs_path,
                "cid": cid
            })
        
        return {
            "success": True,
            "mappings": mappings,
            "count": len(mappings)
        }
    except Exception as e:
        logger.error(f"Error listing mappings: {e}")
        return {"error": str(e)}

async def ipfs_fs_export_to_ipfs(path):
    """Export a file from the virtual filesystem to IPFS"""
    if not IPFS_FS_BRIDGE_AVAILABLE or ipfs_fs_bridge is None:
        return {"error": "IPFS-FS bridge not available"}
    
    try:
        # Export to IPFS
        cid = await ipfs_fs_bridge.export_vfs_to_ipfs(path)
        if cid:
            return {
                "success": True,
                "path": path,
                "cid": cid,
                "ipfs_path": f"/ipfs/{cid}"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to export {path} to IPFS"
            }
    except Exception as e:
        logger.error(f"Error exporting to IPFS: {e}")
        return {"error": str(e)}

async def ipfs_fs_import_from_ipfs(cid, path):
    """Import a file from IPFS to the virtual filesystem"""
    if not IPFS_FS_BRIDGE_AVAILABLE or ipfs_fs_bridge is None:
        return {"error": "IPFS-FS bridge not available"}
    
    try:
        # Import from IPFS
        result = await ipfs_fs_bridge.import_ipfs_to_vfs(cid, path)
        if result:
            return {
                "success": True,
                "cid": cid,
                "path": path,
                "ipfs_path": f"/ipfs/{cid}"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to import {cid} to {path}"
            }
    except Exception as e:
        logger.error(f"Error importing from IPFS: {e}")
        return {"error": str(e)}

# --- Storage Backend Tool Implementations ---

async def init_ipfs_backend(api_url="http://localhost:5001/api/v0"):
    """Initialize IPFS backend for the virtual filesystem"""
    if not MULTI_BACKEND_AVAILABLE or unified_storage is None:
        return {"error": "Multi-backend storage not available"}
    
    try:
        # Initialize IPFS backend
        config = {
            "type": "ipfs",
            "api_url": api_url,
            "enabled": True
        }
        
        unified_storage.add_backend("ipfs", config)
        
        return {
            "success": True,
            "backend": "ipfs",
            "api_url": api_url
        }
    except Exception as e:
        logger.error(f"Error initializing IPFS backend: {e}")
        return {"error": str(e)}

async def init_filecoin_backend(api_url="http://localhost:1234/rpc/v0"):
    """Initialize Filecoin backend for the virtual filesystem"""
    if not MULTI_BACKEND_AVAILABLE or unified_storage is None:
        return {"error": "Multi-backend storage not available"}
    
    try:
        # Initialize Filecoin backend
        config = {
            "type": "filecoin",
            "api_url": api_url,
            "enabled": True
        }
        
        unified_storage.add_backend("filecoin", config)
        
        return {
            "success": True,
            "backend": "filecoin",
            "api_url": api_url
        }
    except Exception as e:
        logger.error(f"Error initializing Filecoin backend: {e}")
        return {"error": str(e)}

async def init_s3_backend(bucket_name, endpoint_url=None, access_key=None, secret_key=None):
    """Initialize S3 backend for the virtual filesystem"""
    if not MULTI_BACKEND_AVAILABLE or unified_storage is None:
        return {"error": "Multi-backend storage not available"}
    
    try:
        # Initialize S3 backend
        config = {
            "type": "s3",
            "bucket_name": bucket_name,
            "enabled": True
        }
        
        if endpoint_url:
            config["endpoint_url"] = endpoint_url
        
        if access_key:
            config["access_key"] = access_key
        
        if secret_key:
            config["secret_key"] = secret_key
        
        unified_storage.add_backend("s3", config)
        
        return {
            "success": True,
            "backend": "s3",
            "bucket_name": bucket_name
        }
    except Exception as e:
        logger.error(f"Error initializing S3 backend: {e}")
        return {"error": str(e)}

async def storage_status(backend="all"):
    """Get status of storage backends"""
    if not MULTI_BACKEND_AVAILABLE or unified_storage is None:
        return {"error": "Multi-backend storage not available"}
    
    try:
        backends = unified_storage.list_backends()
        
        if backend != "all":
            if backend in backends:
                return {
                    "backend": backend,
                    "status": backends[backend]
                }
            else:
                return {
                    "error": f"Backend {backend} not found",
                    "available_backends": list(backends.keys())
                }
        
        return {
            "backends": backends
        }
    except Exception as e:
        logger.error(f"Error getting storage status: {e}")
        return {"error": str(e)}

async def storage_transfer(source, destination, identifier):
    """Transfer content between storage backends"""
    if not MULTI_BACKEND_AVAILABLE or unified_storage is None:
        return {"error": "Multi-backend storage not available"}
    
    try:
        # Check if source backend exists
        backends = unified_storage.list_backends()
        if source not in backends:
            return {
                "error": f"Source backend {source} not found",
                "available_backends": list(backends.keys())
            }
        
        # Check if destination backend exists
        if destination not in backends:
            return {
                "error": f"Destination backend {destination} not found",
                "available_backends": list(backends.keys())
            }
        
        # Transfer content
        result = await unified_storage.transfer(source, destination, identifier)
        
        return {
            "success": result["success"],
            "source": source,
            "destination": destination,
            "source_id": identifier,
            "destination_id": result.get("destination_id"),
            "error": result.get("error")
        }
    except Exception as e:
        logger.error(f"Error transferring content: {e}")
        return {"error": str(e)}

# --- Virtual Filesystem Tool Implementations ---

async def vfs_list(path="/"):
    """List files in a virtual filesystem directory"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # List directory
        entries = virtual_fs.list_directory(path)
        
        # Format result
        result = []
        for name, entry_type in entries.items():
            if name == "." or name == "..":
                continue
                
            entry_path = os.path.join(path, name)
            if entry_type == "directory":
                result.append({
                    "name": name,
                    "type": "directory",
                    "path": entry_path
                })
            else:
                # Get CID if available
                cid = None
                if ipfs_fs_bridge:
                    cid = ipfs_fs_bridge.get_cid_for_path(entry_path)
                
                file_info = virtual_fs.get_file_info(entry_path)
                
                result.append({
                    "name": name,
                    "type": "file",
                    "path": entry_path,
                    "size": file_info.get("size", 0),
                    "cid": cid
                })
        
        return {
            "success": True,
            "path": path,
            "entries": result
        }
    except Exception as e:
        logger.error(f"Error listing directory: {e}")
        return {"error": str(e)}

async def vfs_read(path):
    """Read a file from the virtual filesystem"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Read file
        content = virtual_fs.read_file(path)
        if content is None:
            return {"error": f"File not found: {path}"}
        
        # Get CID if available
        cid = None
        if ipfs_fs_bridge:
            cid = ipfs_fs_bridge.get_cid_for_path(path)
        
        # Get file info
        file_info = virtual_fs.get_file_info(path)
        
        return {
            "success": True,
            "path": path,
            "content": content.decode('utf-8', errors='replace'),
            "size": len(content),
            "cid": cid,
            "last_modified": file_info.get("last_modified")
        }
    except UnicodeDecodeError:
        # For binary files, return base64 encoded content
        import base64
        
        return {
            "success": True,
            "path": path,
            "content": base64.b64encode(content).decode('ascii'),
            "encoding": "base64",
            "size": len(content),
            "cid": cid,
            "last_modified": file_info.get("last_modified")
        }
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        return {"error": str(e)}

async def vfs_write(path, content, metadata=None):
    """Write to a file in the virtual filesystem"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Convert string content to bytes
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        # Write file
        result = virtual_fs.write_file(path, content_bytes)
        
        # Update metadata if provided
        if metadata and result:
            virtual_fs.set_metadata(path, metadata)
        
        # Export to IPFS if bridge is available
        cid = None
        if result and ipfs_fs_bridge:
            cid = await ipfs_fs_bridge.export_vfs_to_ipfs(path)
        
        return {
            "success": result,
            "path": path,
            "size": len(content_bytes),
            "cid": cid
        }
    except Exception as e:
        logger.error(f"Error writing file: {e}")
        return {"error": str(e)}

async def vfs_mkdir(path, metadata=None):
    """Create a directory in the virtual filesystem"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Create directory
        result = virtual_fs.create_directory(path)
        
        # Update metadata if provided
        if metadata and result:
            virtual_fs.set_metadata(path, metadata)
        
        return {
            "success": result,
            "path": path
        }
    except Exception as e:
        logger.error(f"Error creating directory: {e}")
        return {"error": str(e)}

async def vfs_rm(path, recursive=False):
    """Remove a file or directory from the virtual filesystem"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Check if path exists
        if not virtual_fs.exists(path):
            return {"error": f"Path not found: {path}"}
        
        # Check if it's a directory
        is_dir = virtual_fs.is_directory(path)
        
        if is_dir:
            if not recursive:
                # Check if directory is empty
                entries = virtual_fs.list_directory(path)
                if entries and len(entries) > 2:  # More than . and ..
                    return {
                        "error": f"Directory not empty: {path}. Use recursive=True to remove"
                    }
            
            # Remove directory
            result = virtual_fs.remove_directory(path, recursive)
        else:
            # Remove file
            result = virtual_fs.remove_file(path)
        
        return {
            "success": result,
            "path": path
        }
    except Exception as e:
        logger.error(f"Error removing path: {e}")
        return {"error": str(e)}

async def vfs_copy(source, destination):
    """Copy a file or directory in the virtual filesystem"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Check if source exists
        if not virtual_fs.exists(source):
            return {"error": f"Source path not found: {source}"}
        
        # Check if it's a directory
        is_dir = virtual_fs.is_directory(source)
        
        if is_dir:
            # Copy directory (recursive)
            result = virtual_fs.copy_directory(source, destination)
        else:
            # Copy file
            result = virtual_fs.copy_file(source, destination)
        
        return {
            "success": result,
            "source": source,
            "destination": destination
        }
    except Exception as e:
        logger.error(f"Error copying: {e}")
        return {"error": str(e)}

async def vfs_move(source, destination):
    """Move a file or directory in the virtual filesystem"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Check if source exists
        if not virtual_fs.exists(source):
            return {"error": f"Source path not found: {source}"}
        
        # Move file or directory
        result = virtual_fs.move(source, destination)
        
        return {
            "success": result,
            "source": source,
            "destination": destination
        }
    except Exception as e:
        logger.error(f"Error moving: {e}")
        return {"error": str(e)}

async def vfs_stat(path):
    """Get information about a file or directory in the virtual filesystem"""
    if not FS_JOURNAL_AVAILABLE or virtual_fs is None:
        return {"error": "Virtual filesystem not available"}
    
    try:
        # Check if path exists
        if not virtual_fs.exists(path):
            return {"error": f"Path not found: {path}"}
        
        # Check if it's a directory
        is_dir = virtual_fs.is_directory(path)
        
        if is_dir:
            # Get directory info
            info = virtual_fs.get_directory_info(path)
            
            # Format result
            result = {
                "type": "directory",
                "path": path,
                "name": os.path.basename(path),
                "last_modified": info.get("last_modified"),
                "entries_count": len(info.get("entries", {})) - 2  # Subtract . and ..
            }
            
            # Add metadata if available
            metadata = virtual_fs.get_metadata(path)
            if metadata:
                result["metadata"] = metadata
            
            return result
        else:
            # Get file info
            info = virtual_fs.get_file_info(path)
            
            # Get CID if available
            cid = None
            if ipfs_fs_bridge:
                cid = ipfs_fs_bridge.get_cid_for_path(path)
            
            # Format result
            result = {
                "type": "file",
                "path": path,
                "name": os.path.basename(path),
                "size": info.get("size", 0),
                "last_modified": info.get("last_modified"),
                "cid": cid
            }
            
            # Add metadata if available
            metadata = virtual_fs.get_metadata(path)
            if metadata:
                result["metadata"] = metadata
            
            return result
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"error": str(e)}

# --- MCP Server Integration ---

def register_all_fs_tools(mcp_server):
    """
    Register all filesystem tools with the MCP server
    
    Args:
        mcp_server: The MCP server to register tools with
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Initialize components
        status = initialize_components(mcp_server)
        logger.info(f"Component initialization status: {status}")
        
        # Register tools with the server
        all_tools = []
        
        # FS Journal tools
        fs_journal_tools = [
            {"name": "fs_journal_get_history", "handler": fs_journal_get_history},
            {"name": "fs_journal_sync", "handler": fs_journal_sync},
            {"name": "fs_journal_track", "handler": fs_journal_track},
            {"name": "fs_journal_untrack", "handler": fs_journal_untrack},
            {"name": "fs_journal_status", "handler": fs_journal_status}
        ]
        all_tools.extend(fs_journal_tools)
        
        # IPFS-FS Bridge tools
        ipfs_fs_bridge_tools = [
            {"name": "ipfs_fs_bridge_status", "handler": ipfs_fs_bridge_status},
            {"name": "ipfs_fs_bridge_sync", "handler": ipfs_fs_bridge_sync},
            {"name": "ipfs_fs_bridge_map", "handler": ipfs_fs_bridge_map},
            {"name": "ipfs_fs_bridge_unmap", "handler": ipfs_fs_bridge_unmap},
            {"name": "ipfs_fs_bridge_list_mappings", "handler": ipfs_fs_bridge_list_mappings},
            {"name": "ipfs_fs_export_to_ipfs", "handler": ipfs_fs_export_to_ipfs},
            {"name": "ipfs_fs_import_from_ipfs", "handler": ipfs_fs_import_from_ipfs}
        ]
        all_tools.extend(ipfs_fs_bridge_tools)
        
        # Storage Backend tools
        storage_tools = [
            {"name": "init_ipfs_backend", "handler": init_ipfs_backend},
            {"name": "init_filecoin_backend", "handler": init_filecoin_backend},
            {"name": "init_s3_backend", "handler": init_s3_backend},
            {"name": "storage_status", "handler": storage_status},
            {"name": "storage_transfer", "handler": storage_transfer},
        ]
        all_tools.extend(storage_tools)
        
        # Virtual Filesystem tools
        vfs_tools = [
            {"name": "vfs_list", "handler": vfs_list},
            {"name": "vfs_read", "handler": vfs_read},
            {"name": "vfs_write", "handler": vfs_write},
            {"name": "vfs_mkdir", "handler": vfs_mkdir},
            {"name": "vfs_rm", "handler": vfs_rm},
            {"name": "vfs_copy", "handler": vfs_copy},
            {"name": "vfs_move", "handler": vfs_move},
            {"name": "vfs_stat", "handler": vfs_stat}
        ]
        all_tools.extend(vfs_tools)
        
        # Register all tools
        for tool in all_tools:
            try:
                name = tool["name"]
                handler = tool["handler"]
                
                # Find the tool definition in direct_tool_registry
                from direct_tool_registry import create_tool_registry
                tool_defs = create_tool_registry()
                
                tool_def = None
                for td in tool_defs:
                    if td["name"] == name:
                        tool_def = td
                        break
                
                if tool_def:
                    schema = tool_def["schema"]
                    description = tool_def["description"]
                else:
                    # Use default schema and description
                    schema = {"type": "object", "properties": {}}
                    description = f"Tool: {name}"
                
                # Register the tool - adapt to your MCP server API
                if hasattr(mcp_server, "register_tool"):
                    mcp_server.register_tool(
                        name=name,
                        schema=schema,
                        description=description,
                        handler=handler
                    )
                elif hasattr(mcp_server, "tool"):
                    # Alternative decorator-style registration
                    @mcp_server.tool(name=name, schema=schema)
                    async def tool_wrapper(ctx):
                        return await handler(**ctx.params)
                else:
                    # If no registration method found, try adding directly to tools dictionary
                    if hasattr(mcp_server, "tools"):
                        # Create a wrapper function that calls the handler
                        async def create_wrapper(h):
                            async def wrapper(params):
                                return await h(**params)
                            return wrapper
                            
                        mcp_server.tools[name] = {
                            "name": name,
                            "description": description,
                            "schema": schema,
                            "handler": await create_wrapper(handler)
                        }
                    
                logger.info(f"✅ Registered tool: {name}")
                
            except Exception as e:
                logger.error(f"Error registering tool {tool['name']}: {e}")
                logger.error(traceback.format_exc())
        
        logger.info(f"✅ Registered {len(all_tools)} virtual filesystem tools with MCP server")
        return True
        
    except Exception as e:
        logger.error(f"Error registering filesystem tools: {e}")
        logger.error(traceback.format_exc())
        return False

# --- Main execution ---
if __name__ == "__main__":
    # Test initializing components
    status = initialize_components()
    print(f"Component initialization status: {status}")
    
    # If all components initialized successfully, you can test the tools
    if status["fs_journal_available"] and status["ipfs_fs_bridge_available"]:
        print("All components initialized successfully. You can now test the tools.")
    else:
        print("Some components failed to initialize. Check the logs for details.")
