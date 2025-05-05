#!/usr/bin/env python3
"""
Create Standalone VFS-Enabled MCP Server

This script creates a standalone MCP server with VFS capabilities by:
1. Creating a dedicated copy of the server code
2. Adding VFS tools integration
3. Setting up a different port to avoid conflicts with the existing server
4. Starting the server with VFS tools enabled
"""

import os
import sys
import shutil
import logging
import time
import re
import json
import signal
import subprocess
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("vfs_server_setup.log"),
    ],
)
logger = logging.getLogger("vfs-server-setup")

# Configuration
SOURCE_SERVER = "direct_mcp_server.py"
TARGET_SERVER = "vfs_mcp_server.py"
SERVER_PORT = 3030
SERVER_HOST = "0.0.0.0"
SERVER_LOG = "vfs_mcp_server.log"
SERVER_PID = "vfs_mcp_server.pid"
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

def stop_existing_server():
    """Stop any existing VFS MCP server"""
    logger.info("Checking for existing VFS MCP server...")
    
    # Check if PID file exists
    if os.path.exists(SERVER_PID):
        try:
            with open(SERVER_PID, "r") as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            try:
                os.kill(pid, 0)  # Check if process exists
                logger.info(f"Stopping existing server with PID {pid}")
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
                
                # Double check if process is still running
                try:
                    os.kill(pid, 0)
                    logger.warning(f"Process {pid} still running, sending SIGKILL")
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass  # Process is gone
            except OSError:
                logger.info(f"No process found with PID {pid}")
        except Exception as e:
            logger.error(f"Error stopping existing server: {e}")
    
    # Also check for any process using our file name
    try:
        output = subprocess.check_output(["pgrep", "-f", TARGET_SERVER], universal_newlines=True)
        pids = output.strip().split("\n")
        for pid in pids:
            if pid:
                try:
                    pid = int(pid)
                    logger.info(f"Stopping process {pid} running {TARGET_SERVER}")
                    os.kill(pid, signal.SIGTERM)
                except (ValueError, OSError) as e:
                    logger.error(f"Error stopping process {pid}: {e}")
    except subprocess.CalledProcessError:
        # No processes found, which is fine
        pass
    except Exception as e:
        logger.error(f"Error checking for existing processes: {e}")

def create_server_copy():
    """Create a copy of the MCP server file with VFS integration"""
    logger.info(f"Creating copy of {SOURCE_SERVER} as {TARGET_SERVER}")
    
    if not os.path.exists(SOURCE_SERVER):
        logger.error(f"Source server file {SOURCE_SERVER} not found")
        return False
    
    # Create backup first
    backup_file = f"{TARGET_SERVER}.bak"
    if os.path.exists(TARGET_SERVER):
        logger.info(f"Creating backup of existing target file as {backup_file}")
        shutil.copy2(TARGET_SERVER, backup_file)
    
    # Copy the server file
    shutil.copy2(SOURCE_SERVER, TARGET_SERVER)
    logger.info(f"Created copy of server file: {TARGET_SERVER}")
    return True

