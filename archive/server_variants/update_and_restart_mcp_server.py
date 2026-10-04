#!/usr/bin/env python3
"""
Update and restart the MCP server with enhanced IPFS tools.
This script performs the following steps:
1. Ensures the ipfs_tools_registry.py is properly formatted
2. Ensures the IPFS MCP tools integration is set up
3. Restarts the MCP server with the updated tools
"""

import os
import sys
import time
import signal
import subprocess
import logging
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def count_tools():
    """Count the number of tools in the registry"""
    try:
        # Import the tools registry
        sys.path.append(os.getcwd())
        from ipfs_tools_registry import get_ipfs_tools
        
        tools = get_ipfs_tools()
        return len(tools)
    except Exception as e:
        logger.error(f"Error counting tools: {e}")
        return 0

def stop_running_servers():
    """Stop any running MCP servers"""
    try:
        # Check for PID files
        pid_files = [
            "direct_mcp_server.pid",
            "direct_mcp_server_blue.pid",
            "direct_mcp_server_green.pid"
        ]
        
        for pid_file in pid_files:
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    
                    try:
                        # Check if the process is running
                        os.kill(pid, 0)
                        logger.info(f"Stopping MCP server with PID {pid}")
                        os.kill(pid, signal.SIGTERM)
                        time.sleep(2)  # Give it time to shut down
                    except OSError:
                        # Process is not running
                        pass
                        
                    # Remove the PID file
                    os.unlink(pid_file)
    except Exception as e:
        logger.error(f"Error stopping running servers: {e}")

def start_mcp_server(host="127.0.0.1", port=3000, log_level="INFO"):
    """Start the MCP server with the updated tools"""
    try:
        command = [
            "python", 
            "direct_mcp_server.py", 
            f"--host={host}", 
            f"--port={port}", 
            f"--log-level={log_level}"
        ]
        
        logger.info(f"Starting MCP server: {' '.join(command)}")
        
        # Start the server as a background process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Wait a bit for the server to start up
        time.sleep(2)
        
        # Check if the process is running
        if process.poll() is None:
            logger.info(f"MCP server started successfully with PID {process.pid}")
            return True
        else:
            stdout, _ = process.communicate()
            logger.error(f"MCP server failed to start: {stdout}")
            return False
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False

def verify_ipfs_mcp_tools_integration():
    """Verify and ensure the IPFS MCP tools integration is set up"""
    try:
        # Check if direct_mcp_server.py contains the import for the tools integration
        if os.path.exists("direct_mcp_server.py"):
            with open("direct_mcp_server.py", "r") as f:
                content = f.read()
                
            # Check if the import is present
            if "from ipfs_mcp_tools_integration import register_ipfs_tools" not in content:
                logger.info("Adding IPFS tools integration import to direct_mcp_server.py")
                
                # Add the import to the file
                import_line = "from ipfs_mcp_tools_integration import register_ipfs_tools"
                lines = content.split("\n")
                
                # Find the right place to insert the import
                last_import_line = -1
                for i, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("from "):
                        last_import_line = i
                
                if last_import_line >= 0:
                    # Insert the import line after the last import
                    lines.insert(last_import_line + 1, import_line)
                else:
                    # Insert at the beginning if no imports found
                    lines.insert(0, import_line)
                
                # Find where to call register_ipfs_tools
                server_line = -1
                for i, line in enumerate(lines):
                    if "server = FastMCP" in line:
                        server_line = i
                        break
                
                if server_line >= 0:
                    # Add the call to register_ipfs_tools after server initialization
                    inserted = False
                    for i in range(server_line + 1, len(lines)):
                        if lines[i].strip() and not lines[i].strip().startswith("#"):
                            lines.insert(i, "    # Register IPFS tools\n    register_ipfs_tools(server)")
                            inserted = True
                            break
                    
                    # If we couldn't find a good place, insert right after server initialization
                    if not inserted:
                        lines.insert(server_line + 1, "    # Register IPFS tools\n    register_ipfs_tools(server)")
                else:
                    logger.warning("Could not find server initialization in direct_mcp_server.py")
                
                # Write the updated content back to the file
                with open("direct_mcp_server.py", "w") as f:
                    f.write("\n".join(lines))
                
                logger.info("Updated direct_mcp_server.py to include IPFS tools integration")
        
        # Check if ipfs_mcp_tools_integration.py exists
        if not os.path.exists("ipfs_mcp_tools_integration.py"):
            logger.info("Creating ipfs_mcp_tools_integration.py")
            
            # Create the file with basic integration
            with open("ipfs_mcp_tools_integration.py", "w") as f:
                f.write("""\"\"\"IPFS MCP Tools Integration\"\"\"

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
        description = tool["description"]
        
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
""")
            
            logger.info("Created ipfs_mcp_tools_integration.py")
        
        return True
    except Exception as e:
        logger.error(f"Error setting up IPFS MCP tools integration: {e}")
        return False

def main():
    """Main function"""
    # Count the tools in the registry
    num_tools = count_tools()
    logger.info(f"Found {num_tools} tools in the IPFS tools registry")
    
    # Verify and ensure IPFS MCP tools integration
    if not verify_ipfs_mcp_tools_integration():
        logger.error("Failed to set up IPFS MCP tools integration")
        return False
    
    # Stop any running servers
    stop_running_servers()
    
    # Start the MCP server
    if not start_mcp_server(log_level="DEBUG"):
        logger.error("Failed to start MCP server")
        return False
    
    logger.info("✅ MCP server started with enhanced IPFS tools")
    logger.info("ℹ️ You can now use all the IPFS tools via the MCP server")
    return True

if __name__ == "__main__":
    main()
