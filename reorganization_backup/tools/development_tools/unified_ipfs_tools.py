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
from typing import Dict, Any, List, Optional, Union, Callable

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
    "ipfs_fs_bridge_available": False,
    "fixed_ipfs_model_available": False # Always set to False to avoid issues
}

# Import IPFS extensions if available
try:
    from ipfs_kit_py.mcp import ipfs_extensions
    TOOL_STATUS["ipfs_extensions_available"] = True
    logger.info(" IPFS extensions module available")
except ImportError as e:
    logger.warning(f" Could not import IPFS extensions: {e}")
    logger.warning(" Will use mock implementations for IPFS extensions")
except Exception as e:
    logger.error(f" Unexpected error importing IPFS extensions: {e}")
    logger.error(traceback.format_exc())

# Try to import IPFS model if available
try:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    TOOL_STATUS["ipfs_model_available"] = True
    logger.info(" IPFS model available")
except ImportError as e:
    logger.warning(f" Could not import IPFS model: {e}")
except Exception as e:
    logger.error(f" Unexpected error importing IPFS model: {e}")
    logger.error(traceback.format_exc())


# Try to import IPFS-FS bridge if available
try:
    from ipfs_kit_py.fs_journal import IPFSFSBridge
    TOOL_STATUS["ipfs_fs_bridge_available"] = True
    logger.info(" IPFS-FS bridge available")
except ImportError as e:
    logger.warning(f" Could not import IPFS-FS Bridge: {e}")
except Exception as e:
    logger.error(f" Unexpected error importing IPFS-FS Bridge: {e}")
    logger.error(traceback.format_exc())

# Import the tools registry
try:
    from ipfs_tools_registry import IPFS_TOOLS
    logger.info(f" Found {len(IPFS_TOOLS)} tools in registry")
except ImportError as e:
    logger.warning(f" Could not import IPFS tools registry: {e}")
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
fixed_ipfs_model_instance = None # This will always be None now.

