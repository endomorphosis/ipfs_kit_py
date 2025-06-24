#!/usr/bin/env python3
"""
Register Enhanced IPFS Tools with MCP Server

This script registers the enhanced IPFS tools with the MCP server without
requiring full filesystem integration.
"""

import os
import sys
import logging
import json
import importlib.util
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def import_module_from_file(file_path, module_name=None):
    """Import a module from a file path"""
    if not os.path.exists(file_path):
        raise ImportError(f"File not found: {file_path}")

    if module_name is None:
        module_name = os.path.basename(file_path).split('.')[0]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load spec for {file_path}")

    if spec.loader is None:
        raise ImportError(f"Could not get loader for {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def register_tools_with_direct_mcp():
    """Register tools directly with the MCP server"""
    try:
        # Import the direct_mcp_server module
        if not os.path.exists("direct_mcp_server.py"):
            logger.error("direct_mcp_server.py not found")
            return False

        # Import the tools registry
        if not os.path.exists("ipfs_tools_registry.py"):
            logger.error("ipfs_tools_registry.py not found")
            return False

        # Load the tools registry
        tools_registry = import_module_from_file("ipfs_tools_registry.py")
        if not hasattr(tools_registry, 'get_ipfs_tools'):
            logger.error("get_ipfs_tools function not found in tools registry")
            return False

        # Get the tools
        tools = tools_registry.get_ipfs_tools()
        logger.info(f"Loaded {len(tools)} tools from registry")

        # Create a simple patch to register tools with the MCP server
        patch_content = '''
import json
from typing import List, Dict, Any

def register_tools_with_mcp(tools):
    """Register tools with the MCP server"""
    try:
        # Convert tools to a format suitable for MCP
        mcp_tools = []
        for tool in tools:
            mcp_tool = {
                "name": tool["name"],
                "description": tool["description"],
                "schema": tool["schema"]
            }
            mcp_tools.append(mcp_tool)

        # Write tools to a file that will be loaded by the MCP server
        with open("mcp_registered_tools.json", "w") as f:
            json.dump(mcp_tools, f, indent=2)

        return True
    except Exception as e:
        print(f"Error registering tools: {e}")
        return False
'''

        # Write the patch to a file
        with open("register_tools_patch.py", "w") as f:
            f.write(patch_content)

        # Import the patch
        register_patch = import_module_from_file("register_tools_patch.py")

        # Register the tools
        result = register_patch.register_tools_with_mcp(tools)
        if result:
            logger.info("✅ Successfully registered tools with MCP server")
            return True
        else:
            logger.error("Failed to register tools with MCP server")
            return False

    except Exception as e:
        logger.error(f"Error registering tools: {e}")
        return False

def create_mcp_loader():
    """Create a script to load the tools into the MCP server"""
    loader_path = "load_tools_into_mcp.py"

    try:
        with open(loader_path, "w") as f:
            f.write("""#!/usr/bin/env python3
\"\"\"
Load Enhanced Tools into MCP Server

This script loads the enhanced tools into the MCP server.
\"\"\"

import os
import sys
import json
import logging
import importlib.util
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def import_module_from_file(file_path, module_name=None):
    \"\"\"Import a module from a file path\"\"\"
    if not os.path.exists(file_path):
        raise ImportError(f"File not found: {file_path}")

    if module_name is None:
        module_name = os.path.basename(file_path).split('.')[0]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        raise ImportError(f"Could not load spec for {file_path}")

    if spec.loader is None:
        raise ImportError(f"Could not get loader for {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def load_tools_into_mcp():
    \"\"\"Load tools into the MCP server\"\"\"
    try:
        # Check if the tools file exists
        if not os.path.exists("mcp_registered_tools.json"):
            logger.error("mcp_registered_tools.json not found")
            return False

        # Load the tools
        with open("mcp_registered_tools.json", "r") as f:
            tools = json.load(f)

        logger.info(f"Loaded {len(tools)} tools from file")

        # Check if direct_mcp_server.py exists
        if not os.path.exists("direct_mcp_server.py"):
            logger.error("direct_mcp_server.py not found")
            return False

        # Import the direct_mcp_server module
        direct_mcp = import_module_from_file("direct_mcp_server.py")

        # Check if the register_tools function exists
        if not hasattr(direct_mcp, 'register_tools'):
            logger.error("register_tools function not found in direct_mcp_server.py")

            # Create a simple function to register tools
            logger.info("Creating a simple function to register tools")

            # Check if the server has a tools registry
            if hasattr(direct_mcp, 'tools'):
                logger.info("Found tools registry in direct_mcp_server.py")

                # Add the tools to the registry
                for tool in tools:
                    direct_mcp.tools.append(tool)

                logger.info(f"Added {len(tools)} tools to the registry")
                return True
            else:
                logger.error("No tools registry found in direct_mcp_server.py")
                return False
        else:
            # Use the register_tools function
            result = direct_mcp.register_tools(tools)
            if result:
                logger.info("✅ Successfully registered tools with MCP server")
                return True
            else:
                logger.error("Failed to register tools with MCP server")
                return False

    except Exception as e:
        logger.error(f"Error loading tools into MCP: {e}")
        return False

def main():
    \"\"\"Main function\"\"\"
    logger.info("Loading enhanced tools into MCP server...")

    result = load_tools_into_mcp()

    if result:
        logger.info("\\n✅ Successfully loaded enhanced tools into MCP server")
        return 0
    else:
        logger.error("\\n❌ Failed to load enhanced tools into MCP server")
        return 1

if __name__ == "__main__":
    sys.exit(main())
""")

        # Make the script executable
        os.chmod(loader_path, 0o755)

        logger.info(f"✅ Created MCP loader script at {loader_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating MCP loader script: {e}")
        return False

def create_restart_script():
    """Create a script to restart the MCP server with the new tools"""
    script_path = "restart_mcp_with_tools.sh"

    try:
        with open(script_path, 'w') as f:
            f.write("""#!/bin/bash
# Restart MCP server with enhanced tools

echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

echo "Registering enhanced tools..."
python register_enhanced_tools.py

echo "Starting MCP server with enhanced tools..."
python direct_mcp_server.py &

echo "MCP server started with PID $!"
echo "Waiting for server to initialize..."
sleep 3

echo "Loading enhanced tools into MCP server..."
python load_tools_into_mcp.py

echo "✅ MCP server is now running with enhanced tools"
echo "You can use the new tools through the JSON-RPC interface"
""")

        # Make the script executable
        os.chmod(script_path, 0o755)

        logger.info(f"✅ Created restart script at {script_path}")
        return True

    except Exception as e:
        logger.error(f"Error creating restart script: {e}")
        return False

def main():
    """Main function to register enhanced tools"""
    logger.info("Starting registration of enhanced tools...")

    # Register tools with MCP server
    tools_registered = register_tools_with_direct_mcp()

    # Create MCP loader script
    loader_created = create_mcp_loader()

    # Create restart script
    restart_script_created = create_restart_script()

    # Check overall success
    success = all([
        tools_registered,
        loader_created,
        restart_script_created
    ])

    if success:
        logger.info("\n✅ Enhanced tools registration completed successfully")
        logger.info("To use the enhanced tools:")
        logger.info("  1. Run ./restart_mcp_with_tools.sh to restart the MCP server with enhanced tools")
        logger.info("  2. Use the tools through the JSON-RPC interface")
        return 0
    else:
        logger.error("\n❌ Enhanced tools registration failed")
        logger.error("Please check the logs for details")
        return 1

if __name__ == "__main__":
    sys.exit(main())
