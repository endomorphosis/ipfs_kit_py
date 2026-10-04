#!/usr/bin/env python3
"""
Load Enhanced Tools into MCP Server

This script loads the enhanced tools into the MCP server.
"""

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

def load_tools_into_mcp():
    """Load tools into the MCP server"""
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
    """Main function"""
    logger.info("Loading enhanced tools into MCP server...")

    result = load_tools_into_mcp()

    if result:
        logger.info("\n✅ Successfully loaded enhanced tools into MCP server")
        return 0
    else:
        logger.error("\n❌ Failed to load enhanced tools into MCP server")
        return 1

if __name__ == "__main__":
    sys.exit(main())
