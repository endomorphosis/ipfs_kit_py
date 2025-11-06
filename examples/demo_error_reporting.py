#!/usr/bin/env python3
"""
Demonstration script for error reporting system.

This script demonstrates how errors are automatically reported as GitHub issues.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def demo_error_reporting():
    """Demonstrate the error reporting system."""
    
    print("=" * 70)
    print("IPFS Kit - Automatic Error Reporting Demonstration")
    print("=" * 70)
    print()
    
    # Check if GitHub token is set
    github_token = os.environ.get("GITHUB_TOKEN")
    
    if not github_token:
        print("⚠️  WARNING: GITHUB_TOKEN not set")
        print()
        print("To enable error reporting, set the following environment variables:")
        print("  export GITHUB_TOKEN=your_github_personal_access_token")
        print("  export GITHUB_REPO_OWNER=endomorphosis")
        print("  export GITHUB_REPO_NAME=ipfs_kit_py")
        print()
        print("Get a token from: https://github.com/settings/tokens")
        print("Required scope: 'repo'")
        print()
        print("For this demo, we'll simulate error reporting without actually")
        print("creating GitHub issues.")
        print()
    else:
        print("✓ GITHUB_TOKEN is set")
        print(f"  Repository: {os.environ.get('GITHUB_REPO_OWNER', 'endomorphosis')}/{os.environ.get('GITHUB_REPO_NAME', 'ipfs_kit_py')}")
        print()
    
    # Import error reporting (without triggering full ipfs_kit_py import)
    import importlib.util
    
    # Load error_reporter module
    spec = importlib.util.spec_from_file_location(
        'error_reporter',
        os.path.join(os.path.dirname(__file__), '..', 'ipfs_kit_py', 'error_reporter.py')
    )
    error_reporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(error_reporter)
    
    # Initialize reporter
    print("Initializing error reporter...")
    reporter = error_reporter.GitHubIssueReporter(
        github_token=github_token,
        repo_owner=os.environ.get("GITHUB_REPO_OWNER", "endomorphosis"),
        repo_name=os.environ.get("GITHUB_REPO_NAME", "ipfs_kit_py"),
        enabled=bool(github_token),
    )
    
    if reporter.enabled:
        print("✓ Error reporter initialized and enabled")
    else:
        print("✓ Error reporter initialized (disabled - no token)")
    print()
    
    # Example 1: Format an error report
    print("-" * 70)
    print("Example 1: Error Report Formatting")
    print("-" * 70)
    print()
    
    error_info = {
        "error_type": "RuntimeError",
        "error_message": "Storage backend connection failed after 3 retries",
        "timestamp": "2025-11-06T08:30:00.123Z",
        "traceback": """Traceback (most recent call last):
  File "ipfs_kit_py/storage_manager.py", line 142, in connect
    self._establish_connection()
  File "ipfs_kit_py/storage_manager.py", line 89, in _establish_connection
    raise RuntimeError("Storage backend connection failed after 3 retries")
RuntimeError: Storage backend connection failed after 3 retries""",
        "environment": {
            "python_version": "3.12.0",
            "platform": "linux",
            "component": "Storage Manager",
        },
        "details": {
            "backend": "s3",
            "region": "us-east-1",
            "retry_count": 3,
            "last_error": "Connection timeout",
        },
    }
    
    title, body = reporter._format_error_report(error_info, "MCP Server")
    
    print("Issue Title:")
    print(f"  {title}")
    print()
    print("Issue Body (preview):")
    print("-" * 70)
    print(body[:500] + "...")
    print("-" * 70)
    print()
    
    # Example 2: Error hash and deduplication
    print("-" * 70)
    print("Example 2: Error Deduplication")
    print("-" * 70)
    print()
    
    error_hash = reporter._get_error_hash(error_info)
    print(f"Error hash: {error_hash}")
    print()
    print("The error reporter uses hashing to prevent duplicate issues.")
    print("The same error will only create one issue (with 24-hour cooldown).")
    print()
    
    # Example 3: Rate limiting
    print("-" * 70)
    print("Example 3: Rate Limiting")
    print("-" * 70)
    print()
    
    can_report = reporter._check_rate_limit()
    print(f"Can report errors: {can_report}")
    print(f"Maximum reports per hour: {reporter.max_reports_per_hour}")
    print()
    print("Rate limiting prevents spam from error loops.")
    print()
    
    # Summary
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print("The error reporting system provides:")
    print("  ✓ Automatic GitHub issue creation from runtime errors")
    print("  ✓ Support for Python, MCP, and JavaScript errors")
    print("  ✓ Deduplication to prevent duplicate issues")
    print("  ✓ Rate limiting to prevent spam")
    print("  ✓ Rich error context (traceback, environment, details)")
    print()
    
    if not github_token:
        print("To enable error reporting in your application:")
        print()
        print("  from ipfs_kit_py.init_error_reporting import setup_error_reporting")
        print()
        print("  setup_error_reporting(")
        print("      github_token=os.environ.get('GITHUB_TOKEN'),")
        print("      enabled=True,")
        print("  )")
        print()
    else:
        print("Error reporting is ENABLED and ready to use!")
        print()
        print("Test it by running:")
        print("  python examples/error_reporting_example.py")
        print()
    
    print("Full documentation: docs/error_reporting.md")
    print("=" * 70)


if __name__ == "__main__":
    demo_error_reporting()
