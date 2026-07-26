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
    logger.info("✅ IPFS extensions module available")
except ImportError as e:
    logger.warning(f"⚠️ Could not import IPFS extensions: {e}")
    logger.warning("⚠️ Will use mock implementations for IPFS extensions")
except Exception as e:
    logger.error(f"❌ Unexpected error importing IPFS extensions: {e}")
    logger.error(traceback.format_exc())

# Try to import IPFS model if available
try:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    TOOL_STATUS["ipfs_model_available"] = True
    logger.info("✅ IPFS model available")
except ImportError as e:
    logger.warning(f"⚠️ Could not import IPFS model: {e}")
except Exception as e:
    logger.error(f"❌ Unexpected error importing IPFS model: {e}")
    logger.error(traceback.format_exc())


# Try to import IPFS-FS bridge if available
try:
    from ipfs_kit_py.fs_journal import IPFSFSBridge
    TOOL_STATUS["ipfs_fs_bridge_available"] = True
    logger.info("✅ IPFS-FS bridge available")
except ImportError as e:
    logger.warning(f"⚠️ Could not import IPFS-FS Bridge: {e}")
except Exception as e:
    logger.error(f"❌ Unexpected error importing IPFS-FS Bridge: {e}")
    logger.error(traceback.format_exc())

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
fixed_ipfs_model_instance = None # This will always be None now.

# Initialize needed components
def initialize_components():
    """Initialize IPFS components if available."""
    global ipfs_model, fs_bridge, fixed_ipfs_model_instance

    try:
        if TOOL_STATUS["ipfs_model_available"] and ipfs_model is None:
            ipfs_model = IPFSModel()
            logger.info("✅ IPFS Model initialized")

        # fixed_ipfs_model_instance will always be None as its import is removed
        # Fixed IPFS Model initialization removed to prevent hanging
        # fixed_ipfs_model_instance will always be None


        if TOOL_STATUS["ipfs_fs_bridge_available"] and fs_bridge is None:
            fs_bridge = IPFSFSBridge()
            logger.info("✅ IPFS-FS Bridge initialized")

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
        if tool_name in extensions_map:
            impl = extensions_map[tool_name]
            logger.info(f"For {tool_name}, using ipfs_extensions implementation.")
            return impl

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
    logger.warning(f"❓ No implementation found for tool: {tool_name}")
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

    # Create and register each tool
    for tool in IPFS_TOOLS:
        tool_name = tool["name"]
        description = tool.get("description", f"IPFS tool: {tool_name}")
        schema = tool.get("schema", {})

        # Get the appropriate implementation
        impl = get_implementation(tool_name)

        if impl:
            def create_wrapper(implementation, t_name):
                async def wrapper(ctx):
                    # Extract arguments
                    arguments = {}
                    if hasattr(ctx, 'arguments') and ctx.arguments is not None:
                        arguments = ctx.arguments
                    elif hasattr(ctx, 'params') and ctx.params is not None:
                        arguments = ctx.params

                    logger.info(f"Called {t_name} with arguments: {arguments}")

                    try:
                        # Call the implementation
                        # fixed_ipfs_model_instance is no longer used here.
                        # if TOOL_STATUS["fixed_ipfs_model_available"] and implementation in FIXED_TOOL_MAP.values():
                        #      result = await implementation(fixed_ipfs_model_instance.ipfs_client, **arguments)
                        # Pass the ipfs_model instance if using original ipfs_model methods (less likely now)
                        if TOOL_STATUS["ipfs_model_available"] and hasattr(ipfs_model, implementation.__name__):
                             result = await implementation(ipfs_model.ipfs_client, **arguments)
                        # Otherwise, assume it's a standalone function (like mocks or ipfs_extensions)
                        else:
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
                logger.info(f"✅ Registered tool: {tool_name}")
            except Exception as e:
                logger.error(f"❌ Error registering tool {tool_name}: {e}")
                logger.error(traceback.format_exc())


    logger.info(f"✅ Successfully registered {len(registered_tools)}/{len(IPFS_TOOLS)} IPFS tools")

    # Return success only if we actually registered tools
    if len(registered_tools) > 0:
        return registered_tools
    else:
        logger.warning("⚠️ No IPFS tools were actually registered!")
        return False

if __name__ == "__main__":
    logger.info("This module should be imported and used with an MCP server, not run directly.")
    logger.info(f"IPFS extensions available: {TOOL_STATUS['ipfs_extensions_available']}")
    logger.info(f"IPFS model available: {TOOL_STATUS['ipfs_model_available']}")
    logger.info(f"Fixed IPFS model available: {TOOL_STATUS['fixed_ipfs_model_available']}")
    logger.info(f"IPFS-FS bridge available: {TOOL_STATUS['ipfs_fs_bridge_available']}")

