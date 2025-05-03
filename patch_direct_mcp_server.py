#!/usr/bin/env python3
"""Patch for direct_mcp_server.py to add IPFS tools"""

import os
import sys
import re
import logging

logger = logging.getLogger(__name__)

def patch_direct_mcp_server(file_path="direct_mcp_server.py"):
    """Patch the direct_mcp_server.py file to add IPFS tools"""
    try:
        if not os.path.exists(file_path):
            logger.error(f"❌ File not found: {file_path}")
            return False
        
        with open(file_path, "r") as f:
            content = f.read()
        
        # Add the import statement if not already present
        import_line = "from ipfs_mcp_tools_integration import register_ipfs_tools"
        if import_line not in content:
            # Find the last import statement
            import_pattern = r"(^import .*$|^from .* import .*$)"
            matches = re.finditer(import_pattern, content, re.MULTILINE)
            last_import = None
            for match in matches:
                last_import = match
            
            if last_import:
                # Insert after the last import
                pos = last_import.end()
                content = content[:pos] + "\n" + import_line + content[pos:]
                logger.info("✅ Added import statement for IPFS tools integration")
            else:
                logger.error("❌ Could not find a suitable location to add import")
                return False
        
        # Add call to register_ipfs_tools if not already present
        register_call = "register_ipfs_tools(fastmcp)"
        if register_call not in content:
            # Find where the FastMCP is created and tools are registered
            app_pattern = r"(app\s*=\s*fastmcp\.get_app\(\))"
            app_match = re.search(app_pattern, content)
            
            if app_match:
                # Insert before the app is created
                pos = app_match.start()
                content = content[:pos] + "    # Register IPFS tools\n    " + register_call + "\n\n    " + content[pos:]
                logger.info("✅ Added call to register IPFS tools")
            else:
                logger.error("❌ Could not find a suitable location to add register call")
                return False
        
        # Write the updated content back to the file
        with open(file_path, "w") as f:
            f.write(content)
        
        logger.info(f"✅ Successfully patched {file_path} to add IPFS tools")
        return True
    except Exception as e:
        logger.error(f"❌ Error patching direct_mcp_server.py: {e}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_path = sys.argv[1] if len(sys.argv) > 1 else "direct_mcp_server.py"
    patch_direct_mcp_server(file_path)
