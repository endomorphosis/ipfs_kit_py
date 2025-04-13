#!/usr/bin/env python3
"""
Test runner script for the reorganized test structure.
This script makes it easy to run specific categories of tests.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Define test categories and their directories
TEST_CATEGORIES = {
    "unit": "test/unit",
    "integration": "test/integration",
    "functional": "test/functional",
    "performance": "test/performance",
    "mcp": "test/mcp",
    "api": "test/unit/api",
    "core": "test/unit/core",
    "storage": "test/unit/storage",
    "ai_ml": "test/unit/ai_ml",
    "wal": "test/unit/wal",
    "cli": "test/functional/cli",
    "filesystem": "test/functional/filesystem",
    "streaming": "test/functional/streaming",
    "webrtc": "test/integration/webrtc",
    "libp2p": "test/integration/libp2p",
    "ipfs": "test/integration/ipfs",
    "s3": "test/integration/s3",
    "storacha": "test/integration/storacha",
    "lotus": "test/integration/lotus",
    "mcp_controller": "test/mcp/controller",
    "mcp_model": "test/mcp/model",
    "mcp_server": "test/mcp/server",
    "all": "test"
}

def run_tests(category, options=None):
    """Run tests for the specified category with optional pytest arguments."""
    if category not in TEST_CATEGORIES:
        print(f"Error: Unknown test category '{category}'")
        print(f"Available categories: {', '.join(sorted(TEST_CATEGORIES.keys()))}")
        return 1
    
    test_path = TEST_CATEGORIES[category]
    cmd = ["pytest", test_path]
    
    # Add any additional pytest options
    if options:
        cmd.extend(options)
    
    print(f"Running {category} tests with command: {' '.join(cmd)}")
    return subprocess.call(cmd)

def list_categories():
    """List all available test categories."""
    print("Available test categories:")
    for category, path in sorted(TEST_CATEGORIES.items()):
        # Count test files in the category
        if os.path.exists(path):
            test_count = len(list(Path(path).glob("**/test_*.py")))
            print(f"  {category:15} {path:30} ({test_count} test files)")
        else:
            print(f"  {category:15} {path:30} (directory not found)")

def main():
    """Parse arguments and run tests."""
    parser = argparse.ArgumentParser(description="Run tests for IPFS Kit Python")
    parser.add_argument("category", nargs="?", default="all",
                      help=f"Test category to run (default: all)")
    parser.add_argument("--list", action="store_true",
                      help="List available test categories")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Enable verbose output")
    parser.add_argument("--coverage", action="store_true",
                      help="Run with coverage report")
    parser.add_argument("--anyio", action="store_true",
                      help="Run only anyio tests (test files with anyio in the name)")
    parser.add_argument("--async", dest="async_only", action="store_true",
                      help="Run only async tests (requires pytest-asyncio)")
    
    args, unknown = parser.parse_known_args()
    
    if args.list:
        list_categories()
        return 0
    
    # Prepare pytest options
    pytest_options = unknown
    if args.verbose:
        pytest_options.append("-v")
    if args.coverage:
        pytest_options.extend(["--cov=ipfs_kit_py", "--cov-report=term"])
    if args.anyio:
        pytest_options.extend(["-k", "anyio"])
    if args.async_only:
        pytest_options.append("--asyncio-mode=auto")
    
    return run_tests(args.category, pytest_options)

if __name__ == "__main__":
    sys.exit(main())