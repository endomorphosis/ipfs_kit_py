#!/usr/bin/env python3
"""
Comprehensive test runner for IPFS Kit Python.

This script orchestrates running tests across all components of the IPFS Kit
Python project, collecting results and generating reports.
"""

import os
import sys
import subprocess
import argparse
import logging
from pathlib import Path
import datetime
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_run.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("test_runner")

# Define test categories
TEST_CATEGORIES = {
    "core": ["test_basic.py", "test/test_*core*.py", "test/test_ipfs_*.py", "test/test_ipfs_core.py"],
    "mcp": ["test_mcp_*.py", "test/test_mcp_*.py", "test/test_mcp_comprehensive.py"],
    "storage": ["test/test_*storage*.py", "test/test_backend*.py", "test/test_storage_backends.py"],
    "fsspec": ["test/test_*fsspec*.py", "test/test_fs_*.py", "test/test_fsspec_integration.py"],
    "api": ["test/test_*api*.py", "test/test_high_level*.py", "test/test_http_api.py"],
    "tools": ["test/test_*tools*.py", "test/test_tool_*.py"],
    "vfs": ["test/test_*vfs*.py", "test/test_mcp_vfs_integration.py", "comprehensive_mcp_test.py"],
    "integrations": ["test/test_integration/*.py", "tests/integration/*.py"]
}

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run comprehensive tests for IPFS Kit Python")
    parser.add_argument(
        "--category",
        choices=list(TEST_CATEGORIES.keys()) + ["all"],
        default="all",
        help="Test category to run (default: all)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel where possible",
    )
    parser.add_argument(
        "--junit-xml",
        action="store_true",
        help="Generate JUnit XML report",
    )
    parser.add_argument(
        "--html-report",
        action="store_true",
        help="Generate HTML report",
    )
    parser.add_argument(
        "--report-dir",
        default="test_reports",
        help="Directory to store test reports (default: test_reports)",
    )
    return parser.parse_args()

def run_test_category(category, args):
    """Run tests for a specific category."""
    report_dir = Path(args.report_dir)
    report_dir.mkdir(exist_ok=True, parents=True)
    
    if category not in TEST_CATEGORIES:
        logger.error(f"Unknown test category: {category}")
        return False

    logger.info(f"Running tests for category: {category}")
    patterns = TEST_CATEGORIES[category]
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add patterns
    for pattern in patterns:
        cmd.extend([pattern])
    
    # Add flags
    if args.verbose:
        cmd.append("-v")
    
    if args.parallel:
        cmd.append("-xvs")
    
    if args.junit_xml:
        cmd.extend(["--junitxml", str(report_dir / f"{category}_results.xml")])
    
    if args.html_report:
        cmd.extend(["--html", str(report_dir / f"{category}_report.html"), "--self-contained-html"])
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        # Run the command
        result = subprocess.run(
            cmd,
            check=False,  # Don't raise exception on test failure
            capture_output=True,
            text=True
        )
        
        # Log output
        logger.info(f"{category} tests complete with exit code {result.returncode}")
        logger.info("STDOUT: " + result.stdout)
        
        if result.stderr:
            logger.error("STDERR: " + result.stderr)
        
        # Save output to file
        with open(report_dir / f"{category}_output.txt", "w") as f:
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        logger.exception(f"Error running tests for category {category}: {e}")
        return False

def main():
    """Main entry point for the test runner."""
    args = parse_args()
    
    # Create timestamp for this test run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path(args.report_dir) / timestamp
    args.report_dir = str(report_dir)
    report_dir.mkdir(exist_ok=True, parents=True)
    
    logger.info(f"Starting comprehensive test run at {timestamp}")
    
    results = {}
    if args.category == "all":
        for category in TEST_CATEGORIES:
            results[category] = run_test_category(category, args)
    else:
        results[args.category] = run_test_category(args.category, args)
    
    # Generate summary
    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)
    
    logger.info(f"Test run complete: {success_count}/{total_count} categories successful")
    for category, success in results.items():
        logger.info(f"  {category}: {'SUCCESS' if success else 'FAILURE'}")
    
    # Save summary to file
    summary = {
        "timestamp": timestamp,
        "success_rate": f"{success_count}/{total_count}",
        "categories": {category: "success" if success else "failure" for category, success in results.items()}
    }
    
    with open(report_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main())
