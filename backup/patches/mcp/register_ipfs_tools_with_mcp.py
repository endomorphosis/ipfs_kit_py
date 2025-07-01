#!/usr/bin/env python3
"""
Register IPFS Tools with MCP Server

This script registers the comprehensive set of IPFS tools defined in
add_comprehensive_ipfs_tools.py with the MCP server.

MCP SERVER DOCUMENTATION
=======================

Overview:
--------
The MCP (Model Context Protocol) server provides a unified interface for IPFS
functionality and tools. It enables communication between IPFS services and clients
such as IDEs, notebooks, and applications.

Starting the MCP Server:
----------------------
To start the MCP server:

1. Run the final integration script to prepare the environment:
   ```
   python3 final_integration.py
   ```

2. Start the server using the provided start script:
   ```
   ./start_final_mcp_server.sh
   ```

3. The server will run on port 3000 by default. You can customize this
   by editing the start script or passing arguments:
   ```
   ./start_final_mcp_server.sh --port 3001
   ```

Server Endpoints:
---------------
- `/` - Homepage with server information
- `/health` - Health check endpoint
- `/initialize` - Client initialization endpoint
- `/mcp` - MCP SSE connection endpoint
- `/jsonrpc` - JSON-RPC endpoint for tool invocation

Available Tools:
--------------
The server provides a wide range of IPFS tools, including:
- Core IPFS operations (add, cat, pin, etc.)
- Mutable File System (MFS) operations
- Filecoin integration
- WebRTC connectivity
- Storage backend integrations

Testing the Server:
----------------
You can test the server functionality using:
```
python3 test_final_mcp_server.py
```

Integration with VS Code:
----------------------
The server automatically configures VS Code settings to use the MCP server.
You can access these tools through the VS Code extension interface.
"""

import os
import sys
import json
import importlib
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ipfs_tools_registration.log')
    ]
)
logger = logging.getLogger('ipfs_tools_registration')

# Import the tool definitions
try:
    from add_comprehensive_ipfs_tools import (
        IPFS_TOOL_DEFINITIONS,
        FILESYSTEM_TOOL_DEFINITIONS,
        create_tool_handler,
        create_fs_integration_handler
    )
except ImportError as e:
    logger.error(f"Failed to import tool definitions: {e}")
    sys.exit(1)

def get_ipfs_controller():
    """
    Get the IPFS controller instance from the MCP server.

    Returns:
        The IPFS controller instance or None if not found.
    """
    # Try different ways to import the IPFS controller
    try:
        # First, try to import from direct_mcp_server
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import direct_mcp_server

        # Check if the server instance exists and has controllers
        if hasattr(direct_mcp_server, 'server') and hasattr(direct_mcp_server.server, 'controllers'):
            for controller in direct_mcp_server.server.controllers:
                if hasattr(controller, '__class__') and controller.__class__.__name__ == 'IPFSController':
                    logger.info("Found IPFS controller in direct_mcp_server")
                    return controller
    except ImportError:
        logger.warning("Could not import direct_mcp_server")

    # Try to import from ipfs_kit_py
    try:
        from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
        controller = IPFSController()
        logger.info("Created new IPFS controller instance")
        return controller
    except ImportError:
        logger.warning("Could not import IPFSController from ipfs_kit_py")

    # As a last resort, create a mock controller
    logger.warning("Creating a mock IPFS controller - some functionality may be limited")
    class MockIPFSController:
        def __init__(self):
            self.name = "MockIPFSController"
            logger.warning("Using MockIPFSController - only logging method calls, not executing them")

        def __getattr__(self, name):
            def mock_method(*args, **kwargs):
                logger.info(f"MockIPFSController called method {name} with args: {args}, kwargs: {kwargs}")
                return {"mocked": True, "method": name, "args": args, "kwargs": kwargs}
            return mock_method

    return MockIPFSController()