</final_file_content>

IMPORTANT: For any future changes to this file, use the final_file_content shown above as your reference. This content reflects the current state of the file, including any auto-formatting (e.g., if you used single quotes but the formatter converted them to double quotes). Always base your SEARCH/REPLACE operations on this final version to ensure accuracy.



New problems detected after saving the file:
unified_ipfs_tools.py
  Attribute "ipfs_client" is unknown

  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Attribute "ipfs_client" is unknown
  Type "Any | None" is not assignable to type "str"
    "None" is not assignable to "str"
  Type "Any | None" is not assignable to type "str"
    "None" is not assignable to "str"

ipfs_kit_py/tools/protobuf_compat.py
# VSCode Visible Files
../../../response_05c33efd-eeb6-4ed3-9626-0e15193899e2/4
../../../response_05c33efd-eeb6-4ed3-9626-0e15193899e2/10
../../../response_05c33efd-eeb6-4ed3-9626-0e15193899e2/4
../../../response_05c33efd-eeb6-4ed3-9626-0e15193899e2/10
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-0
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-1
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-2
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-3
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-4
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-5
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-6
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-7
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-8
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-9
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-10
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-11
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-12
../../../response_b03420fa-878c-4465-9474-1b8e32805a98/tools-13
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-1
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-2
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-3
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-4
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-5
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-6
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-7
../../../response_77c90608-a720-4c4c-a2e4-b853010257d8/tools-8
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-0
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-1
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-2
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-3
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-4
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-5
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-6
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-7
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-8
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-9
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-11
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-14
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-15
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-16
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-0
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-1
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-2
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-3
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-4
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-5
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-6
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-7
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-8
../../../response_3a35b393-f9dd-4497-b4b0-6f8992385084/tools-9
../../../response_8f4b0f51-8d9d-4363-8279-1e9a282f5182/tools-0
../../../response_8f4b0f51-8d9d-4363-8279-1e9a282f5182/tools-1
../../../response_8f4b0f51-8d9d-4363-8279-1e9a282f5182/tools-0
../../../1081
unified_ipfs_tools.py

