#!/usr/bin/env python3
"""
IPFS MCP Tool Implementation Script

This script implements the missing IPFS methods needed for MCP tools to work properly.
"""

import os
import sys
import json
import logging
import importlib
import inspect
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='implement_mcp_ipfs_tools.log'
)
logger = logging.getLogger(__name__)

# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Define paths
CWD = os.getcwd()
IPFS_KIT_PATH = os.path.join(CWD, "ipfs_kit_py")
MCP_PATH = os.path.join(IPFS_KIT_PATH, "mcp")
CONTROLLERS_PATH = os.path.join(MCP_PATH, "controllers")
MODELS_PATH = os.path.join(MCP_PATH, "models")

# Missing methods from logs
MISSING_METHODS = [
    "add_content",
    "cat",
    "pin_add",
    "pin_rm",
    "pin_ls",
    "swarm_peers",
    "swarm_connect",
    "swarm_disconnect",
    "storage_transfer",
    "get_version"
]

def fix_server_bridge():
    """Fix server_bridge.py to properly handle tool requests."""
    server_bridge_path = os.path.join(MCP_PATH, "server_bridge.py")

    if not os.path.exists(server_bridge_path):
        logger.error(f"Server bridge file not found at {server_bridge_path}")
        return False

    try:
        # Read the current file
        with open(server_bridge_path, 'r') as f:
            content = f.read()

        # Check if the file already has tool handling
        if "tool_handler" in content and "/mcp/tools" in content:
            logger.info("Server bridge already has tool handling")

            # Make sure the route is properly registered
            if "app.add_api_route(\"/mcp/tools\"" not in content:
                # Add the route if it's missing
                route_code = """
    # Add MCP tool handling route
    app.add_api_route(
        "/mcp/tools",
        tool_handler,
        methods=["POST"],
        tags=["mcp"],
        summary="Execute MCP tool",
        description="Execute an MCP tool with the given parameters"
    )
"""
                # Find the right position to add the route
                if "def register_with_app(app" in content:
                    # Add after the register_with_app function definition
                    content = content.replace(
                        "def register_with_app(app",
                        f"def register_with_app(app{route_code}"
                    )
                    logger.info("Added MCP tools route to server_bridge.py")
                else:
                    logger.warning("Could not find a place to add the MCP tools route")
        else:
            # Add tool handling code if it's missing
            tool_code = """
# MCP Tool handling
async def tool_handler(request: Request):
    \"\"\"Handle MCP tool requests.\"\"\"
    data = await request.json()

    tool_name = data.get("name")
    server_name = data.get("server", "default")
    args = data.get("args", {})

    if not tool_name:
        return JSONResponse(
            status_code=400,
            content={"error": "Tool name is required"}
        )

    # Find the tool implementation
    try:
        # Try to get the tool from controllers
        for controller_name, controller in controllers.items():
            if hasattr(controller, tool_name):
                tool_impl = getattr(controller, tool_name)
                if callable(tool_impl):
                    # Call the tool with args
                    result = await tool_impl(**args)
                    return JSONResponse(content=result)

        # If not found in controllers, try model methods
        for model_name, model in models.items():
            if hasattr(model, tool_name):
                tool_impl = getattr(model, tool_name)
                if callable(tool_impl):
                    # Call the tool with args
                    result = await tool_impl(**args)
                    return JSONResponse(content=result)

        # If still not found, check extensions
        if hasattr(extensions, tool_name):
            tool_impl = getattr(extensions, tool_name)
            if callable(tool_impl):
                # Call the tool with args
                result = await tool_impl(**args)
                return JSONResponse(content=result)

        # Tool not found
        return JSONResponse(
            status_code=404,
            content={"error": f"Tool '{tool_name}' not found"}
        )
    except Exception as e:
        # Log the error
        logger.error(f"Error executing tool '{tool_name}': {e}")
        logger.error(traceback.format_exc())

        # Return error response
        return JSONResponse(
            status_code=500,
            content={"error": f"Error executing tool: {str(e)}"}
        )
"""
            # Add the tool handler code
            content += tool_code
            logger.info("Added tool handler code to server_bridge.py")

            # Add the route
            route_code = """
    # Add MCP tool handling route
    app.add_api_route(
        "/mcp/tools",
        tool_handler,
        methods=["POST"],
        tags=["mcp"],
        summary="Execute MCP tool",
        description="Execute an MCP tool with the given parameters"
    )
"""
            # Find the right position to add the route
            if "def register_with_app(app" in content:
                # Add after the register_with_app function definition
                content = content.replace(
                    "def register_with_app(app",
                    f"def register_with_app(app{route_code}"
                )
                logger.info("Added MCP tools route to server_bridge.py")
            else:
                logger.warning("Could not find a place to add the MCP tools route")

        # Write the updated content
        with open(server_bridge_path, 'w') as f:
            f.write(content)

        logger.info(f"Updated server bridge file at {server_bridge_path}")
        return True
    except Exception as e:
        logger.error(f"Error fixing server bridge: {e}")
        logger.error(traceback.format_exc())
        return False

