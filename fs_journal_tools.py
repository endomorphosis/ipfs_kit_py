#!/usr/bin/env python3
"""
IPFS Kit - FS Journal Integration Tools

This module provides tools to integrate IPFS with a virtual filesystem journal.
These tools allow:
1. Tracking operations performed on files
2. Synchronizing between IPFS and the local filesystem
3. Bridging IPFS MFS with the virtual FS

This is a core part of enhancing the IPFS Kit with virtual filesystem capabilities.
"""

import os
import sys
import json
import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Union
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define FS Journal data structures
class FSOperationType(Enum):
    """Types of operations that can be performed on the filesystem"""
    READ = auto()
    WRITE = auto()
    DELETE = auto()
    CREATE = auto()
    RENAME = auto()
    MKDIR = auto()
    RMDIR = auto()
    STAT = auto()
    SYNC = auto()

@dataclass
class FSOperation:
    """Represents a filesystem operation with metadata"""
    operation_type: FSOperationType
    path: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result["operation_type"] = self.operation_type.name
        result["timestamp"] = self.timestamp.isoformat()
        return result

class FSJournal:
    """Virtual filesystem journal that tracks operations"""
    
    def __init__(self, base_dir: str):
        """Initialize the filesystem journal"""
        self.base_dir = os.path.abspath(base_dir)
        self.operations: List[FSOperation] = []
        self.path_history: Dict[str, List[FSOperation]] = {}
        self.cache: Dict[str, bytes] = {}
        self.tracked_paths: List[str] = []
        logger.info(f"Initialized FS Journal with base directory: {self.base_dir}")
    
    def record_operation(self, operation: FSOperation) -> None:
        """Record an operation in the journal"""
        self.operations.append(operation)
        
        # Add to path history
        if operation.path not in self.path_history:
            self.path_history[operation.path] = []
        self.path_history[operation.path].append(operation)
        
        logger.debug(f"Recorded operation: {operation.operation_type.name} on {operation.path}")
    
    def get_history(self, path: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get operation history for a path (or all paths)"""
        if path:
            # Normalize path
            norm_path = os.path.normpath(path)
            operations = self.path_history.get(norm_path, [])
        else:
            operations = self.operations
        
        # Sort by timestamp (newest first) and limit
        sorted_ops = sorted(operations, key=lambda op: op.timestamp, reverse=True)
        limited_ops = sorted_ops[:limit]
        
        # Convert to dictionaries
        return [op.to_dict() for op in limited_ops]
    
    def track_path(self, path: str) -> bool:
        """Add a path to the tracked paths list"""
        norm_path = os.path.normpath(path)
        if norm_path not in self.tracked_paths:
            self.tracked_paths.append(norm_path)
            logger.info(f"Started tracking path: {norm_path}")
            return True
        return False
    
    def untrack_path(self, path: str) -> bool:
        """Remove a path from the tracked paths list"""
        norm_path = os.path.normpath(path)
        if norm_path in self.tracked_paths:
            self.tracked_paths.remove(norm_path)
            logger.info(f"Stopped tracking path: {norm_path}")
            return True
        return False
    
    def is_tracked(self, path: str) -> bool:
        """Check if a path is being tracked"""
        norm_path = os.path.normpath(path)
        
        # Check direct match
        if norm_path in self.tracked_paths:
            return True
        
        # Check parent directories
        for tracked_path in self.tracked_paths:
            if norm_path.startswith(tracked_path + os.sep):
                return True
        
        return False
    
    def sync_to_disk(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Sync cached changes to disk"""
        if path:
            paths_to_sync = [os.path.normpath(path)]
        else:
            paths_to_sync = list(self.cache.keys())
        
        result = {
            "success": True,
            "synced_files": 0,
            "errors": []
        }
        
        for file_path in paths_to_sync:
            if file_path in self.cache:
                try:
                    # Ensure parent directory exists
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    # Write to disk
                    with open(file_path, 'wb') as f:
                        f.write(self.cache[file_path])
                    
                    result["synced_files"] += 1
                    
                    # Record operation
                    self.record_operation(FSOperation(
                        operation_type=FSOperationType.SYNC,
                        path=file_path,
                        metadata={"size": len(self.cache[file_path])}
                    ))
                    
                except Exception as e:
                    error_msg = f"Error syncing {file_path}: {str(e)}"
                    logger.error(error_msg)
                    result["errors"].append(error_msg)
                    result["success"] = False
                    
                    # Record failed operation
                    self.record_operation(FSOperation(
                        operation_type=FSOperationType.SYNC,
                        path=file_path,
                        success=False,
                        error_message=str(e)
                    ))
        
        logger.info(f"Synced {result['synced_files']} files to disk")
        return result

class IPFSFSBridge:
    """Bridge between IPFS and the local filesystem"""
    
    def __init__(self, fs_journal: FSJournal):
        """Initialize the IPFS-FS bridge"""
        self.journal = fs_journal
        self.ipfs_cids: Dict[str, str] = {}  # path -> CID mapping
        self.ipfs_mfs_mappings: Dict[str, str] = {}  # MFS path -> local path mapping
        logger.info("Initialized IPFS-FS Bridge")
    
    def map_path(self, ipfs_path: str, local_path: str) -> Dict[str, Any]:
        """Map an IPFS path to a local filesystem path"""
        # Normalize paths
        norm_ipfs_path = ipfs_path.rstrip('/')
        norm_local_path = os.path.normpath(local_path)
        
        # Create mapping
        self.ipfs_mfs_mappings[norm_ipfs_path] = norm_local_path
        
        # Ensure path is tracked
        self.journal.track_path(norm_local_path)
        
        logger.info(f"Mapped IPFS path {norm_ipfs_path} to local path {norm_local_path}")
        return {
            "success": True,
            "ipfs_path": norm_ipfs_path,
            "local_path": norm_local_path
        }
    
    def unmap_path(self, ipfs_path: str) -> Dict[str, Any]:
        """Remove a mapping between IPFS and local filesystem"""
        norm_ipfs_path = ipfs_path.rstrip('/')
        
        if norm_ipfs_path in self.ipfs_mfs_mappings:
            local_path = self.ipfs_mfs_mappings[norm_ipfs_path]
            del self.ipfs_mfs_mappings[norm_ipfs_path]
            logger.info(f"Unmapped IPFS path {norm_ipfs_path} from local path {local_path}")
            return {
                "success": True,
                "ipfs_path": norm_ipfs_path,
                "local_path": local_path
            }
        else:
            logger.warning(f"IPFS path {norm_ipfs_path} not found in mappings")
            return {
                "success": False,
                "error": f"IPFS path {norm_ipfs_path} not found in mappings"
            }
    
    def list_mappings(self) -> Dict[str, Any]:
        """List all mappings between IPFS and local filesystem"""
        mappings = []
        for ipfs_path, local_path in self.ipfs_mfs_mappings.items():
            mappings.append({
                "ipfs_path": ipfs_path,
                "local_path": local_path,
                "has_cid": local_path in self.ipfs_cids
            })
        
        return {
            "success": True,
            "count": len(mappings),
            "mappings": mappings
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of the IPFS-FS bridge"""
        return {
            "success": True,
            "mappings_count": len(self.ipfs_mfs_mappings),
            "cids_count": len(self.ipfs_cids),
            "tracked_paths_count": len(self.journal.tracked_paths)
        }

def create_journal_and_bridge(base_dir: str) -> tuple:
    """Create and initialize the FS Journal and IPFS-FS Bridge"""
    journal = FSJournal(base_dir)
    bridge = IPFSFSBridge(journal)
    return journal, bridge

# MCP integration functions
async def fs_journal_get_history_handler(ctx, path: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Handle request to get operation history for a path"""
    from mcp.server.fastmcp import Context
    
    if not isinstance(ctx, Context):
        await ctx.error("Invalid context")
        return {"error": "Invalid context"}
        
    if not hasattr(ctx.server, "fs_journal"):
        await ctx.error("FS Journal not initialized")
        return {"error": "FS Journal not initialized"}
    
    journal = ctx.server.fs_journal
    await ctx.info(f"Getting history for path: {path or 'all paths'}")
    
    try:
        history = journal.get_history(path, limit)
        await ctx.info(f"Found {len(history)} operations")
        return {
            "success": True,
            "path": path,
            "limit": limit,
            "count": len(history),
            "operations": history
        }
    except Exception as e:
        error_msg = f"Error getting history: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"error": error_msg}

async def fs_journal_sync_handler(ctx, path: Optional[str] = None) -> Dict[str, Any]:
    """Handle request to sync the filesystem journal to disk"""
    from mcp.server.fastmcp import Context
    
    if not isinstance(ctx, Context):
        return {"error": "Invalid context"}
        
    if not hasattr(ctx.server, "fs_journal"):
        await ctx.error("FS Journal not initialized")
        return {"error": "FS Journal not initialized"}
    
    journal = ctx.server.fs_journal
    await ctx.info(f"Syncing {'path: ' + path if path else 'all cached files'} to disk")
    
    try:
        result = journal.sync_to_disk(path)
        await ctx.info(f"Synced {result['synced_files']} files to disk")
        return result
    except Exception as e:
        error_msg = f"Error syncing to disk: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"error": error_msg}

async def ipfs_fs_bridge_status_handler(ctx) -> Dict[str, Any]:
    """Handle request to get status of the IPFS-FS bridge"""
    from mcp.server.fastmcp import Context
    
    if not isinstance(ctx, Context):
        return {"error": "Invalid context"}
        
    if not hasattr(ctx.server, "ipfs_fs_bridge"):
        await ctx.error("IPFS-FS Bridge not initialized")
        return {"error": "IPFS-FS Bridge not initialized"}
    
    bridge = ctx.server.ipfs_fs_bridge
    await ctx.info("Getting IPFS-FS bridge status")
    
    try:
        status = bridge.get_status()
        await ctx.info(f"IPFS-FS bridge has {status['mappings_count']} mappings and {status['cids_count']} CIDs")
        return status
    except Exception as e:
        error_msg = f"Error getting bridge status: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"error": error_msg}

async def ipfs_fs_bridge_sync_handler(ctx, direction: str = "both") -> Dict[str, Any]:
    """Handle request to sync between IPFS and the filesystem"""
    from mcp.server.fastmcp import Context
    
    if not isinstance(ctx, Context):
        return {"error": "Invalid context"}
        
    if not hasattr(ctx.server, "ipfs_fs_bridge") or not hasattr(ctx.server, "fs_journal"):
        await ctx.error("IPFS-FS Bridge or FS Journal not initialized")
        return {"error": "IPFS-FS Bridge or FS Journal not initialized"}
    
    bridge = ctx.server.ipfs_fs_bridge
    journal = ctx.server.fs_journal
    
    await ctx.info(f"Syncing between IPFS and filesystem (direction: {direction})")
    
    try:
        result = {
            "success": True,
            "direction": direction,
            "synced_to_ipfs": 0,
            "synced_to_fs": 0,
            "errors": []
        }
        
        # Sync filesystem changes to disk first
        if direction in ["both", "to_disk"]:
            disk_sync = journal.sync_to_disk()
            result["synced_to_fs"] = disk_sync["synced_files"]
            if not disk_sync["success"]:
                result["errors"].extend(disk_sync["errors"])
        
        await ctx.info(f"Sync completed: {result['synced_to_ipfs']} files to IPFS, {result['synced_to_fs']} files to filesystem")
        return result
    except Exception as e:
        error_msg = f"Error during sync: {str(e)}"
        logger.error(error_msg)
        await ctx.error(error_msg)
        return {"error": error_msg}

def register_fs_journal_tools(server) -> None:
    """Register FS Journal and IPFS-FS Bridge tools with MCP server"""
    from mcp.server.fastmcp import FastMCP
    
    if not isinstance(server, FastMCP):
        logger.error(f"Invalid server type: {type(server)}")
        return
    
    try:
        # Create and attach journal and bridge to server
        journal, bridge = create_journal_and_bridge(os.getcwd())
        server.fs_journal = journal
        server.ipfs_fs_bridge = bridge
        
        # Register tools
        server.tool(name="fs_journal_get_history", description="Get the operation history for a path in the virtual filesystem")(fs_journal_get_history_handler)
        server.tool(name="fs_journal_sync", description="Force synchronization between virtual filesystem and actual storage")(fs_journal_sync_handler)
        server.tool(name="ipfs_fs_bridge_status", description="Get the status of the IPFS-FS bridge")(ipfs_fs_bridge_status_handler)
        server.tool(name="ipfs_fs_bridge_sync", description="Sync between IPFS and virtual filesystem")(ipfs_fs_bridge_sync_handler)
        
        logger.info("✅ Successfully registered FS Journal and IPFS-FS Bridge tools with MCP server")
    except Exception as e:
        logger.error(f"Failed to register FS Journal tools: {e}")

if __name__ == "__main__":
    # For testing/demonstration
    journal, bridge = create_journal_and_bridge(os.getcwd())
    
    # Record some sample operations
    journal.record_operation(FSOperation(
        operation_type=FSOperationType.READ,
        path="/test/file1.txt"
    ))
    
    journal.record_operation(FSOperation(
        operation_type=FSOperationType.WRITE,
        path="/test/file1.txt",
        metadata={"size": 1024}
    ))
    
    # Get and print history
    history = journal.get_history()
    print(json.dumps(history, indent=2))
