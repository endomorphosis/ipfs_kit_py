#!/usr/bin/env python3
"""
Unified IPFS Tools Module

This module consolidates all IPFS tool functionality into a single place,
providing both real implementations (when possible) and fallback mock implementations.
"""

import os
import sys
import json
import base64
import logging
import tempfile
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("unified-ipfs-tools")

# Dictionary to keep track of tool availability
TOOL_STATUS = {
    "ipfs_extensions_available": False,
    "ipfs_model_available": False,
    "ipfs_fs_bridge_available": False
}

# Import IPFS extensions if available
try:
    # Add possible paths to import from
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.append(script_dir)
    sys.path.append(os.path.join(script_dir, "ipfs_kit_py"))
    
    # Try to import IPFS extensions
    from ipfs_kit_py.mcp.ipfs_extensions import (
        add_content, cat, pin_add, pin_rm, pin_ls, get_version,
        files_ls, files_mkdir, files_write, files_read,
        files_rm, files_stat, files_cp, files_mv, files_flush
    )
    TOOL_STATUS["ipfs_extensions_available"] = True
    logger.info("✅ Successfully imported IPFS extensions")
except ImportError as e:
    logger.warning(f"⚠️ Could not import IPFS extensions: {e}")
    logger.warning("⚠️ Will use mock implementations for IPFS extensions")

# Try to import IPFS model if available
try:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    TOOL_STATUS["ipfs_model_available"] = True
    logger.info("✅ Successfully imported IPFS Model")
except ImportError as e:
    logger.warning(f"⚠️ Could not import IPFS Model: {e}")

# Try to import IPFS-FS bridge if available
try:
    from ipfs_kit_py.fs_journal import IPFSFSBridge
    TOOL_STATUS["ipfs_fs_bridge_available"] = True
    logger.info("✅ Successfully imported IPFS-FS Bridge")
except ImportError as e:
    logger.warning(f"⚠️ Could not import IPFS-FS Bridge: {e}")

# Import the tools registry
try:
    from ipfs_tools_registry import IPFS_TOOLS
    logger.info(f"✅ Found {len(IPFS_TOOLS)} tools in registry")
except ImportError as e:
    logger.warning(f"⚠️ Could not import IPFS tools registry: {e}")
    # Define a minimal set of tools if registry not available
    IPFS_TOOLS = [
        {
            "name": "ipfs_add",
            "description": "Add content to IPFS",
            "schema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to add to IPFS"
                    },
                    "filename": {
                        "type": "string",
                        "description": "Optional filename"
                    },
                    "pin": {
                        "type": "boolean",
                        "description": "Whether to pin the content",
                        "default": True
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "ipfs_cat",
            "description": "Retrieve content from IPFS",
            "schema": {
                "type": "object",
                "properties": {
                    "cid": {
                        "type": "string",
                        "description": "CID of the content to retrieve"
                    }
                },
                "required": ["cid"]
            }
        }
    ]

# Initialize global instances
ipfs_model = None
fs_bridge = None

# Initialize needed components
def initialize_components():
    """Initialize IPFS components if available."""
    global ipfs_model, fs_bridge
    
    try:
        if TOOL_STATUS["ipfs_model_available"] and ipfs_model is None:
            ipfs_model = IPFSModel()
            logger.info("✅ Initialized IPFS Model")
        
        if TOOL_STATUS["ipfs_fs_bridge_available"] and fs_bridge is None:
            fs_bridge = IPFSFSBridge()
            logger.info("✅ Initialized IPFS-FS Bridge")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error initializing IPFS components: {e}")
        logger.error(traceback.format_exc())
        return False

# Mock implementations for when real implementations are not available
async def mock_add_content(content, filename=None, pin=True):
    """Mock implementation of add_content."""
    logger.info(f"[MOCK] Adding content to IPFS (length: {len(content) if isinstance(content, str) else 'binary'})")
    
    # Generate a mock CID based on content
    import hashlib
    content_hash = hashlib.sha256(content.encode() if isinstance(content, str) else content).hexdigest()
    mock_cid = f"Qm{content_hash[:38]}"
    
    return {
        "success": True,
        "cid": mock_cid,
        "name": filename or "unnamed_file",
        "size": len(content) if isinstance(content, str) else len(content),
        "pinned": pin,
        "warning": "This is a mock implementation"
    }