# Initialize needed components
def initialize_components():
    """Initialize IPFS components if available."""
    global ipfs_model, fs_bridge, fixed_ipfs_model_instance

    try:
        if TOOL_STATUS["ipfs_model_available"] and ipfs_model is None:
            ipfs_model = IPFSModel()
            logger.info(" IPFS Model initialized")

        # fixed_ipfs_model_instance will always be None as its import is removed
        # if TOOL_STATUS["fixed_ipfs_model_available"] and fixed_ipfs_model_instance is None:
        #      fixed_ipfs_model_instance = FixedIPFSModel()
        #      logger.info(" Fixed IPFS Model initialized")


        if TOOL_STATUS["ipfs_fs_bridge_available"] and fs_bridge is None:
            fs_bridge = IPFSFSBridge()
            logger.info(" IPFS-FS Bridge initialized")

        return True
    except Exception as e:
        logger.error(f" Error initializing IPFS components: {e}")
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
    Prioritize real implementations from fixed_ipfs_model,
    then ipfs_extensions, otherwise use mocks.
    """
    # fixed_ipfs_model implementations are no longer considered here.

    # Fallback to ipfs_extensions if available
    if TOOL_STATUS["ipfs_extensions_available"]:
        # Map tool names to ipfs_extensions functions (adjust if names differ)
        extensions_map = {
            "ipfs_add": ipfs_extensions.add_content,
            "ipfs_add_file": ipfs_extensions.add_file,
            "ipfs_cat": ipfs_extensions.cat,
            "ipfs_pin": ipfs_extensions.pin_add,
            "ipfs_unpin": ipfs_extensions.pin_rm,
            "ipfs_list_pins": ipfs_extensions.pin_ls,
            "ipfs_version": ipfs_extensions.get_version,
            # Add other mappings for ipfs_extensions if they exist
        }
        # Temporarily skip ipfs_add and ipfs_add_file from ipfs_extensions to test mocks
        if tool_name in extensions_map and tool_name not in ["ipfs_add", "ipfs_add_file"]:
            impl = extensions_map[tool_name]
            logger.info(f"For {tool_name}, using ipfs_extensions implementation.")
            return impl
        elif tool_name in ["ipfs_add", "ipfs_add_file"]:
             logger.warning(f"For {tool_name}, skipping ipfs_extensions and falling back to mock.")

    # Fallback to mocks
    mock_map = {
        "ipfs_add": mock_add_content,
        "ipfs_add_file": mock_add_content, # Using add_content mock for add_file
        "ipfs_cat": mock_cat,
        "ipfs_pin": mock_pin_add,
        "ipfs_unpin": mock_pin_rm,
        "ipfs_list_pins": mock_pin_ls,
        "ipfs_version": mock_get_version,
        "ipfs_files_ls": mock_files_ls,
        "ipfs_files_mkdir": mock_files_mkdir,
        "ipfs_files_write": mock_files_write,
        "ipfs_files_read": mock_files_read,
        "ipfs_files_rm": mock_files_rm,
        "ipfs_files_stat": mock_files_stat,
        "ipfs_files_cp": mock_files_cp,
        "ipfs_files_mv": mock_files_mv,
        "ipfs_files_flush": mock_files_flush,
        # Add other mock mappings
    }
    if tool_name in mock_map:
        impl = mock_map[tool_name]
        logger.warning(f"For {tool_name}, using mock implementation.")
        return impl


    # Default fallback for unknown tools
    logger.warning(f" No implementation found for tool: {tool_name}")
    return None

# Main registration function
def register_all_ipfs_tools(mcp_server):
    """Register all IPFS tools with the MCP server."""
    logger.info(f"Registering all IPFS tools with MCP server...")

    # Enhanced logging for debugging
    logger.info(f"Current TOOL_STATUS: {TOOL_STATUS}")
    logger.info(f"Number of tools to register: {len(IPFS_TOOLS)}")

    # Initialize components
    initialize_components()

    # Keep track of registered tools
    registered_tools = []

    # Explicitly register mock implementations for ipfs_add and ipfs_add_file
    logger.warning("Explicitly registering mock implementations for ipfs_add and ipfs_add_file.")
    mcp_server.tool(name="ipfs_add", description="Add content to IPFS (Mock)")(mock_add_content)
    mcp_server.tool(name="ipfs_add_file", description="Add a file or directory to IPFS (Mock)")(mock_add_content) # Use add_content mock for add_file
    registered_tools.extend(["ipfs_add", "ipfs_add_file"])


    # Create and register remaining tools using get_implementation
    for tool in IPFS_TOOLS:
        tool_name = tool["name"]
        if tool_name in registered_tools:
            logger.info(f"Tool {tool_name} already explicitly registered, skipping get_implementation.")
            continue # Skip if already registered

        description = tool.get("description", f"IPFS tool: {tool_name}")
        schema = tool.get("schema", {})

        # Get the appropriate implementation
        impl = get_implementation(tool_name)

        if impl:
            def create_wrapper(implementation, t_name):
                async def wrapper(**kwargs): # Accept arguments directly as keyword arguments
                    # Arguments are already in kwargs, no need to extract from ctx
                    arguments = kwargs

                    logger.info(f"Called {t_name} with arguments: {arguments}")

                    try:
                        # Call the implementation
                        # Call the implementation with arguments unpacked
                        # Assuming implementations (mocks or ipfs_extensions) accept arguments via **kwargs
                        result = await implementation(**arguments)

                        return result
                    except Exception as e:
                        logger.error(f"Error in {t_name}: {e}")
                        logger.error(traceback.format_exc())
                        return {
                            "success": False,
                            "error": str(e),
                            "tool": t_name
                        }
                return wrapper

            # Register the wrapped handler
            try:
                wrapped_handler = create_wrapper(impl, tool_name)
                mcp_server.tool(name=tool_name, description=description)(wrapped_handler)
                registered_tools.append(tool_name)
                logger.info(f" Registered tool: {tool_name}")
            except Exception as e:
                logger.error(f" Error registering tool {tool_name}: {e}")
                logger.error(traceback.format_exc())


    logger.info(f" Successfully registered {len(registered_tools)}/{len(IPFS_TOOLS)} IPFS tools")

    # Return success only if we actually registered tools
    if len(registered_tools) > 0:
        return registered_tools
    else:
        logger.warning(" No IPFS tools were actually registered!")
        return False

if __name__ == "__main__":
    logger.info("This module should be imported and used with an MCP server, not run directly.")
    logger.info(f"IPFS extensions available: {TOOL_STATUS['ipfs_extensions_available']}")
    logger.info(f"IPFS model available: {TOOL_STATUS['ipfs_model_available']}")
    logger.info(f"Fixed IPFS model available: {TOOL_STATUS['fixed_ipfs_model_available']}")
    logger.info(f"IPFS-FS bridge available: {TOOL_STATUS['ipfs_fs_bridge_available']}")