def register_tools_with_mcp(ipfs_controller):
    """
    Register IPFS tools with the MCP server.

    Args:
        ipfs_controller: The IPFS controller instance to use.

    Returns:
        Dict of registered tools.
    """
    registered_tools = {}

    # Register IPFS tools
    logger.info(f"Registering {len(IPFS_TOOL_DEFINITIONS)} IPFS tools...")
    for tool_name, tool_def in IPFS_TOOL_DEFINITIONS.items():
        method_name = tool_def["method"]
        tool_handler = create_tool_handler(method_name, ipfs_controller, tool_def)

        if tool_handler:
            registered_tools[tool_name] = tool_handler
            logger.info(f"Registered IPFS tool: {tool_name}")
        else:
            logger.warning(f"Failed to register IPFS tool: {tool_name}")

    # Register filesystem integration tools
    logger.info(f"Registering {len(FILESYSTEM_TOOL_DEFINITIONS)} filesystem integration tools...")
    for tool_name, tool_def in FILESYSTEM_TOOL_DEFINITIONS.items():
        method_name = tool_def["method"]
        tool_handler = create_fs_integration_handler(method_name, tool_def, ipfs_controller)

        if tool_handler:
            registered_tools[tool_name] = tool_handler
            logger.info(f"Registered filesystem integration tool: {tool_name}")
        else:
            logger.warning(f"Failed to register filesystem integration tool: {tool_name}")

    return registered_tools

def update_mcp_server_tools(registered_tools):
    """
    Update the MCP server with the registered tools.

    Args:
        registered_tools: Dict of registered tools.

    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        # First, try to get direct_mcp_server
        import direct_mcp_server

        # Check if the server instance exists and has a tools attribute
        if hasattr(direct_mcp_server, 'server') and hasattr(direct_mcp_server.server, 'tools'):
            # Update the server's tools dictionary
            for tool_name, tool_handler in registered_tools.items():
                direct_mcp_server.server.tools[tool_name] = tool_handler

            logger.info(f"Updated MCP server with {len(registered_tools)} tools")
            return True
    except ImportError:
        logger.warning("Could not import direct_mcp_server to update tools")

    # If we can't update directly, create a tools registry file
    try:
        with open('ipfs_tools_registry.py', 'w') as f:
            f.write(f"""#!/usr/bin/env python3
\"\"\"
IPFS tools registry for MCP server.

This file was generated by register_ipfs_tools_with_mcp.py and contains
{len(registered_tools)} registered IPFS tools.
\"\"\"

# Tool registry
TOOLS_REGISTRY = {{
""")
            for tool_name in registered_tools:
                f.write(f"    '{tool_name}': '{tool_name}',\n")
            f.write("}\n\n")

            f.write("# Tool definitions from add_comprehensive_ipfs_tools.py\n")
            f.write("from add_comprehensive_ipfs_tools import (\n")
            f.write("    IPFS_TOOL_DEFINITIONS,\n")
            f.write("    FILESYSTEM_TOOL_DEFINITIONS,\n")
            f.write("    create_tool_handler,\n")
            f.write("    create_fs_integration_handler\n")
            f.write(")\n\n")

            f.write("def register_ipfs_tools(ipfs_controller):\n")
            f.write("    \"\"\"Register IPFS tools with the given controller.\"\"\"\n")
            f.write("    registered_tools = {}\n\n")

            f.write("    # Register IPFS tools\n")
            f.write("    for tool_name, tool_def in IPFS_TOOL_DEFINITIONS.items():\n")
            f.write("        method_name = tool_def[\"method\"]\n")
            f.write("        tool_handler = create_tool_handler(method_name, ipfs_controller, tool_def)\n")
            f.write("        if tool_handler:\n")
            f.write("            registered_tools[tool_name] = tool_handler\n\n")

            f.write("    # Register filesystem integration tools\n")
            f.write("    for tool_name, tool_def in FILESYSTEM_TOOL_DEFINITIONS.items():\n")
            f.write("        method_name = tool_def[\"method\"]\n")
            f.write("        tool_handler = create_fs_integration_handler(method_name, tool_def, ipfs_controller)\n")
            f.write("        if tool_handler:\n")
            f.write("            registered_tools[tool_name] = tool_handler\n\n")

            f.write("    return registered_tools\n")

        logger.info(f"Created ipfs_tools_registry.py with {len(registered_tools)} registered tools")
        return True
    except Exception as e:
        logger.error(f"Failed to create tools registry file: {e}")
        return False

def main():
    """Register IPFS tools with MCP server."""
    logger.info("Starting IPFS tools registration...")

    # Get the IPFS controller
    ipfs_controller = get_ipfs_controller()
    if not ipfs_controller:
        logger.error("Failed to get IPFS controller")
        sys.exit(1)

    # Register tools
    registered_tools = register_tools_with_mcp(ipfs_controller)
    logger.info(f"Registered {len(registered_tools)} tools")

    # Update MCP server tools
    if update_mcp_server_tools(registered_tools):
        logger.info("Successfully updated MCP server tools")
    else:
        logger.warning("Failed to update MCP server tools")

    logger.info("IPFS tools registration complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
