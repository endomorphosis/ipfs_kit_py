#!/usr/bin/env python
"""
Run script for MCP communication tests.

This script configures the environment and runs the MCP communication tests,
which verify that the MCP server and ipfs_kit_py can communicate via
WebRTC, WebSockets, and libp2p.
"""

import os
import sys
import argparse
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Run MCP communication tests with configured environment."""
    parser = argparse.ArgumentParser(description="Run MCP communication tests")
    parser.add_argument("--force-webrtc", action="store_true", 
                      help="Force WebRTC tests even if dependencies missing")
    parser.add_argument("--force-libp2p", action="store_true",
                      help="Force libp2p tests even if dependencies missing")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Enable verbose output")
    parser.add_argument("--test-only", action="store", 
                      choices=["webrtc", "websocket", "libp2p", "integrated"],
                      help="Run only a specific test")
    args = parser.parse_args()
    
    # Set environment variables based on args
    if args.force_webrtc:
        os.environ["FORCE_WEBRTC_TESTS"] = "1"
        os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"
    
    if args.force_libp2p:
        os.environ["FORCE_LIBP2P_TESTS"] = "1"
    
    # Construct pytest command
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.extend(["-v"])
    else:
        cmd.extend(["-v"])  # Always use some verbosity for better feedback
    
    # Add test selection if specified
    if args.test_only:
        test_function = f"test_{args.test_only}_communication"
        cmd.extend([f"test/test_mcp_communication.py::TestMCPServerCommunication::{test_function}"])
    else:
        cmd.extend(["test/test_mcp_communication.py"])
    
    # Add capturing (no capture for verbose)
    if not args.verbose:
        cmd.append("-s")
    
    # Print the command being run
    logger.info(f"Running: {' '.join(cmd)}")
    
    # Run the tests
    result = subprocess.run(cmd)
    
    # Return the exit code
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())