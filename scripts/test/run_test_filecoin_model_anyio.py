#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
Test script for FilecoinModelAnyIO.

This script tests the FilecoinModelAnyIO implementation by running
the unit tests and verifying the implementation is working correctly.
"""

import os
import sys
import subprocess
import importlib.util

def check_anyio_available():
    """Check if AnyIO is available."""
    try:
        import anyio
        print("✅ AnyIO is available.")
        return True
    except ImportError:
        print("❌ AnyIO is not available. Please install with: pip install anyio")
        return False

def check_file_exists():
    """Check if the FilecoinModelAnyIO implementation exists."""
    file_path = os.path.join(
        "ipfs_kit_py", "mcp", "models", "storage", "filecoin_model_anyio.py"
    )
    if os.path.exists(file_path):
        print(f"✅ Implementation file {file_path} exists.")
        return True
    else:
        print(f"❌ Implementation file {file_path} does not exist.")
        return False

def check_class_implementation():
    """Check if the FilecoinModelAnyIO class is properly implemented."""
    try:
        from ipfs_kit_py.mcp.models.storage.filecoin_model_anyio import FilecoinModelAnyIO

        # Check that it inherits from FilecoinModel
        from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
        if not issubclass(FilecoinModelAnyIO, FilecoinModel):
            print("❌ FilecoinModelAnyIO does not inherit from FilecoinModel.")
            return False

        # Check for key methods
        required_methods = [
            "get_backend",
            "_warn_if_async_context",
            "check_connection_async",
            "list_wallets_async",
            "get_wallet_balance_async",
            "create_wallet_async",
            "import_file_async",
            "list_imports_async",
            "find_data_async",
            "list_deals_async",
            "get_deal_info_async",
            "start_deal_async",
            "retrieve_data_async",
            "list_miners_async",
            "get_miner_info_async",
            "ipfs_to_filecoin_async",
            "filecoin_to_ipfs_async"
        ]

        missing_methods = []
        for method in required_methods:
            if not hasattr(FilecoinModelAnyIO, method) or not callable(getattr(FilecoinModelAnyIO, method)):
                missing_methods.append(method)

        if missing_methods:
            print(f"❌ FilecoinModelAnyIO is missing required methods: {', '.join(missing_methods)}")
            return False

        print("✅ FilecoinModelAnyIO class is properly implemented.")
        return True

    except ImportError as e:
        print(f"❌ Error importing FilecoinModelAnyIO: {e}")
        return False
    except Exception as e:
        print(f"❌ Error checking FilecoinModelAnyIO implementation: {e}")
        return False

def run_tests():
    """Run the unit tests for FilecoinModelAnyIO."""
    test_file = "test/test_mcp_filecoin_model_anyio.py"

    if not os.path.exists(test_file):
        print(f"❌ Test file {test_file} does not exist.")
        return False

    try:
        print(f"Running tests from {test_file}...")
        result = subprocess.run(
            [sys.executable, "-m", "unittest", test_file],
            capture_output=True,
            text=True
        )

        print("\nTest output:")
        print("=" * 40)
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        print("=" * 40)

        if result.returncode == 0:
            print("✅ All tests passed.")
            return True
        else:
            print(f"❌ Tests failed with return code {result.returncode}.")
            return False

    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def main():
    """Main function to check FilecoinModelAnyIO implementation."""
    print("Checking FilecoinModelAnyIO implementation...")
    print("-" * 40)

    checks = [
        check_anyio_available,
        check_file_exists,
        check_class_implementation,
        run_tests
    ]

    success = True
    for check in checks:
        check_success = check()
        print("-" * 40)
        success = success and check_success
        if not check_success:
            # Stop at first failure
            break

    if success:
        print("✅ FilecoinModelAnyIO implementation is complete and working correctly!")
        return 0
    else:
        print("❌ FilecoinModelAnyIO implementation needs fixes.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
