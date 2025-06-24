# examples/wal_cli_example.py

#!/usr/bin/env python3
"""
Example demonstrating the WAL command-line interface.

This script shows how to use the WAL CLI for managing WAL operations,
checking backend health, and monitoring operation status.
"""

import os
import time
import logging
import subprocess
import tempfile
import random
import sys
import argparse
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_sample_file(size_kb: int) -> str:
    """Create a sample file for testing.

    Args:
        size_kb: Size of the file in KB

    Returns:
        Path to the created file
    """
    fd, path = tempfile.mkstemp(suffix=".bin")
    with os.fdopen(fd, 'wb') as f:
        # Create random data in 1KB chunks
        for _ in range(size_kb):
            f.write(random.randbytes(1024))

    logger.info(f"Created test file: {path} ({size_kb} KB)")
    return path

def run_wal_cli(args: list) -> int:
    """Run the WAL CLI with the given arguments.

    Args:
        args: Command-line arguments

    Returns:
        Exit code
    """
    cmd = [sys.executable, "-m", "ipfs_kit_py.wal_cli"] + args
    logger.info(f"Running: {' '.join(cmd)}")

    try:
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        # Display output
        if process.stdout:
            print(process.stdout)

        return process.returncode
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with code {e.returncode}")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(f"Error: {e.stderr}")
        return e.returncode

def demo_wal_cli():
    """Demonstrate WAL CLI functionality."""
    logger.info("\n=== WAL CLI Demonstration ===")

    # Check WAL status
    logger.info("Checking WAL status...")
    run_wal_cli(["status"])

    # Check backend health
    logger.info("\nChecking backend health...")
    run_wal_cli(["health"])

    # Add a test file
    logger.info("\nAdding a test file...")
    test_file = create_sample_file(5)
    run_wal_cli(["add", test_file])

    # List pending operations
    logger.info("\nListing pending operations...")
    run_wal_cli(["list", "pending"])

    # Clean up old operations
    logger.info("\nCleaning up old operations...")
    run_wal_cli(["cleanup"])

    # Clean up test file
    if os.path.exists(test_file):
        os.remove(test_file)

def main():
    """Main function demonstrating WAL CLI."""
    parser = argparse.ArgumentParser(description="WAL CLI demo")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Demonstrate WAL CLI
        demo_wal_cli()

    except Exception as e:
        logger.exception(f"Demonstration failed: {e}")
        return 1

    logger.info("WAL CLI demonstration completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())
