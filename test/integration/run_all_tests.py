#!/usr/bin/env python3
"""
Comprehensive test runner for the MCP server.

This script runs the full test suite, including:
- Integration tests (mocked and standard)
- End-to-end tests
- Performance tests
- AnyIO variants of the above

It produces detailed test reports and can be configured with various options.
"""

import os
import sys
import time
import argparse
import unittest
import subprocess
import json
from typing import Dict, List, Any, Optional

# Ensure package is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Define the test suites to run
INTEGRATION_TESTS = [
    "test_mcp_controller_mocked_integration",
    "test_mcp_controller_integration",
]

INTEGRATION_ANYIO_TESTS = [
    "test_mcp_controller_mocked_integration_anyio",
    "test_mcp_controller_integration_anyio",
]

END_TO_END_TESTS = [
    "test_mcp_end_to_end",
]

PERFORMANCE_TESTS = [
    "test_mcp_performance",
]

# Define colors for terminal output
COLORS = {
    "RED": "\033[91m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "MAGENTA": "\033[95m",
    "CYAN": "\033[96m",
    "WHITE": "\033[97m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
    "END": "\033[0m",
}


def print_header(title: str) -> None:
    """Print a formatted header."""
    header = f"{COLORS['BOLD']}{COLORS['CYAN']}{'=' * 80}{COLORS['END']}"
    title_line = f"{COLORS['BOLD']}{COLORS['CYAN']}{'=' * 3} {title} {'=' * (75 - len(title))}{COLORS['END']}"
    print(header)
    print(title_line)
    print(header)


def print_result(title: str, passed: int, failed: int, skipped: int) -> None:
    """Print a formatted result."""
    total = passed + failed + skipped
    if failed == 0:
        status_color = COLORS["GREEN"]
    else:
        status_color = COLORS["RED"]
    
    result_line = f"{COLORS['BOLD']}{status_color}RESULTS: {passed} passed, {failed} failed, {skipped} skipped{COLORS['END']}"
    coverage = (passed / (total - skipped)) * 100 if (total - skipped) > 0 else 0
    coverage_line = f"{COLORS['BOLD']}Coverage: {coverage:.1f}% ({passed}/{total - skipped}){COLORS['END']}"
    
    print(result_line)
    print(coverage_line)
    print()


def run_test_module(module_name: str, verbose: bool = False) -> Dict[str, int]:
    """Run a test module and return the results."""
    print(f"Running test module: {COLORS['BOLD']}{module_name}{COLORS['END']}")
    
    # Check if it's in the integration directory
    if module_name in INTEGRATION_TESTS or module_name in INTEGRATION_ANYIO_TESTS:
        module_path = f"test.integration.{module_name}"
    elif module_name in END_TO_END_TESTS:
        module_path = f"test.integration.{module_name}"
    else:
        module_path = f"test.{module_name}"
    
    # Create a test loader
    loader = unittest.TestLoader()
    
    try:
        # Try to load the test module
        module = __import__(module_path, fromlist=["*"])
        suite = loader.loadTestsFromModule(module)
        
        # Run the tests
        result = unittest.TextTestRunner(verbosity=2 if verbose else 1).run(suite)
        
        # Calculate results
        passed = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        failed = len(result.failures) + len(result.errors)
        skipped = len(result.skipped)
        
        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": result.testsRun
        }
    except (ImportError, AttributeError) as e:
        print(f"{COLORS['YELLOW']}Error loading module: {str(e)}{COLORS['END']}")
        return {
            "passed": 0,
            "failed": 0, 
            "skipped": 0,
            "total": 0,
            "error": str(e)
        }