def add_vfs_integration():
    """Add VFS integration to the server copy"""
    logger.info("Adding VFS integration to server copy")
    
    try:
        # Read the server file
        with open(TARGET_SERVER, "r") as f:
            content = f.read()
        
        # Add import for mcp_vfs_config
        if "import mcp_vfs_config" not in content:
            # Look for a good spot to add the import
            import_section_end = content.find("# Configure logging")
            if import_section_end == -1:
                import_section_end = content.find("logging.basicConfig")
            
            if import_section_end != -1:
                # Add the import
                import_line = "import mcp_vfs_config  # VFS integration\n"
                content = content[:import_section_end] + import_line + content[import_section_end:]
                logger.info("Added import for mcp_vfs_config")
            else:
                logger.error("Could not find a good spot to add import")
                return False
        
        # Set the server port
        port_pattern = r"SERVER_PORT\s*=\s*\d+"
        if re.search(port_pattern, content):
            content = re.sub(port_pattern, f"SERVER_PORT = {SERVER_PORT}", content)
            logger.info(f"Updated SERVER_PORT to {SERVER_PORT}")
        else:
            # If SERVER_PORT is not defined, add it near the top
            header_end = content.find("import")
            if header_end != -1:
                port_line = f"\n# Server port\nSERVER_PORT = {SERVER_PORT}\n"
                content = content[:header_end] + port_line + content[header_end:]
                logger.info(f"Added SERVER_PORT = {SERVER_PORT}")
            else:
                logger.error("Could not find a good spot to add SERVER_PORT")
                return False
        
        # Find the register_all_tools function
        register_all_tools_pos = content.find("def register_all_tools(")
        if register_all_tools_pos == -1:
            logger.error("Could not find register_all_tools function")
            return False
        
        # Find the VFS registration section
        vfs_section_pos = content.find("# Register virtual filesystem tools", register_all_tools_pos)
        if vfs_section_pos == -1:
            logger.error("Could not find VFS registration section")
            return False
        
        # Find the end of the VFS section
        next_section_pos = content.find("#", vfs_section_pos + 1)
        if next_section_pos == -1:
            next_section_pos = content.find("def ", vfs_section_pos)
            if next_section_pos == -1:
                logger.error("Could not find end of VFS registration section")
                return False
        
        # Extract the VFS section
        vfs_section_end = content.rfind("}", vfs_section_pos, next_section_pos)
        if vfs_section_end == -1:
            vfs_section_end = content.rfind("except", vfs_section_pos, next_section_pos)
            if vfs_section_end == -1:
                logger.error("Could not find the end of the VFS section")
                return False
        
        # Find the actual end of the VFS try/except block
        vfs_block_end = content.find("\n\n", vfs_section_end)
        if vfs_block_end == -1:
            # If no double newline, find the next section
            vfs_block_end = next_section_pos
        
        # Replace the VFS section with our custom integration
        vfs_replacement = """    # Register virtual filesystem tools
    try:
        mcp_vfs_config.register_vfs_tools(mcp_server)
        logger.info("✅ Successfully registered virtual filesystem tools")
    except Exception as e:
        logger.error(f"Failed to register virtual filesystem tools: {e}")

"""
        content = content[:vfs_section_pos] + vfs_replacement + content[vfs_block_end:]
        logger.info("Updated VFS registration section to use mcp_vfs_config.register_vfs_tools")
        
        # Write back the modified content
        with open(TARGET_SERVER, "w") as f:
            f.write(content)
        
        logger.info(f"Successfully added VFS integration to {TARGET_SERVER}")
        return True
    except Exception as e:
        logger.error(f"Error adding VFS integration: {e}")
        logger.error(traceback.format_exc())
        return False

def start_server():
    """Start the VFS-enabled MCP server"""
    logger.info(f"Starting VFS-enabled MCP server on port {SERVER_PORT}")
    
    try:
        # Start the server
        cmd = [sys.executable, TARGET_SERVER]
        with open(SERVER_LOG, "w") as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=PROJECT_ROOT,
            )
        
        # Save the PID
        with open(SERVER_PID, "w") as f:
            f.write(str(process.pid))
        
        logger.info(f"Server started with PID {process.pid}")
        logger.info(f"Server log file: {SERVER_LOG}")
        
        # Wait for server to initialize
        logger.info("Waiting for server to initialize...")
        time.sleep(5)
        
        # Check if the process is still running
        if process.poll() is not None:
            logger.error(f"Server process exited with code {process.returncode}")
            logger.error("Last 20 lines of server log:")
            try:
                with open(SERVER_LOG, "r") as f:
                    lines = f.readlines()
                    for line in lines[-20:]:
                        logger.error(line.strip())
            except Exception as e:
                logger.error(f"Error reading server log: {e}")
            return False
        
        # Check if server is responding
        for attempt in range(10):
            try:
                import requests
                response = requests.get(f"http://localhost:{SERVER_PORT}/")
                if response.status_code == 200:
                    logger.info("Server is running and responding")
                    logger.info(f"Server info: {response.json()}")
                    return True
            except Exception:
                logger.info(f"Server not ready yet (attempt {attempt + 1}/10)")
                time.sleep(2)
        
        logger.error("Server not responding after multiple attempts")
        return False
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        logger.error(traceback.format_exc())
        return False

