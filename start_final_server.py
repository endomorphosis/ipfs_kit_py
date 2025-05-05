#!/usr/bin/env python3

"""
Start Final MCP Server with IPFS tools and asyncio patches
This script properly handles the asyncio compatibility issues
and starts the final_mcp_server.py server
"""

import os
import sys
import importlib.util
import traceback

# Configure logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("start_final_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("start-final-server")

def patch_asyncio():
    """Apply patches to fix asyncio compatibility issues"""
    logger.info("Applying asyncio compatibility patches...")
    
    try:
        import asyncio
        
        # Safely patch asyncio without using 'async' as a direct attribute name
        if not hasattr(asyncio, '_patched_for_mcp'):
            # Get the original attribute if it exists
            orig_attr = getattr(asyncio, "async", None)
            
            # Define a safe patching method that uses getattr/setattr
            def safe_patch_async():
                # Create alias for the coroutine function
                if hasattr(asyncio, "coroutine"):
                    # Use setattr to avoid syntax errors with 'async' keyword
                    setattr(asyncio, "async_alias", asyncio.coroutine)
                    logger.info("Created asyncio.async_alias")
                
                # If there was already an async attribute, preserve it
                if orig_attr is not None:
                    # Mark that we've patched asyncio
                    setattr(asyncio, '_patched_for_mcp', True)
                    logger.info("Preserved original asyncio.async functionality")
                else:
                    # If there wasn't an original async attribute, mark as patched
                    setattr(asyncio, '_patched_for_mcp', True)
                    logger.info("No original asyncio.async to preserve")
                
                return True
                    
            # Apply the patch
            safe_patch_async()
            logger.info("Successfully patched asyncio")
        else:
            logger.info("asyncio already patched, skipping")
            
        return True
    except Exception as e:
        logger.error(f"Failed to patch asyncio: {e}")
        logger.error(traceback.format_exc())
        return False

def patch_multiaddr():
    """Apply patches for multiaddr compatibility"""
    logger.info("Applying multiaddr compatibility patches...")
    
    try:
        try:
            import multiaddr
            if not hasattr(multiaddr, 'exceptions'):
                class Exceptions:
                    class Error(Exception):
                        pass
                    class ParseError(Error):
                        pass
                    class ProtocolNotFoundError(Error):
                        pass
                
                multiaddr.exceptions = Exceptions
                logger.info("Added mock exceptions to multiaddr module")
        except ImportError:
            logger.warning("multiaddr module not found, creating mock")
            
            # Create a mock multiaddr module
            import sys
            from types import ModuleType
            
            mock_multiaddr = ModuleType("multiaddr")
            
            class Exceptions:
                class Error(Exception):
                    pass
                class ParseError(Error):
                    pass
                class ProtocolNotFoundError(Error):
                    pass
            
            mock_multiaddr.exceptions = Exceptions
            
            # Add basic functionality
            def parse_multiaddr(addr_str):
                return {"original": addr_str}
            
            mock_multiaddr.parse = parse_multiaddr
            
            # Install the mock module
            sys.modules["multiaddr"] = mock_multiaddr
            logger.info("Created and installed mock multiaddr module")
        
        return True
    except Exception as e:
        logger.error(f"Failed to patch multiaddr: {e}")
        logger.error(traceback.format_exc())
        return False

def add_paths():
    """Add necessary paths to sys.path"""
    logger.info("Adding required paths...")
    
    # Current directory
    cwd = os.getcwd()
    
    # Paths to add
    paths_to_add = [
        cwd,
        os.path.join(cwd, "ipfs_kit_py"),
        os.path.join(cwd, "docs/mcp-python-sdk/src"),
    ]
    
    for path in paths_to_add:
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)
            logger.info(f"Added path: {path}")
    
    return True

def run_server(port=3000, host="0.0.0.0", debug=False):
    """Run the final MCP server"""
    logger.info(f"Starting final MCP server on {host}:{port}...")
    
    try:
        # Import and load final_mcp_server module
        spec = importlib.util.find_spec("final_mcp_server")
        if spec is None:
            logger.error("Could not find final_mcp_server module")
            return False
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Extract the necessary components from the module
        if hasattr(module, "app"):
            app = module.app
        elif hasattr(module, "server") and hasattr(module.server, "sse_app"):
            app = module.server.sse_app()
        else:
            import uvicorn
            import sys
            
            # The module has set up the server, but we need to run it
            logger.info("Running server with uvicorn directly")
            sys.argv = ["final_mcp_server.py", "--port", str(port), "--host", host]
            if debug:
                sys.argv.append("--debug")
            
            # Call main if it exists
            if hasattr(module, "main"):
                result = module.main()
                logger.info(f"Server main function returned: {result}")
                return result
            else:
                # Final option: run the module directly as a script
                with open(spec.origin, 'r') as f:
                    code = compile(f.read(), spec.origin, 'exec')
                    exec(code, {"__name__": "__main__"})
                return True
                
        # Run the app with uvicorn if we got it
        import uvicorn
        logger.info(f"Running final MCP server app with uvicorn on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
        return True
    
    except Exception as e:
        logger.error(f"Failed to run server: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # Apply patches
    patch_asyncio()
    patch_multiaddr()
    
    # Add necessary paths
    add_paths()
    
    # Set any necessary environment variables
    os.environ["MCP_SERVER_PORT"] = "3000"
    
    # Run the server
    run_server(port=3000)
