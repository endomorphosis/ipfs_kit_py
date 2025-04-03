#!/usr/bin/env python3
"""
Test runner for IPFS Kit mocked tests.

This script runs all the mocked test files using pytest, producing both
console output and an HTML report.

Usage:
    python run_mocked_tests.py           # Run all mocked tests
    python run_mocked_tests.py <file>    # Run tests from specific file
"""

import datetime
import os
import subprocess
import sys


def main():
    """Run the mocked tests."""
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Set up output directory for reports
    reports_dir = os.path.join(script_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # Generate timestamp for the report filename
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(reports_dir, f"test_report_{timestamp}.html")

    # Determine which test files to run
    if len(sys.argv) > 1:
        # Run specific test file
        test_file = sys.argv[1]
        if not test_file.startswith("/"):
            test_file = os.path.join(script_dir, test_file)
        test_files = [test_file]
    else:
        # Run all mocked test files
        test_files = [
            os.path.join(script_dir, "test_ipfs_py_mocked.py"),
            os.path.join(script_dir, "test_ipfs_kit_mocked.py"),
            os.path.join(script_dir, "test_storacha_kit_mocked.py"),
        ]

    # Build pytest command
    cmd = [
        "python",
        "-m",
        "pytest",
        "-v",  # Verbose output
        "--html=" + report_file,  # Generate HTML report
        "--self-contained-html",  # Make the HTML self-contained
        "--cov=ipfs_kit_py",  # Measure code coverage
        "--cov-report=html:" + os.path.join(reports_dir, "coverage"),  # HTML coverage report
        "--cov-report=term",  # Terminal coverage report
    ]
    cmd.extend(test_files)

    print(f"Running tests: {' '.join(cmd)}")

    # Run the tests
    try:
        subprocess.run(cmd, check=True)
        print(f"\nHTML report generated: {report_file}")
        print(f"Coverage report: {os.path.join(reports_dir, 'coverage/index.html')}")
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with exit code {e.returncode}")
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
