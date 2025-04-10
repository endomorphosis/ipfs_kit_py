#!/usr/bin/env python3
"""
Run the enhanced MCP discovery test with minimal logging
to focus on test results.
"""

import os
import sys
import unittest
import logging

# Configure minimal logging
logging.basicConfig(level=logging.ERROR)

# Add parent directory to path to allow importing the test
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the test
from test_discovery.enhanced_mcp_discovery_test import EnhancedMCPDiscoveryTest

if __name__ == "__main__":
    # Run a specific test or all tests
    if len(sys.argv) > 1:
        # Run a specific test method
        test_method = sys.argv[1]
        suite = unittest.TestSuite([EnhancedMCPDiscoveryTest(test_method)])
        print(f"Running test: {test_method}")
    else:
        # Run all tests
        suite = unittest.TestLoader().loadTestsFromTestCase(EnhancedMCPDiscoveryTest)
        print("Running all enhanced tests")
    
    # Run the tests
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    # Exit with status code
    sys.exit(not result.wasSuccessful())