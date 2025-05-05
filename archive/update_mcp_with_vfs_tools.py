#!/usr/bin/env python3
"""
Update MCP Server with Virtual Filesystem Tools

This script integrates all VFS functionality into the running MCP server.
It handles loading and registering the various components including:
- Filesystem journal tools
- IPFS-FS bridge
- Multi-backend storage
- Virtual filesystem operations
"""

import os
import sys
import json
import time
import logging
import requests
import importlib.util
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MCP server URL
MCP_SERVER_URL = "http://localhost:3000"

def check_server_status():
    """Check if the MCP server is running"""
    try:
        response = requests.get(f"{MCP_SERVER_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"MCP server is running: {data.get('message')}")
            logger.info(f"Uptime: {data.get('uptime_seconds')} seconds")
            logger.info(f"Registered tools: {data.get('registered_tools_count', 0)}")
            return True
        else:
            logger.error(f"Error accessing MCP server: HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to MCP server. Is it running?")
        return False
    except Exception as e:
        logger.error(f"Error checking server status: {e}")
        return False

def load_module(module_name, fail_silently=True):
    """
    Load a module dynamically

    Args:
        module_name: Name of the module to load
        fail_silently: If True, return None on error instead of raising an exception

    Returns:
        The loaded module or None if it couldn't be loaded and fail_silently is True
    """
    try:
        # Try to import the module
        if module_name in sys.modules:
            return sys.modules[module_name]

        spec = importlib.util.find_spec(module_name)
        if spec is None:
            logger.warning(f"Module not found: {module_name}")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module not found: {module_name}")

        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        else:
            logger.warning(f"Module {module_name} found but couldn't be loaded (no spec.loader)")
            if fail_silently:
                return None
            else:
                raise ImportError(f"Module {module_name} found but couldn't be loaded")
    except Exception as e:
        logger.error(f"Error loading module {module_name}: {e}")
        if fail_silently:
            return None
        else:
            raise

def restart_server_with_vfs():
    """Restart the MCP server with VFS tools enabled"""
    # First check if the server is running
    if not check_server_status():
        logger.error("Cannot proceed: MCP server is not running")
        return False
    
    # Create or modify the server's configuration to include VFS tools
    try:
        # Inject the VFS integration code directly into direct_mcp_server.py
        with open('direct_mcp_server.py', 'r') as f:
            server_code = f.read()
        
        # Check if VFS integration is already included
        if "register_all_fs_tools" in server_code:
            logger.info("VFS integration already present in server code")
        else:
            # Backup the original file
            backup_path = 'direct_mcp_server.py.bak.vfs'
            with open(backup_path, 'w') as f:
                f.write(server_code)
            logger.info(f"Backed up original server code to {backup_path}")
            
            # Modify the server code to import and register VFS tools
            if "def register_all_tools(server):" in server_code:
                # Find the register_all_tools function
                import_line = "import integrate_vfs_to_final_mcp"
                
                # Add the import at the top if not already there
                if import_line not in server_code:
                    imports_end = server_code.find("# Configure logging")
                    if imports_end == -1:
                        imports_end = server_code.find("logging.basicConfig")
                    
                    server_code = server_code[:imports_end] + import_line + "\n" + server_code[imports_end:]
                
                # Add VFS tool registration inside the register_all_tools function
                register_func_pos = server_code.find("def register_all_tools(server):")
                register_func_body_pos = server_code.find("    ", register_func_pos)
                register_vfs_code = """    # Register VFS tools
    try:
        integrate_vfs_to_final_mcp.register_all_fs_tools(server)
        logger.info("✅ VFS tools registered successfully")
    except Exception as e:
        logger.error(f"❌ Error registering VFS tools: {e}")
        logger.error(traceback.format_exc())
    
"""
                server_code = server_code[:register_func_body_pos] + register_vfs_code + server_code[register_func_body_pos:]
                
                # Write the modified code back
                with open('direct_mcp_server.py', 'w') as f:
                    f.write(server_code)
                
                logger.info("✅ Updated server code with VFS integration")
            else:
                logger.error("Could not find the register_all_tools function in server code")
                return False
            
            # Restart the server
            logger.info("Restarting MCP server...")
            # Here we should restart the server, but we'll leave that to an external script
            # to avoid killing the current process
            
            return True
    except Exception as e:
        logger.error(f"Error updating server with VFS tools: {e}")
        logger.error(traceback.format_exc())
        return False

def direct_register_tools():
    """Directly register VFS tools with the running MCP server via its API"""
    # First check if the server is running
    if not check_server_status():
        logger.error("Cannot proceed: MCP server is not running")
        return False
    
    # Create a script to dynamically register tools
    try:
        # Try to import the server bridge module
        server_bridge = load_module("ipfs_kit_py.mcp.server_bridge")
        if not server_bridge:
            logger.error("Could not load server bridge module")
            return False
        
        # Create a server client
        client = server_bridge.ServerBridge(MCP_SERVER_URL)
        
        # Import and register VFS tools
        modules_to_register = [
            "fs_journal_tools",
            "ipfs_mcp_fs_integration",
            "multi_backend_fs_integration",
            "unified_ipfs_tools",
            "ipfs_mcp_tools_integration"
        ]
        
        registered_count = 0
        
        # Try registering from the main integration module first
        vfs_integration = load_module("integrate_vfs_to_final_mcp")
        if vfs_integration and hasattr(vfs_integration, "register_all_fs_tools"):
            try:
                logger.info("Registering VFS tools from integrate_vfs_to_final_mcp...")
                result = vfs_integration.register_all_fs_tools(client)
                if result:
                    logger.info("✅ Successfully registered VFS tools from main integration module")
                    return True
                else:
                    logger.warning("⚠️ Failed to register VFS tools from main integration module")
            except Exception as e:
                logger.error(f"Error registering VFS tools from main integration module: {e}")
                logger.error(traceback.format_exc())
        else:
            logger.warning("Main VFS integration module not available, trying individual modules...")
        
        # Try individual modules
        for module_name in modules_to_register:
            module = load_module(module_name)
            if not module:
                logger.warning(f"Module {module_name} not found, skipping")
                continue
            
            # Check for the appropriate registration function
            registration_funcs = [
                "register_tools",
                "register_integration_tools",
                "register_all_ipfs_tools",
                "register_ipfs_tools",
                "register_all_fs_tools"
            ]
            
            registered = False
            for func_name in registration_funcs:
                if hasattr(module, func_name):
                    try:
                        logger.info(f"Registering tools from {module_name} using {func_name}...")
                        result = getattr(module, func_name)(client)
                        if result:
                            logger.info(f"✅ Successfully registered tools from {module_name}")
                            registered_count += 1
                            registered = True
                            break
                        else:
                            logger.warning(f"⚠️ Failed to register tools from {module_name}")
                    except Exception as e:
                        logger.error(f"Error registering tools from {module_name}: {e}")
                        logger.error(traceback.format_exc())
            
            if not registered:
                logger.warning(f"No registration function found in {module_name}")
        
        # Report results
        if registered_count > 0:
            logger.info(f"✅ Successfully registered tools from {registered_count} modules")
            return True
        else:
            logger.error("❌ Failed to register any VFS tools")
            return False
        
    except Exception as e:
        logger.error(f"Error directly registering VFS tools: {e}")
        logger.error(traceback.format_exc())
        return False

def verify_tool_registration():
    """Verify that VFS tools were registered with the MCP server"""
    try:
        # Call the JSON-RPC endpoint to get the list of tools
        response = requests.post(
            f"{MCP_SERVER_URL}/jsonrpc",
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
        
        # Extract tool names
        tools = data["result"]
        tool_names = [tool["name"] for tool in tools]
        
        # Check for VFS-related tools
        vfs_tools = [name for name in tool_names if any(x in name for x in ["vfs_", "fs_", "virtual_", "filesystem_"])]
        
        if not vfs_tools:
            logger.warning("No virtual filesystem tools found")
            return False
        
        logger.info(f"✅ Found {len(vfs_tools)} virtual filesystem tools:")
        for tool in vfs_tools:
            logger.info(f"  - {tool}")
        
        return True
        
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to MCP server. Is it running?")
        return False
    except Exception as e:
        logger.error(f"Error verifying tool registration: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function"""
    logger.info("🚀 Starting VFS integration with MCP server")
    
    # Check if the server is running
    if not check_server_status():
        logger.error("Cannot proceed: MCP server is not running")
        sys.exit(1)
    
    # Try to directly register tools first (without server restart)
    logger.info("Attempting direct registration of VFS tools...")
    if direct_register_tools():
        logger.info("⭐ Direct registration successful, verifying...")
        if verify_tool_registration():
            logger.info("✅ VFS tools successfully registered and verified!")
            sys.exit(0)
        else:
            logger.warning("⚠️ Direct registration appeared successful but tools not verified")
    else:
        logger.warning("⚠️ Direct registration failed")
    
    # If direct registration failed or verification failed, try updating server code
    logger.info("Attempting to update server code for VFS integration...")
    if restart_server_with_vfs():
        logger.info("✅ Server code updated. Please restart the MCP server to apply changes.")
        logger.info("   You can use the restart_mcp_with_vfs.sh script for this purpose.")
        
        # Create restart script
        with open("restart_mcp_with_vfs.sh", "w") as f:
            f.write("""#!/bin/bash
echo "🚀 Restarting MCP server with VFS tools..."

# Kill existing MCP server processes
echo "Stopping existing MCP server processes..."
pkill -f "python.*direct_mcp_server.py" || true
sleep 2

# Start the server in the background
echo "Starting MCP server with VFS tools..."
python3 direct_mcp_server.py > mcp_server_vfs.log 2>&1 &
echo $! > mcp_server_vfs.pid
echo "Server started with PID $(cat mcp_server_vfs.pid)"

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 3

# Verify tool registration
echo "Verifying tool registration..."
python3 verify_vfs_tools.py
if [ $? -eq 0 ]; then
    echo "✅ VFS tools successfully registered and verified!"
else
    echo "❌ Error: VFS tools not properly registered. Check mcp_server_vfs.log for details."
fi
""")
        os.chmod("restart_mcp_with_vfs.sh", 0o755)
        logger.info("Created restart_mcp_with_vfs.sh script")
    else:
        logger.error("❌ Failed to update server code")
        sys.exit(1)

if __name__ == "__main__":
    main()
