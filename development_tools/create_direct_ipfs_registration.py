#!/usr/bin/env python3
"""
Direct IPFS Tool Registration

This script directly registers the IPFS tool handlers with the MCP server.
"""

import os
import sys
import logging
import traceback

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("direct-register")

def register_ipfs_tools_directly():
    """Create a script to directly register IPFS tools."""
    # First create the script content
    script_content = """#!/usr/bin/env python3
\"\"\"
Direct IPFS Tool Registration

This file is used to register IPFS tools directly with the MCP server.
\"\"\"

import logging
from typing import Dict, Any, Callable, Optional, Union

logger = logging.getLogger("direct-ipfs-tools")

# Dictionary mapping tool names to handler functions
TOOL_HANDLERS = {}

# Import handlers from ipfs_tool_adapters if available
try:
    from ipfs_tool_adapters import (
        handle_ipfs_add, handle_ipfs_cat,
        handle_ipfs_pin_add, handle_ipfs_pin_rm, handle_ipfs_pin_ls,
        handle_ipfs_files_mkdir, handle_ipfs_files_write, handle_ipfs_files_read,
        handle_ipfs_files_ls, handle_ipfs_files_rm, handle_ipfs_files_stat,
        handle_ipfs_files_cp, handle_ipfs_files_mv
    )
    
    # Register the handlers
    TOOL_HANDLERS.update({
        "ipfs_add": handle_ipfs_add,
        "ipfs_cat": handle_ipfs_cat,
        "ipfs_pin_add": handle_ipfs_pin_add,
        "ipfs_pin_rm": handle_ipfs_pin_rm,
        "ipfs_pin_ls": handle_ipfs_pin_ls,
        "ipfs_files_mkdir": handle_ipfs_files_mkdir,
        "ipfs_files_write": handle_ipfs_files_write,
        "ipfs_files_read": handle_ipfs_files_read,
        "ipfs_files_ls": handle_ipfs_files_ls,
        "ipfs_files_rm": handle_ipfs_files_rm,
        "ipfs_files_stat": handle_ipfs_files_stat,
        "ipfs_files_cp": handle_ipfs_files_cp,
        "ipfs_files_mv": handle_ipfs_files_mv,
    })
    logger.info("Loaded IPFS tool handlers from ipfs_tool_adapters")
except ImportError as e:
    logger.error(f"Error importing ipfs_tool_adapters: {e}")
    # Create empty handlers
    async def not_implemented_handler(ctx):
        return {"error": "Tool implementation not available"}
    
    # Register empty handlers
    for tool_name in [
        "ipfs_add", "ipfs_cat",
        "ipfs_pin_add", "ipfs_pin_rm", "ipfs_pin_ls",
        "ipfs_files_mkdir", "ipfs_files_write", "ipfs_files_read",
        "ipfs_files_ls", "ipfs_files_rm", "ipfs_files_stat",
        "ipfs_files_cp", "ipfs_files_mv"
    ]:
        TOOL_HANDLERS[tool_name] = not_implemented_handler
    
    logger.warning("Using placeholder handlers for IPFS tools")

def register_all_ipfs_tools(mcp_server):
    \"\"\"Register all IPFS tools with the MCP server.\"\"\"
    logger.info("Registering IPFS tools directly...")
    
    registered_tools = []
    for tool_name, handler in TOOL_HANDLERS.items():
        try:
            mcp_server.register_tool(tool_name, handler)
            registered_tools.append(tool_name)
            logger.info(f"Registered tool: {tool_name}")
        except Exception as e:
            logger.error(f"Error registering tool {tool_name}: {e}")
    
    logger.info(f"Successfully registered {len(registered_tools)} IPFS tools")
    return registered_tools
"""
    
    # Write the script to a file
    filepath = "/home/barberb/ipfs_kit_py/direct_ipfs_tools.py"
    with open(filepath, 'w') as f:
        f.write(script_content)
    
    logger.info(f"Created direct IPFS tool registration script: {filepath}")
    
    # Create an integration script
    integration_script = """#!/usr/bin/env python3
\"\"\"
IPFS MCP Integration Fix

This script modifies final_mcp_server.py to use direct_ipfs_tools.py for tool registration.
\"\"\"

import os
import sys
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ipfs-mcp-integration-fix")

def update_final_mcp_server():
    \"\"\"Update final_mcp_server.py to use direct_ipfs_tools.py.\"\"\"
    filepath = "/home/barberb/ipfs_kit_py/final_mcp_server.py"
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Update the imports
        if "import direct_ipfs_tools" not in content:
            # Find the import section
            import_section = "# --- BEGIN MCP SERVER DIAGNOSTIC LOGGING ---"
            if import_section in content:
                new_import = "import direct_ipfs_tools  # Direct IPFS tool registration\\n"
                content = content.replace(import_section, new_import + import_section)
        
        # Update the register_ipfs_tools function
        register_pattern = r'def register_ipfs_tools\(server\):(.*?)(?=def|class|if __name__)'
        if re.search(register_pattern, content, re.DOTALL):
            old_register = re.search(register_pattern, content, re.DOTALL).group(0)
            new_register = \"\"\"def register_ipfs_tools(server):
    \"\"\"Register IPFS tools with the MCP server.\"\"\"
    logger.info("Registering IPFS tools...")
    
    try:
        # Try to use direct_ipfs_tools first
        direct_ipfs_tools.register_all_ipfs_tools(server)
        logger.info("✅ Registered IPFS tools using direct_ipfs_tools")
        return True
    except Exception as e:
        logger.error(f"❌ Error registering IPFS tools with direct_ipfs_tools: {e}")
        logger.info("Falling back to unified_ipfs_tools...")
        
        try:
            # Fall back to unified_ipfs_tools
            import unified_ipfs_tools
            unified_ipfs_tools.register_all_ipfs_tools(server)
            logger.info("✅ Registered IPFS tools using unified_ipfs_tools")
            return True
        except Exception as e:
            logger.error(f"❌ Error in unified_ipfs_tools: {e}")
            return False

"""
            content = content.replace(old_register, new_register)
        
        # Write the updated content back to the file
        with open(filepath, 'w') as f:
            f.write(content)
        
        logger.info(f"Updated {filepath} to use direct_ipfs_tools.py")
        return True
    except Exception as e:
        logger.error(f"Error updating {filepath}: {e}")
        return False

if __name__ == "__main__":
    logger.info("Applying IPFS MCP integration fix...")
    update_final_mcp_server()
    logger.info("Integration fix applied. Please restart the MCP server.")
"""
    
    # Write the integration script to a file
    integration_filepath = "/home/barberb/ipfs_kit_py/integrate_direct_ipfs_tools.py"
    with open(integration_filepath, 'w') as f:
        f.write(integration_script)
    
    logger.info(f"Created integration script: {integration_filepath}")
    return True

if __name__ == "__main__":
    logger.info("Creating direct IPFS tool registration...")
    if register_ipfs_tools_directly():
        logger.info("Direct IPFS tool registration created successfully.")
    else:
        logger.error("Failed to create direct IPFS tool registration.")
