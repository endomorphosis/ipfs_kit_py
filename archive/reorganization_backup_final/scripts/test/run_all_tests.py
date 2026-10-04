#!/usr/bin/env python
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

    python test_runner.py --categories unit integration --coverage

The test runner supports all test categories, coverage reporting, and more options.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Run all tests using the new test_runner."""
    # Show deprecation warning
    warnings.warn(
        "run_all_tests.py is deprecated and will be removed in a future version. "
        "Please use test_runner.py instead.",
        DeprecationWarning, stacklevel=2
    )
    
    print("Running tests using the new test_runner module...")
    
    # Check if test_runner.py exists
    test_runner_path = os.path.join(os.path.dirname(__file__), "test_runner.py")
    if not os.path.exists(test_runner_path):
        print("ERROR: test_runner.py not found. Please make sure it's in the same directory.")
        return 1
    
    # Set environment variables to force WebRTC dependencies as the original script did
    os.environ["IPFS_KIT_FORCE_WEBRTC"] = "1"
    os.environ["FORCE_WEBRTC_TESTS"] = "1"
    os.environ["IPFS_KIT_RUN_ALL_TESTS"] = "1"
    
    # Import the module to set the environment variables
    print("Importing IPFS Kit components to apply environment variables...")
    try:
        import ipfs_kit_py.webrtc_streaming
        print(f"HAVE_WEBRTC: {ipfs_kit_py.webrtc_streaming.HAVE_WEBRTC}")
    except ImportError:
        print("Warning: Could not import WebRTC modules. Some tests may be skipped.")
    
    # Build command - run all test categories
    cmd = [
        sys.executable,
        test_runner_path,
        "--verbose"
    ]
    
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