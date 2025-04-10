#!/usr/bin/env python3
"""
Run the intermittent connectivity test with reduced output.
"""

import logging
import sys
import unittest
import os

# Set global log level to ERROR to reduce output
logging.getLogger().setLevel(logging.ERROR)

# Only show our test logger at INFO level
test_logger = logging.getLogger("enhanced_mcp_discovery_test")
test_logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
test_logger.addHandler(handler)

# Import the test
from test_discovery.enhanced_mcp_discovery_test import EnhancedMCPDiscoveryTest

# Create test suite with just our test
suite = unittest.TestSuite()
suite.addTest(EnhancedMCPDiscoveryTest("test_intermittent_connectivity"))

# Run the test
if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())