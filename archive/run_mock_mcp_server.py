#!/usr/bin/env python3
"""
Simplified MCP server runner that uses our mock implementations
to start the final MCP server with all 53 models.
"""

import os
import sys
import importlib
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mcp_server_startup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("mcp-startup")

def setup_paths():
    """Set up Python paths for module imports."""
    cwd = os.getcwd()
    
    # Add critical paths
    paths = [
        cwd,
        os.path.join(cwd, "docs/mcp-python-sdk/src"),
        os.path.join(cwd, "ipfs_kit_py"),
    ]
    
    for path in paths:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path: {path}")
    
    return True

def fix_asyncio():
    """Fix asyncio module for compatibility."""
    import asyncio
    
    if hasattr(asyncio, 'events'):
        events = asyncio.events
        
        # Handle 'async' attribute safely
        if hasattr(events, 'async') and not hasattr(events, '_orig_async'):
            orig_async = getattr(events, 'async')
            setattr(events, '_orig_async', orig_async)
            delattr(events, 'async')
            setattr(events, 'async_', orig_async)
            logger.info("Applied asyncio compatibility patch")
    
    return True

def fix_multiaddr():
    """Fix multiaddr module for compatibility."""
    try:
        import multiaddr
        if not hasattr(multiaddr, 'exceptions'):
            class Exceptions:
                class Error(Exception):
                    pass
            multiaddr.exceptions = Exceptions
            logger.info("Added mock exceptions to multiaddr module")
    except ImportError:
        logger.warning("multiaddr module not found, continuing without it")
    
    return True

def run_server():
    """Run the final MCP server."""
    try:
        # Set up command line arguments
        sys.argv = ['final_mcp_server.py', '--port', '3000']
        
        # Import the server module
        spec = importlib.util.find_spec('final_mcp_server')
        if spec is None:
            logger.error("Could not find final_mcp_server.py")
            return False
        
        # Create the module
        module = importlib.util.module_from_spec(spec)
        sys.modules['final_mcp_server'] = module
        
        # Execute the module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Error loading final_mcp_server.py: {e}")
            logger.error(traceback.format_exc())
            return False
        
        # Run the main function
        if hasattr(module, 'main'):
            logger.info("Starting server via main() function")
            module.main()
        else:
            # Try alternative approaches to start the server
            if hasattr(module, 'app') and hasattr(module, 'run_server'):
                logger.info("Starting server via run_server() function")
                module.run_server()
            elif hasattr(module, 'app'):
                logger.info("Found app object, running it directly")
                import uvicorn
                uvicorn.run(module.app, host="0.0.0.0", port=3000)
            else:
                logger.error("No main() function or app object found in final_mcp_server.py")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error running server: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    logger.info("Starting MCP server with mock implementations...")
    
    # Setup paths and fix modules
    setup_paths()
    fix_asyncio()
    fix_multiaddr()
    
    # Run the server
    run_server()
