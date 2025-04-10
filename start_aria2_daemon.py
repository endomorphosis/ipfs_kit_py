#!/usr/bin/env python3
"""
Helper script to start the Aria2 daemon for testing.

This script ensures that the Aria2 daemon is running for MCP server integration testing.
"""

import argparse
import time
from ipfs_kit_py.aria2_kit import aria2_kit
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to start Aria2 daemon."""
    parser = argparse.ArgumentParser(description="Start Aria2 daemon for testing")
    parser.add_argument("--rpc-secret", help="RPC secret for Aria2 daemon", default="ipfs_kit_secret")
    parser.add_argument("--port", type=int, help="RPC port for Aria2 daemon", default=6800)
    parser.add_argument("--dir", help="Download directory", default="/tmp/aria2_downloads")
    args = parser.parse_args()
    
    # Initialize aria2_kit
    kit = aria2_kit()
    
    # Check if daemon is already running
    version_result = kit.get_version()
    if version_result.get("success", True):
        logger.info("Aria2 daemon already running")
        logger.info(f"Version: {version_result.get('version', {}).get('version', 'unknown')}")
        return True
    
    # Start the daemon
    options = {
        "rpc-secret": args.rpc_secret,
        "rpc-listen-port": args.port,
        "dir": args.dir,
        "continue": True,
        "auto-file-renaming": True,
        "max-concurrent-downloads": 5,
        "max-connection-per-server": 16,
        "split": 8,
        "min-split-size": "1M",
        "piece-length": "1M",
        "file-allocation": "falloc"
    }
    
    logger.info("Starting Aria2 daemon...")
    result = kit.start_daemon(**options)
    
    if result.get("success", False):
        logger.info("Aria2 daemon started successfully")
        
        # Verify daemon is running by getting version
        time.sleep(1)  # Give daemon time to start
        version_result = kit.get_version()
        if version_result.get("success", False):
            logger.info(f"Verified Aria2 daemon running, version: {version_result.get('version', {}).get('version', 'unknown')}")
            return True
        else:
            logger.error("Failed to verify Aria2 daemon is running")
            return False
    else:
        logger.error(f"Failed to start Aria2 daemon: {result.get('error', 'Unknown error')}")
        return False

if __name__ == "__main__":
    main()