# VSCode Open Tabs
../.config/Code/User/settings.json
fixed_direct_ipfs_tools.py
fixed_ipfs_model.py
final_mcp_server.py
ipfs_kit_py/libp2p/hooks.py
unified_ipfs_tools.py
test_imports.py
test_ipfs_direct.py
ipfs_kit_py/mcp/server_bridge.py
start_mcp_direct.sh
run_fixed_server.py
ipfs_kit_py/mcp/__init__.py
README_MCP_SERVER.md
register_ipfs_tools_with_mcp.py
verify_ipfs_tools.py
start_ipfs_mcp_server.sh
stop_ipfs_mcp_server.sh
make_scripts_executable.sh
enhance_final_integration.py
final_integration.py
test_comprehensive_mcp_server.py
README_COMPREHENSIVE_MCP_SOLUTION.md
start_final_solution.sh
integrate_vfs_to_final_mcp.py
organize_workspace.py
fix_mcp_dependencies.py
run_fixed_final_solution.sh
ipfs_tools_fix.py
test_mcp_basic.py
run_final_solution.sh
fix_test_imports.py
ipfs_kit_py/tools/protobuf_compat.py
ipfs_kit_py/libp2p/__init__.py
test_ipfs_tools.py
start_comprehensive_mcp_server.sh
stop_comprehensive_mcp_server.sh
fixed_final_mcp_server.py
make_comprehensive_scripts_executable.sh
start_final_mcp.py
README_FIXED_MCP_SERVER.md
start_enhanced_mcp_server.sh
verify_fixed_mcp_tools.py
restart_fixed_mcp_server.sh
integrate_features.py
mcp_module_patch.py
restart_enhanced_mcp_server.sh
ipfs_tools_registry.py
../.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
test_ipfs_mcp_tools.py
../.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
test_basic_ipfs_mcp.py
ipfs_tools_minimal.py
restart_final_solution.sh
enhanced_test_diagnostics.py
enhance_vfs_mcp_integration.py
create_mock_modules.py
start_mcp_with_vfs_integration.sh
README_IPFS_VFS_INTEGRATION.md
start_integrated_mcp_server.sh
README_INTEGRATED_IPFS_VFS_MCP.md
register_ipfs_vfs_tools.py
fix_jsonrpc_dispatch.py
mcp_integration_patch.py
register_all_backend_tools.py
fix_ipfs_mcp_tools_integration.py
fix_jsonrpc_dispatcher.py
fix_jsonrpc_simple.py
restart_mcp_server.sh
fix_jsonrpc_correct.py
fix_jsonrpc_final.py
fix_jsonrpc_complete.py
fix_jsonrpc_final_serialization.py
README_IPFS_MCP_INTEGRATION_COMPLETE.md
fix_tool_implementation.py
fix_tool_implementation_updated.py
fix_jsonrpc_handler.py
fix_jsonrpc_run_method.py
enhance_tool_coverage.py
integrate_fs_with_tools.py
README_ENHANCED_TOOL_COVERAGE.md
register_enhanced_tools.py
direct_tool_registry.py
load_mcp_tools.py
patch_direct_mcp.py
README_COMPREHENSIVE_TOOL_COVERAGE.md
fix_direct_mcp_server.py
fix_all_syntax_errors.py
fix_server_constructor.py
fix_server_constructor_final.py
fix_subprocess_call.py
fix_subprocess_popen.py
fix_pytest_call.py
fix_async_io_sleep.py
fix_unmatched_parenthesis.py
fix_logger_info.py
fix_unmatched_parenthesis2.py
fix_list_comprehension.py
fix_line_881.py
fix_indentation.py
fix_if_block_indentation.py
fix_missing_except.py
fix_missing_parentheses.py
fix_routes_parentheses.py
fix_cors_middleware.py
fix_double_braces.py
fix_boolean_values.py
fix_uvicorn_run.py
restart_mcp_with_tools.sh
enhance_mcp_tool_coverage.py
run_direct_mcp_server.py
enhance_ipfs_fs_integration.py
fix_mcp_ipfs_integration.py
direct_mcp_server.py
ipfs_mcp_fs_integration.py
README_IPFS_TOOL_COVERAGE.md
start_ipfs_mcp_with_fs.sh
ipfs_mcp_tools_integration.py
make_tools_executable.sh
start_ipfs_mcp_with_tools.sh
stop_ipfs_mcp.sh
ipfs_mcp_tools.py
multi_backend_fs_integration.py
fs_journal_tools.py
patch_direct_mcp_server.py
README_IPFS_COMPREHENSIVE_TOOLS.md
integrate_all_tools.py
register_all_controller_tools.py
register_and_integrate_all_tools.sh
fix_mcp_resource_handler.py
test_final_mcp_server.py
direct_fix_resource_handlers.py
start_final_mcp_server.sh
start_mcp_with_logger_fix.sh
README_COMPREHENSIVE_IPFS_TOOLS.md
stop_ipfs_mcp_server_noninteractive.sh
add_comprehensive_ipfs_tools.py
add_new_ipfs_tools.py
fix_ipfs_tools_registry.py
fix_ipfs_registry_complete.py
update_and_restart_mcp_server.py
README_IPFS_MCP_INTEGRATION_FINAL.md
enhance_comprehensive_mcp_tools.py
verify_integration_tools.py
register_integration_tools.py
README_IPFS_FS_INTEGRATION.md
test_ipfs_fs_integration.py
register_multi_backend_tools.py
README_MCP_FIXES_SUMMARY.md
direct_server_fix.py
complete_server_fix.py
start_fixed_direct_mcp.sh
enhance_ipfs_mcp_tools.py
load_ipfs_mcp_tools.py
README_IPFS_MCP_INTEGRATION.md
stop_ipfs_enhanced_mcp.sh
start_ipfs_enhanced_mcp.sh
fix_patch_script.py
directly_modify_mcp.py
fix_tools_registry.py
fix_server_registration.py
fix_registration_order.py
fix_server_indentation.py
fix_ipfs_tools_integration.py
fix_tools_for_fastmcp.py
fix_mcp_ipfs_extensions.py
verify_sse_endpoints.py
run_mcp_server_simple.py
conftest.py
ipfs_kit_py/mcp/storage_manager/storage_types.py
ipfs_kit_py/mcp/controllers/filecoin_controller.py
ipfs_kit_py/mcp/models/storage_manager.py
restart_and_verify_mcp_tools.sh
debug_vscode_connection.py
mcp_jsonrpc_proxy.py
start_mcp_stack.sh
ipfs_kit_py/mcp/models/storage/ipfs_model.py
run_mcp_server_tests.py
test/test_mcp_server.py
fix_jsonrpc_url.py
verify_mcp_compatibility.py

# Current Time
5/24/2025, 9:19:11 PM (America/Los_Angeles, UTC-7:00)

# Context Window Usage
505,261 / 1,048.576K tokens used (48%)

# Current Mode
ACT MODE
</environment_details>
