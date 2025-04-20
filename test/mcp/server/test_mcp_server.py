#!/usr/bin/env python3
"""
MCP Server Testing Suite

This script runs all available tests for the MCP server implementation, including:
- Core functionality tests
- Component tests (Models, Controllers, Persistence)
- API integration tests

It provides a comprehensive verification of the MCP server's capabilities.
"""

import os
import sys
import time
import json
import logging
import argparse
import unittest
import tempfile
import subprocess
from unittest import TestLoader, TextTestRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_test_suite")

def run_mini_test():
    """Run the minimal MCP server test."""
    logger.info("Running minimal MCP server test...")
    test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_mcp_mini.py")
    
    result = subprocess.run(
        [sys.executable, test_path, "-v"],
        capture_output=True,
        text=True
    )
    
    # Print output
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
        
    return result.returncode == 0

def run_api_test(port=9999):
    """Run the MCP API tests."""
    logger.info(f"Running MCP API tests against port {port}...")
    
    # Check if MCP server is running on the specified port
    try:
        import requests
        response = requests.get(f"http://localhost:{port}/api/v0/mcp/health", timeout=1)
        if response.status_code != 200:
            logger.warning(f"MCP server health check failed with status {response.status_code}")
            logger.warning("Make sure the MCP server is running before running API tests")
            return False
    except Exception as e:
        logger.warning(f"Failed to connect to MCP server: {e}")
        logger.warning("Make sure the MCP server is running before running API tests")
        return False
    
    # Run the API test script
    test_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_mcp_api.py")
    
    # Modify the test script to use the correct port
    with open(test_path, 'r') as f:
        content = f.read()
    
    # Replace port if needed
    if "base_url = 'http://localhost:9999'" in content and port != 9999:
        logger.info(f"Updating port in test script from 9999 to {port}")
        content = content.replace("base_url = 'http://localhost:9999'", f"base_url = 'http://localhost:{port}'")
        with open(test_path, 'w') as f:
            f.write(content)
    
    # Run the test
    result = subprocess.run(
        [sys.executable, test_path],
        capture_output=True,
        text=True
    )
    
    # Print output
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
        
    return result.returncode == 0

def run_mcp_server(port=9999, timeout=10, debug=True, isolation=True):
    """Launch an MCP server instance for testing."""
    logger.info(f"Starting MCP server on port {port} (debug={debug}, isolation={isolation})...")
    
    # Use the example server script
    example_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples", "mcp_server_example.py")
    
    # Build arguments
    args = [sys.executable, example_path, "--port", str(port)]
    if debug:
        args.append("--debug")
    if isolation:
        args.append("--isolation")
    
    # Start server process
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    logger.info(f"Waiting up to {timeout} seconds for server to start...")
    start_time = time.time()
    server_ready = False
    
    while time.time() - start_time < timeout:
        try:
            import requests
            response = requests.get(f"http://localhost:{port}/api/v0/mcp/health", timeout=1)
            if response.status_code == 200:
                server_ready = True
                logger.info("MCP server is ready!")
                break
        except Exception:
            # Server not ready yet
            time.sleep(0.5)
    
    if not server_ready:
        logger.error("Failed to start MCP server within timeout period")
        process.terminate()
        stdout, stderr = process.communicate()
        if stdout:
            logger.error(f"Server stdout: {stdout}")
        if stderr:
            logger.error(f"Server stderr: {stderr}")
        return None
    
    return process

def main():
    """Run the MCP server test suite."""
    parser = argparse.ArgumentParser(description="MCP Server Test Suite")
    parser.add_argument("--port", type=int, default=9999, help="Port for MCP server")
    parser.add_argument("--no-server", action="store_true", help="Don't start a server instance")
    parser.add_argument("--no-mini", action="store_true", help="Skip the minimal component tests")
    parser.add_argument("--no-api", action="store_true", help="Skip the API tests")
    # Only parse args when running the script directly, not when imported by pytest
    if __name__ == "__main__":
        args = parser.parse_args()
    else:
        # When run under pytest, use default values
        args = parser.parse_args([])
    
    # Define test state
    success = True
    server_process = None
    
    try:
        # Run mini tests
        if not args.no_mini:
            mini_success = run_mini_test()
            if not mini_success:
                logger.warning("Minimal component tests failed")
                success = False
        
        # Start server if needed
        if not args.no_api and not args.no_server:
            server_process = run_mcp_server(port=args.port)
            if not server_process:
                logger.error("Failed to start MCP server")
                return 1
        
        # Run API tests
        if not args.no_api:
            api_success = run_api_test(port=args.port)
            if not api_success:
                logger.warning("API tests failed")
                success = False
        
        # Print overall status
        if success:
            logger.info("All MCP server tests completed successfully!")
        else:
            logger.warning("Some MCP server tests failed")
        
        return 0 if success else 1
        
    finally:
        # Clean up server process if we started one
        if server_process:
            logger.info("Stopping MCP server...")
            server_process.terminate()
            server_process.wait(timeout=5)

if __name__ == "__main__":
    sys.exit(main())