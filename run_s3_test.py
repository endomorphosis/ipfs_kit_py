#!/usr/bin/env python3
"""
Script to run specific S3 controller tests and report results clearly.
"""

import unittest
import sys
import io
import os
import logging

# Suppress logging
logging.basicConfig(level=logging.ERROR)
for logger_name in logging.root.manager.loggerDict:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# Add the current directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the test
from test.test_mcp_storage_controllers import TestMCPStorageControllers

# Create a test suite with just the tests we want to run
def create_suite():
    suite = unittest.TestSuite()
    suite.addTest(TestMCPStorageControllers('test_s3_controller_http_endpoints'))
    suite.addTest(TestMCPStorageControllers('test_s3_model_parity'))
    return suite

if __name__ == "__main__":
    # Capture stdout/stderr
    stdout_backup = sys.stdout
    stderr_backup = sys.stderr
    
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    
    # Run the tests
    suite = create_suite()
    result = unittest.TextTestRunner().run(suite)
    
    # Restore stdout/stderr
    captured_out = sys.stdout.getvalue()
    captured_err = sys.stderr.getvalue()
    
    sys.stdout = stdout_backup
    sys.stderr = stderr_backup
    
    # Report the result
    print("\n=== S3 Controller Test Results ===")
    print(f"Ran {result.testsRun} test(s)")
    print(f"Errors: {len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    
    if not result.wasSuccessful():
        print("\n=== Errors ===")
        for test, error in result.errors:
            print(f"Error in {test}: {error}")
        
        print("\n=== Failures ===")
        for test, failure in result.failures:
            print(f"Failure in {test}: {failure}")
    else:
        print("All tests passed!")