async def mock_cat(cid):
    """Mock implementation of cat."""
    logger.info(f"[MOCK] Retrieving content for CID: {cid}")
    
    mock_content = f"This is mock content for CID: {cid}\nGenerated at {datetime.now().isoformat()}"
    
    return {
        "success": True,
        "cid": cid,
        "content": mock_content,
        "content_encoding": "text",
        "size": len(mock_content),
        "warning": "This is a mock implementation"
    }

async def mock_pin_add(cid, recursive=True):
    """Mock implementation of pin_add."""
    logger.info(f"[MOCK] Pinning CID: {cid} (recursive={recursive})")
    
    return {
        "success": True,
        "cid": cid,
        "pins": [cid],
        "recursive": recursive,
        "warning": "This is a mock implementation"
    }

async def mock_pin_rm(cid, recursive=True):
    """Mock implementation of pin_rm."""
    logger.info(f"[MOCK] Unpinning CID: {cid} (recursive={recursive})")
    
    return {
        "success": True,
        "cid": cid,
        "pins": [cid],
        "recursive": recursive,
        "warning": "This is a mock implementation"
    }

async def mock_pin_ls(cid=None, type_filter="all"):
    """Mock implementation of pin_ls."""
    logger.info(f"[MOCK] Listing pins (cid={cid}, filter={type_filter})")
    
    # Generate some mock pins
    mock_pins = []
    if cid:
        mock_pins.append({"cid": cid, "type": "recursive"})
    else:
        for i in range(5):
            mock_pins.append({
                "cid": f"Qm{''.join(str(i) for _ in range(38))}",
                "type": "recursive" if i % 2 == 0 else "direct"
            })
    
    return {
        "success": True,
        "pins": mock_pins,
        "count": len(mock_pins),
        "type_filter": type_filter,
        "warning": "This is a mock implementation"
    }

async def mock_get_version():
    """Mock implementation of get_version."""
    logger.info("[MOCK] Getting IPFS version")
    
    return {
        "success": True,
        "version": "0.12.0-mock",
        "commit": "mock-commit",
        "repo": "10",
        "system": "mock-system",
        "golang": "go1.16.5-mock",
        "warning": "This is a mock implementation"
    }

# Mock implementations for MFS operations
async def mock_files_ls(path="/", long=False):
    """Mock implementation of files_ls."""
    logger.info(f"[MOCK] Listing files in MFS path: {path}")
    
    # Generate mock entries
    mock_entries = []
    if path == "/":
        mock_entries = [
            {"name": "documents", "type": 0, "size": 0, "hash": "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"},
            {"name": "images", "type": 0, "size": 0, "hash": "QmUNLLsPACCz1vLxQVkXqqLX5R1X345qqfHbsf67hvA3Nn"},
            {"name": "readme.txt", "type": 1, "size": 1024, "hash": "QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU"}
        ]
    elif path == "/documents":
        mock_entries = [
            {"name": "notes.txt", "type": 1, "size": 512, "hash": "QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU"},
            {"name": "report.pdf", "type": 1, "size": 2048, "hash": "QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU"}
        ]
    
    return {
        "success": True,
        "path": path,
        "entries": mock_entries,
        "count": len(mock_entries),
        "warning": "This is a mock implementation"
    }

async def mock_files_mkdir(path, parents=True):
    """Mock implementation of files_mkdir."""
    logger.info(f"[MOCK] Creating directory in MFS: {path}")
    
    return {
        "success": True,
        "path": path,
        "parents": parents,
        "warning": "This is a mock implementation"
    }

async def mock_files_write(path, content, create=True, truncate=True):
    """Mock implementation of files_write."""
    logger.info(f"[MOCK] Writing to file in MFS: {path}")
    
    content_size = len(content) if isinstance(content, str) else len(content)
    
    return {
        "success": True,
        "path": path,
        "size": content_size,
        "create": create,
        "truncate": truncate,
        "warning": "This is a mock implementation"
    }

