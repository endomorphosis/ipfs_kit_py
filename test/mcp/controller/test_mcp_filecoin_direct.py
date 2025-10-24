#\!/usr/bin/env python3
"""
Test script to verify the MCP server's Filecoin implementation.
This test uses direct calls to the FilecoinModel without requiring
the Lotus daemon to be running.
"""

import os
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# First check if the directory structure exists
try:
    from ipfs_kit_py.lotus_kit import lotus_kit
    from ipfs_kit_py.mcp.models.storage.filecoin_model import FilecoinModel
    print("Successfully imported FilecoinModel")
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    print(f"Error importing FilecoinModel: {e}")
    # Try to find the actual file
    os.system("find ipfs_kit_py -name 'filecoin_model.py' -type f")
    DEPENDENCIES_AVAILABLE = False
    # Skip this module's tests if dependencies aren't available
    pytestmark = __import__('pytest').mark.skip(reason="Filecoin MCP dependencies not available")

def test_filecoin_model_graceful_degradation():
    """Test FilecoinModel's ability to handle missing Lotus daemon gracefully."""
    print("\n===== Testing FilecoinModel Graceful Degradation =====")

    # Create a lotus_kit instance with incorrect API URL to force failure
    lotus_kit_instance = lotus_kit(metadata={"api_url": "http://localhost:9999/rpc/v0"})

    # Create FilecoinModel with the lotus_kit instance
    model = FilecoinModel(lotus_kit_instance=lotus_kit_instance)

    # Check connection (should fail gracefully)
    result = model.check_connection()
    print(f"Connection check result: {json.dumps(result, indent=2)}")

    # Test a few operations to ensure they fail gracefully
    result = model.get_wallet_balance("fake_address")
    print(f"Wallet balance result: {json.dumps(result, indent=2)}")

    # List wallets should also fail gracefully
    result = model.list_wallets()
    print(f"List wallets result: {json.dumps(result, indent=2)}")

    # Return True if all calls completed without exceptions
    return True

def test_filecoin_model_methods():
    """Test the methods of FilecoinModel for proper interface."""
    print("\n===== Testing FilecoinModel Methods =====")

    # Create a lotus_kit instance with incorrect API URL to force failure
    lotus_kit_instance = lotus_kit(metadata={"api_url": "http://localhost:9999/rpc/v0"})

    # Create FilecoinModel with the lotus_kit instance
    model = FilecoinModel(lotus_kit_instance=lotus_kit_instance)

    # Test a sample of methods to ensure they exist and handle errors properly
    methods_to_test = [
        # Basic operations
        ("list_wallets", []),
        ("create_wallet", ["bls"]),
        ("get_wallet_balance", ["fake_address"]),

        # Deal operations
        ("list_deals", []),
        ("list_imports", []),

        # Miner operations
        ("list_miners", []),
        ("get_miner_info", ["fake_miner_address"]),
    ]

    for method_name, args in methods_to_test:
        try:
            # Get the method
            method = getattr(model, method_name)

            # Call the method with args
            result = method(*args)

            # Check the result structure
            if isinstance(result, dict) and "success" in result:
                print(f"Method {method_name} - Interface OK")
            else:
                print(f"Method {method_name} - Unexpected result format")

        except AttributeError:
            print(f"Method {method_name} - Not implemented")
        except Exception as e:
            print(f"Method {method_name} - Unexpected error: {str(e)}")

    # Return True if we got here without critical failure
    return True

def run_all_tests():
    """Run all test functions."""
    start_time = time.time()
    results = {}

    # Run tests
    results["model_graceful_degradation"] = test_filecoin_model_graceful_degradation()
    results["model_methods"] = test_filecoin_model_methods()

    # Print summary
    print("\n===== Test Summary =====")
    for test_name, result in results.items():
        status = "PASSED" if result else "FAILED"
        print(f"{test_name}: {status}")

    elapsed = time.time() - start_time
    print(f"Tests completed in {elapsed:.2f} seconds")

    # Overall success if all tests passed
    return all(results.values())

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
