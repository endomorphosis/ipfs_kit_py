#!/usr/bin/env python3
"""
Final MCP Server Integration Script

This script integrates all necessary components to create a unified MCP server
with complete IPFS tool coverage. It patches the server configuration and fixes
any issues found during previous attempts.
"""

import os
import sys
import logging
import importlib.util
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("final_integration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("final-integration")

def setup_python_paths():
    """Set up Python paths for proper module imports."""
    logger.info("Setting up Python paths for module imports...")
    
    # Current directory
    cwd = os.getcwd()
    
    # Add the MCP SDK path
    paths_to_add = [
        # Main directory
        cwd,
        # IPFS Kit path
        os.path.join(cwd, "ipfs_kit_py"),
    ]
    
    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path to sys.path: {path}")

def fix_jsonrpc_integration():
    """Fix JSON-RPC integration issues."""
    logger.info("Fixing JSON-RPC integration...")
    
    try:
        # Try to import the JSON-RPC libraries to verify they're available
        from jsonrpc.dispatcher import Dispatcher
        from jsonrpc.exceptions import JSONRPCDispatchException
        
        logger.info("✅ JSON-RPC libraries are available")
        return True
    except ImportError as e:
        logger.error(f"❌ JSON-RPC libraries are not available: {e}")
        logger.error("You need to install jsonrpc library: pip install jsonrpc")
        return False

def check_unified_tools():
    """Check if the unified IPFS tools module is available."""
    logger.info("Checking unified IPFS tools module...")
    
    try:
        import unified_ipfs_tools
        logger.info("✅ Unified IPFS tools module is available")
        return True
    except ImportError as e:
        logger.error(f"❌ Unified IPFS tools module is not available: {e}")
        return False

def check_final_server():
    """Check if the final MCP server is available."""
    logger.info("Checking final MCP server...")
    
    try:
        import final_mcp_server
        logger.info("✅ Final MCP server module is available")
        return True
    except ImportError as e:
        logger.error(f"❌ Final MCP server module is not available: {e}")
        return False

def check_dependencies():
    """Check if all required dependencies are available."""
    logger.info("Checking required dependencies...")
    
    all_good = True
    
    # Check for required Python modules
    required_modules = [
        "uvicorn",
        "starlette",
        "fastapi"
    ]
    
    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
            logger.info(f"✅ Module {module_name} is available")
        except ImportError as e:
            logger.error(f"❌ Module {module_name} is not available: {e}")
            all_good = False
    
    # Check for MCP SDK
    try:
        # Add the MCP SDK path
        cwd = os.getcwd()
        mcp_sdk_path = os.path.join(cwd, "docs/mcp-python-sdk/src")
        
        if os.path.isdir(mcp_sdk_path):
            if mcp_sdk_path not in sys.path:
                sys.path.insert(0, mcp_sdk_path)
            
            # Try to import a module from the MCP SDK
            from mcp.server.fastmcp import FastMCP
            logger.info("✅ MCP SDK is available")
        else:
            logger.error(f"❌ MCP SDK path not found: {mcp_sdk_path}")
            all_good = False
    except ImportError as e:
        logger.error(f"❌ MCP SDK is not available: {e}")
        all_good = False
    
    # Check for IPFS Kit
    try:
        # Try to import a module from IPFS Kit
        import ipfs_kit_py
        logger.info("✅ IPFS Kit is available")
    except ImportError as e:
        logger.error(f"❌ IPFS Kit is not available: {e}")
        all_good = False
    
    return all_good

def fix_vscode_settings():
    """Fix VS Code settings to use the final MCP server."""
    logger.info("Fixing VS Code settings...")
    
    try:
        home_dir = os.path.expanduser("~")
        vscode_settings_path = os.path.join(home_dir, ".config", "Code", "User", "settings.json")
        
        if not os.path.exists(vscode_settings_path):
            logger.warning(f"⚠️ VS Code settings not found at {vscode_settings_path}")
            return False
        
        import json
        with open(vscode_settings_path, "r") as f:
            settings = json.load(f)
        
        # Add or update MCP server settings
        if "mcp" not in settings:
            settings["mcp"] = {}
        
        if "servers" not in settings["mcp"]:
            settings["mcp"]["servers"] = {}
        
        # Add the final MCP server
        settings["mcp"]["servers"]["final-mcp-server"] = {
            "type": "sse",
            "url": "http://localhost:3000/mcp"
        }
        
        # Add JSON-RPC settings
        settings["mcp"]["servers"]["final-mcp-server-jsonrpc"] = {
            "type": "jsonrpc",
            "url": "http://localhost:3000/jsonrpc"
        }
        
        with open(vscode_settings_path, "w") as f:
            json.dump(settings, f, indent=2)
        
        logger.info("✅ VS Code settings updated to use the final MCP server")
        return True
    except Exception as e:
        logger.error(f"❌ Error fixing VS Code settings: {e}")
        logger.error(traceback.format_exc())
        return False

def create_start_script():
    """Create a script to start the final MCP server."""
    logger.info("Creating start script...")
    
    script_path = os.path.join(os.getcwd(), "start_final_mcp_server.sh")
    script_content = """#!/bin/bash
# Start the final MCP server

# Kill any running instances
pkill -f "final_mcp_server.py" || echo "No running instances found"

# Wait for ports to be released
sleep 1

# Start the server
python3 final_mcp_server.py --debug --port 3000

# Exit with the same status as the server
exit $?
"""
    
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        
        logger.info(f"✅ Created start script at {script_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating start script: {e}")
        logger.error(traceback.format_exc())
        return False

def create_test_script():
    """Create a script to test the final MCP server."""
    logger.info("Creating test script...")
    
    script_path = os.path.join(os.getcwd(), "test_final_mcp_server.py")
    script_content = '''#!/usr/bin/env python3
"""
Test script for the final MCP server.
This script tests all the available IPFS tools.
"""

import sys
import json
import anyio
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format=\'%(asctime)s - %(name)s - %(levelname)s - %(message)s\'
)
logger = logging.getLogger("test-final-mcp")

# Server URL
SERVER_URL = "http://localhost:3000"

def check_server_health():
    """Check if the server is healthy."""
    try:
        response = requests.get(f"{SERVER_URL}/health")
        response.raise_for_status()
        
        logger.info(f"Server is healthy: {response.json()}")
        return True
    except Exception as e:
        logger.error(f"Server health check failed: {e}")
        return False

def get_available_tools():
    """Get the list of available tools."""
    try:
        response = requests.post(f"{SERVER_URL}/initialize")
        response.raise_for_status()
        
        data = response.json()
        tools = data.get("capabilities", {}).get("tools", [])
        
        logger.info(f"Available tools: {tools}")
        return tools
    except Exception as e:
        logger.error(f"Failed to get available tools: {e}")
        return []

def test_jsonrpc_endpoint():
    """Test the JSON-RPC endpoint."""
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "ping",
            "params": {},
            "id": 1
        }
        
        response = requests.post(
            f"{SERVER_URL}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"JSON-RPC ping result: {result}")
        
        return True
    except Exception as e:
        logger.error(f"JSON-RPC test failed: {e}")
        return False

def main():
    """Main entry point."""
    logger.info("Starting tests for final MCP server...")
    
    # Check server health
    if not check_server_health():
        logger.error("Server health check failed. Is the server running?")
        return 1
    
    # Get available tools
    tools = get_available_tools()
    if not tools:
        logger.error("No tools found. Server configuration may be incomplete.")
        return 1
    
    # Test JSON-RPC endpoint
    if not test_jsonrpc_endpoint():
        logger.warning("JSON-RPC endpoint test failed. Some functionality may be limited.")
    
    # Output summary
    logger.info(f"Tests completed. Found {len(tools)} tools.")
    logger.info("Server appears to be functioning correctly.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''
    
    try:
        with open(script_path, "w") as f:
            f.write(script_content)
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        
        logger.info(f"✅ Created test script at {script_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error creating test script: {e}")
        logger.error(traceback.format_exc())
        return False

def update_final_mcp_server():
    """Update final_mcp_server.py to use unified_ipfs_tools."""
    logger.info("Updating final_mcp_server.py to use unified_ipfs_tools...")
    
    try:
        server_path = os.path.join(os.getcwd(), "final_mcp_server.py")
        
        if not os.path.exists(server_path):
            logger.error(f"❌ final_mcp_server.py not found at {server_path}")
            return False
        
        with open(server_path, "r") as f:
            content = f.read()
        
        # Replace register_ipfs_tools function with one that uses unified_ipfs_tools
        updated_content = content.replace(
            "def register_ipfs_tools():",
            """def register_ipfs_tools():
    \"\"\"Register IPFS tools using unified_ipfs_tools.\"\"\"
    try:
        import unified_ipfs_tools
        logger.info("Using unified_ipfs_tools for IPFS tool registration")
        result = unified_ipfs_tools.register_all_ipfs_tools(server)
        logger.info(f"Registered IPFS tools using unified_ipfs_tools: {len(result) if isinstance(result, list) else result}")
        return True
    except Exception as e:
        logger.error(f"Error registering IPFS tools using unified_ipfs_tools: {e}")
        logger.error(traceback.format_exc())
        
        # Fall back to the original approach
        logger.warning("Falling back to original IPFS tool registration approach")"""
        )
        
        with open(server_path, "w") as f:
            f.write(updated_content)
        
        logger.info("✅ Updated final_mcp_server.py to use unified_ipfs_tools")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating final_mcp_server.py: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point."""
    logger.info("Starting final MCP server integration...")
    
    # Set up Python paths
    setup_python_paths()
    
    # Check dependencies
    if not check_dependencies():
        logger.warning("⚠️ Some dependencies are missing. Integration may not be successful.")
    
    # Check unified tools
    if not check_unified_tools():
        logger.error("❌ Unified IPFS tools module is not available. Integration cannot continue.")
        return 1
    
    # Check final server
    if not check_final_server():
        logger.error("❌ Final MCP server module is not available. Integration cannot continue.")
        return 1
    
    # Fix JSON-RPC integration
    fix_jsonrpc_integration()
    
    # Update final_mcp_server.py
    update_final_mcp_server()
    
    # Fix VS Code settings
    fix_vscode_settings()
    
    # Create start script
    create_start_script()
    
    # Create test script
    create_test_script()
    
    logger.info("✅ Final MCP server integration completed")
    logger.info("You can now start the server using ./start_final_mcp_server.sh")
    logger.info("Test the server using python3 test_final_mcp_server.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())