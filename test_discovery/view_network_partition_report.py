#!/usr/bin/env python3
"""
View the network partition test report in a more readable format.
"""

import os
import sys
import json
import datetime

def format_duration(seconds):
    """Format duration in seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds:.2f} seconds"
    
    minutes = int(seconds // 60)
    seconds = seconds % 60
    return f"{minutes} min {seconds:.2f} sec"

def parse_timestamp(timestamp):
    """Parse ISO timestamp string to datetime object."""
    try:
        return datetime.datetime.fromisoformat(timestamp)
    except ValueError:
        return None

def format_timestamp(timestamp):
    """Format timestamp as a readable string."""
    dt = parse_timestamp(timestamp)
    if not dt:
        return timestamp
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def print_test_results(report_data):
    """Print test results in a readable format."""
    # Print summary
    summary = report_data["summary"]
    print("\nNetwork Partition Test Summary")
    print("=" * 80)
    print(f"Total tests:      {summary['total_tests']}")
    print(f"Successful tests: {summary['successful_tests']}")
    print(f"Failed tests:     {summary['failed_tests']}")
    print(f"Total duration:   {format_duration(summary['total_duration'])}")
    print(f"Timestamp:        {format_timestamp(summary['timestamp'])}")
    print()
    
    # Print individual test results
    print("Individual Test Results")
    print("=" * 80)
    
    for i, test in enumerate(report_data["tests"], 1):
        status = "PASS" if test["success"] else "FAIL"
        print(f"{i}. {test['test_method']}: {status}")
        print(f"   Duration: {format_duration(test['duration'])}")
        print(f"   Timestamp: {format_timestamp(test['timestamp'])}")
        if not test["success"]:
            print(f"   Failures: {test['failures']}")
            print(f"   Errors: {test['errors']}")
        print()
    
    # Print result summary
    if summary["failed_tests"] == 0:
        print("SUCCESS: All network partition tests passed!")
    else:
        print(f"FAILURE: {summary['failed_tests']} of {summary['total_tests']} tests failed.")

if __name__ == "__main__":
    # Determine report path
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 
        "network_partition_test_report.json"
    )
    
    # Check if alternative report file is provided
    if len(sys.argv) > 1:
        report_path = sys.argv[1]
    
    # Check if report file exists
    if not os.path.exists(report_path):
        print(f"Error: Report file not found at {report_path}")
        print("Run run_all_network_partition_tests.py first to generate the report.")
        sys.exit(1)
    
    # Load and parse report
    try:
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        # Print report
        print(f"Network Partition Test Report: {report_path}")
        print_test_results(report_data)
        
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in report file {report_path}")
        sys.exit(1)
    except KeyError as e:
        print(f"Error: Missing key in report file: {e}")
        sys.exit(1)