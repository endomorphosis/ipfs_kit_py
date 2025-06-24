#!/usr/bin/env python3
"""
Directly modify direct_mcp_server.py to add IPFS tools registration
"""

import os
import re
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MCP_SERVER_PATH = "direct_mcp_server.py"

def add_ipfs_tools_to_mcp():
    """Directly modify the direct_mcp_server.py file to add IPFS tools"""
    if not os.path.exists(MCP_SERVER_PATH):
        logger.error(f"❌ File not found: {MCP_SERVER_PATH}")
        return False

    try:
        # Read the file
        with open(MCP_SERVER_PATH, 'r') as f:
            content = f.read()

        # Add the import statement
        import_line = "from ipfs_mcp_tools_integration import register_ipfs_tools"
        if import_line not in content:
            # Find the last import statement
            import_pattern = r"^(?:import\s+.*|from\s+.*\s+import\s+.*)$"
            matches = list(re.finditer(import_pattern, content, re.MULTILINE))

            if matches:
                last_import = matches[-1]
                pos = last_import.end()
                content = content[:pos] + "\n" + import_line + content[pos:]
                logger.info("✅ Added import statement for IPFS tools integration")
            else:
                logger.error("❌ Could not find a suitable location to add import")
                return False

        # Add the tools registration call
        register_call = "register_ipfs_tools(server)"
        if register_call not in content:
            # Find where the FastMCP server is created
            server_pattern = r"(server\s*=\s*FastMCP\([^)]*\))"
            server_match = re.search(server_pattern, content)

            if server_match:
                # Insert after the server creation
                pos = server_match.end()
                # Add a newline and indentation
                content = content[:pos] + "\n\n# Register IPFS tools\n" + register_call + content[pos:]
                logger.info("✅ Added call to register IPFS tools")
            else:
                # Try a different approach - find where the server variable is first used
                server_use_pattern = r"(?<=\n)(\s*server\.)"
                server_use_match = re.search(server_use_pattern, content)

                if server_use_match:
                    # Insert before the first use of server
                    indentation = server_use_match.group(1).replace("server.", "")
                    pos = server_use_match.start()
                    content = content[:pos] + "\n" + indentation + "# Register IPFS tools\n" + indentation + register_call + "\n" + content[pos:]
                    logger.info("✅ Added call to register IPFS tools")
                else:
                    logger.error("❌ Could not find a suitable location to add register call")
                    return False

        # Write the updated content back to the file
        with open(MCP_SERVER_PATH, 'w') as f:
            f.write(content)

        logger.info(f"✅ Successfully modified {MCP_SERVER_PATH} to add IPFS tools")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating MCP server file: {e}")
        return False

if __name__ == "__main__":
    add_ipfs_tools_to_mcp()
