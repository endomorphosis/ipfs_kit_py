#!/usr/bin/env python3
"""
Run all WebRTC event loop fix tests.

This script runs all the tests for the WebRTC event loop fixes,
demonstrating the issue and verifying the solutions.
"""

import os
import sys
import time
import logging
import argparse
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("webrtc_tests.log")
    ]
)
logger = logging.getLogger(__name__)

# Colors for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'
END = '\033[0m'

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run all WebRTC event loop fix tests")
    
    parser.add_argument("--skip-demos", action="store_true", help="Skip demo scripts")
    parser.add_argument("--skip-integration", action="store_true", help="Skip integration tests")
    parser.add_argument("--skip-server", action="store_true", help="Skip server tests")
    parser.add_argument("--anyio-only", action="store_true", help="Only run AnyIO tests (skip asyncio)")
    parser.add_argument("--install-deps", action="store_true", help="Install dependencies before running tests")
    
    return parser.parse_args()

def run_command(cmd, description=None, timeout=300):
    """Run a command and return the result."""
    if description:
        logger.info(f"{BLUE}{description}{END}")
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.error(f"{RED}Command failed with return code {result.returncode}{END}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
        
        logger.info(f"{GREEN}Command succeeded{END}")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"{RED}Command timed out after {timeout} seconds{END}")
        return False
    except Exception as e:
        logger.error(f"{RED}Error running command: {e}{END}")
        return False

def install_dependencies():
    """Install the required dependencies."""
    logger.info(f"{BLUE}{BOLD}Installing dependencies...{END}")
    
    # Install from requirements.txt
    return run_command(
        ["pip", "install", "-r", "fixes/requirements.txt"],
        "Installing dependencies from requirements.txt"
    )

def run_demo_scripts(args):
    """Run the demo scripts."""
    logger.info(f"{BLUE}{BOLD}{UNDERLINE}Running demo scripts...{END}")
    
    success = True
    
    if not args.anyio_only:
        # Run asyncio demo
        asyncio_success = run_command(
            ["python", "event_loop_issue_demo.py"],
            "Running asyncio event loop demo"
        )
        if not asyncio_success:
            success = False
    
    # Run AnyIO demo
    anyio_success = run_command(
        ["python", "anyio_event_loop_demo.py"],
        "Running AnyIO event loop demo"
    )
    if not anyio_success:
        success = False
    
    return success

def run_integration_tests(args):
    """Run the integration tests."""
    logger.info(f"{BLUE}{BOLD}{UNDERLINE}Running integration tests...{END}")
    
    # Run the comprehensive integration test
    return run_command(
        ["python", "-m", "test.test_webrtc_anyio_integration"],
        "Running comprehensive integration test"
    )

def start_test_server(mcp_script, port=9999):
    """Start the test MCP server."""
    logger.info(f"{BLUE}Starting test MCP server on port {port}...{END}")
    
    # Start the server in a separate process
    process = subprocess.Popen(
        ["python", mcp_script, "--debug", "--port", str(port), "--host", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait for server to start
    max_retries = 10
    retries = 0
    started = False
    
    while retries < max_retries:
        try:
            import requests
            response = requests.get(f"http://127.0.0.1:{port}/api/health")
            if response.status_code == 200:
                started = True
                break
        except:
            pass
        time.sleep(1)
        retries += 1
    
    if not started:
        logger.error(f"{RED}Server failed to start{END}")
        process.terminate()
        return None
    
    logger.info(f"{GREEN}Server started successfully{END}")
    return process

def run_server_tests(args):
    """Run the server tests."""
    logger.info(f"{BLUE}{BOLD}{UNDERLINE}Running server tests...{END}")
    
    success = True
    
    if not args.anyio_only:
        # Test with asyncio-based server
        asyncio_server = start_test_server("run_mcp_with_webrtc_fixed.py")
        if asyncio_server:
            try:
                # Run the test against the asyncio server
                asyncio_success = run_command(
                    ["python", "test_webrtc_event_loop_fix.py", "--server-url", "http://127.0.0.1:9999", "--verbose"],
                    "Testing asyncio-based server"
                )
                if not asyncio_success:
                    success = False
            finally:
                # Stop the server
                logger.info("Stopping asyncio server...")
                asyncio_server.terminate()
                asyncio_server.wait()
    
    # Test with AnyIO-based server
    anyio_server = start_test_server("run_mcp_with_anyio_fixed.py", port=9998)
    if anyio_server:
        try:
            # Run the test against the AnyIO server
            anyio_success = run_command(
                ["python", "test_webrtc_event_loop_fix.py", "--server-url", "http://127.0.0.1:9998", "--verbose"],
                "Testing AnyIO-based server"
            )
            if not anyio_success:
                success = False
        finally:
            # Stop the server
            logger.info("Stopping AnyIO server...")
            anyio_server.terminate()
            anyio_server.wait()
    else:
        success = False
    
    return success

def main():
    """Main function to run all tests."""
    args = parse_args()
    
    logger.info(f"{BLUE}{BOLD}{UNDERLINE}WebRTC Event Loop Fix Tests{END}")
    
    # Check for Python version
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        logger.error(f"{RED}Python 3.8 or higher is required. You are using Python {python_version.major}.{python_version.minor}.{python_version.micro}{END}")
        return False
    
    # Install dependencies if requested
    if args.install_deps:
        if not install_dependencies():
            logger.error(f"{RED}Failed to install dependencies{END}")
            return False
    
    # Run tests based on arguments
    all_passed = True
    
    if not args.skip_demos:
        if not run_demo_scripts(args):
            all_passed = False
    
    if not args.skip_integration:
        if not run_integration_tests(args):
            all_passed = False
    
    if not args.skip_server:
        if not run_server_tests(args):
            all_passed = False
    
    # Print summary
    if all_passed:
        logger.info(f"{GREEN}{BOLD}All tests passed!{END}")
    else:
        logger.error(f"{RED}{BOLD}Some tests failed. Check the logs for details.{END}")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)