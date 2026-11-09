#!/usr/bin/env python3
"""
MCP Integration Test Runner

This script runs all the integration tests for the MCP server components
to verify that they function correctly after the architecture consolidation.
"""

import os
import sys
import unittest
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_runner")

def run_tests(args):
    """Run the specified integration tests."""
    # Set environment variables based on args
    if args.mock:
        os.environ['MCP_TEST_MOCK'] = '1'
        logger.info("Running tests in MOCK mode")
    
    # Add project root to path
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    
    # Determine test path
    if args.component:
        if args.component == 'ipfs':
            test_path = 'tests.integration.backends.test_ipfs_backend'
        elif args.component == 'filecoin':
            test_path = 'tests.integration.backends.test_filecoin_backend'
        elif args.component == 'streaming':
            test_path = 'tests.integration.streaming.test_streaming'
        elif args.component == 'search':
            test_path = 'tests.integration.search.test_search'
        elif args.component == 'migration':
            test_path = 'tests.integration.migration.test_migration'
        elif args.component == 'backends':
            test_path = 'tests.integration.backends'
        else:
            test_path = f'tests.integration.{args.component}'
    else:
        test_path = 'tests.integration'
    
    logger.info(f"Running tests from: {test_path}")
    
    # Run the tests
    result = unittest.main(module=test_path, exit=False, argv=[''])
    
    # Return appropriate exit code
    return 0 if result.result.wasSuccessful() else 1

def main():
    """Parse arguments and run tests."""
    parser = argparse.ArgumentParser(description='Run MCP integration tests')
    parser.add_argument('--mock', action='store_true', help='Run tests in mock mode')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--component', '-c', help='Test specific component (ipfs, filecoin, streaming, search)')
    
    # Only parse args when running the script directly, not when imported by pytest
    
    if __name__ == "__main__":
    
        args = parser.parse_args()
    
    else:
    
        # When run under pytest, use default values
    
        args = parser.parse_args([])
    
    # Set logging level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    return run_tests(args)

if __name__ == '__main__':
    sys.exit(main())