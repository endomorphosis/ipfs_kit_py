#!/usr/bin/env python3
"""
Example demonstrating the integrated WAL CLI commands.

This script shows how to use the WAL commands integrated with the main IPFS Kit CLI.
"""

import os
import sys
import time
import logging
import subprocess
import tempfile
import random
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Directory to store test files
DATA_DIR = Path(tempfile.gettempdir()) / "ipfs_kit_test_data"

def create_sample_file(size_kb: int) -> str:
    """Create a sample file for testing.
    
    Args:
        size_kb: Size of the file in KB
        
    Returns:
        Path to the created file
    """
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True)
    
    # Create a file with random content
    file_path = DATA_DIR / f"test_file_{size_kb}kb_{random.randint(1000, 9999)}.bin"
    
    with open(file_path, 'wb') as f:
        # Create random data in 1KB chunks
        for _ in range(size_kb):
            f.write(random.randbytes(1024))
    
    logger.info(f"Created test file: {file_path} ({size_kb} KB)")
    return str(file_path)

def run_ipfs_cli(command: list) -> int:
    """Run the IPFS CLI with the given command.
    
    Args:
        command: Command-line arguments
        
    Returns:
        Exit code
    """
    # Check if we should run from source or installed package
    if os.path.exists(os.path.join(os.path.dirname(__file__), '..', 'ipfs_kit_py', 'cli.py')):
        cmd = [sys.executable, "-m", "ipfs_kit_py.cli"] + command
    else:
        cmd = ["ipfs-kit"] + command
        
    logger.info(f"Running: {' '.join(cmd)}")
    
    try:
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Display output
        if process.stdout:
            print(process.stdout)
        
        if process.returncode != 0:
            logger.error(f"Command failed with code {process.returncode}")
            if process.stderr:
                print(f"Error: {process.stderr}", file=sys.stderr)
                
        return process.returncode
    except Exception as e:
        logger.error(f"Failed to run command: {e}")
        return 1

def perform_wal_operations():
    """Perform a series of operations that will be tracked in the WAL."""
    # Create test files
    files = [
        create_sample_file(1),
        create_sample_file(5),
        create_sample_file(10)
    ]
    
    # Add files to IPFS
    logger.info("Adding files to IPFS...")
    for file_path in files:
        run_ipfs_cli(["add", file_path])
    
    # Show WAL status
    logger.info("\nChecking WAL status...")
    run_ipfs_cli(["wal", "status"])
    
    # List pending operations
    logger.info("\nListing pending operations...")
    run_ipfs_cli(["wal", "list", "pending"])
    
    # Get backend health status
    logger.info("\nChecking backend health...")
    run_ipfs_cli(["wal", "health"])
    
    # Process pending operations
    logger.info("\nProcessing pending operations...")
    run_ipfs_cli(["wal", "process"])
    
    # Show WAL metrics
    logger.info("\nShowing WAL metrics...")
    run_ipfs_cli(["wal", "metrics"])
    
    # Get WAL configuration
    logger.info("\nShowing WAL configuration...")
    run_ipfs_cli(["wal", "config"])
    
    # Clean up files
    for file_path in files:
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to remove file {file_path}: {e}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="WAL CLI Integration Example")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Demonstrate WAL CLI integration
        logger.info("=== WAL CLI Integration Example ===")
        perform_wal_operations()
        logger.info("\nExample completed successfully.")
        return 0
    except Exception as e:
        logger.exception(f"Example failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())