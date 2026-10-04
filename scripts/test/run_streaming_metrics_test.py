#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
Script to test the streaming metrics integration.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the test module
from test.test_streaming import TestStreaming, TestAsyncStreaming, TestWebSocketStreaming
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

def run_tests():
    """Run the streaming metrics tests."""
    logger.info("Testing streaming metrics integration")
    
    # Create a test suite with the test classes
    suite = unittest.TestSuite()
    
    # Add tests from the TestStreaming class
    suite.addTest(unittest.makeSuite(TestStreaming))
    
    # Add tests from the TestAsyncStreaming class
    # suite.addTest(unittest.makeSuite(TestAsyncStreaming))
    
    # Add tests from the TestWebSocketStreaming class
    # suite.addTest(unittest.makeSuite(TestWebSocketStreaming))
    
    # Run the test suite
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    # Print the results
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Errors: {len(result.errors)}")
    logger.info(f"Failures: {len(result.failures)}")
    
    # Log any errors
    for i, (test, error) in enumerate(result.errors, start=1):
        logger.error(f"Error {i} in {test}: {error}")
        
    # Log any failures
    for i, (test, failure) in enumerate(result.failures, start=1):
        logger.error(f"Failure {i} in {test}: {failure}")
        
    # Return success status
    return len(result.errors) == 0 and len(result.failures) == 0

if __name__ == "__main__":
    # Verify IPFSSimpleAPI has needed attributes
    api = IPFSSimpleAPI()
    api.enable_metrics = True
    
    # Test if track_streaming_operation attribute is available
    if hasattr(api, 'track_streaming_operation'):
        logger.info("track_streaming_operation method is available in IPFSSimpleAPI")
    else:
        logger.error("track_streaming_operation method is NOT available in IPFSSimpleAPI")
        
    # Run the tests
    success = run_tests()
    
    # Exit with appropriate status code
    sys.exit(0 if success else 1)