def run_test_suite(test_modules: List[str], title: str, verbose: bool = False) -> Dict[str, Any]:
    """Run a full test suite and return the combined results."""
    print_header(title)
    
    combined_results = {
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "modules": {},
        "start_time": time.time(),
    }
    
    for module in test_modules:
        result = run_test_module(module, verbose)
        combined_results["passed"] += result.get("passed", 0)
        combined_results["failed"] += result.get("failed", 0)
        combined_results["skipped"] += result.get("skipped", 0)
        combined_results["modules"][module] = result
    
    combined_results["end_time"] = time.time()
    combined_results["duration"] = combined_results["end_time"] - combined_results["start_time"]
    
    print_result(
        title, 
        combined_results["passed"], 
        combined_results["failed"], 
        combined_results["skipped"]
    )
    
    return combined_results


def generate_report(results: Dict[str, Any], output_path: str) -> None:
    """Generate a comprehensive test report."""
    # Create report
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_duration": sum(suite["duration"] for suite in results.values()),
        "total_passed": sum(suite["passed"] for suite in results.values()),
        "total_failed": sum(suite["failed"] for suite in results.values()),
        "total_skipped": sum(suite["skipped"] for suite in results.values()),
        "suites": results
    }
    
    # Calculate overall status
    report["status"] = "SUCCESS" if report["total_failed"] == 0 else "FAILURE"
    
    # Write report to file
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"{COLORS['BOLD']}Test report saved to: {output_path}{COLORS['END']}")

def main():
    """Run the full test suite."""
    parser = argparse.ArgumentParser(description="Run MCP server tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--e2e", action="store_true", help="Run end-to-end tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--anyio", action="store_true", help="Run AnyIO tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--report", action="store_true", help="Generate test report")
    parser.add_argument("--output", default="test_results.json", help="Output file for test report")
    args = parser.parse_args()
    
    # Default to all tests if none specified
    if not any([args.integration, args.e2e, args.performance, args.anyio, args.all]):
        args.all = True
    
    # Start time
    start_time = time.time()
    
    # Initialize results
    results = {}
    
    # Run Integration Tests
    if args.all or args.integration:
        results["integration"] = run_test_suite(
            INTEGRATION_TESTS, 
            "INTEGRATION TESTS", 
            args.verbose
        )
    
    # Run Integration Tests (AnyIO)
    if args.all or (args.integration and args.anyio) or args.anyio:
        results["integration_anyio"] = run_test_suite(
            INTEGRATION_ANYIO_TESTS, 
            "INTEGRATION TESTS (ANYIO)", 
            args.verbose
        )
    
    # Run End-to-End Tests
    if args.all or args.e2e:
        results["e2e"] = run_test_suite(
            END_TO_END_TESTS, 
            "END-TO-END TESTS", 
            args.verbose
        )
    
    # Run Performance Tests
    if args.all or args.performance:
        results["performance"] = run_test_suite(
            PERFORMANCE_TESTS, 
            "PERFORMANCE TESTS", 
            args.verbose
        )
    
    # End time
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Print Summary
    print_header("TEST SUMMARY")
    
    total_passed = sum(suite["passed"] for suite in results.values())
    total_failed = sum(suite["failed"] for suite in results.values())
    total_skipped = sum(suite["skipped"] for suite in results.values())
    
    print(f"{COLORS['BOLD']}Total tests: {total_passed + total_failed + total_skipped}{COLORS['END']}")
    print(f"{COLORS['BOLD']}Total passed: {COLORS['GREEN']}{total_passed}{COLORS['END']}")
    print(f"{COLORS['BOLD']}Total failed: {COLORS['RED']}{total_failed}{COLORS['END']}")
    print(f"{COLORS['BOLD']}Total skipped: {COLORS['YELLOW']}{total_skipped}{COLORS['END']}")
    print(f"{COLORS['BOLD']}Total duration: {total_duration:.2f} seconds{COLORS['END']}")
    
    # Overall status
    status = "SUCCESS" if total_failed == 0 else "FAILURE"
    status_color = COLORS["GREEN"] if status == "SUCCESS" else COLORS["RED"]
    print(f"{COLORS['BOLD']}Overall status: {status_color}{status}{COLORS['END']}")
    
    # Generate report if requested
    if args.report:
        generate_report(results, args.output)
    
    # Return exit code
    if total_failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()