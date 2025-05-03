#!/usr/bin/env python3
"""
IPFS MCP FS Integration

This script integrates the FS Journal and IPFS Bridge tools with the MCP server,
creating a seamless connection between the virtual filesystem and IPFS operations.
"""

import os
import sys
import logging
import json
import asyncio
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global variables to hold our integration objects
_fs_journal = None
_ipfs_fs_bridge = None

def init_integration(base_dir: Optional[str] = None) -> Dict[str, Any]:
    """Initialize the filesystem journal and IPFS-FS bridge"""
    global _fs_journal, _ipfs_fs_bridge
    
    # Import classes from fs_journal_tools
    try:
        from fs_journal_tools import FSJournal, IPFSFSBridge, FSOperation, FSOperationType, create_journal_and_bridge
        
        # Initialize the journal and bridge
        base_dir = os.path.abspath(base_dir or os.getcwd())
        _fs_journal, _ipfs_fs_bridge = create_journal_and_bridge(base_dir)
        
        logger.info(f"✅ Successfully initialized FS Journal and IPFS-FS Bridge with base directory: {base_dir}")
        return {
            "success": True,
            "base_dir": base_dir,
            "journal_initialized": _fs_journal is not None,
            "bridge_initialized": _ipfs_fs_bridge is not None
        }
    except ImportError as e:
        logger.error(f"Failed to import required classes from fs_journal_tools: {e}")
        return {
            "success": False,
            "error": f"Failed to import required classes: {e}"
        }
    except Exception as e:
        logger.error(f"Failed to initialize FS Journal and IPFS-FS Bridge: {e}")
        return {
            "success": False,
            "error": f"Initialization error: {e}"
        }

def register_with_mcp_server(server) -> bool:
    """Register the FS Journal tools with the MCP server"""
    try:
        from fs_journal_tools import register_fs_journal_tools
        
        # Initialize if not already done
        if not _fs_journal or not _ipfs_fs_bridge:
            init_result = init_integration()
            if not init_result["success"]:
                logger.error(f"Failed to initialize before registration: {init_result.get('error')}")
                return False
        
        # Register the tools with the MCP server
        register_fs_journal_tools(server)
        logger.info("✅ Successfully registered FS Journal tools with MCP server")
        
        return True
    except Exception as e:
        logger.error(f"Failed to register with MCP server: {e}")
        return False

