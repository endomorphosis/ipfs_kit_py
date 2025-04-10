#!/usr/bin/env python3
"""
Run the MCP Discovery cascading network failures test with minimal logging
to focus on test results.

This script specifically runs the test_cascading_network_failures test method
from the EnhancedMCPDiscoveryTest class, which simulates a series of progressive
network failures that spread across the system.
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
    # Create test suite with just the cascading network failures test
    test_method = "test_cascading_network_failures"
    suite = unittest.TestSuite([EnhancedMCPDiscoveryTest(test_method)])
    
    print(f"Running MCP Discovery cascading network failures test...")
    print("This test simulates progressively degrading network conditions where")
    print("failures spread across the system in several stages:")
    print("  1. Initial full connectivity")
    print("  2. First failure: Isolated node")
    print("  3. Cascading failure: Network partition")
    print("  4. Progressive node failures within one group")
    print("  5. Partial recovery process")
    print("  6. Full recovery process")
    print("")
    
    # Run the test
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    # Check if test was successful
    if result.wasSuccessful():
        print("\nSUCCESS: MCP Discovery protocol successfully handled cascading network failures")
    else:
        print("\nFAILURE: MCP Discovery protocol failed to handle cascading network failures")
    
    # Exit with status code
    sys.exit(not result.wasSuccessful())