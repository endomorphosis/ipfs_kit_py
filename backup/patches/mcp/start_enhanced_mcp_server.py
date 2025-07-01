#!/usr/bin/env python3
"""
Enhanced MCP server with complete IPFS tool coverage and FS integration.
This wrapper ensures the server starts correctly by importing and running the main code.
"""

import os
import sys
import logging
import importlib.util

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("enhanced-mcp")

def start_server():
    """Start the enhanced MCP server with integrated FS and tools"""
    logger.info("Starting enhanced MCP server with integrated IPFS tools and FS...")

    # Load the server module
    spec = importlib.util.spec_from_file_location("mcp_server", "direct_mcp_server_with_tools.py")
    server_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server_module)

    # The server should have started in the module's execution
    logger.info("Server module loaded successfully")

if __name__ == "__main__":
    start_server()
