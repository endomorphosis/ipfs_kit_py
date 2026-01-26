#!/usr/bin/env python3
"""
Streamlined MCP Server for IPFS Kit - Using Enhanced Daemon Manager
====================================================================

This server uses the centralized daemon management from the main ipfs_kit_py package,
providing a clean separation of concerns between the MCP server logic and daemon management.

Key improvements:
1. Uses EnhancedDaemonManager for all daemon operations
2. Clean separation between MCP server and daemon management
3. Simplified initialization and operation handling
4. Comprehensive error handling and fallback logic
"""

import sys
import json
import anyio
import logging
import traceback
import os
import time
import subprocess
import tempfile
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

# Configure logging to stderr (stdout is reserved for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("streamlined-mcp-ipfs-kit")

# Server metadata
__version__ = "3.0.0"

# Add the project root to Python path to import ipfs_kit_py
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the VFS system
try:
    from ipfs_fsspec import (
        get_vfs, vfs_mount, vfs_unmount, vfs_list_mounts, vfs_read, vfs_write,
        vfs_ls, vfs_stat, vfs_mkdir, vfs_rmdir, vfs_copy, vfs_move,
        vfs_sync_to_ipfs, vfs_sync_from_ipfs
    )
    HAS_VFS = True
    logger.info("✓ VFS system imported successfully")
except ImportError as e:
    logger.warning(f"VFS system not available: {e}")
    HAS_VFS = False


