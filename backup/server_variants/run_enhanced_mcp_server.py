#!/usr/bin/env python3
"""
Enhanced MCP Server Runner

This script starts the final MCP server with enhanced parameter handling and
other stability improvements applied.
"""

import os
import sys
import time
import signal
import logging
import importlib
import traceback
import subprocess
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("enhanced_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced-runner")

# Configuration
DEFAULT_SERVER_MODULE = "final_mcp_server"
DEFAULT_PORT = 9998
DEFAULT_HOST = "0.0.0.0"
PID_FILE = "enhanced_mcp_server.pid"


def apply_fixes(server_module_name=DEFAULT_SERVER_MODULE):
    """
    Apply all necessary fixes to the server before running it.
    
    Args:
        server_module_name: The name of the server module to fix
    
    Returns:
        bool: True if fixes were applied successfully, False otherwise
    """
    logger.info("Applying fixes to server modules...")
    
    success = True
    
    # Fix 1: Apply parameter handling fixes
    try:
        # Import our parameter handling fixes
        fixed_param = importlib.import_module("fixed_ipfs_param_handling")
        
        # Import the unified IPFS tools module
        try:
            unified_tools = importlib.import_module("unified_ipfs_tools")
            # Apply the fixes to the unified tools module
            if fixed_param.apply_param_fixes_to_unified_tools(unified_tools):
                logger.info("✅ Parameter handling fixes applied successfully")
            else:
                logger.error("❌ Failed to apply parameter handling fixes")
                success = False
        except ImportError as e:
            logger.error(f"❌ Failed to import unified_ipfs_tools: {e}")
            success = False
    except ImportError as e:
        logger.error(f"❌ Failed to import fixed_ipfs_param_handling: {e}")
        success = False
    
    # Fix 2: Ensure server module can be imported without hanging
    try:
        logger.info(f"Testing import of {server_module_name}...")
        # Use subprocess to prevent hanging in the current process
        cmd = [sys.executable, "-c", f"import {server_module_name}; print('{server_module_name} imported successfully')"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info(f"✅ {server_module_name} module imported successfully")
        else:
            logger.error(f"❌ {server_module_name} module import failed: {result.stderr.strip()}")
            success = False
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {server_module_name} module import timed out (possibly hanging)")
        success = False
    except Exception as e:
        logger.error(f"❌ Error testing import of {server_module_name}: {e}")
        success = False
    
    return success


def run_server(server_module_name=DEFAULT_SERVER_MODULE, host=DEFAULT_HOST, port=DEFAULT_PORT, debug=False):
    """
    Run the MCP server with fixes applied.
    
    Args:
        server_module_name: The name of the server module to run
        host: The host to bind to
        port: The port to listen on
        debug: Whether to enable debug mode
    
    Returns:
        int: The process ID of the server process, or None if it failed to start
    """
    logger.info(f"Starting enhanced MCP server ({server_module_name}) on {host}:{port}...")
    
    # Apply fixes before running
    if not apply_fixes(server_module_name):
        logger.warning("Some fixes could not be applied, but continuing with server startup...")
    
    # Build the command to run the server
    cmd = [
        sys.executable,
        f"{server_module_name}.py",
        "--host", host,
        "--port", str(port)
    ]
    
    if debug:
        cmd.append("--debug")
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        # Start the server in a subprocess
        log_file = open(f"{server_module_name}.log", "w")
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True  # This creates a new session for the process
        )
        
        if process.poll() is None:
            logger.info(f"Server process started with PID {process.pid}")
            
            # Write PID to file
            with open(PID_FILE, "w") as f:
                f.write(str(process.pid))
            
            # Wait a moment to ensure the process doesn't immediately exit
            time.sleep(2)
            if process.poll() is None:
                logger.info("Server startup looks successful")
                return process.pid
            else:
                logger.error(f"Server process exited quickly with code {process.returncode}")
                return None
        else:
            logger.error(f"Server process failed to start (exit code: {process.returncode})")
            return None
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        logger.error(traceback.format_exc())
        return None


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run the enhanced MCP server with improved stability')
    parser.add_argument('--module', default=DEFAULT_SERVER_MODULE, help='Server module name')
    parser.add_argument('--host', default=DEFAULT_HOST, help='Host to bind to')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    args = parser.parse_args()
    
    logger.info("================== Starting Enhanced MCP Server ==================")
    
    pid = run_server(args.module, args.host, args.port, args.debug)
    
    if pid:
        logger.info(f"Server running with PID {pid}")
        logger.info(f"To stop the server, run: kill {pid}")
        return 0
    else:
        logger.error("Failed to start server")
        return 1


if __name__ == "__main__":
    sys.exit(main())
