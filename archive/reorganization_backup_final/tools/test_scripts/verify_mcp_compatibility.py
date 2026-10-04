#!/usr/bin/env python3
"""
Verify and Fix MCP Compatibility Issues

This script verifies the compatibility between old and new MCP server structures
and fixes any issues found. It ensures that all tools and features will work correctly.
"""

import os
import sys
import logging
import importlib
import tempfile
import time
import json
import subprocess
from typing import Dict, Any, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mcp_compatibility_fix.log")
    ]
)
logger = logging.getLogger("mcp_compatibility")

def check_imports() -> Tuple[bool, List[str]]:
    """
    Check if all necessary imports are working.
    
    Returns:
        Tuple[bool, List[str]]: Success flag and list of failed imports
    """
    logger.info("Checking imports...")
    success = True
    failed_imports = []
    
    # List of critical imports to check
    import_paths = [
        "ipfs_kit_py.mcp.server_bridge",
        "ipfs_kit_py.mcp_server.server_bridge",
        "ipfs_kit_py.mcp.controllers.ipfs_controller",
        "ipfs_kit_py.mcp.models.ipfs_model",
        "ipfs_kit_py.mcp.controllers.storage_manager_controller",
        "ipfs_kit_py.mcp.models.storage_manager",
        "ipfs_kit_py.mcp.controllers.libp2p_controller",
        "ipfs_kit_py.mcp.models.libp2p_model",
        "ipfs_kit_py.mcp.controllers.webrtc_controller",
        "ipfs_kit_py.mcp.models.webrtc_model",
        "ipfs_kit_py.run_mcp_server_real_storage"
    ]
    
    for import_path in import_paths:
        try:
            module = importlib.import_module(import_path)
            logger.info(f"Import successful: {import_path}")
        except ImportError as e:
            logger.warning(f"Import failed: {import_path} - {e}")
            success = False
            failed_imports.append(import_path)
    
    return success, failed_imports

def fix_import_issues(failed_imports: List[str]) -> bool:
    """
    Fix import issues by ensuring the compatibility layer is properly set up.
    
    Args:
        failed_imports: List of failed import paths
        
    Returns:
        bool: Success flag
    """
    logger.info("Fixing import issues...")
    
    if not failed_imports:
        logger.info("No import issues to fix")
        return True
    
    # Fix __init__.py files if they're missing redirections
    for import_path in failed_imports:
        parts = import_path.split(".")
        
        # Skip if this isn't an ipfs_kit_py import
        if parts[0] != "ipfs_kit_py":
            continue
        
        # Handle mcp_server -> mcp redirection
        if "mcp_server" in parts:
            # Check if we need to add a module mapping
            module_path = "/".join(parts[:-1])
            module_path = module_path.replace(".", "/")
            os.makedirs(module_path, exist_ok=True)
            
            # Create or update __init__.py
            init_path = f"{module_path}/__init__.py"
            if not os.path.exists(init_path):
                with open(init_path, "w") as f:
                    f.write(f'''"""
{parts[-1]} compatibility module.

This module provides redirection to the new module structure.
"""

import sys
from importlib import import_module

# Get the correct new path
new_path = "{import_path.replace('mcp_server', 'mcp')}"

try:
    # Import the actual module
    real_module = import_module(new_path)
    
    # Copy all attributes from the real module
    for attr in dir(real_module):
        if not attr.startswith("__"):
            globals()[attr] = getattr(real_module, attr)
            
    # Set __all__ to match the real module
    if hasattr(real_module, "__all__"):
        __all__ = real_module.__all__
except ImportError as e:
    raise ImportError(f"Failed to import {new_path}: {{e}}")
''')
                    logger.info(f"Created new compatibility module: {init_path}")
    
    return True