async def mock_files_read(path, offset=0, count=-1):
    """Mock implementation of files_read."""
    logger.info(f"[MOCK] Reading file from MFS: {path}")
    
    # Generate mock content based on path
    mock_content = f"This is mock content for MFS file: {path}\nGenerated at {datetime.now().isoformat()}"
    
    return {
        "success": True,
        "path": path,
        "content": mock_content,
        "content_encoding": "text",
        "size": len(mock_content),
        "offset": offset,
        "warning": "This is a mock implementation"
    }

async def mock_files_rm(path, recursive=False, force=False):
    """Mock implementation of files_rm."""
    logger.info(f"[MOCK] Removing {path} from MFS")
    
    return {
        "success": True,
        "path": path,
        "recursive": recursive,
        "force": force,
        "warning": "This is a mock implementation"
    }

async def mock_files_stat(path):
    """Mock implementation of files_stat."""
    logger.info(f"[MOCK] Getting stats for MFS path: {path}")
    
    return {
        "success": True,
        "path": path,
        "hash": f"QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU",
        "size": 1024,
        "cumulative_size": 1024,
        "blocks": 1,
        "type": "file" if "." in path else "directory",
        "warning": "This is a mock implementation"
    }

async def mock_files_cp(source, dest):
    """Mock implementation of files_cp."""
    logger.info(f"[MOCK] Copying {source} to {dest} in MFS")
    
    return {
        "success": True,
        "source": source,
        "destination": dest,
        "warning": "This is a mock implementation"
    }

async def mock_files_mv(source, dest):
    """Mock implementation of files_mv."""
    logger.info(f"[MOCK] Moving {source} to {dest} in MFS")
    
    return {
        "success": True,
        "source": source,
        "destination": dest,
        "warning": "This is a mock implementation"
    }

async def mock_files_flush(path="/"):
    """Mock implementation of files_flush."""
    logger.info(f"[MOCK] Flushing MFS path: {path}")
    
    return {
        "success": True,
        "path": path,
        "cid": f"QmY7Yh4UquoXHLPFo2XbhXkhBvFoPwmQUSa92pxnxjQuPU",
        "warning": "This is a mock implementation"
    }

# Function to choose the appropriate implementation
def get_implementation(tool_name):
    """
    Get the appropriate implementation for a tool.
    Uses real implementation if available, otherwise falls back to mock.
    """
    # Core IPFS operations
    if tool_name == "ipfs_add":
        return add_content if TOOL_STATUS["ipfs_extensions_available"] else mock_add_content
    elif tool_name == "ipfs_cat":
        return cat if TOOL_STATUS["ipfs_extensions_available"] else mock_cat
    elif tool_name == "ipfs_pin":
        return pin_add if TOOL_STATUS["ipfs_extensions_available"] else mock_pin_add
    elif tool_name == "ipfs_unpin":
        return pin_rm if TOOL_STATUS["ipfs_extensions_available"] else mock_pin_rm
    elif tool_name == "ipfs_list_pins":
        return pin_ls if TOOL_STATUS["ipfs_extensions_available"] else mock_pin_ls
    elif tool_name == "ipfs_version":
        return get_version if TOOL_STATUS["ipfs_extensions_available"] else mock_get_version
    
    # MFS operations
    elif tool_name == "ipfs_files_ls":
        return files_ls if TOOL_STATUS["ipfs_extensions_available"] else mock_files_ls
    elif tool_name == "ipfs_files_mkdir":
        return files_mkdir if TOOL_STATUS["ipfs_extensions_available"] else mock_files_mkdir
    elif tool_name == "ipfs_files_write":
        return files_write if TOOL_STATUS["ipfs_extensions_available"] else mock_files_write
    elif tool_name == "ipfs_files_read":
        return files_read if TOOL_STATUS["ipfs_extensions_available"] else mock_files_read
    elif tool_name == "ipfs_files_rm":
        return files_rm if TOOL_STATUS["ipfs_extensions_available"] else mock_files_rm
    elif tool_name == "ipfs_files_stat":
        return files_stat if TOOL_STATUS["ipfs_extensions_available"] else mock_files_stat
    elif tool_name == "ipfs_files_cp":
        return files_cp if TOOL_STATUS["ipfs_extensions_available"] else mock_files_cp
    elif tool_name == "ipfs_files_mv":
        return files_mv if TOOL_STATUS["ipfs_extensions_available"] else mock_files_mv
    elif tool_name == "ipfs_files_flush":
        return files_flush if TOOL_STATUS["ipfs_extensions_available"] else mock_files_flush
    
    # Default fallback for unknown tools
    return None