async def fs_journal_get_history(path: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Get operation history from the FS Journal"""
    global _fs_journal
    
    if not _fs_journal:
        logger.error("FS Journal not initialized")
        return {"success": False, "error": "FS Journal not initialized"}
    
    try:
        history = _fs_journal.get_history(path, limit)
        logger.info(f"Got history for path: {path or 'all paths'}, {len(history)} entries")
        return {
            "success": True,
            "path": path,
            "count": len(history),
            "operations": history
        }
    except Exception as e:
        error_msg = f"Error getting history: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def fs_journal_sync(path: Optional[str] = None) -> Dict[str, Any]:
    """Sync the FS Journal to disk"""
    global _fs_journal
    
    if not _fs_journal:
        logger.error("FS Journal not initialized")
        return {"success": False, "error": "FS Journal not initialized"}
    
    try:
        result = _fs_journal.sync_to_disk(path)
        logger.info(f"Synced FS Journal to disk: {result['synced_files']} files")
        return result
    except Exception as e:
        error_msg = f"Error syncing to disk: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def fs_journal_track(path: str) -> Dict[str, Any]:
    """Start tracking a path in the FS Journal"""
    global _fs_journal
    
    if not _fs_journal:
        logger.error("FS Journal not initialized")
        return {"success": False, "error": "FS Journal not initialized"}
    
    try:
        success = _fs_journal.track_path(path)
        if success:
            logger.info(f"Started tracking path: {path}")
            return {"success": True, "path": path, "tracked": True}
        else:
            logger.info(f"Path already being tracked: {path}")
            return {"success": True, "path": path, "tracked": False, "reason": "already_tracked"}
    except Exception as e:
        error_msg = f"Error tracking path: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def fs_journal_untrack(path: str) -> Dict[str, Any]:
    """Stop tracking a path in the FS Journal"""
    global _fs_journal
    
    if not _fs_journal:
        logger.error("FS Journal not initialized")
        return {"success": False, "error": "FS Journal not initialized"}
    
    try:
        success = _fs_journal.untrack_path(path)
        if success:
            logger.info(f"Stopped tracking path: {path}")
            return {"success": True, "path": path, "untracked": True}
        else:
            logger.info(f"Path not being tracked: {path}")
            return {"success": True, "path": path, "untracked": False, "reason": "not_tracked"}
    except Exception as e:
        error_msg = f"Error untracking path: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def ipfs_fs_bridge_status() -> Dict[str, Any]:
    """Get the status of the IPFS-FS Bridge"""
    global _ipfs_fs_bridge
    
    if not _ipfs_fs_bridge:
        logger.error("IPFS-FS Bridge not initialized")
        return {"success": False, "error": "IPFS-FS Bridge not initialized"}
    
    try:
        status = _ipfs_fs_bridge.get_status()
        logger.info(f"Got IPFS-FS Bridge status: {status['mappings_count']} mappings")
        return status
    except Exception as e:
        error_msg = f"Error getting bridge status: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def ipfs_fs_bridge_map(ipfs_path: str, local_path: str) -> Dict[str, Any]:
    """Map an IPFS path to a local filesystem path"""
    global _ipfs_fs_bridge
    
    if not _ipfs_fs_bridge:
        logger.error("IPFS-FS Bridge not initialized")
        return {"success": False, "error": "IPFS-FS Bridge not initialized"}
    
    try:
        result = _ipfs_fs_bridge.map_path(ipfs_path, local_path)
        logger.info(f"Mapped IPFS path {ipfs_path} to local path {local_path}")
        return result
    except Exception as e:
        error_msg = f"Error mapping path: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def ipfs_fs_bridge_unmap(ipfs_path: str) -> Dict[str, Any]:
    """Remove a mapping between IPFS and local filesystem"""
    global _ipfs_fs_bridge
    
    if not _ipfs_fs_bridge:
        logger.error("IPFS-FS Bridge not initialized")
        return {"success": False, "error": "IPFS-FS Bridge not initialized"}
    
    try:
        result = _ipfs_fs_bridge.unmap_path(ipfs_path)
        if result["success"]:
            logger.info(f"Unmapped IPFS path {ipfs_path}")
        else:
            logger.warning(f"Failed to unmap IPFS path {ipfs_path}: {result.get('error')}")
        return result
    except Exception as e:
        error_msg = f"Error unmapping path: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def ipfs_fs_bridge_list_mappings() -> Dict[str, Any]:
    """List all mappings between IPFS and local filesystem"""
    global _ipfs_fs_bridge
    
    if not _ipfs_fs_bridge:
        logger.error("IPFS-FS Bridge not initialized")
        return {"success": False, "error": "IPFS-FS Bridge not initialized"}
    
    try:
        result = _ipfs_fs_bridge.list_mappings()
        logger.info(f"Listed {result['count']} IPFS-FS mappings")
        return result
    except Exception as e:
        error_msg = f"Error listing mappings: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

async def ipfs_fs_bridge_sync(direction: str = "both") -> Dict[str, Any]:
    """Sync between IPFS and the filesystem"""
    global _ipfs_fs_bridge, _fs_journal
    
    if not _ipfs_fs_bridge or not _fs_journal:
        logger.error("IPFS-FS Bridge or FS Journal not initialized")
        return {"success": False, "error": "IPFS-FS Bridge or FS Journal not initialized"}
    
    try:
        result = {
            "success": True,
            "direction": direction,
            "synced_to_ipfs": 0,
            "synced_to_fs": 0,
            "errors": []
        }
        
        # Sync filesystem changes to disk
        if direction in ["both", "to_disk"]:
            disk_sync = _fs_journal.sync_to_disk()
            result["synced_to_fs"] = disk_sync["synced_files"]
            if not disk_sync["success"]:
                result["errors"].extend(disk_sync["errors"])
        
        logger.info(f"Synced between IPFS and filesystem: {result['synced_to_ipfs']} to IPFS, {result['synced_to_fs']} to filesystem")
        return result
    except Exception as e:
        error_msg = f"Error during sync: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

# MCP tool registration helpers
def _register_tool(server, name, description, handler):
    """Register a tool with the MCP server"""
    @server.tool(name=name, description=description)
    async def tool_wrapper(ctx, **kwargs):
        try:
            await ctx.info(f"Calling {name} with args: {kwargs}")
            result = await handler(**kwargs)
            if result.get("success", False):
                await ctx.info(f"{name} succeeded")
            else:
                await ctx.error(f"{name} failed: {result.get('error', 'Unknown error')}")
            return result
        except Exception as e:
            error_msg = f"Error in {name}: {str(e)}"
            logger.error(error_msg)
            await ctx.error(error_msg)
            return {"success": False, "error": error_msg}

def register_all_tools(server) -> bool:
    """Register all FS Journal and IPFS-FS Bridge tools with the MCP server"""
    try:
        # Initialize if not already done
        if not _fs_journal or not _ipfs_fs_bridge:
            init_result = init_integration()
            if not init_result["success"]:
                logger.error(f"Failed to initialize before tool registration: {init_result.get('error')}")
                return False
        
        # Register FS Journal tools
        _register_tool(server, "fs_journal_get_history", 
                      "Get the operation history for a path in the virtual filesystem",
                      fs_journal_get_history)
        
        _register_tool(server, "fs_journal_sync",
                      "Force synchronization between virtual filesystem and actual storage",
                      fs_journal_sync)
        
        _register_tool(server, "fs_journal_track",
                      "Start tracking operations on a path in the filesystem",
                      fs_journal_track)
        
        _register_tool(server, "fs_journal_untrack",
                      "Stop tracking operations on a path in the filesystem",
                      fs_journal_untrack)
        
        # Register IPFS-FS Bridge tools
        _register_tool(server, "ipfs_fs_bridge_status",
                      "Get the status of the IPFS-FS bridge",
                      ipfs_fs_bridge_status)
        
        _register_tool(server, "ipfs_fs_bridge_map",
                      "Map an IPFS path to a filesystem path",
                      ipfs_fs_bridge_map)
        
        _register_tool(server, "ipfs_fs_bridge_unmap",
                      "Remove a mapping between IPFS and filesystem",
                      ipfs_fs_bridge_unmap)
        
        _register_tool(server, "ipfs_fs_bridge_list_mappings",
                      "List all mappings between IPFS and filesystem",
                      ipfs_fs_bridge_list_mappings)
        
        _register_tool(server, "ipfs_fs_bridge_sync",
                      "Sync between IPFS and filesystem",
                      ipfs_fs_bridge_sync)
        
        logger.info("✅ Successfully registered all FS Journal and IPFS-FS Bridge tools")
        return True
    except Exception as e:
        logger.error(f"Failed to register tools: {e}")
        return False

if __name__ == "__main__":
    # Initialize for testing
    init_result = init_integration()
    print(json.dumps(init_result, indent=2))
    
    # Test some functions
    async def test():
        history = await fs_journal_get_history()
        print(f"Got {len(history.get('operations', []))} history entries")
        
        status = await ipfs_fs_bridge_status()
        print(f"Bridge status: {status}")
    
    # Run the test
    asyncio.run(test())
