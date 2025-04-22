#!/usr/bin/env python3
"""
MCP Server Entrypoint

This script provides an easy way to start the MCP server with configurable options.
It serves as the main entrypoint for running the MCP server.

Usage:
    python run_mcp_server.py [--port PORT] [--debug] [--no-isolation] [--skip-daemon] [--api-prefix PREFIX]

Options:
    --port PORT        Port number to use (default: 9994)
    --debug            Enable debug mode (default)
    --no-debug         Disable debug mode
    --isolation        Enable isolation mode (default)
    --no-isolation     Disable isolation mode
    --skip-daemon      Skip daemon initialization (default)
    --no-skip-daemon   Don't skip daemon initialization
    --api-prefix PREFIX  API prefix to use (default: /api/v0)
    --log-file FILE    Log file to use (default: mcp_server.log)
"""

import os
import sys
import argparse
import logging
import importlib

def main():
    """Run the MCP server with the specified configuration."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start the MCP server")
    parser.add_argument("--port", type=int, default=9994, help="Port number to use (default: 9994)")
    parser.add_argument("--debug", dest="debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-debug", dest="debug", action="store_false", help="Disable debug mode")
    parser.add_argument("--isolation", dest="isolation", action="store_true", help="Enable isolation mode")
    parser.add_argument("--no-isolation", dest="isolation", action="store_false", help="Disable isolation mode")
    parser.add_argument("--skip-daemon", dest="skip_daemon", action="store_true", help="Skip daemon initialization")
    parser.add_argument("--no-skip-daemon", dest="skip_daemon", action="store_false", help="Don't skip daemon initialization")
    parser.add_argument("--api-prefix", type=str, default="/api/v0", help="API prefix to use")
    parser.add_argument("--log-file", type=str, default="mcp_server.log", help="Log file to use")
    
    # Set default values
    parser.set_defaults(debug=True, isolation=True, skip_daemon=True)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=args.log_file
    )
    logger = logging.getLogger("mcp_server")
    
    # Set environment variables for configuration
    os.environ["MCP_DEBUG_MODE"] = str(args.debug).lower()
    os.environ["MCP_ISOLATION_MODE"] = str(args.isolation).lower()
    os.environ["MCP_SKIP_DAEMON"] = str(args.skip_daemon).lower()
    os.environ["MCP_PORT"] = str(args.port)
    os.environ["MCP_API_PREFIX"] = args.api_prefix
    
    # Log configuration
    logger.info(f"Starting MCP server with configuration:")
    logger.info(f"  Port: {args.port}")
    logger.info(f"  Debug mode: {args.debug}")
    logger.info(f"  Isolation mode: {args.isolation}")
    logger.info(f"  Skip daemon: {args.skip_daemon}")
    logger.info(f"  API prefix: {args.api_prefix}")
    logger.info(f"  Log file: {args.log_file}")
    
    # Start the server
    try:
        # Import the run_mcp_server_real_storage module
        # This is the current recommended implementation
        from ipfs_kit_py.run_mcp_server_real_storage import app, create_app
        
        # Import and run uvicorn
        import uvicorn
        
        # Run the server
        uvicorn.run(
            "ipfs_kit_py.run_mcp_server_real_storage:app",
            host="0.0.0.0",
            port=args.port,
            reload=False,
            log_level="debug" if args.debug else "info"
        )
    except ImportError as e:
        logger.error(f"Failed to import MCP server module: {e}")
        print(f"Error: Failed to import MCP server module: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        print(f"Error: Failed to start MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
