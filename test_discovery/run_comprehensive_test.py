#!/usr/bin/env python3
"""
Runner script for the MCP Discovery Protocol test suite.

This script executes multiple test suites for the MCP Discovery Protocol and
reports detailed results, providing a clear summary of which aspects of the
protocol are working correctly.
"""

import os
import sys
import unittest
import time
import json
import logging
import importlib
import subprocess
from unittest import TextTestRunner, TestResult
from typing import Dict, List, Any

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("run_tests")

# Add the parent directory to the path to allow importing tests
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class DetailedTestResult(TestResult):
    """Custom test result class with more detailed reporting."""
    
    def __init__(self):
        super().__init__()
        self.test_details = {}
        self.start_times = {}
        self.durations = {}
    
    def startTest(self, test):
        """Record the start time of each test."""
        super().startTest(test)
        test_name = self._get_test_name(test)
        self.start_times[test_name] = time.time()
    
    def addSuccess(self, test):
        """Record test details for successful tests."""
        super().addSuccess(test)
        test_name = self._get_test_name(test)
        self.test_details[test_name] = {
            "status": "PASS",
            "details": None
        }
        self._record_duration(test_name)
    
    def addError(self, test, err):
        """Record test details for tests with errors."""
        super().addError(test, err)
        test_name = self._get_test_name(test)
        self.test_details[test_name] = {
            "status": "ERROR",
            "details": self._format_error(err)
        }
        self._record_duration(test_name)
    
    def addFailure(self, test, err):
        """Record test details for failed tests."""
        super().addFailure(test, err)
        test_name = self._get_test_name(test)
        self.test_details[test_name] = {
            "status": "FAIL",
            "details": self._format_error(err)
        }
        self._record_duration(test_name)
    
    def addSkip(self, test, reason):
        """Record test details for skipped tests."""
        super().addSkip(test, reason)
        test_name = self._get_test_name(test)
        self.test_details[test_name] = {
            "status": "SKIP",
            "details": reason
        }
        self._record_duration(test_name)
    
    def _get_test_name(self, test):
        """Get a formatted test name."""
        return f"{test.__class__.__name__}.{test._testMethodName}"
    
    def _format_error(self, err):
        """Format error information for display."""
        exctype, value, tb = err
        return f"{exctype.__name__}: {value}"
    
    def _record_duration(self, test_name):
        """Record the duration of a test."""
        if test_name in self.start_times:
            self.durations[test_name] = time.time() - self.start_times[test_name]
    
    def get_report_data(self):
        """Generate a detailed report of the test results."""
        # Group tests by feature being tested
        feature_groups = {
            "Server Discovery": ["test_server_discovery"],
            "Feature Compatibility": ["test_feature_compatibility", "test_feature_hash_grouping"],
            "Task Distribution": ["test_task_distribution"],
            "Health Monitoring": ["test_health_monitoring"],
            "Network Resilience": ["test_network_partition_and_recovery"],
            "Server Management": ["test_server_update", "test_scenario_feature_update"],
            "Server Collaboration": ["test_scenario_specialized_task_routing"]
        }
        
        # Build report data
        report_data = {
            "summary": {
                "total": self.testsRun,
                "passed": len(self.successes),
                "failures": len(self.failures),
                "errors": len(self.errors),
                "skipped": len(self.skipped)
            },
            "feature_status": {},
            "tests": {}
        }
        
        # Record individual test details
        for test_name, details in self.test_details.items():
            method_name = test_name.split('.')[-1]
            report_data["tests"][test_name] = {
                "status": details["status"],
                "details": details["details"],
                "duration": self.durations.get(test_name, 0)
            }
        
        # Determine feature status
        for feature, test_methods in feature_groups.items():
            feature_tests = []
            for test_method in test_methods:
                for test_name in self.test_details:
                    if test_name.endswith(f".{test_method}"):
                        feature_tests.append(test_name)
            
            # Calculate feature status
            all_passed = True
            any_skipped = False
            for test_name in feature_tests:
                status = self.test_details.get(test_name, {}).get("status", "")
                if status != "PASS":
                    all_passed = False
                if status == "SKIP":
                    any_skipped = True
            
            if not feature_tests:
                status = "UNKNOWN"
            elif all_passed:
                status = "PASS"
            elif any_skipped and not all_passed:
                status = "PARTIAL"
            else:
                status = "FAIL"
            
            report_data["feature_status"][feature] = {
                "status": status,
                "tests": feature_tests
            }
        
        return report_data

def print_colored_status(status):
    """Print a colored status message if terminal supports it."""
    if not sys.stdout.isatty():
        return status
        
    if status == "PASS":
        return f"\033[92m{status}\033[0m"  # Green
    elif status == "FAIL":
        return f"\033[91m{status}\033[0m"  # Red
    elif status == "ERROR":
        return f"\033[91m{status}\033[0m"  # Red
    elif status == "SKIP":
        return f"\033[93m{status}\033[0m"  # Yellow
    elif status == "PARTIAL":
        return f"\033[93m{status}\033[0m"  # Yellow
    elif status == "UNKNOWN":
        return f"\033[94m{status}\033[0m"  # Blue
    else:
        return status

