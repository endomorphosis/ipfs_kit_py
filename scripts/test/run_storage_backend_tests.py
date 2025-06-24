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

    python test_runner.py --categories storage

The test runner supports all test categories, including storage backend tests,
coverage reporting, and more options.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Run storage backend tests using the new test_runner."""
    # Show deprecation warning
    warnings.warn(
        "run_storage_backend_tests.py is deprecated and will be removed in a future version. "
        "Please use test_runner.py instead.",
        DeprecationWarning, stacklevel=2
    )

    print("Running storage backend tests using the new test_runner module...")

    # Check if test_runner.py exists
    test_runner_path = os.path.join(os.path.dirname(__file__), "test_runner.py")
    if not os.path.exists(test_runner_path):
        print("ERROR: test_runner.py not found. Please make sure it's in the same directory.")
        return 1

    # Build command for the test runner
    cmd = [
        sys.executable,
        test_runner_path,
        "--categories", "storage",
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
