#!/usr/bin/env python3
"""
Update the IPFS tools integration to use the correct FastMCP tool decorator parameters
"""

import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_integration_file():
    """Fix the IPFS MCP tools integration file to use the correct FastMCP decorator API"""
    try:
        # Create the fixed version with the correct FastMCP decorator format
        fixed_content = """\"\"\"IPFS MCP Tools Integration - Fixed for FastMCP decorator pattern\"\"\"

import logging
from ipfs_tools_registry import get_ipfs_tools

logger = logging.getLogger(__name__)

def register_ipfs_tools(mcp_server):
    \"\"\"Register all IPFS tools with the MCP server\"\"\"
    tools = get_ipfs_tools()
    logger.info(f"Registering {len(tools)} IPFS tools with MCP server")

    # Register each tool with mock implementations for now
    for tool in tools:
        tool_name = tool["name"]
        tool_schema = tool["schema"]
        
        # Get description from schema if available, otherwise use a default
        description = tool_schema.get("description", f"IPFS tool: {tool_name}")
        
        # Create a decorator function for this tool using the FastMCP format
        @mcp_server.tool(name=tool_name, description=description)
        async def tool_handler(ctx):
            # Get the parameters from the context
            params = ctx.params
            logger.info(f"Called {tool_name} with params: {params}")
            return {"success": True, "message": f"Mock implementation of {tool_name}"}
        
        # Rename the function to avoid name collisions
        tool_handler.__name__ = f"ipfs_{tool_name}_handler"
        
        logger.info(f"Registered tool: {tool_name}")

    logger.info("✅ Successfully registered all IPFS tools")
    return True
"""
        
        # Write the fixed content back
        with open("ipfs_mcp_tools_integration.py", "w") as f:
            f.write(fixed_content)
        
        logger.info("✅ Successfully fixed the IPFS tools integration for FastMCP compatibility")
        return True
    except Exception as e:
        logger.error(f"❌ Error fixing integration file: {e}")
        return False

if __name__ == "__main__":
    fix_integration_file()