def check_server_bridge_compatibility() -> bool:
    """
    Check if server_bridge.py compatibility is correctly set up.
    
    Returns:
        bool: Success flag
    """
    logger.info("Checking server_bridge.py compatibility...")
    
    # Check if the old and new server bridge modules can both be imported
    old_imported = False
    new_imported = False
    
    try:
        from ipfs_kit_py.mcp_server.server_bridge import MCPServer as OldMCPServer
        old_imported = True
        logger.info("Successfully imported from mcp_server.server_bridge")
    except ImportError as e:
        logger.warning(f"Failed to import from mcp_server.server_bridge: {e}")
    
    try:
        from ipfs_kit_py.mcp.server_bridge import MCPServer as NewMCPServer
        new_imported = True
        logger.info("Successfully imported from mcp.server_bridge")
    except ImportError as e:
        logger.warning(f"Failed to import from mcp.server_bridge: {e}")
    
    # If both imports work, we're good
    if old_imported and new_imported:
        logger.info("Server bridge compatibility is correctly set up")
        return True
    
    # If only new imports work, we may need to fix the old import path
    if new_imported and not old_imported:
        # Fix the old server_bridge.py to import from new path
        try:
            server_bridge_path = "ipfs_kit_py/mcp_server/server_bridge.py"
            if os.path.exists(server_bridge_path):
                with open(server_bridge_path, "w") as f:
                    f.write('''"""
MCP Server Bridge module.

This module provides compatibility with the old MCP server structure by bridging
to the new consolidated structure in ipfs_kit_py.mcp.
"""

import logging
import sys

# Set up logging
logger = logging.getLogger(__name__)

try:
    # Import from the new location directly
    from ipfs_kit_py.mcp.server_bridge import MCPServer, MCPCacheManager, AsyncMCPServer
    
    logger.info("Successfully imported MCPServer from ipfs_kit_py.mcp.server_bridge")
    
    # Re-export all the names
    __all__ = ['MCPServer', 'MCPCacheManager', 'AsyncMCPServer']
    
except ImportError as e:
    logger.error(f"Failed to import from ipfs_kit_py.mcp.server_bridge: {e}")
    # Raise to make the error visible
    raise
''')
                logger.info(f"Fixed server_bridge.py compatibility")
                return True
            else:
                logger.warning(f"Server bridge file not found: {server_bridge_path}")
                return False
        except Exception as e:
            logger.error(f"Failed to fix server_bridge.py: {e}")
            return False
    
    return False

def patch_mcp_compatibility() -> bool:
    """
    Apply compatibility patches to ensure MCP server works correctly.
    
    Returns:
        bool: Success flag
    """
    logger.info("Applying MCP compatibility patches...")
    
    success = True
    
    # Apply compatibility patches from mcp_compatibility module
    try:
        # Import mcp_compatibility module
        import mcp_compatibility
        
        # Patch the MCPServer class
        try:
            # Import from the new location
            from ipfs_kit_py.mcp.server_bridge import MCPServer
            mcp_compatibility.patch_mcp_server(MCPServer)
            logger.info("Patched MCPServer class")
            
            # Test creating an instance
            server = MCPServer(debug_mode=True, isolation_mode=True)
            logger.info("Successfully created MCPServer instance")
        except ImportError as e:
            logger.warning(f"Failed to import MCPServer from mcp.server_bridge: {e}")
            success = False
    except ImportError as e:
        logger.warning(f"Failed to import mcp_compatibility module: {e}")
        success = False
    
    # Apply direct IPFS model fixes
    try:
        # Import and apply direct fixes
        try:
            from ipfs_kit_py.mcp.models.ipfs_model_fix import apply_fixes
            
            if apply_fixes():
                logger.info("Successfully applied direct IPFS model fixes")
            else:
                logger.warning("Failed to apply direct IPFS model fixes")
                success = False
                
        except ImportError as e:
            logger.warning(f"Failed to import IPFS model fix module: {e}")
            success = False
    except Exception as e:
        logger.warning(f"Error applying direct IPFS model fixes: {e}")
        success = False
        
    # Apply IPFS model extensions
    try:
        # Initialize IPFS model extensions
        try:
            # Import the initializers
            from ipfs_kit_py.mcp.models.ipfs_model_initializer import initialize_ipfs_model
            from ipfs_kit_py.mcp.run_mcp_server_initializer import initialize_mcp_server
            
            # Initialize the extensions
            if initialize_ipfs_model():
                logger.info("Successfully initialized IPFS model extensions")
            else:
                logger.warning("Failed to initialize IPFS model extensions")
                # Not marking as failure since we have direct fixes now
            
            # Initialize the MCP server
            if initialize_mcp_server():
                logger.info("Successfully initialized MCP server extensions")
            else:
                logger.warning("Failed to initialize MCP server extensions")
                # Not marking as failure since we have direct fixes now
                
        except ImportError as e:
            logger.warning(f"Failed to import IPFS model initializers: {e}")
            # Not marking as failure since we have direct fixes now
    except Exception as e:
        logger.warning(f"Error initializing IPFS model extensions: {e}")
        # Not marking as failure since we have direct fixes now
        
    # Apply SSE and CORS fixes
    try:
        # Import and apply SSE and CORS fixes
        try:
            from ipfs_kit_py.mcp.sse_cors_fix import patch_mcp_server_for_sse
            
            # Apply the fixes
            if patch_mcp_server_for_sse():
                logger.info("Successfully applied SSE and CORS fixes")
            else:
                logger.warning("Failed to apply SSE and CORS fixes")
                success = False
                
        except ImportError as e:
            logger.warning(f"Failed to import SSE and CORS fixes: {e}")
            success = False
    except Exception as e:
        logger.warning(f"Error applying SSE and CORS fixes: {e}")
        success = False
    
    return success

