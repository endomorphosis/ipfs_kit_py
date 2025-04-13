#!/usr/bin/env python3
"""
This test script is the properly named version of the original:
run_mcp_network_tests.py

It has been moved to the appropriate test directory for better organization.
"""

# Original content follows:

#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
Run MCP network partition tests with reduced output.

This script allows you to run any combination of the network partition tests:
- Partial network partition test
- Intermittent connectivity test
- Time-based recovery test

Usage:
  ./run_mcp_network_tests.py [--partial] [--intermittent] [--time-based] [--all]

Arguments:
  --partial      Run the partial network partition test
  --intermittent Run the intermittent connectivity test
  --time-based   Run the time-based recovery test
  --all          Run all network partition tests (default if no args provided)
"""

import logging
import sys
import unittest
import os
import argparse

def setup_logging():
    """Configure logging to reduce output but show test info messages."""
    # Set global log level to ERROR to reduce output
    logging.getLogger().setLevel(logging.ERROR)

    # Only show our test logger at INFO level
    test_logger = logging.getLogger("enhanced_mcp_discovery_test")
    test_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    test_logger.addHandler(handler)

def create_test_suite(tests_to_run):
    """Create a test suite with the specified tests."""
    from test_discovery.enhanced_mcp_discovery_test import EnhancedMCPDiscoveryTest
    
    suite = unittest.TestSuite()
    
    for test_name in tests_to_run:
        suite.addTest(EnhancedMCPDiscoveryTest(test_name))
        
    return suite

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run MCP network partition tests.")
    parser.add_argument("--partial", action="store_true", help="Run partial network partition test")
    parser.add_argument("--intermittent", action="store_true", help="Run intermittent connectivity test")
    parser.add_argument("--time-based", action="store_true", help="Run time-based recovery test")
    parser.add_argument("--all", action="store_true", help="Run all network tests")
    
    args = parser.parse_args()
    
    # If no arguments provided, run all tests
    if not (args.partial or args.intermittent or args.time_based or args.all):
        args.all = True
        
    return args

if __name__ == "__main__":
    # Setup logging
    setup_logging()
    
    # Parse command-line arguments
    args = parse_args()
    
    # Determine which tests to run
    tests_to_run = []
    
    if args.partial or args.all:
        tests_to_run.append("test_partial_network_partition")
        
    if args.intermittent or args.all:
        tests_to_run.append("test_intermittent_connectivity")
        
    if args.time_based or args.all:
        tests_to_run.append("test_time_based_recovery")
    
    if not tests_to_run:
        print("No tests selected to run.")
        sys.exit(1)
    
    # Create and run test suite
    suite = create_test_suite(tests_to_run)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    
    # Exit with appropriate status code
    sys.exit(not result.wasSuccessful())