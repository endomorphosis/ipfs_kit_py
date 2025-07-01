#!/usr/bin/env python3
"""
Script to ensure the MCP server exposes the register_tool endpoint.
Run this script to verify and fix the server's registration capabilities.
"""

import os
import sys
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("fix-server-registration")

def read_file(path):
    """Read a file and return its contents."""
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    """Write content to a file."""
    with open(path, "w") as f:
        f.write(content)

def backup_file(path):
    """Create a backup of a file."""
    backup_path = f"{path}.bak.{int(Path(path).stat().st_mtime)}"
    logger.info(f"Creating backup at {backup_path}")
    with open(path, "r") as src:
        with open(backup_path, "w") as dst:
            dst.write(src.read())

def check_server_exposes_register_tool():
    """Check if the server exposes the register_tool endpoint."""
    server_file = "direct_mcp_server.py"
    if not os.path.exists(server_file):
        logger.error(f"Server file {server_file} not found")
        return False
    
    content = read_file(server_file)
    
    # Check for register_tool in the exposed methods
    if "register_tool" in content and "jsonrpc_methods" in content:
        # Look for the pattern where register_tool is added to jsonrpc_methods
        if re.search(r"jsonrpc_methods\s*=\s*\{[^}]*['\"]register_tool['\"]", content, re.DOTALL):
            logger.info("Server already exposes register_tool endpoint")
            return True
        else:
            logger.warning("Server doesn't expose register_tool endpoint")
            return False
    else:
        logger.warning("Couldn't determine if server exposes register_tool endpoint")
        return False

def fix_server_registration():
    """Fix the server to expose the register_tool endpoint."""
    server_file = "direct_mcp_server.py"
    if not os.path.exists(server_file):
        logger.error(f"Server file {server_file} not found")
        return False
    
    # Backup the file before making changes
    backup_file(server_file)
    
    content = read_file(server_file)
    
    # Look for the jsonrpc_methods definition
    methods_pattern = r'jsonrpc_methods\s*=\s*\{([^}]*)\}'
    match = re.search(methods_pattern, content, re.DOTALL)
    
    if not match:
        logger.error("Couldn't find jsonrpc_methods definition in the server file")
        return False
    
    # Check if register_tool is already in the methods
    methods_text = match.group(1)
    if "'register_tool':" in methods_text or '"register_tool":' in methods_text:
        logger.info("register_tool is already exposed")
        return True
    
    # Add register_tool to the methods
    new_methods = methods_text + ',\n        "register_tool": self.register_tool'
    updated_content = content.replace(methods_text, new_methods)
    
    # Also ensure the register_tool method exists
    if "def register_tool" not in content:
        # Find a good place to add the method, preferably with other API methods
        api_methods_end = content.find("# --- Server lifecycle methods ---")
        if api_methods_end == -1:
            # Try another pattern
            api_methods_end = content.rfind("def ")
            if api_methods_end != -1:
                # Find the end of this method
                next_def = content.find("def ", api_methods_end + 4)
                if next_def != -1:
                    api_methods_end = next_def
                else:
                    api_methods_end = len(content) - 1
        
        if api_methods_end == -1:
            logger.error("Couldn't find a good place to add the register_tool method")
            return False
        
        # Add the register_tool method
        register_tool_method = """
    async def register_tool(self, name: str, description: str, parameters: dict, function: str):
        # Register a custom tool with the server
        try:
            logger.info(f"Registering tool: {name}")
            # Validate parameters
            if not isinstance(name, str) or not name:
                return {"error": "Tool name must be a non-empty string"}
            
            if not isinstance(description, str):
                return {"error": "Tool description must be a string"}
                
            if not isinstance(parameters, dict):
                return {"error": "Tool parameters must be a dictionary"}
                
            if not isinstance(function, str) or not function:
                return {"error": "Tool function must be a non-empty string"}
            
            # Add the tool to the server
            await self.mcp_server.register_tool(
                name=name,
                description=description,
                parameters=parameters,
                function_str=function
            )
            
            logger.info(f"Successfully registered tool: {name}")
            return {"success": True}
        except Exception as e:
            logger.error(f"Error registering tool {name}: {str(e)}")
            return {"error": str(e)}
"""
        
        updated_content = updated_content[:api_methods_end] + register_tool_method + updated_content[api_methods_end:]
    
    # Write the updated content back to the file
    write_file(server_file, updated_content)
    logger.info(f"Updated {server_file} to expose register_tool endpoint")
    
    return True

def main():
    """Main function."""
    logger.info("=== Fixing MCP Server Registration ===")
    
    if check_server_exposes_register_tool():
        logger.info("Server already exposes register_tool endpoint, no changes needed")
        return True
    
    logger.info("Attempting to fix server registration...")
    if fix_server_registration():
        logger.info("Successfully fixed server registration")
        return True
    else:
        logger.error("Failed to fix server registration")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