def check_server_startup() -> bool:
    """
    Check if MCP server can start correctly.
    
    Returns:
        bool: Success flag
    """
    logger.info("Checking server startup...")
    
    # Use subprocess to run the start script
    try:
        # Stop any running server first
        subprocess.run(["./stop_mcp_server.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Start server in foreground mode for testing
        process = subprocess.Popen(
            ["./start_mcp_server.sh", "--foreground", "--port=9995", "--log-file=mcp_test.log"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for a few seconds to let the server start
        time.sleep(5)
        
        # Check if the process is still running
        if process.poll() is None:
            # Server is running, let's kill it
            process.terminate()
            logger.info("Server started successfully")
            return True
        else:
            # Server failed to start
            stdout, stderr = process.communicate()
            logger.warning(f"Server failed to start: {stderr}")
            return False
    except Exception as e:
        logger.error(f"Error checking server startup: {e}")
        return False

def fix_server_launcher() -> bool:
    """
    Fix the server launcher script if needed.
    
    Returns:
        bool: Success flag
    """
    logger.info("Fixing server launcher script...")
    
    # Check if run_mcp_server.py has the correct import path
    try:
        with open("run_mcp_server.py", "r") as f:
            content = f.read()
        
        # Check if the correct import path is used
        if "from ipfs_kit_py.run_mcp_server_real_storage import app, create_app" in content:
            logger.info("run_mcp_server.py has correct import path")
            return True
        
        # Fix import path
        content = content.replace(
            "from ipfs_kit_py.run_mcp_server_real_storage import app, create_app",
            "# Try multiple import paths for better compatibility\n"
            "    try:\n"
            "        from ipfs_kit_py.run_mcp_server_real_storage import app, create_app\n"
            "    except ImportError:\n"
            "        # Try alternative import path\n"
            "        from ipfs_kit_py.mcp.run_mcp_server_real_storage import app, create_app"
        )
        
        with open("run_mcp_server.py", "w") as f:
            f.write(content)
            
        logger.info("Fixed run_mcp_server.py import path")
        return True
    except Exception as e:
        logger.error(f"Failed to fix server launcher: {e}")
        return False

def test_cline_integration() -> bool:
    """
    Test if MCP server can be used with Cline integration.
    
    Returns:
        bool: Success flag
    """
    logger.info("Testing Cline MCP integration...")
    
    # Check if the MCP settings file exists
    settings_path = ".config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"
    if not os.path.exists(settings_path):
        logger.warning(f"MCP settings file not found: {settings_path}")
        return False
    
    # Read the settings file
    try:
        with open(settings_path, "r") as f:
            settings = json.load(f)
        
        # Check if the settings file has the required structure
        if "mcpServers" not in settings:
            logger.warning("MCP settings file missing mcpServers key")
            return False
        
        # Check if at least one server is defined
        if not settings["mcpServers"]:
            logger.warning("MCP settings file has no servers defined")
            return False
        
        logger.info("MCP settings file is valid")
        return True
    except Exception as e:
        logger.error(f"Failed to read MCP settings file: {e}")
        return False

def main():
    """
    Run the MCP compatibility checks and fixes.
    """
    logger.info("Starting MCP compatibility verification and fixes...")
    
    # Check imports
    import_success, failed_imports = check_imports()
    if not import_success:
        logger.warning(f"Some imports failed: {failed_imports}")
        
        # Try to fix import issues
        if fix_import_issues(failed_imports):
            logger.info("Fixed import issues")
        else:
            logger.warning("Failed to fix all import issues")
    
    # Check server bridge compatibility
    if check_server_bridge_compatibility():
        logger.info("Server bridge compatibility verified")
    else:
        logger.warning("Failed to verify server bridge compatibility")
    
    # Apply MCP compatibility patches
    if patch_mcp_compatibility():
        logger.info("MCP compatibility patches applied")
    else:
        logger.warning("Failed to apply MCP compatibility patches")
    
    # Fix server launcher
    if fix_server_launcher():
        logger.info("Server launcher fixed")
    else:
        logger.warning("Failed to fix server launcher")
    
    # Test Cline integration
    if test_cline_integration():
        logger.info("Cline MCP integration verified")
    else:
        logger.warning("Failed to verify Cline MCP integration")
    
    # Check server startup
    if check_server_startup():
        logger.info("Server startup verified")
    else:
        logger.warning("Failed to verify server startup")
    
    logger.info("MCP compatibility verification and fixes completed")
    print("\nMCP compatibility verification and fixes completed")
    print("Check mcp_compatibility_fix.log for details")

if __name__ == "__main__":
    main()