def run_test_module(module_name):
    """Run standalone test in a separate process."""
    logger.info(f"Running {module_name}...")
    script_path = os.path.join(os.path.dirname(__file__), f"{module_name}.py")
    
    if not os.path.exists(script_path):
        logger.error(f"Test script not found: {script_path}")
        return False
    
    try:
        # Run the script in a separate process
        result = subprocess.run([sys.executable, script_path], 
                               capture_output=True, 
                               text=True,
                               check=False)
        
        # Print output
        if result.stdout:
            for line in result.stdout.splitlines():
                logger.info(f"[{module_name}] {line}")
        
        if result.stderr:
            for line in result.stderr.splitlines():
                if "WARNING" in line:
                    logger.warning(f"[{module_name}] {line}")
                else:
                    logger.error(f"[{module_name}] {line}")
        
        # Return success status
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Error running {module_name}: {str(e)}")
        return False

def run_unittest_module(module_path, test_class, test_method=None):
    """Run a unittest module, optionally a specific test method."""
    try:
        # Import the test module
        module = importlib.import_module(module_path)
        
        # Get the test class
        test_cls = getattr(module, test_class)
        
        # Create a test suite
        if test_method:
            # Create suite with just the specific test method
            suite = unittest.TestSuite([test_cls(test_method)])
            logger.info(f"Running {test_class}.{test_method} test...")
        else:
            # Create suite with all test methods
            suite = unittest.TestLoader().loadTestsFromTestCase(test_cls)
            logger.info(f"Running {test_class} tests...")
        
        # Create result object
        result = DetailedTestResult()
        
        # Run the tests
        runner = TextTestRunner(verbosity=2, failfast=False, resultclass=lambda: result)
        runner.run(suite)
        
        # Generate report
        report_data = result.get_report_data()
        
        # Save report
        report_name = f"{test_class.lower()}_{test_method}" if test_method else f"{test_class.lower()}"
        report_path = os.path.join(os.path.dirname(__file__), f"{report_name}_report.json")
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
        
        # Print summary
        test_name = f"{test_class}.{test_method}" if test_method else test_class
        logger.info(f"{test_name} Results:")
        logger.info(f"  Tests: {report_data['summary']['total']}")
        logger.info(f"  Passed: {report_data['summary']['passed']}")
        logger.info(f"  Failed: {report_data['summary']['failures']}")
        logger.info(f"  Errors: {report_data['summary']['errors']}")
        logger.info(f"  Skipped: {report_data['summary']['skipped']}")
        
        # Return success status
        return (report_data["summary"]["failures"] == 0 and 
                report_data["summary"]["errors"] == 0)
    
    except ImportError as e:
        logger.error(f"Error importing {module_path}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error running {test_class} tests: {str(e)}")
        return False

def run_comprehensive_tests():
    """Run the comprehensive test suite."""
    return run_unittest_module(
        "test_discovery.test_mcp_discovery_comprehensive", 
        "MCPDiscoveryComprehensiveTest"
    )

def run_all_tests():
    """Run all available MCP Discovery tests."""
    logger.info("\n=== Starting MCP Discovery Protocol Test Suite ===\n")
    
    # Track results for each test type
    results = {}
    
    # 1. Run minimal test (self-contained, no dependencies)
    logger.info("\n=== Running Minimal Test ===\n")
    minimal_success = run_test_module("minimal_discovery_test")
    results["Minimal Test"] = minimal_success
    
    # 2. Run simple test (mock-based, no libp2p)
    logger.info("\n=== Running Simple Test ===\n")
    simple_success = run_test_module("simple_mcp_discovery_test")
    results["Simple Mock Test"] = simple_success
    
    # 3. Run enhanced test (improved mock with network simulation)
    logger.info("\n=== Running Enhanced Test ===\n")
    enhanced_success = run_test_module("enhanced_mcp_discovery_test")
    results["Enhanced Mock Test"] = enhanced_success
    
    # 4. Run direct test (imports real components when available)
    logger.info("\n=== Running Direct Test ===\n")
    direct_success = run_test_module("direct_mcp_discovery_test")
    results["Direct Test"] = direct_success
    
    # 5. Run scenario test (full network simulation)
    logger.info("\n=== Running Scenario Test ===\n")
    scenario_success = run_test_module("test_mcp_discovery_scenario")
    results["Scenario Test"] = scenario_success
    
    # 6. Run comprehensive test suite (most complete test)
    logger.info("\n=== Running Comprehensive Test Suite ===\n")
    comprehensive_success = run_comprehensive_tests()
    results["Comprehensive Test"] = comprehensive_success
    
    # Print overall summary
    logger.info("\n=== MCP Discovery Test Summary ===\n")
    for test_name, success in results.items():
        status = "PASSED" if success else "FAILED"
        logger.info(f"  {test_name}: {print_colored_status(status if success else 'FAIL')}")
    
    # Determine overall success
    all_passed = all(results.values())
    
    # Create combined report
    report = {
        "timestamp": time.time(),
        "all_passed": all_passed,
        "results": results,
    }
    
    report_path = os.path.join(os.path.dirname(__file__), "combined_test_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"\nCombined test report saved to: {report_path}")
    logger.info(f"\nOverall result: {print_colored_status('PASS' if all_passed else 'FAIL')}")
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)