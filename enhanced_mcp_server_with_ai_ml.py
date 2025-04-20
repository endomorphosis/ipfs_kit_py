#!/usr/bin/env python3
"""
Enhanced MCP Server with AI/ML Integration

This script extends the direct_mcp_server.py with AI/ML capabilities from Phase 2 
of the MCP roadmap. It registers the AI/ML router with the MCP server to expose
AI/ML functionality through the API.
"""

import os
import sys
import logging
import importlib.util
import time
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("enhanced-mcp")

# Try to add file handler for persistent logging
try:
    file_handler = logging.FileHandler('enhanced_mcp_server.log')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    logger.info("File logging initialized to enhanced_mcp_server.log")
except Exception as e:
    logger.warning(f"Could not set up file logging: {e}")

def import_module_from_path(module_name, module_path):
    """Import a module from a specific path."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None:
            logger.error(f"Could not find module at {module_path}")
            return None
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        logger.info(f"Successfully imported {module_name} from {module_path}")
        return module
    except Exception as e:
        logger.error(f"Error importing {module_name} from {module_path}: {e}")
        return None

def main():
    """Main entry point for the enhanced MCP server."""
    parser = argparse.ArgumentParser(description="Enhanced MCP Server with AI/ML Integration")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--disable-ai-ml", action="store_true", help="Disable AI/ML integration")
    args = parser.parse_args()
    
    # Find the path to the direct_mcp_server.py script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    direct_mcp_path = os.path.join(current_dir, "direct_mcp_server.py")
    
    if not os.path.exists(direct_mcp_path):
        logger.error(f"Could not find direct_mcp_server.py at {direct_mcp_path}")
        sys.exit(1)
    
    # Import the direct_mcp_server module
    logger.info(f"Importing direct_mcp_server from {direct_mcp_path}")
    direct_mcp = import_module_from_path("direct_mcp_server", direct_mcp_path)
    
    if direct_mcp is None:
        logger.error("Failed to import direct_mcp_server module. Cannot start enhanced server.")
        sys.exit(1)
    
    # Access the server instance from the direct_mcp_server module
    if not hasattr(direct_mcp, "app") or not hasattr(direct_mcp, "server"):
        logger.error("Could not find app or server in direct_mcp_server. Cannot integrate AI/ML.")
        # Since we can't integrate our components, just run the original server
        logger.info("Falling back to original server without AI/ML integration")
        # Set the PORT environment variable
        os.environ["PORT"] = str(args.port)
        # Execute the main function from direct_mcp_server
        if hasattr(direct_mcp, "__main__"):
            direct_mcp.__main__()
        else:
            # Just import and run the script directly
            exec(open(direct_mcp_path).read())
        return
    
    # Access the app and server from direct_mcp_server
    app = getattr(direct_mcp, "app")
    server = getattr(direct_mcp, "server")
    
    logger.info("Successfully accessed app and server from direct_mcp_server")
    
    # Integrate AI/ML components if not disabled
    if not args.disable_ai_ml:
        try:
            # Import the integrator
            logger.info("Importing AI/ML integrator")
            from ipfs_kit_py.mcp.integrator import integrate_ai_ml_with_mcp_server
            
            # Integrate AI/ML components with the app
            success = integrate_ai_ml_with_mcp_server(app)
            
            if success:
                logger.info("Successfully integrated AI/ML components with MCP server")
            else:
                logger.warning("Failed to integrate AI/ML components with MCP server")
        except Exception as e:
            logger.error(f"Error integrating AI/ML components: {e}")
    else:
        logger.info("AI/ML integration disabled by command-line argument")
    
    # Start the server
    logger.info(f"Starting enhanced MCP server on port {args.port}")
    
    # Set the PORT environment variable
    os.environ["PORT"] = str(args.port)
    
    # Run the uvicorn server
    try:
        import uvicorn
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=args.port,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()