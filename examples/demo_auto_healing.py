#!/usr/bin/env python3
"""
Demo script showing the auto-healing feature in action.

This script intentionally triggers different types of errors to demonstrate
how the auto-healing system captures them and creates GitHub issues.
"""

import sys
import os

# Add parent directory to path to import ipfs_kit_py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ipfs_kit_py.auto_heal.config import AutoHealConfig
from ipfs_kit_py.auto_heal.error_capture import ErrorCapture
from ipfs_kit_py.auto_heal.github_issue_creator import GitHubIssueCreator


def demo_error_capture():
    """Demonstrate error capture functionality."""
    print("=" * 60)
    print("Demo 1: Error Capture")
    print("=" * 60)
    
    error_capture = ErrorCapture(max_log_lines=20)
    
    try:
        # Trigger a test error
        raise ValueError("This is a demonstration error for auto-healing")
    except Exception as e:
        captured = error_capture.capture_error(
            e,
            command="ipfs-kit demo test",
            arguments={'demo': True, 'test_mode': True}
        )
        
        print("\n✓ Error captured successfully!")
        print(f"  Error Type: {captured.error_type}")
        print(f"  Error Message: {captured.error_message}")
        print(f"  Timestamp: {captured.timestamp}")
        print(f"  Command: {captured.command}")
        print(f"\n📋 Formatted for GitHub Issue:")
        print("-" * 60)
        issue_body = captured.format_for_issue(max_log_lines=10)
        # Print first 500 chars
        print(issue_body[:500] + "...")
        print("-" * 60)


def demo_config():
    """Demonstrate configuration management."""
    print("\n" + "=" * 60)
    print("Demo 2: Configuration Management")
    print("=" * 60)
    
    # Create a test configuration
    config = AutoHealConfig(
        enabled=True,
        github_repo="owner/repo",
        max_log_lines=50,
    )
    
    print("\n✓ Configuration created:")
    print(f"  Enabled: {config.enabled}")
    print(f"  Repository: {config.github_repo}")
    print(f"  Max log lines: {config.max_log_lines}")
    print(f"  Include stack trace: {config.include_stack_trace}")
    print(f"  Auto-create issues: {config.auto_create_issues}")
    print(f"  Issue labels: {', '.join(config.issue_labels)}")
    
    print(f"\n  Is Configured: {config.is_configured()}")
    if not config.is_configured():
        print("  ⚠️  Note: Needs GITHUB_TOKEN to be fully configured")


def demo_issue_format():
    """Demonstrate issue formatting."""
    print("\n" + "=" * 60)
    print("Demo 3: GitHub Issue Formatting")
    print("=" * 60)
    
    config = AutoHealConfig(
        enabled=True,
        github_token='demo_token',
        github_repo='owner/repo'
    )
    
    creator = GitHubIssueCreator(config)
    
    # Create a sample error
    from ipfs_kit_py.auto_heal.error_capture import CapturedError
    
    error = CapturedError(
        error_type='ConnectionError',
        error_message='Failed to connect to IPFS daemon on localhost:5001',
        stack_trace='Traceback (most recent call last):\n  File "test.py", line 10, in <module>\n    connect_to_ipfs()\nConnectionError: Failed to connect',
        timestamp='2024-01-31T10:00:00Z',
        command='ipfs-kit daemon start',
        arguments={'port': 5001},
        environment={'IPFS_PATH': '/home/user/.ipfs'},
        log_context=['Starting IPFS daemon...', 'Checking port availability...', 'ERROR: Port already in use'],
        working_directory='/home/user/project',
        python_version='3.12.0'
    )
    
    title = creator._format_issue_title(error)
    
    print("\n✓ Issue title formatted:")
    print(f"  {title}")
    
    print("\n✓ Issue body would contain:")
    print("  - Error type and message")
    print("  - Full stack trace")
    print("  - Command that caused the error")
    print("  - Arguments passed")
    print("  - Log context (last N lines)")
    print("  - Environment variables")
    print("  - System information")


def demo_error_patterns():
    """Demonstrate different error pattern recognition."""
    print("\n" + "=" * 60)
    print("Demo 4: Error Pattern Recognition")
    print("=" * 60)
    
    test_errors = [
        ("ModuleNotFoundError: No module named 'flask'", "Missing Dependency"),
        ("FileNotFoundError: [Errno 2] No such file or directory: 'config.json'", "Missing File"),
        ("PermissionError: [Errno 13] Permission denied: '/etc/ipfs'", "Permission Error"),
        ("ConnectionRefusedError: [Errno 111] Connection refused", "Connection Error"),
        ("AttributeError: 'NoneType' object has no attribute 'get'", "Logic Error"),
    ]
    
    print("\n✓ The system recognizes these error patterns:")
    print()
    
    for error_msg, pattern_type in test_errors:
        print(f"  Pattern: {pattern_type}")
        print(f"  Example: {error_msg}")
        
        # Determine if fixable
        fixable = pattern_type in ["Missing Dependency", "Missing File", "Permission Error", "Connection Error"]
        if fixable:
            print(f"  Auto-fix: ✓ Can generate automatic fix")
        else:
            print(f"  Auto-fix: 🤖 Will invoke GitHub Copilot")
        print()


def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("IPFS-Kit Auto-Healing Feature Demo")
    print("=" * 60)
    
    demo_error_capture()
    demo_config()
    demo_issue_format()
    demo_error_patterns()
    
    print("\n" + "=" * 60)
    print("Demo Complete!")
    print("=" * 60)
    print("\n📚 For more information, see:")
    print("  - docs/AUTO_HEALING.md - Complete documentation")
    print("  - docs/AUTO_HEALING_QUICKSTART.md - Quick start guide")
    print("\n💡 To enable auto-healing:")
    print("  1. Set GITHUB_TOKEN environment variable")
    print("  2. Run: ipfs-kit autoheal enable --github-repo owner/repo")
    print("  3. Errors will now automatically create GitHub issues!")
    print()


if __name__ == '__main__':
    main()
