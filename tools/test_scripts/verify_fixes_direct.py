#!/usr/bin/env python3
"""
Direct verification of IPFS Kit Python fixes.

This script verifies our specific fixes without relying on any test frameworks.
It should run with Python 3.12 without any compatibility issues.
"""

import os
import sys
import time
import inspect
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
)
logger = logging.getLogger("verification")

# Constants for colored output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

# Test results
results = {
    "passed": 0,
    "failed": 0,
    "total": 0,
    "details": []
}

def run_test(test_func):
    """Run a test function and record the result."""
    test_name = test_func.__name__
    
    # Update stats
    results["total"] += 1
    
    # Print test name
    print(f"Running {test_name}...")
    
    # Run the test
    start_time = time.time()
    try:
        test_func()
        
        # If we get here, the test passed
        duration = time.time() - start_time
        results["passed"] += 1
        results["details"].append({
            "name": test_name,
            "status": "passed",
            "duration": duration
        })
        
        print(f"  {GREEN}PASSED{RESET} ({duration:.3f}s)")
        return True
    except Exception as e:
        # Test failed
        duration = time.time() - start_time
        results["failed"] += 1
        results["details"].append({
            "name": test_name,
            "status": "failed",
            "duration": duration,
            "error": str(e),
            "traceback": traceback.format_exc()
        })
        
        print(f"  {RED}FAILED{RESET} ({duration:.3f}s)")
        print(f"  {RED}Error: {str(e)}{RESET}")
        print(f"  Stack trace:")
        print(f"{YELLOW}{traceback.format_exc()}{RESET}")
        return False

def test_lotus_kit_available():
    """Test the LOTUS_KIT_AVAILABLE constant."""
    import ipfs_kit_py.lotus_kit
    
    # Check if the constant exists
    assert hasattr(ipfs_kit_py.lotus_kit, 'LOTUS_KIT_AVAILABLE'), "LOTUS_KIT_AVAILABLE is missing"
    
    # Check if it's set to True
    assert ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE is True, "LOTUS_KIT_AVAILABLE should be True"
    
    print(f"  Found LOTUS_KIT_AVAILABLE = {ipfs_kit_py.lotus_kit.LOTUS_KIT_AVAILABLE}")

def test_backend_storage_exists():
    """Test that BackendStorage class exists."""
    import ipfs_kit_py.mcp.storage_manager.backend_base
    
    # Check if BackendStorage exists
    assert hasattr(ipfs_kit_py.mcp.storage_manager.backend_base, 'BackendStorage'), "BackendStorage class is missing"
    
    BackendStorage = ipfs_kit_py.mcp.storage_manager.backend_base.BackendStorage
    
    # Verify it's a class
    assert inspect.isclass(BackendStorage), "BackendStorage is not a class"
    
    print(f"  Found BackendStorage class: {BackendStorage}")

def test_backend_storage_methods():
    """Test that BackendStorage has the required methods."""
    from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage
    
    # Check for required methods
    required_methods = ['store', 'retrieve', 'list_keys', 'delete']
    for method_name in required_methods:
        assert hasattr(BackendStorage, method_name), f"BackendStorage is missing '{method_name}' method"
        method = getattr(BackendStorage, method_name)
        assert callable(method), f"BackendStorage.{method_name} is not callable"
    
    print(f"  BackendStorage has all required methods: {', '.join(required_methods)}")

def print_summary():
    """Print a summary of the test results."""
    # Print header
    print("\n" + "=" * 70)
    print(f"{BOLD}TEST RESULTS{RESET}")
    print("=" * 70)
    
    # Print statistics
    print(f"Total tests: {results['total']}")
    print(f"Passed:      {GREEN}{results['passed']}{RESET}")
    print(f"Failed:      {RED if results['failed'] > 0 else ''}{results['failed']}{RESET}")
    
    # Print success rate
    if results["total"] > 0:
        success_rate = (results["passed"] / results["total"]) * 100
        color = GREEN if success_rate == 100 else (YELLOW if success_rate >= 80 else RED)
        print(f"\nSuccess rate: {color}{success_rate:.1f}%{RESET}")
    
    # Print separator
    print("=" * 70)
    
    # Print failed tests if any
    failed_tests = [test for test in results["details"] if test["status"] == "failed"]
    if failed_tests:
        print(f"\n{BOLD}{RED}FAILED TESTS:{RESET}")
        for test in failed_tests:
            print(f"  {RED}{test['name']}{RESET}")
            print(f"    Error: {test['error']}")
        print("")

def main():
    """Run all verification tests."""
    # Add project root to sys.path
    project_root = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, project_root)
    
    print(f"\n{BOLD}IPFS Kit Python Fixes Verification{RESET}\n")
    
    # Run the tests
    tests = [
        test_lotus_kit_available,
        test_backend_storage_exists,
        test_backend_storage_methods
    ]
    
    for test_func in tests:
        run_test(test_func)
    
    # Print summary
    print_summary()
    
    # Return exit code based on test results
    return 0 if results["failed"] == 0 else 1

if __name__ == "__main__":
    sys.exit(main())