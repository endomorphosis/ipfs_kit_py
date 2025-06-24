#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
DEPRECATED: This script has been replaced by test_runner.py

This file is kept for backward compatibility. Please use the unified test runner instead,
which provides comprehensive test execution capabilities:

    python test_runner.py --help

The new test runner supports all test categories, coverage reporting, and more options.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Run tests using the new test_runner."""
    # Show deprecation warning
    warnings.warn(
        "run_tests.py is deprecated and will be removed in a future version. "
        "Please use test_runner.py instead.",
        DeprecationWarning, stacklevel=2
    )

    print("Running tests using the new test_runner module...")

    # Check if test_runner.py exists
    test_runner_path = os.path.join(os.path.dirname(__file__), "test_runner.py")
    if not os.path.exists(test_runner_path):
        print("ERROR: test_runner.py not found. Please make sure it's in the same directory.")
        return 1

    # Get original command line arguments, skipping the script name
    args = sys.argv[1:]

    # Map the original arguments to the new test runner format
    import argparse
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

    try:
        original_args, unknown = parser.parse_known_args(args)
    except SystemExit:
        # If argparse exits (e.g., with --help), just pass through to the new script
        cmd = [sys.executable, test_runner_path] + args
        return subprocess.call(cmd)

    # Build command for the new test runner
    cmd = [sys.executable, test_runner_path]

    # Convert category to --categories format if specified
    if original_args.category != "all":
        cmd.extend(["--categories", original_args.category])

    # Add other options
    if original_args.list:
        cmd.append("--list-categories")

    if original_args.verbose:
        cmd.append("--verbose")

    if original_args.coverage:
        cmd.append("--coverage")

    # Add any unknown arguments
    if unknown:
        cmd.extend(unknown)

    # Run test_runner
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopping test execution...")
        return 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
