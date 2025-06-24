#!/usr/bin/env python3
"""
Runner script for MCP controller integration tests.

This script runs both the standard and AnyIO versions of the integration tests.
It provides a consistent way to run the tests from the command line and CI/CD.
"""

import os
import sys
import unittest
import argparse
import time

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

def run_test_suite(test_module, title, verbose=False):
    """Run a test suite and print results."""
    print(f"\n{'=' * 80}")
    print(f"RUNNING INTEGRATION TEST SUITE: {title}")
    print(f"{'=' * 80}")

    # Dynamically import the test module
    try:
        # Use a relative import from the test.integration package
        module = __import__(f"test.integration.{test_module}", fromlist=['*'])

        # Find all test classes in the module
        test_classes = []
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, unittest.TestCase) and attr.__module__ == module.__name__:
                test_classes.append(attr)

        if not test_classes:
            print(f"No test classes found in module {test_module}")
            return 0

        # Run each test class
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0

        for test_class in test_classes:
            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            result = unittest.TextTestRunner(verbosity=2 if verbose else 1).run(suite)

            passed_tests += len(result.successes) if hasattr(result, 'successes') else (result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped))
            failed_tests += len(result.failures) + len(result.errors)
            skipped_tests += len(result.skipped)

        print(f"\nRESULTS: {passed_tests} passed, {failed_tests} failed, {skipped_tests} skipped")
        return failed_tests

    except ImportError as e:
        print(f"Failed to import test module {test_module}: {e}")
        return 1

def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(description="Run integration tests for MCP controllers")
    parser.add_argument("--standard", action="store_true", help="Run standard integration tests")
    parser.add_argument("--anyio", action="store_true", help="Run AnyIO integration tests")
    parser.add_argument("--mocked", action="store_true", help="Run only mocked integration tests")
    parser.add_argument("--all", action="store_true", help="Run all integration tests")
    parser.add_argument("-v", "--verbose", action="store_true", help="Increase output verbosity")

    # Only parse args when running the script directly, not when imported by pytest

    if __name__ == "__main__":

        args = parser.parse_args()

    else:

        # When run under pytest, use default values

        args = parser.parse_args([])

    # If no test type is specified, run all
    if not (args.standard or args.anyio or args.mocked or args.all):
        args.all = True

    # Set up test configurations
    test_configs = []

    if args.mocked or args.all:
        # Add the mocked integration tests
        test_configs.append(("test_mcp_controller_mocked_integration", "Mocked Integration Tests"))

    if args.standard or args.all:
        test_configs.append(("test_mcp_controller_integration", "Standard Integration Tests"))

    if args.anyio or args.all:
        test_configs.append(("test_mcp_controller_integration_anyio", "AnyIO Integration Tests"))

    # Track failures
    total_failures = 0

    # Run all test suites
    start_time = time.time()

    for test_module, title in test_configs:
        failures = run_test_suite(test_module, title, args.verbose)
        total_failures += failures

    end_time = time.time()

    # Print overall results
    print(f"\n{'=' * 80}")
    print(f"INTEGRATION TEST SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total test suites run: {len(test_configs)}")
    print(f"Total time: {end_time - start_time:.2f} seconds")

    if total_failures == 0:
        print("\nOVERALL RESULT: SUCCESS - All test suites passed")
        return 0
    else:
        print(f"\nOVERALL RESULT: FAILURE - {total_failures} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