class StreamlinedIPFSKitIntegration:
    """Streamlined integration layer that uses the enhanced daemon manager."""
    
    def __init__(self):
        self.ipfs_kit = None
        self.daemon_manager = None
        self.daemon_process = None
        self._initialize_ipfs_kit()
    
    def _initialize_ipfs_kit(self):
        """Initialize the IPFS Kit and enhanced daemon manager."""
        try:
            # Import and initialize IPFS Kit
            from ipfs_kit_py.ipfs_kit import ipfs_kit
            from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
            
            # Initialize IPFS Kit
            self.ipfs_kit = ipfs_kit(metadata={
                "role": "master",
                "ipfs_path": os.path.expanduser("~/.ipfs")
            })
            
            # Initialize Enhanced Daemon Manager
            self.daemon_manager = EnhancedDaemonManager(self.ipfs_kit)
            
            logger.info("Successfully initialized IPFS Kit and Enhanced Daemon Manager")
            
            # Ensure daemon is running using the enhanced daemon manager
            self._ensure_daemon_running()
                    
        except Exception as e:
            error_msg = str(e)
            if "Protobuf" in error_msg and "version" in error_msg:
                logger.error(f"Protobuf version mismatch detected: {e}")
                logger.info("This is a known issue that doesn't affect core IPFS functionality")
                logger.info("Attempting to use direct IPFS commands instead...")
                
                # Initialize daemon manager without IPFS Kit for direct commands
                try:
                    from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
                    self.daemon_manager = EnhancedDaemonManager(None)
                    
                    # Test if direct IPFS works
                    if self.daemon_manager.test_direct_ipfs():
                        logger.info("Direct IPFS commands working, will use direct commands.")
                        self.ipfs_kit = None  # Use direct commands
                    else:
                        logger.error("Direct IPFS also unavailable. This server will not function correctly.")
                        self.ipfs_kit = None
                        self.daemon_manager = None
                except Exception as daemon_e:
                    logger.error(f"Failed to initialize daemon manager: {daemon_e}")
                    self.daemon_manager = None
            else:
                logger.error(f"Failed to initialize IPFS Kit: {e}")
                self.ipfs_kit = None
                self.daemon_manager = None
    
    def _ensure_daemon_running(self) -> bool:
        """Ensure IPFS daemon is running using the enhanced daemon manager."""
        if not self.daemon_manager:
            logger.error("No daemon manager available")
            return False
        
        try:
            # Use the comprehensive daemon management from enhanced daemon manager
            result = self.daemon_manager.ensure_daemon_running_comprehensive()
            
            if result["success"]:
                logger.info("✓ IPFS daemon is running and accessible")
                # Store daemon process if one was started
                if result.get("daemon_process"):
                    self.daemon_process = result["daemon_process"]
                return True
            else:
                logger.warning(f"Failed to ensure daemon running: {result.get('errors', [])}")
                # Check if we can still operate with direct commands
                if self.daemon_manager.test_direct_ipfs():
                    logger.info("✓ Direct IPFS commands work, proceeding without daemon")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error ensuring daemon running: {e}")
            return False
    
    async def execute_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Execute an IPFS operation using the real IPFS Kit or direct commands."""
        
        if self.ipfs_kit:
            # Use real IPFS Kit
            try:
                method = getattr(self.ipfs_kit, operation, None)
                if method:
                    result = method(**kwargs)
                    # Ensure result is always a dictionary for consistency
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, bytes):
                        # Handle bytes result (like from ipfs_get)
                        return {
                            "success": True,
                            "operation": operation,
                            "data": result.decode('utf-8', errors='ignore'),
                            "size": len(result)
                        }
                    elif isinstance(result, str):
                        # Handle string result
                        return {
                            "success": True,
                            "operation": operation,
                            "data": result
                        }
                    else:
                        # Handle other types
                        return {
                            "success": True,
                            "operation": operation,
                            "result": str(result)
                        }
                else:
                    logger.warning(f"Method {operation} not found in IPFS Kit, trying direct commands")
                    # Fall back to direct commands instead of returning error
                    return await self._try_direct_ipfs_operation(operation, **kwargs)
            except Exception as e:
                logger.error(f"IPFS Kit operation {operation} failed: {e}")
                # Fall back to direct commands
                return await self._try_direct_ipfs_operation(operation, **kwargs)
        else:
            # Try direct IPFS commands
            return await self._try_direct_ipfs_operation(operation, **kwargs)
    
    async def _try_direct_ipfs_operation(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Try to execute IPFS operation using direct commands."""
        try:
            if operation == "ipfs_add":
                content = kwargs.get("content")
                file_path = kwargs.get("file_path")
                
                if file_path and os.path.exists(file_path):
                    # Add file directly
                    result = subprocess.run(['ipfs', 'add', file_path], 
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        # Parse output: "added <hash> <filename>"
                        lines = result.stdout.strip().split('\n')
                        last_line = lines[-1]
                        parts = last_line.split()
                        if len(parts) >= 2 and parts[0] == "added":
                            cid = parts[1]
                            return {
                                "success": True,
                                "operation": operation,
                                "cid": cid,
                                "name": os.path.basename(file_path)
                            }
                elif content:
                    # Add content via stdin
                    result = subprocess.run(['ipfs', 'add', '-Q'], 
                                          input=content, text=True,
                                          capture_output=True, timeout=30)
                    if result.returncode == 0:
                        cid = result.stdout.strip()
                        return {
                            "success": True,
                            "operation": operation,
                            "cid": cid,
                            "size": len(content)
                        }
                        
            elif operation == "ipfs_cat":
                cid = kwargs.get("cid")
                if cid:
                    result = subprocess.run(['ipfs', 'cat', cid], 
                                          capture_output=True, text=True, timeout=60)
                    if result.returncode == 0 and result.stdout.strip():
                        return {
                            "success": True,
                            "operation": operation,
                            "data": result.stdout,
                            "cid": cid
                        }
                    else:
                        return {
                            "success": False,
                            "operation": operation,
                            "error": result.stderr.strip() or f"No content for CID {cid}"
                        }
                        
            elif operation == "ipfs_id":
                result = subprocess.run(['ipfs', 'id'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    id_data = json.loads(result.stdout)
                    id_data["success"] = True
                    id_data["operation"] = operation
                    return id_data
            
            # Add more operations as needed...
            
            # If we reach here, the operation isn't implemented or failed
            return {
                "success": False,
                "operation": operation,
                "error": f"Operation {operation} not implemented in direct commands or failed"
            }
            
        except Exception as e:
            logger.error(f"Direct IPFS operation {operation} failed with exception: {e}")
            return {
                "success": False,
                "operation": operation,
                "error": f"Exception: {e}"
            }
    
    def cleanup(self):
        """Clean up resources when shutting down."""
        try:
            if self.daemon_manager and self.daemon_process:
                logger.info("Cleaning up managed daemon process...")
                self.daemon_manager.kill_managed_daemon(self.daemon_process)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Initialize the integration
ipfs_integration = StreamlinedIPFSKitIntegration()

async def ipfs_add_handler(content: Optional[str] = None, file_path: Optional[str] = None) -> Dict[str, Any]:
    """Add content to IPFS."""
    try:
        return await ipfs_integration.execute_ipfs_operation("ipfs_add", content=content, file_path=file_path)
    except Exception as e:
        return {"success": False, "error": str(e)}

async def ipfs_cat_handler(cid: str) -> Dict[str, Any]:
    """Retrieve and display content from IPFS."""
    try:
        return await ipfs_integration.execute_ipfs_operation("ipfs_cat", cid=cid)
    except Exception as e:
        return {"success": False, "error": str(e)}

async def ipfs_id_handler() -> Dict[str, Any]:
    """Get IPFS node identity and network information."""
    try:
        return await ipfs_integration.execute_ipfs_operation("ipfs_id")
    except Exception as e:
        return {"success": False, "error": str(e)}

async def system_health_handler() -> Dict[str, Any]:
    """Get comprehensive system health status."""
    try:
        if ipfs_integration.daemon_manager:
            status = ipfs_integration.daemon_manager.get_daemon_status_summary()
            return {
                "success": True,
                "system_health": status,
                "ipfs_accessible": ipfs_integration.daemon_manager.test_ipfs_connection(),
                "direct_ipfs_works": ipfs_integration.daemon_manager.test_direct_ipfs()
            }
        else:
            return {
                "success": False,
                "error": "No daemon manager available"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

# MCP Tool definitions
MCP_TOOLS = [
    {
        "name": "ipfs_add",
        "description": "Add content to IPFS and return the CID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Content to add to IPFS"},
                "file_path": {"type": "string", "description": "Path to file to add to IPFS"}
            }
        }
    },
    {
        "name": "ipfs_cat",
        "description": "Retrieve and display content from IPFS",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cid": {"type": "string", "description": "IPFS CID to retrieve content from"}
            },
            "required": ["cid"]
        }
    },
    {
        "name": "ipfs_id",
        "description": "Get IPFS node identity and network information",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "system_health",
        "description": "Get comprehensive system health status including IPFS daemon status",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# Tool name to handler mapping
TOOL_HANDLERS = {
    "ipfs_add": ipfs_add_handler,
    "ipfs_cat": ipfs_cat_handler,
    "ipfs_id": ipfs_id_handler,
    "system_health": system_health_handler
}

async def handle_call_tool(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tool calls from the MCP client."""
    try:
        tool_name = request.get("params", {}).get("name")
        arguments = request.get("params", {}).get("arguments", {})
        
        if tool_name not in TOOL_HANDLERS:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
        
        # Execute the tool
        handler = TOOL_HANDLERS[tool_name]
        result = await handler(**arguments)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Error in handle_call_tool: {e}")
        logger.error(traceback.format_exc())
        return {
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }

async def handle_list_tools(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle list tools request."""
    return {"tools": MCP_TOOLS}

async def handle_initialize(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle initialization request."""
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "tools": {"listChanged": True}
        },
        "serverInfo": {
            "name": "streamlined-ipfs-kit-mcp-server",
            "version": __version__
        }
    }

async def main():
    """Main MCP server loop."""
    logger.info(f"Starting Streamlined IPFS Kit MCP Server v{__version__}")
    logger.info("Using Enhanced Daemon Manager for centralized daemon management")
    
    try:
        while True:
            try:
                line = await anyio.to_thread.run_sync(sys.stdin.readline)
                if not line:
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    continue
                
                method = request.get("method")
                response = {"jsonrpc": "2.0", "id": request.get("id")}
                
                if method == "initialize":
                    response["result"] = await handle_initialize(request)
                elif method == "tools/list":
                    response["result"] = await handle_list_tools(request)
                elif method == "tools/call":
                    tool_response = await handle_call_tool(request)
                    if "error" in tool_response:
                        response["error"] = tool_response["error"]
                    else:
                        response["result"] = tool_response
                else:
                    response["error"] = {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                
                print(json.dumps(response), flush=True)
                
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                logger.error(traceback.format_exc())
                
    finally:
        logger.info("Cleaning up...")
        ipfs_integration.cleanup()
        logger.info("Streamlined IPFS Kit MCP Server shutdown complete")

if __name__ == "__main__":
    anyio.run(main)