def create_ipfs_extensions():
    """Create a file with IPFS extension methods."""
    extensions_path = os.path.join(MCP_PATH, "ipfs_extensions.py")

    extensions_code = """#!/usr/bin/env python3
\"\"\"
IPFS Extensions for MCP

This module provides IPFS methods for MCP tools.
\"\"\"

import os
import json
import base64
import tempfile
import logging
import anyio
from typing import Dict, Any, List, Optional, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='ipfs_extensions.log'
)
logger = logging.getLogger(__name__)

# Import IPFS model if available
try:
    from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
    IPFS_MODEL_AVAILABLE = True
    logger.info("Successfully imported IPFSModel")
except ImportError:
    logger.warning("Failed to import IPFSModel")
    IPFS_MODEL_AVAILABLE = False

# Global IPFS model instance
ipfs_model = None

def initialize_ipfs_model():
    \"\"\"Initialize IPFS model.\"\"\"
    global ipfs_model, IPFS_MODEL_AVAILABLE

    if not IPFS_MODEL_AVAILABLE:
        logger.error("IPFSModel not available")
        return False

    try:
        if ipfs_model is None:
            ipfs_model = IPFSModel()
            logger.info("Initialized IPFSModel")
        return True
    except Exception as e:
        logger.error(f"Error initializing IPFSModel: {e}")
        IPFS_MODEL_AVAILABLE = False
        return False

# Initialize IPFS model
initialize_ipfs_model()

# Helper functions
def ensure_ipfs_model():
    \"\"\"Ensure IPFS model is initialized.\"\"\"
    if ipfs_model is None:
        return initialize_ipfs_model()
    return True

async def add_content(content: str, filename: Optional[str] = None, pin: bool = True) -> Dict[str, Any]:
    \"\"\"
    Add content to IPFS.

    Args:
        content: Content to add
        filename: Optional filename
        pin: Whether to pin the content

    Returns:
        Dictionary with CID and other information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Create a temporary file with the content
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_file:
            if isinstance(content, str):
                temp_file.write(content.encode('utf-8'))
            else:
                temp_file.write(content)
            temp_path = temp_file.name

        # Add the file to IPFS
        result = ipfs_model.ipfs_client.add(temp_path)

        # Clean up the temporary file
        os.unlink(temp_path)

        # Pin the content if requested
        if pin and 'Hash' in result:
            ipfs_model.ipfs_client.pin.add(result['Hash'])

        # Return the result
        return {
            "success": True,
            "cid": result.get('Hash'),
            "name": result.get('Name', filename or 'file'),
            "size": result.get('Size', 0),
            "pinned": pin
        }
    except Exception as e:
        logger.error(f"Error adding content to IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def cat(cid: str) -> Dict[str, Any]:
    \"\"\"
    Retrieve content from IPFS.

    Args:
        cid: Content ID to retrieve

    Returns:
        Dictionary with content and other information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Get the content from IPFS
        content = ipfs_model.ipfs_client.cat(cid)

        # Try to decode as text if possible
        try:
            content_str = content.decode('utf-8')
            content_encoding = "text"
        except UnicodeDecodeError:
            # If not decodable as text, encode as base64
            content_str = base64.b64encode(content).decode('utf-8')
            content_encoding = "base64"

        # Return the result
        return {
            "success": True,
            "cid": cid,
            "content": content_str,
            "content_encoding": content_encoding,
            "size": len(content)
        }
    except Exception as e:
        logger.error(f"Error retrieving content from IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def pin_add(cid: str, recursive: bool = True) -> Dict[str, Any]:
    \"\"\"
    Pin content to IPFS.

    Args:
        cid: Content ID to pin
        recursive: Whether to pin recursively

    Returns:
        Dictionary with pin information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Pin the content
        result = ipfs_model.ipfs_client.pin.add(cid, recursive=recursive)

        # Return the result
        return {
            "success": True,
            "cid": cid,
            "pins": result.get('Pins', [cid]),
            "recursive": recursive
        }
    except Exception as e:
        logger.error(f"Error pinning content to IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def pin_rm(cid: str, recursive: bool = True) -> Dict[str, Any]:
    \"\"\"
    Unpin content from IPFS.

    Args:
        cid: Content ID to unpin
        recursive: Whether to unpin recursively

    Returns:
        Dictionary with unpin information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Unpin the content
        result = ipfs_model.ipfs_client.pin.rm(cid, recursive=recursive)

        # Return the result
        return {
            "success": True,
            "cid": cid,
            "pins": result.get('Pins', [cid]),
            "recursive": recursive
        }
    except Exception as e:
        logger.error(f"Error unpinning content from IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def pin_ls(cid: Optional[str] = None, type_filter: str = "all") -> Dict[str, Any]:
    \"\"\"
    List pinned content in IPFS.

    Args:
        cid: Optional content ID to filter by
        type_filter: Type of pins to list (all, direct, indirect, recursive)

    Returns:
        Dictionary with pin information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # List pins
        if cid:
            result = ipfs_model.ipfs_client.pin.ls(cid, type=type_filter)
        else:
            result = ipfs_model.ipfs_client.pin.ls(type=type_filter)

        # Format the result
        pins = []
        for pin_cid, pin_type in result.get('Keys', {}).items():
            pins.append({
                "cid": pin_cid,
                "type": pin_type.get('Type', 'unknown')
            })

        # Return the result
        return {
            "success": True,
            "pins": pins,
            "count": len(pins),
            "type_filter": type_filter
        }
    except Exception as e:
        logger.error(f"Error listing pins in IPFS: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def get_version() -> Dict[str, Any]:
    \"\"\"
    Get IPFS version information.

    Returns:
        Dictionary with version information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Get version information
        version = ipfs_model.ipfs_client.version()

        # Return the result
        return {
            "success": True,
            "version": version.get('Version', 'unknown'),
            "commit": version.get('Commit', 'unknown'),
            "repo": version.get('Repo', 'unknown'),
            "system": version.get('System', 'unknown'),
            "golang": version.get('Golang', 'unknown')
        }
    except Exception as e:
        logger.error(f"Error getting IPFS version: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# MFS methods
async def files_ls(path: str = '/', long: bool = False) -> Dict[str, Any]:
    \"\"\"
    List files in MFS.

    Args:
        path: Path to list
        long: Whether to show detailed information

    Returns:
        Dictionary with file information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # List files
        result = ipfs_model.ipfs_client.files.ls(path, long=long)

        # Format the result
        entries = []
        for entry in result.get('Entries', []):
            entries.append({
                "name": entry.get('Name', ''),
                "type": entry.get('Type', 0),
                "size": entry.get('Size', 0),
                "hash": entry.get('Hash', '')
            })

        # Return the result
        return {
            "success": True,
            "path": path,
            "entries": entries,
            "count": len(entries)
        }
    except Exception as e:
        logger.error(f"Error listing files in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_mkdir(path: str, parents: bool = True) -> Dict[str, Any]:
    \"\"\"
    Create a directory in MFS.

    Args:
        path: Path to create
        parents: Whether to create parent directories

    Returns:
        Dictionary with result information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Create directory
        ipfs_model.ipfs_client.files.mkdir(path, parents=parents)

        # Return the result
        return {
            "success": True,
            "path": path,
            "parents": parents
        }
    except Exception as e:
        logger.error(f"Error creating directory in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_write(path: str, content: str, create: bool = True, truncate: bool = True) -> Dict[str, Any]:
    \"\"\"
    Write content to a file in MFS.

    Args:
        path: Path to write to
        content: Content to write
        create: Whether to create the file if it does not exist
        truncate: Whether to truncate the file before writing

    Returns:
        Dictionary with result information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Convert content to bytes if it's a string
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        # Create a temporary file with the content
        with tempfile.NamedTemporaryFile(mode='w+b', delete=False) as temp_file:
            temp_file.write(content_bytes)
            temp_path = temp_file.name

        # Write the file to MFS
        ipfs_model.ipfs_client.files.write(path, temp_path, create=create, truncate=truncate)

        # Clean up the temporary file
        os.unlink(temp_path)

        # Return the result
        return {
            "success": True,
            "path": path,
            "size": len(content_bytes),
            "create": create,
            "truncate": truncate
        }
    except Exception as e:
        logger.error(f"Error writing to file in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_read(path: str, offset: int = 0, count: int = -1) -> Dict[str, Any]:
    \"\"\"
    Read content from a file in MFS.

    Args:
        path: Path to read from
        offset: Offset to start reading from
        count: Number of bytes to read (-1 for all)

    Returns:
        Dictionary with content and result information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Read the file from MFS
        content = ipfs_model.ipfs_client.files.read(path, offset=offset, count=count)

        # Try to decode as text if possible
        try:
            content_str = content.decode('utf-8')
            content_encoding = "text"
        except UnicodeDecodeError:
            # If not decodable as text, encode as base64
            content_str = base64.b64encode(content).decode('utf-8')
            content_encoding = "base64"

        # Return the result
        return {
            "success": True,
            "path": path,
            "content": content_str,
            "content_encoding": content_encoding,
            "size": len(content),
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error reading file from MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_rm(path: str, recursive: bool = False) -> Dict[str, Any]:
    \"\"\"
    Remove a file or directory from MFS.

    Args:
        path: Path to remove
        recursive: Whether to recursively remove directories

    Returns:
        Dictionary with result information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Remove the file or directory
        ipfs_model.ipfs_client.files.rm(path, recursive=recursive)

        # Return the result
        return {
            "success": True,
            "path": path,
            "recursive": recursive
        }
    except Exception as e:
        logger.error(f"Error removing file from MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_stat(path: str) -> Dict[str, Any]:
    \"\"\"
    Get information about a file or directory in MFS.

    Args:
        path: Path to get information about

    Returns:
        Dictionary with file information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Get file information
        stat = ipfs_model.ipfs_client.files.stat(path)

        # Return the result
        return {
            "success": True,
            "path": path,
            "hash": stat.get('Hash', ''),
            "size": stat.get('Size', 0),
            "cumulative_size": stat.get('CumulativeSize', 0),
            "blocks": stat.get('Blocks', 0),
            "type": stat.get('Type', ''),
            "mode": stat.get('Mode', 0)
        }
    except Exception as e:
        logger.error(f"Error getting file information from MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

async def files_cp(source: str, dest: str) -> Dict[str, Any]:
    \"\"\"
    Copy a file or directory in MFS.

    Args:
        source: Source path
        dest: Destination path

    Returns:
        Dictionary with result information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Copy the file or directory
        ipfs_model.ipfs_client.files.cp(source, dest)

        # Return the result
        return {
            "success": True,
            "source": source,
            "destination": dest
        }
    except Exception as e:
        logger.error(f"Error copying file in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "source": source,
            "destination": dest
        }

async def files_mv(source: str, dest: str) -> Dict[str, Any]:
    \"\"\"
    Move a file or directory in MFS.

    Args:
        source: Source path
        dest: Destination path

    Returns:
        Dictionary with result information
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Move the file or directory
        ipfs_model.ipfs_client.files.mv(source, dest)

        # Return the result
        return {
            "success": True,
            "source": source,
            "destination": dest
        }
    except Exception as e:
        logger.error(f"Error moving file in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "source": source,
            "destination": dest
        }

async def files_flush(path: str = "/") -> Dict[str, Any]:
    \"\"\"
    Flush changes in MFS to IPFS.

    Args:
        path: Path to flush

    Returns:
        Dictionary with CID of the flushed path
    \"\"\"
    if not ensure_ipfs_model():
        return {
            "success": False,
            "error": "IPFS model not available"
        }

    try:
        # Flush the path
        result = ipfs_model.ipfs_client.files.flush(path)

        # Return the result
        return {
            "success": True,
            "path": path,
            "cid": result.get('Cid', '')
        }
    except Exception as e:
        logger.error(f"Error flushing path in MFS: {e}")
        return {
            "success": False,
            "error": str(e),
            "path": path
        }

# Map tool names to functions
TOOL_MAP = {
    "ipfs_add": add_content,
    "ipfs_cat": cat,
    "ipfs_pin": pin_add,
    "ipfs_unpin": pin_rm,
    "ipfs_list_pins": pin_ls,
    "ipfs_version": get_version,
    "ipfs_files_ls": files_ls,
    "ipfs_files_mkdir": files_mkdir,
    "ipfs_files_write": files_write,
    "ipfs_files_read": files_read,
    "ipfs_files_rm": files_rm,
    "ipfs_files_stat": files_stat,
    "ipfs_files_cp": files_cp,
    "ipfs_files_mv": files_mv,
    "ipfs_files_flush": files_flush
}

# Main function for testing
async def main():
    \"\"\"Test IPFS extensions.\"\"\"
    # Initialize IPFS model
    if not initialize_ipfs_model():
        print("Failed to initialize IPFS model")
        return 1

    # Test add content
    content = "Hello, IPFS from Python extensions!"
    print(f"Adding content: {content}")
    add_result = await add_content(content, filename="hello.txt", pin=True)
    print(f"Add result: {json.dumps(add_result, indent=2)}")

    if add_result.get("success"):
        # Get the CID
        cid = add_result.get("cid")
        print(f"Content CID: {cid}")

        # Test cat
        print(f"Retrieving content for CID: {cid}")
        cat_result = await cat(cid)
        print(f"Cat result: {json.dumps(cat_result, indent=2)}")

        # Test pin operations
        print(f"Pinning CID: {cid}")
        pin_result = await pin_add(cid)
        print(f"Pin result: {json.dumps(pin_result, indent=2)}")

        print(f"Listing pins")
        pins_result = await pin_ls()
        print(f"Pins result: {json.dumps(pins_result, indent=2)}")

    # Test version
    print("Getting IPFS version")
    version_result = await get_version()
    print(f"Version result: {json.dumps(version_result, indent=2)}")

    # Test MFS operations
    print("Creating directory in MFS")
    mkdir_result = await files_mkdir("/test")
    print(f"Mkdir result: {json.dumps(mkdir_result, indent=2)}")

    print("Writing file to MFS")
    write_result = await files_write("/test/hello.txt", "Hello, MFS!")
    print(f"Write result: {json.dumps(write_result, indent=2)}")

    print("Listing files in MFS")
    ls_result = await files_ls("/test")
    print(f"Ls result: {json.dumps(ls_result, indent=2)}")

    print("Reading file from MFS")
    read_result = await files_read("/test/hello.txt")
    print(f"Read result: {json.dumps(read_result, indent=2)}")

    print("Removing file from MFS")
    rm_result = await files_rm("/test/hello.txt")
    print(f"Rm result: {json.dumps(rm_result, indent=2)}")

    print("Getting file stats in MFS")
    stat_result = await files_stat("/test")
    print(f"Stat result: {json.dumps(stat_result, indent=2)}")

    print("Copying file in MFS")
    cp_result = await files_cp("/test", "/test_copy")
    print(f"Cp result: {json.dumps(cp_result, indent=2)}")

    print("Moving file in MFS")
    mv_result = await files_mv("/test_copy", "/test_moved")
    print(f"Mv result: {json.dumps(mv_result, indent=2)}")

    print("Flushing changes in MFS")
    flush_result = await files_flush("/test_moved")
    print(f"Flush result: {json.dumps(flush_result, indent=2)}")

    return 0

if __name__ == "__main__":
    anyio.run(main)
"""

    try:
        # Write the file
        with open(extensions_path, 'w') as f:
            f.write(extensions_code)

        logger.info(f"Created IPFS extensions file at {extensions_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating IPFS extensions: {e}")
        logger.error(traceback.format_exc())
        return False