# Main registration function
def register_all_ipfs_tools(mcp_server):
    """Register all IPFS tools with the MCP server."""
    logger.info(f"Registering all IPFS tools with MCP server...")
    
    # Initialize components
    initialize_components()
    
    # Keep track of registered tools
    registered_tools = []
    
    # Register each tool
    for tool in IPFS_TOOLS:
        tool_name = tool["name"]
        description = tool.get("description", f"IPFS tool: {tool_name}")
        
        # Get the appropriate implementation
        impl = get_implementation(tool_name)
        
        if impl is None:
            # Create a generic implementation if no specific one is available
            async def generic_tool_handler(ctx):
                params = ctx.params
                await ctx.info(f"Called {tool_name} with params: {params}")
                await ctx.warning(f"Using generic implementation for {tool_name}")
                return {
                    "success": True,
                    "warning": "Generic implementation",
                    "timestamp": datetime.now().isoformat(),
                    "tool": tool_name,
                    "params": params
                }
            
            # Register the generic handler
            try:
                # The registration approach depends on the server implementation
                mcp_server.tool(name=tool_name, description=description)(generic_tool_handler)
                registered_tools.append(tool_name)
                logger.info(f"✅ Registered tool with generic implementation: {tool_name}")
            except Exception as e:
                logger.error(f"❌ Error registering tool {tool_name}: {e}")
        else:
            # Create a wrapper function that uses the implementation
            def create_wrapper_for_impl(impl_func, tool_name):
                async def wrapper(ctx):
                    try:
                        # Extract parameters from context
                        params = ctx.params
                        
                        # Log the call
                        await ctx.info(f"Called {tool_name} with params: {params}")
                        
                        # Call the implementation
                        result = await impl_func(**params)
                        
                        # Check if it's a mock implementation
                        if "warning" in result and "mock" in result["warning"].lower():
                            await ctx.warning("Using mock implementation")
                        
                        # Return the result
                        return result
                    except Exception as e:
                        logger.error(f"Error in {tool_name}: {e}")
                        logger.error(traceback.format_exc())
                        await ctx.error(f"Error executing {tool_name}: {e}")
                        return {
                            "success": False,
                            "error": str(e),
                            "tool": tool_name
                        }
                return wrapper
            
            # Register the wrapped handler
            try:
                # Create the wrapper without await
                wrapped_handler = create_wrapper_for_impl(impl, tool_name)
                
                # Register it with the MCP server
                mcp_server.tool(name=tool_name, description=description)(wrapped_handler)
                registered_tools.append(tool_name)
                logger.info(f"✅ Registered tool with implementation: {tool_name}")
            except Exception as e:
                logger.error(f"❌ Error registering tool {tool_name}: {e}")
    
    logger.info(f"✅ Successfully registered {len(registered_tools)}/{len(IPFS_TOOLS)} IPFS tools")
    return registered_tools

if __name__ == "__main__":
    logger.info("This module should be imported and used with an MCP server, not run directly.")
    logger.info(f"IPFS extensions available: {TOOL_STATUS['ipfs_extensions_available']}")
    logger.info(f"IPFS model available: {TOOL_STATUS['ipfs_model_available']}")
    logger.info(f"IPFS-FS bridge available: {TOOL_STATUS['ipfs_fs_bridge_available']}")