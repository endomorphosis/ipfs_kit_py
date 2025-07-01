#!/usr/bin/env python3
"""
Fix MCP Import Script

This script fixes the import issue in final_mcp_server.py by adding proper Python path setup
and improving the import mechanism for the MCP SDK.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix-mcp-import")

def fix_import_in_final_mcp_server():
    """Fix the import issue in final_mcp_server.py"""
    logger.info("Fixing import issue in final_mcp_server.py")
    
    # Read the current content of final_mcp_server.py
    with open("final_mcp_server.py", "r") as f:
        content = f.read()
    
    # Replace the import_required_modules function with a more robust version
    old_import_function = """def import_required_modules():
    \"\"\"Import required modules after setting up paths.\"\"\"
    global server, FastMCP, Context, JSONResponse, Starlette, CORSMiddleware
    
    try:
        # Try imports that require the MCP SDK
        import uvicorn
        from mcp.server.fastmcp import FastMCP, Context
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import JSONResponse, StreamingResponse, Response
        from starlette.middleware.cors import CORSMiddleware
        
        # JSON-RPC libraries
        from jsonrpc.dispatcher import Dispatcher
        from jsonrpc.exceptions import JSONRPCDispatchException
        
        # Create FastMCP server
        server = FastMCP(
            name=f"final-mcp-server",
            instructions="Unified MCP server with comprehensive IPFS tool coverage"
        )
        
        logger.info("Successfully imported required modules and created server instance")
        return True
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        return False"""
    
    new_import_function = """def import_required_modules():
    \"\"\"Import required modules after setting up paths.\"\"\"
    global server, FastMCP, Context, JSONResponse, Starlette, CORSMiddleware
    
    try:
        # Try imports that require the MCP SDK
        import uvicorn
        
        # Handle MCP SDK import more robustly
        try:
            # First try direct import
            from mcp.server.fastmcp import FastMCP, Context
        except ImportError:
            # If that fails, try importing from the specific SDK directory
            logger.info("Direct import failed, trying alternate import path")
            sdk_path = os.path.join(os.getcwd(), "docs/mcp-python-sdk/src")
            
            if sdk_path not in sys.path:
                sys.path.insert(0, sdk_path)
            
            # Add the module directory itself to handle relative imports
            mcp_dir = os.path.join(sdk_path, "mcp")
            if os.path.isdir(mcp_dir) and mcp_dir not in sys.path:
                sys.path.insert(0, mcp_dir)
            
            # Try to import the server module specifically 
            server_dir = os.path.join(mcp_dir, "server")
            if os.path.isdir(server_dir) and server_dir not in sys.path:
                sys.path.insert(0, server_dir)
                
            # Try importing directly from the path
            sys.path.insert(0, os.path.join(server_dir, "fastmcp"))
            
            # Now try the import again
            from mcp.server.fastmcp import FastMCP, Context
            
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.responses import JSONResponse, StreamingResponse, Response
        from starlette.middleware.cors import CORSMiddleware
        
        # JSON-RPC libraries
        from jsonrpc.dispatcher import Dispatcher
        from jsonrpc.exceptions import JSONRPCDispatchException
        
        # Create FastMCP server
        server = FastMCP(
            name=f"final-mcp-server",
            instructions="Unified MCP server with comprehensive IPFS tool coverage"
        )
        
        logger.info("Successfully imported required modules and created server instance")
        return True
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Detailed import error:", exc_info=True)
        return False"""
    
    # Replace the function in the content
    updated_content = content.replace(old_import_function, new_import_function)
    
    # Also improve the setup_python_paths function to include the actual MCP path
    old_setup_paths = """def setup_python_paths():
    \"\"\"Set up Python paths for proper module imports.\"\"\"
    logger.info("Setting up Python paths for module imports...")
    
    # Current directory
    cwd = os.getcwd()
    
    # Add the MCP SDK path
    paths_to_add = [
        # Main directory
        cwd,
        # MCP SDK path
        os.path.join(cwd, "docs/mcp-python-sdk/src"),
        # IPFS Kit path
        os.path.join(cwd, "ipfs_kit_py"),
    ]
    
    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path to sys.path: {path}")

    # Return True if successful
    return True"""
    
    new_setup_paths = """def setup_python_paths():
    \"\"\"Set up Python paths for proper module imports.\"\"\"
    logger.info("Setting up Python paths for module imports...")
    
    # Current directory
    cwd = os.getcwd()
    
    # Add the MCP SDK path
    paths_to_add = [
        # Main directory
        cwd,
        # MCP SDK path
        os.path.join(cwd, "docs/mcp-python-sdk/src"),
        # IPFS Kit path
        os.path.join(cwd, "ipfs_kit_py"),
    ]
    
    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path to sys.path: {path}")
    
    # Add specific MCP module paths to handle nested imports
    mcp_module_path = os.path.join(cwd, "docs/mcp-python-sdk/src/mcp")
    if os.path.isdir(mcp_module_path) and mcp_module_path not in sys.path:
        sys.path.insert(0, mcp_module_path)
        logger.info(f"Added MCP module path to sys.path: {mcp_module_path}")
    
    mcp_server_path = os.path.join(mcp_module_path, "server")
    if os.path.isdir(mcp_server_path) and mcp_server_path not in sys.path:
        sys.path.insert(0, mcp_server_path)
        logger.info(f"Added MCP server path to sys.path: {mcp_server_path}")
    
    # Return True if successful
    return True"""
    
    # Replace the function in the content
    updated_content = updated_content.replace(old_setup_paths, new_setup_paths)
    
    # Write the updated content back to the file
    with open("final_mcp_server.py", "w") as f:
        f.write(updated_content)
    
    logger.info("Successfully updated final_mcp_server.py")

if __name__ == "__main__":
    fix_import_in_final_mcp_server()
    print("Import fix complete. Try running ./start_final_solution.sh again.")