def update_ipfs_controller():
    """Update IPFS controller to use the extensions."""
    controller_path = os.path.join(CONTROLLERS_PATH, "ipfs_controller.py")

    if not os.path.exists(controller_path):
        logger.error(f"IPFS controller file not found at {controller_path}")
        return False

    try:
        # Read the current file
        with open(controller_path, 'r') as f:
            content = f.read()

        # Check if the file already imports the extensions
        if "from ipfs_kit_py.mcp.ipfs_extensions import" in content:
            logger.info("IPFS controller already imports extensions")
        else:
            # Add the import
            import_code = """
# Import IPFS extensions
try:
    from ipfs_kit_py.mcp.ipfs_extensions import (
        add_content, cat, pin_add, pin_rm, pin_ls,
        get_version, files_ls, files_mkdir, files_write, files_read,
        files_rm, files_stat, files_cp, files_mv, files_flush
    )
    logger.info("Successfully imported IPFS extensions")
except ImportError as e:
    logger.warning(f"Failed to import IPFS extensions: {e}")
"""
            # Add the import after the other imports
            if "import " in content:
                last_import_index = content.rfind("import ")
                last_import_line_end = content.find("\n", last_import_index)

                if last_import_line_end > 0:
                    content = content[:last_import_line_end + 1] + import_code + content[last_import_line_end + 1:]
                    logger.info("Added IPFS extensions import to IPFS controller")
                else:
                    logger.warning("Could not find a place to add the IPFS extensions import")
            else:
                # Add at the beginning of the file
                content = import_code + content
                logger.info("Added IPFS extensions import to IPFS controller")

        # Add the tool methods if not already present
        for method_name in MISSING_METHODS:
            # Check if the method is already defined
            if f"async def {method_name}" in content:
                logger.info(f"Method {method_name} already defined in IPFS controller")
                continue

            # Add the method
            method_code = f"""
    async def {method_name}(self, **kwargs):
        \"\"\"Proxy to extensions.{method_name}.\"\"\"
        try:
            if '{method_name}' in globals():
                return await globals()['{method_name}'](**kwargs)
            else:
                logger.error("Method {method_name} not found in extensions")
                return {{
                    "success": False,
                    "error": "Method {method_name} not found in extensions"
                }}
        except Exception as e:
            logger.error(f"Error in {method_name}: {{e}}")
            return {{
                "success": False,
                "error": str(e)
            }}
"""
            # Add the method to the IPFSController class
            if "class IPFSController" in content:
                class_end_index = content.find("class IPFSController")
                next_class_index = content.find("class ", class_end_index + 1)

                if next_class_index > 0:
                    # Insert before the next class
                    content = content[:next_class_index] + method_code + content[next_class_index:]
                else:
                    # Add at the end of the file
                    content += method_code

                logger.info(f"Added method {method_name} to IPFS controller")
            else:
                logger.warning(f"Could not find IPFSController class to add method {method_name}")

        # Write the updated content
        with open(controller_path, 'w') as f:
            f.write(content)

        logger.info(f"Updated IPFS controller file at {controller_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating IPFS controller: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function."""
    logger.info("Starting IPFS MCP tool implementation")

    # Fix server bridge
    logger.info("Fixing server bridge...")
    if fix_server_bridge():
        logger.info("Server bridge fixed successfully")
    else:
        logger.warning("Failed to fix server bridge")

    # Create IPFS extensions
    logger.info("Creating IPFS extensions...")
    if create_ipfs_extensions():
        logger.info("IPFS extensions created successfully")
    else:
        logger.warning("Failed to create IPFS extensions")

    # Update IPFS controller
    logger.info("Updating IPFS controller...")
    if update_ipfs_controller():
        logger.info("IPFS controller updated successfully")
    else:
        logger.warning("Failed to update IPFS controller")

    logger.info("IPFS MCP tool implementation complete")

    print("\n=== IPFS MCP Tool Implementation ===")
    print("The script has created and updated the necessary files to implement IPFS MCP tools.")
    print("To apply these changes, you need to:")
    print("1. Restart the MCP server")
    print("2. Restart VS Code to apply the new settings")
    print("3. Test the tools using the working_example.py script")
    print("\nSee the log file for details: implement_mcp_ipfs_tools.log")

    return 0

if __name__ == "__main__":
    sys.exit(main())
