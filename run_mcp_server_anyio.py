#!/usr/bin/env python
"""
Run the MCP server with AnyIO support for testing.

This script serves as a convenient way to start the MCP server
with AnyIO support for testing purposes.
"""

import os
import sys
import logging
import argparse
from ipfs_kit_py.mcp.server_anyio import main as run_server

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting MCP server with AnyIO support for tests")
    
    # Parse arguments from command line
    parser = argparse.ArgumentParser(description="Run MCP server with AnyIO support for tests")
    
    # Add server arguments
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--isolation", action="store_true", help="Enable isolation mode")
    parser.add_argument("--port", type=int, default=8002, help="Port to run the server on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--persistence-path", help="Path for persistence files")
    parser.add_argument("--api-prefix", default="/api/v0/mcp", help="Prefix for API endpoints")
    parser.add_argument("--log-level", default="INFO", help="Logging level (DEBUG, INFO, WARNING, ERROR)")
    parser.add_argument("--backend", default="asyncio", choices=["asyncio", "trio"], 
                        help="AnyIO backend to use")
    
    # Parse args and run server
    args = parser.parse_args()
    
    # Additional logging
    logger.info(f"MCP server initialized and registered with app")
    logger.info(f"Starting MCP server on port {args.port} for tests with AnyIO {args.backend} backend")
    
    # Convert args to list for main function
    arg_list = []
    if args.debug:
        arg_list.append("--debug")
    if args.isolation:
        arg_list.append("--isolation")
    arg_list.extend(["--port", str(args.port)])
    arg_list.extend(["--host", args.host])
    if args.persistence_path:
        arg_list.extend(["--persistence-path", args.persistence_path])
    arg_list.extend(["--api-prefix", args.api_prefix])
    arg_list.extend(["--log-level", args.log_level])
    arg_list.extend(["--backend", args.backend])
    
    # Run the server
    run_server(arg_list)