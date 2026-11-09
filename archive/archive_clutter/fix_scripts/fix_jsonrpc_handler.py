#!/usr/bin/env python3
"""
Fix for JSON-RPC handler in the direct_mcp_server.py file.
This script modifies the JSON-RPC endpoint to work with the Tool class's run method.
"""

import os
import sys
import re
import logging
import shutil
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def backup_file(file_path):
    """Create a backup of the file."""
    backup_path = f"{file_path}.bak.jsonrpc"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup at {backup_path}")
    return backup_path

def fix_jsonrpc_handler():
    """Fix the JSON-RPC handler in direct_mcp_server.py."""
    direct_mcp_file = Path("direct_mcp_server.py")
    
    # Create a backup
    backup_file(direct_mcp_file)
    
    with open(direct_mcp_file, 'r') as f:
        content = f.read()
    
    # Pattern to find the use_tool endpoint where it calls tool.use(arguments)
    use_tool_pattern = re.compile(
        r'(async def use_tool\(.*?tool_name.*?arguments.*?\).*?\n.*?)(tool = tools.get\(tool_name\))(.*?)(?:await )?tool\.use\(arguments\)(.*?)(?=\n\s*@app\.)',
        re.DOTALL
    )
    
    if not use_tool_pattern.search(content):
        logger.error("Could not find the use_tool endpoint in the JSON-RPC handler.")
        return False
    
    # Replace 'tool.use(arguments)' with 'await tool.run(arguments)'
    modified_content = use_tool_pattern.sub(
        r'\1\2\3await tool.run(arguments)\4',
        content
    )
    
    # If no changes were made, try another pattern
    if modified_content == content:
        logger.warning("First replacement pattern didn't match, trying alternative...")
        
        # Try to find the section using a different pattern
        alt_pattern = re.compile(
            r'(async def use_tool\(.*?tool_name.*?arguments.*?\).*?\n.*?)(tool = .*?get\(tool_name\).*?)(?:return await |return |await )?tool\.use\((.*?)\)(.*?)(?=\n\s*@app\.|\n\s*@route|\n\s*async def)',
            re.DOTALL
        )
        
        modified_content = alt_pattern.sub(
            r'\1\2return await tool.run(\3)\4',
            content
        )
        
        if modified_content == content:
            logger.error("Could not find the tool.use() call in the JSON-RPC handler.")
            return False
    
    # Write the modified content
    with open(direct_mcp_file, 'w') as f:
        f.write(modified_content)
    
    logger.info("Successfully updated the JSON-RPC handler to use tool.run() instead of tool.use()")
    return True

def fix_get_tools_handler():
    """Fix the get_tools handler to properly handle schema serialization."""
    direct_mcp_file = Path("direct_mcp_server.py")
    
    # Ensure we have a backup
    if not os.path.exists(f"{direct_mcp_file}.bak.jsonrpc"):
        backup_file(direct_mcp_file)
    
    with open(direct_mcp_file, 'r') as f:
        content = f.read()
    
    # Find the get_tools method
    get_tools_pattern = re.compile(
        r'(async def get_tools\(\).*?)(return \[\{.*?schema.*?for tool in tools.values\(\)\])(.*?)(?=\n\s*@app\.|\n\s*async def)',
        re.DOTALL
    )
    
    get_tools_match = get_tools_pattern.search(content)
    if not get_tools_match:
        logger.warning("Could not find the get_tools handler for updating schema serialization.")
        return False
    
    # Replace with safer schema handling
    modified_content = get_tools_pattern.sub(
        r'\1tools_list = []\n'
        r'        for tool in tools.values():\n'
        r'            try:\n'
        r'                schema = tool.fn_metadata.arg_model.model_json_schema() if hasattr(tool, "fn_metadata") and hasattr(tool.fn_metadata, "arg_model") else {}\n'
        r'            except Exception as e:\n'
        r'                logger.error(f"Error getting schema for {tool.name}: {e}")\n'
        r'                schema = {"properties": {}}\n'
        r'            tools_list.append({\n'
        r'                "name": tool.name,\n'
        r'                "description": tool.description,\n'
        r'                "schema": schema\n'
        r'            })\n'
        r'        return tools_list\3',
        content
    )
    
    # If no changes were made, try another pattern
    if modified_content == content:
        logger.warning("First get_tools replacement pattern didn't match, trying alternative...")
        
        # Try with a more generic pattern
        alt_pattern = re.compile(
            r'(async def get_tools\(\).*?return )(\[.*?schema.*?for tool in.*?\])(.*?)(?=\n\s*@app\.|\n\s*async def|\n\s*def)',
            re.DOTALL
        )
        
        modified_content = alt_pattern.sub(
            r'\1[{"name": tool.name, "description": tool.description, "schema": getattr(tool, "parameters", {"properties": {}})} for tool in tools.values()]\3',
            content
        )
        
        if modified_content == content:
            logger.warning("Could not update the get_tools handler schema handling.")
            return False
    
    # Write the modified content
    with open(direct_mcp_file, 'w') as f:
        f.write(modified_content)
    
    logger.info("Successfully updated the get_tools handler with safer schema handling")
    return True

def main():
    """Main function."""
    logger.info("Fixing JSON-RPC handler to work with the MCP Tool class...")
    
    jsonrpc_fix_result = fix_jsonrpc_handler()
    get_tools_fix_result = fix_get_tools_handler()
    
    if jsonrpc_fix_result and get_tools_fix_result:
        logger.info("\n✅ JSON-RPC handler fixes applied successfully")
        logger.info("The server should now be able to use tools through JSON-RPC")
        logger.info("Restart the MCP server to apply the changes:")
        logger.info("  1. Stop the current server")
        logger.info("  2. Start the server again")
        return 0
    else:
        logger.error("Failed to fix the JSON-RPC handler")
        if jsonrpc_fix_result:
            logger.info("✅ Successfully fixed the use_tool handler")
        if get_tools_fix_result:
            logger.info("✅ Successfully fixed the get_tools handler")
        return 1

if __name__ == "__main__":
    sys.exit(main())
