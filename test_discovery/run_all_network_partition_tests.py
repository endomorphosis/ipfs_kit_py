#!/usr/bin/env python3
"""
Run all MCP Discovery network partition tests and generate a combined report.

This script runs the following network partition tests:
1. Basic network partition test
2. Asymmetric network partition test
3. Intermittent connectivity test
4. Time-based recovery test
5. Cascading network failures test

Results are combined into a single report file.
"""

import os
import sys
import unittest
import json
import time
import logging
from datetime import datetime

# Configure minimal logging
logging.basicConfig(level=logging.ERROR)

# Add parent directory to path to allow importing the test
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the test class
from test_discovery.enhanced_mcp_discovery_test import EnhancedMCPDiscoveryTest

# Network partition test methods to run
PARTITION_TESTS = [
    "test_basic_network_partition",
    "test_asymmetric_network_partition",
    "test_intermittent_connectivity",
    "test_time_based_recovery",
    "test_cascading_network_failures"
]

def run_test(test_method):
    """Run a single test method and return the result."""
    print(f"\nRunning test: {test_method}")
    print("-" * 80)
    
    # Create test suite with specific test method
    suite = unittest.TestSuite([EnhancedMCPDiscoveryTest(test_method)])
    
    # Run test and collect results
    start_time = time.time()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    end_time = time.time()
    
    # Return test results
    return {
        "test_method": test_method,
        "success": result.wasSuccessful(),
        "failures": len(result.failures),
        "errors": len(result.errors),
        "duration": round(end_time - start_time, 2),
        "timestamp": datetime.now().isoformat()
    }

def save_report(results):
    """Save test results to a JSON file."""
    report_data = {
        "summary": {
            "total_tests": len(results),
            "successful_tests": sum(1 for r in results if r["success"]),
            "failed_tests": sum(1 for r in results if not r["success"]),
            "total_duration": sum(r["duration"] for r in results),
            "timestamp": datetime.now().isoformat()
        },
        "tests": results
    }
    
    # Save to file
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        "network_partition_test_report.json"
    )
    
    with open(report_path, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    return report_path

if __name__ == "__main__":
    print("MCP Discovery Network Partition Test Suite")
    print("=" * 80)
    print(f"Running {len(PARTITION_TESTS)} network partition tests...")
    
    # Run all tests and collect results
    results = []
    for test_method in PARTITION_TESTS:
        results.append(run_test(test_method))
    
    # Save report
    report_path = save_report(results)
    
    # Print summary
    successful = sum(1 for r in results if r["success"])
    print("\nNetwork Partition Test Summary")
    print("=" * 80)
    print(f"Total tests:      {len(results)}")
    print(f"Successful tests: {successful}")
    print(f"Failed tests:     {len(results) - successful}")
    print(f"Total duration:   {sum(r['duration'] for r in results):.2f} seconds")
    print(f"Report saved to:  {report_path}")
    
    # Exit with status code
    sys.exit(successful != len(results))