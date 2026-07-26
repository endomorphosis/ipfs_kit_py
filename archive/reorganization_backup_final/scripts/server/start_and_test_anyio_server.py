#!/usr/bin/env python
"""
DEPRECATED: This script has been replaced by mcp_server_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
Script to start the MCP AnyIO server, wait for it to be ready, and then test it.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import requests
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def start_server(port=9993):
    """Start the MCP AnyIO server and return the process."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                              "run_mcp_server_anyio_fixed.py")
    
    # Start the server process
    logger.info(f"Starting MCP AnyIO server on port {port}")
    server_process = subprocess.Popen([
        sys.executable, script_path, 
        "--debug", "--isolation", "--port", str(port)
    ])
    
    logger.info(f"Server process started with PID {server_process.pid}")
    return server_process

def wait_for_server(url, max_retries=30, retry_interval=1):
    """Wait for the server to be ready."""
    logger.info(f"Waiting for server at {url} to be ready...")
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                logger.info(f"Server is ready (attempt {attempt+1}/{max_retries})")
                return True
        except requests.exceptions.RequestException:
            pass
            
        # Only log every few attempts to avoid spam
        if attempt % 5 == 0 or attempt == max_retries - 1:
            logger.info(f"Server not ready, waiting... (attempt {attempt+1}/{max_retries})")
            
        # Wait before retrying
        time.sleep(retry_interval)
    
    logger.error(f"Server failed to start after {max_retries} attempts")
    return False

def run_tests(url):
    """Run the test script against the server."""
    test_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                   "test_mcp_api_anyio.py")
    
    logger.info(f"Running test script against {url}")
    test_process = subprocess.run([sys.executable, test_script_path, "--url", url])
    
    if test_process.returncode == 0:
        logger.info("Tests passed!")
        return True
    else:
        logger.error(f"Tests failed with return code {test_process.returncode}")
        return False

def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Start and test MCP AnyIO server")
    parser.add_argument("--port", type=int, default=9993, help="Port to run the server on")
    parser.add_argument("--test-only", action="store_true", help="Only run tests, don't start server")
    parser.add_argument("--start-only", action="store_true", help="Only start server, don't run tests")
    args = parser.parse_args()
    
    # Determine the server URL
    server_url = f"http://localhost:{args.port}"
    
    # Start server if needed
    server_process = None
    if not args.test_only:
        server_process = start_server(port=args.port)
        
        # Wait for server to be ready
        if not wait_for_server(server_url):
            if server_process:
                logger.info("Terminating server process")
                server_process.terminate()
            return 1
    
    # Run tests if needed
    test_success = True
    if not args.start_only:
        test_success = run_tests(server_url)
    
    # Keep server running if tests succeeded and start_only is specified
    if args.start_only:
        logger.info("Server started successfully, keeping it running...")
        logger.info(f"Server URL: {server_url}")
        logger.info("Press Ctrl+C to stop")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping server...")
    
    # Clean up server process if we started it
    if server_process and not args.start_only:
        logger.info("Terminating server process")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning("Server process did not terminate, killing it")
            server_process.kill()
    
    # Exit with appropriate code
    return 0 if test_success else 1

if __name__ == "__main__":
    sys.exit(main())