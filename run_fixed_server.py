#!/usr/bin/env python3
"""
Wrapper script to run the fixed final MCP server with compatibility fixes
"""
import os
import sys
import importlib
import importlib.util
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/wrapper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("wrapper")

def apply_compatibility_fixes():
    """Apply fixes for compatibility issues."""
    logger.info("Applying compatibility fixes...")
    
    # Fix asyncio 'async' function naming issue by importing it under controlled conditions
    try:
        import asyncio
        
        # Check if anything needs to be fixed
        fix_applied = False
        
        # Don't access 'async' directly to avoid syntax error
        # Instead use getattr/setattr to handle it
        if hasattr(asyncio, "async"):
            # getattr to get the function, then add it under the new name
            ensure_future = getattr(asyncio, "async")
            setattr(asyncio, "ensure_future", ensure_future)
            # Remove the 'async' attribute using delattr
            delattr(asyncio, "async")
            fix_applied = True
            logger.info("Fixed asyncio.async -> asyncio.ensure_future")
        
        # Same for tasks module if it exists
        if hasattr(asyncio, "tasks") and hasattr(asyncio.tasks, "async"):
            ensure_future = getattr(asyncio.tasks, "async")
            setattr(asyncio.tasks, "ensure_future", ensure_future)
            delattr(asyncio.tasks, "async")
            fix_applied = True
            logger.info("Fixed asyncio.tasks.async -> asyncio.tasks.ensure_future")
        
        if fix_applied:
            logger.info("Successfully applied asyncio compatibility fixes")
        else:
            logger.info("No asyncio compatibility issues detected")
    
    except Exception as e:
        logger.error(f"Warning: Error applying asyncio fix: {e}")
        logger.error(traceback.format_exc())
    
    # Add multiaddr.exceptions if needed
    try:
        import multiaddr
        if not hasattr(multiaddr, 'exceptions'):
            class Exceptions:
                class Error(Exception):
                    pass
            multiaddr.exceptions = Exceptions
            logger.info("Added mock exceptions to multiaddr module")
    except ImportError:
        logger.info("multiaddr module not found, skipping patch")
    
    # Set up paths for imports
    cwd = os.getcwd()
    paths_to_add = [
        cwd,
        os.path.join(cwd, "docs/mcp-python-sdk/src"),
        os.path.join(cwd, "ipfs_kit_py"),
        os.path.join(cwd, "ipfs_kit_py/mcp"),
    ]
    
    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path to sys.path: {path}")
    
    return True

def run_server():
    """Import and run the server script."""
    server_path = os.path.join(os.getcwd(), "fixed_final_mcp_server.py")
    
    try:
        # Use spec to avoid direct imports which might trigger syntax errors
        spec = importlib.util.spec_from_file_location("fixed_final_mcp_server", server_path)
        server_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server_module)
        
        # Run the main function
        logger.info("Starting fixed_final_mcp_server.py...")
        exit_code = server_module.main()
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Error running server: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    # Apply fixes
    apply_compatibility_fixes()
    
    # Set command line arguments
    sys.argv = [sys.argv[0]] + ["--debug", "--port", "3001"]
    
    # Run the server
    run_server()
