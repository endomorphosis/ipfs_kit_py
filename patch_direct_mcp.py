#!/usr/bin/env python3
"""
Patch Direct MCP Server with IPFS Tools

This script patches the direct_mcp_server.py file to include the IPFS tools
from mcp_registered_tools.json.
"""

import os
import sys
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def load_tools():
    """Load tools from the JSON file"""
    try:
        if not os.path.exists("mcp_registered_tools.json"):
            logger.error("mcp_registered_tools.json not found")
            return None
        
        with open("mcp_registered_tools.json", "r") as f:
            tools = json.load(f)
        
        logger.info(f"Loaded {len(tools)} tools from JSON file")
        return tools
    
    except Exception as e:
        logger.error(f"Error loading tools from JSON: {e}")
        return None

def create_patched_mcp_server():
    """Create a patched version of direct_mcp_server.py with the tools"""
    try:
        # Check if the original server file exists
        if not os.path.exists("direct_mcp_server.py"):
            logger.error("direct_mcp_server.py not found")
            return False
        
        # Load tools
        tools = load_tools()
        if not tools:
            return False
        
        # Read the original server file content
        with open("direct_mcp_server.py", "r") as f:
            server_content = f.read()
        
        # Create the patched server file
        with open("direct_mcp_server_with_tools.py", "w") as f:
            # Look for the tools section
            if "tools = [" in server_content:
                # If tools section exists, replace it
                lines = server_content.split("\n")
                tools_start_index = None
                tools_end_index = None
                
                # Find the start and end of the tools section
                for i, line in enumerate(lines):
                    if line.strip().startswith("tools = ["):
                        tools_start_index = i
                    elif tools_start_index is not None and line.strip() == "]":
                        tools_end_index = i
                        break
                
                if tools_start_index is not None and tools_end_index is not None:
                    # Replace the existing tools section
                    new_content = lines[:tools_start_index]
                    new_content.append("# Enhanced IPFS tools registered")
                    new_content.append("tools = " + json.dumps(tools, indent=4))
                    new_content.extend(lines[tools_end_index+1:])
                    
                    f.write("\n".join(new_content))
                    logger.info("✅ Replaced existing tools section in server file")
                else:
                    # Could not find the end of tools section, append tools
                    f.write(server_content)
                    f.write("\n\n# Enhanced IPFS tools\n")
                    f.write("tools = " + json.dumps(tools, indent=4))
                    logger.info("✅ Appended tools to server file (could not find end of existing tools section)")
            else:
                # No tools section found, append tools
                f.write(server_content)
                f.write("\n\n# Enhanced IPFS tools\n")
                f.write("tools = " + json.dumps(tools, indent=4))
                logger.info("✅ Appended tools to server file (no existing tools section)")
        
        logger.info(f"✅ Created patched MCP server file at direct_mcp_server_with_tools.py")
        return True
    
    except Exception as e:
        logger.error(f"Error creating patched MCP server: {e}")
        return False

def create_restart_script():
    """Create a script to restart the MCP server with the new tools"""
    try:
        with open("restart_mcp_with_tools.sh", "w") as f:
            f.write("""#!/bin/bash
# Restart MCP server with the enhanced IPFS tools

echo "Stopping any running MCP servers..."
pkill -f "python.*direct_mcp_server" || true
sleep 2

echo "Starting MCP server with enhanced tools..."
python direct_mcp_server_with_tools.py &
SERVER_PID=$!
echo "MCP server started with PID $SERVER_PID"
echo "Waiting for server to initialize..."
sleep 3

echo "✅ MCP server is now running with enhanced IPFS tools"
echo "You can use the new tools through the JSON-RPC interface"
echo "To test, try using a tool with the MCP interface"
""")
        
        # Make the script executable
        os.chmod("restart_mcp_with_tools.sh", 0o755)
        
        logger.info(f"✅ Created restart script at restart_mcp_with_tools.sh")
        return True
    
    except Exception as e:
        logger.error(f"Error creating restart script: {e}")
        return False

def main():
    """Main function"""
    logger.info("Starting to patch direct MCP server with IPFS tools...")
    
    # Create patched server
    if not create_patched_mcp_server():
        logger.error("❌ Failed to create patched MCP server")
        return 1
    
    # Create restart script
    if not create_restart_script():
        logger.error("❌ Failed to create restart script")
        return 1
    
    logger.info("\n✅ Successfully patched direct MCP server with IPFS tools")
    logger.info("To start the enhanced MCP server:")
    logger.info("  1. Run './restart_mcp_with_tools.sh'")
    logger.info("  2. The MCP server will now have access to all the enhanced IPFS tools")
    logger.info("  3. Test the tools through the MCP JSON-RPC interface")
    return 0

if __name__ == "__main__":
    sys.exit(main())
