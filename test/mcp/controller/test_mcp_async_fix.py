"""
Test script to validate async fixes in MCP server.

This script creates an MCP server instance with AnyIO support and verifies
that the correct controller is loaded based on the async context.
"""

import asyncio
import logging
import sys
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("test_mcp_async_fix")

async def async_test():
    """Run tests in an async context to validate fixes."""
    logger.info("Starting async test...")
    
    # Import MCPServer after we're in the async context
    from ipfs_kit_py.mcp.server_anyio import MCPServer
    
    # Check the async backend
    try:
        import sniffio
        backend = sniffio.current_async_library()
        logger.info(f"Running in async context with backend: {backend}")
    except Exception as e:
        logger.error(f"Error detecting async backend: {e}")
        backend = None
    
    # Create server with debug mode for detailed logs
    logger.info("Creating MCP server...")
    server = MCPServer(
        debug_mode=True,
        log_level="INFO",
        isolation_mode=True  # Use isolation mode to avoid affecting host system
    )
    
    # Check if get_backend() method is working properly
    backend_detected = server.get_backend()
    logger.info(f"Server detected backend: {backend_detected}")
    
    # Check if storage_manager_controller was properly loaded
    if "storage_manager" in server.controllers:
        controller_type = type(server.controllers["storage_manager"]).__name__
        logger.info(f"Storage Manager Controller type: {controller_type}")
        
        # Verify we're using the AnyIO version
        is_anyio = "AnyIO" in controller_type
        logger.info(f"Using AnyIO version: {is_anyio}")
        
        if is_anyio and backend_detected:
            logger.info("SUCCESS: Correctly loaded AnyIO controller in async context")
        elif not is_anyio and backend_detected:
            logger.warning("WARNING: Using sync controller despite being in async context")
        elif not backend_detected:
            logger.warning("Backend detection failed, cannot verify controller selection")
    else:
        logger.error("No storage_manager controller found in server.controllers")
    
    # Test the health endpoint
    try:
        logger.info("Testing health endpoint...")
        health_response = await server.health_check()
        logger.info(f"Health endpoint response: success={health_response.get('success', False)}")
        
        # Check controllers in health response
        controllers = health_response.get("controllers", {})
        logger.info(f"Controllers in health response: {list(controllers.keys())}")
        
        if "storage_manager" in controllers:
            logger.info("SUCCESS: Storage Manager Controller included in health response")
        else:
            logger.error("ERROR: Storage Manager Controller not included in health response")
    except Exception as e:
        logger.error(f"Error calling health endpoint: {e}")
    
    # Check if storage models were initialized properly
    try:
        logger.info("Checking storage models initialization...")
        storage_models = server.storage_manager.get_all_models()
        logger.info(f"Initialized storage models: {list(storage_models.keys())}")
    except Exception as e:
        logger.error(f"Error checking storage models: {e}")
    
    # Shutdown server
    logger.info("Shutting down server...")
    await server.shutdown()
    
    logger.info("Async test completed")

def main():
    """Main test function."""
    logger.info("Starting MCP async fix validation test...")
    
    # Run the async test
    asyncio.run(async_test())
    
    logger.info("Test completed")

if __name__ == "__main__":
    main()