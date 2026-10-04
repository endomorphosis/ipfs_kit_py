#!/usr/bin/env python
"""
Simple unittest-based test runner that doesn't rely on pytest.
"""
import sys
import unittest
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add the project root to the system path
sys.path.insert(0, '.')

# Import some basic test modules to run
from test_basic import TestBasicFunctionality

if __name__ == "__main__":
    # Create a test suite
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTest(unittest.makeSuite(TestBasicFunctionality))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Set exit code based on test results
    sys.exit(not result.wasSuccessful())