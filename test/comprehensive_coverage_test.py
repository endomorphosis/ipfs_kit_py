"""
Comprehensive coverage test to combine all our standalone tests.

This file imports and runs all our standalone test files to make them part of the test suite.
"""

import os
import sys
import unittest

# Add test modules here as they are created
test_modules = ["simple_performance_metrics_test", "simple_api_test", "simple_benchmark_test"]


# Build a test suite from all modules
def build_test_suite():
    """Build a test suite from all test modules."""
    test_loader = unittest.TestLoader()
    test_suite = unittest.TestSuite()

    for module_name in test_modules:
        try:
            # Import the module
            module = __import__(f"test.{module_name}", fromlist=["*"])

            # Add all tests from the module to the suite
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                    test_suite.addTest(test_loader.loadTestsFromTestCase(obj))
        except (ImportError, AttributeError) as e:
            print(f"Warning: Could not import test module {module_name}: {e}")

    return test_suite


if __name__ == "__main__":
    # Run the test suite
    test_suite = build_test_suite()
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)

    # Return a non-zero exit code if tests failed
    sys.exit(not result.wasSuccessful())