def update_vscode_settings():
    """Update VS Code settings to use the new MCP server"""
    logger.info("Updating VS Code settings")
    
    try:
        # Locate the VS Code settings file
        vscode_settings = Path.home() / ".vscode" / "settings.json"
        
        if not vscode_settings.exists():
            logger.warning(f"VS Code settings file not found at {vscode_settings}")
            return False
        
        # Read the current settings
        with open(vscode_settings, "r") as f:
            settings = json.load(f)
        
        # Create a backup
        backup_file = vscode_settings.with_suffix(".json.bak")
        with open(backup_file, "w") as f:
            json.dump(settings, f, indent=2)
        
        # Update the MCP server URL
        settings["claude-dev.mcp.serverUrl"] = f"http://localhost:{SERVER_PORT}"
        
        # Write the updated settings
        with open(vscode_settings, "w") as f:
            json.dump(settings, f, indent=2)
        
        logger.info(f"Updated VS Code settings to use MCP server at http://localhost:{SERVER_PORT}")
        return True
    except Exception as e:
        logger.error(f"Error updating VS Code settings: {e}")
        logger.error(traceback.format_exc())
        return False

def verify_vfs_tools():
    """Verify that the VFS tools are registered with the server"""
    logger.info("Verifying VFS tools registration")
    
    try:
        import requests
        
        # Get the list of registered tools
        response = requests.post(
            f"http://localhost:{SERVER_PORT}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "get_tools",
                "params": {}
            },
            timeout=5
        )
        
        if response.status_code != 200:
            logger.error(f"Error accessing MCP server: HTTP {response.status_code}")
            return False
        
        data = response.json()
        if "result" not in data:
            logger.error(f"Invalid response from server: {data}")
            return False
        
        tools = data["result"]
        logger.info(f"Found {len(tools)} registered tools")
        
        # Look for VFS tools
        vfs_prefixes = ["vfs_", "fs_", "virtual_", "filesystem_", "ipfs_fs_"]
        vfs_tools = [tool for tool in tools if any(tool["name"].startswith(prefix) for prefix in vfs_prefixes)]
        
        if not vfs_tools:
            logger.error("No VFS tools found")
            return False
        
        logger.info(f"Found {len(vfs_tools)} VFS tools:")
        for tool in vfs_tools:
            logger.info(f"  - {tool['name']}: {tool['description']}")
        
        # Test a VFS tool (vfs_write_file)
        logger.info("Testing VFS tool vfs_write_file")
        test_file = f"vfs_test_{int(time.time())}.txt"
        test_content = f"This is a test file created by the VFS integration test at {time.ctime()}"
        
        response = requests.post(
            f"http://localhost:{SERVER_PORT}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "execute_tool",
                "params": {
                    "name": "vfs_write_file",
                    "arguments": {
                        "path": test_file,
                        "content": test_content
                    }
                }
            },
            timeout=5
        )
        
        if response.status_code != 200:
            logger.error(f"Error executing VFS tool: HTTP {response.status_code}")
            return False
        
        data = response.json()
        if "result" not in data or not data["result"].get("success"):
            logger.error(f"VFS tool execution failed: {data}")
            return False
        
        logger.info(f"Successfully created test file: {test_file}")
        
        # Check if the file exists on disk
        if not os.path.exists(test_file):
            logger.error(f"Test file {test_file} not found on disk")
            return False
        
        with open(test_file, "r") as f:
            content = f.read()
        
        if content != test_content:
            logger.error(f"Test file content does not match: {content}")
            return False
        
        logger.info("VFS tool test passed!")
        return True
    except Exception as e:
        logger.error(f"Error verifying VFS tools: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function"""
    logger.info("🚀 Setting up standalone VFS-enabled MCP server")
    
    # Stop any existing VFS server
    stop_existing_server()
    
    # Create a copy of the server
    if not create_server_copy():
        logger.error("Failed to create server copy")
        return False
    
    # Add VFS integration
    if not add_vfs_integration():
        logger.error("Failed to add VFS integration")
        return False
    
    # Start the server
    if not start_server():
        logger.error("Failed to start server")
        return False
    
    # Update VS Code settings
    update_vscode_settings()
    
    # Verify VFS tools
    if not verify_vfs_tools():
        logger.error("❌ VFS tools verification failed")
        logger.error("Please check the server log for details")
        return False
    
    logger.info("✅ VFS-enabled MCP server is running successfully!")
    logger.info(f"Server URL: http://localhost:{SERVER_PORT}")
    logger.info(f"Server PID: {open(SERVER_PID, 'r').read().strip()}")
    logger.info(f"Server log: {SERVER_LOG}")
    
    logger.info("")
    logger.info("⚠️  To stop the server, run:")
    logger.info(f"kill $(cat {SERVER_PID})")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
