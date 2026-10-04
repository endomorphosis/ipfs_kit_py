#!/usr/bin/env python3
"""
Fix the registration order in direct_mcp_server.py
"""

import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_mcp_server():
    """Fix the MCP server file to add IPFS tools in the correct order"""
    # Read the current file
    with open("direct_mcp_server.py", "r") as f:
        content = f.read()
    
    # Add import if not already present
    if "from ipfs_mcp_tools_integration import register_ipfs_tools" not in content:
        # Find a good spot to add the import (after other imports)
        import_match = re.search(r'(^from .* import .*$)', content, re.MULTILINE)
        if import_match:
            last_import_pos = content.rindex(import_match.group(0)) + len(import_match.group(0))
            content = (content[:last_import_pos] + 
                      "\nfrom ipfs_mcp_tools_integration import register_ipfs_tools" + 
                      content[last_import_pos:])
            logger.info("✅ Added import statement")
    
    # Remove any incorrect registration calls
    content = re.sub(r'# Register IPFS tools\s*\nregister_ipfs_tools\(\s*server\s*\)', '', content)
    
    # Find the server initialization
    server_match = re.search(r'server\s*=\s*FastMCP\([^)]*\)', content)
    if not server_match:
        logger.error("❌ Could not find server initialization")
        return False
    
    server_init_end = server_match.end()
    
    # Add the registration call after server initialization
    registration_code = "\n\n# Register IPFS tools\nregister_ipfs_tools(server)"
    content = content[:server_init_end] + registration_code + content[server_init_end:]
    
    # Write the modified content back
    with open("direct_mcp_server.py", "w") as f:
        f.write(content)
    
    logger.info("✅ Successfully fixed registration call order")
    return True

if __name__ == "__main__":
    fix_mcp_server()
