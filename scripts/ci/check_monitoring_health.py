#!/usr/bin/env python3
"""
Monitoring System Health Check

This script checks if all monitoring components are properly installed and configured.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def check_item(description, check_func):
    """Check an item and print status."""
    try:
        result = check_func()
        if result:
            print(f"✅ {description}")
            return True
        else:
            print(f"❌ {description}")
            return False
    except Exception as e:
        print(f"❌ {description}: {str(e)}")
        return False


def check_python():
    """Check if Python is available."""
    return sys.version_info >= (3, 8)


def check_gh_cli():
    """Check if GitHub CLI is installed."""
    return shutil.which("gh") is not None


def check_gh_auth():
    """Check if GitHub CLI is authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except:
        return False


def check_script_exists(script_path):
    """Check if a script exists and is executable."""
    path = Path(script_path)
    return path.exists() and os.access(path, os.X_OK)


def check_log_dir_writable(log_dir):
    """Check if log directory is writable."""
    try:
        path = Path(log_dir)
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".test_write"
        test_file.write_text("test")
        test_file.unlink()
        return True
    except:
        return False


def main():
    print("=" * 60)
    print("Monitoring System Health Check")
    print("=" * 60)
    print()
    
    checks = []
    
    # Check Python
    print("Python Environment:")
    checks.append(check_item(
        f"Python 3.8+ (found: {sys.version.split()[0]})",
        check_python
    ))
    print()
    
    # Check GitHub CLI
    print("GitHub CLI:")
    checks.append(check_item(
        "GitHub CLI (gh) installed",
        check_gh_cli
    ))
    checks.append(check_item(
        "GitHub CLI authenticated",
        check_gh_auth
    ))
    print()
    
    # Check monitoring scripts
    print("Monitoring Scripts:")
    scripts_dir = Path(__file__).parent
    
    checks.append(check_item(
        "trigger_and_monitor_workflow.py",
        lambda: check_script_exists(scripts_dir / "trigger_and_monitor_workflow.py")
    ))
    checks.append(check_item(
        "monitor_first_install.py",
        lambda: check_script_exists(scripts_dir / "monitor_first_install.py")
    ))
    checks.append(check_item(
        "monitor_arm64_installation.py",
        lambda: check_script_exists(scripts_dir / "monitor_arm64_installation.py")
    ))
    checks.append(check_item(
        "verify_arm64_dependencies.py",
        lambda: check_script_exists(scripts_dir / "verify_arm64_dependencies.py")
    ))
    checks.append(check_item(
        "installation_wrapper.sh",
        lambda: check_script_exists(scripts_dir / "installation_wrapper.sh")
    ))
    checks.append(check_item(
        "demo_workflow_monitoring.sh",
        lambda: check_script_exists(scripts_dir / "demo_workflow_monitoring.sh")
    ))
    print()
    
    # Check log directories
    print("Log Directories:")
    checks.append(check_item(
        "/tmp/workflow_monitor writable",
        lambda: check_log_dir_writable("/tmp/workflow_monitor")
    ))
    checks.append(check_item(
        "/tmp/install_monitor writable",
        lambda: check_log_dir_writable("/tmp/install_monitor")
    ))
    checks.append(check_item(
        "/tmp/arm64_monitor writable",
        lambda: check_log_dir_writable("/tmp/arm64_monitor")
    ))
    checks.append(check_item(
        "/tmp/arm64_install_logs writable",
        lambda: check_log_dir_writable("/tmp/arm64_install_logs")
    ))
    print()
    
    # Check documentation
    print("Documentation:")
    repo_root = scripts_dir.parent.parent
    checks.append(check_item(
        "WORKFLOW_MONITORING.md",
        lambda: (scripts_dir / "WORKFLOW_MONITORING.md").exists()
    ))
    checks.append(check_item(
        "MONITORING_GUIDE.md",
        lambda: (repo_root / "MONITORING_GUIDE.md").exists()
    ))
    checks.append(check_item(
        "ARM64_MONITORING_GUIDE.md",
        lambda: (repo_root / "ARM64_MONITORING_GUIDE.md").exists()
    ))
    print()
    
    # Summary
    passed = sum(checks)
    total = len(checks)
    
    print("=" * 60)
    print(f"Health Check Summary: {passed}/{total} checks passed")
    print("=" * 60)
    print()
    
    if passed == total:
        print("✅ All monitoring systems are properly configured!")
        print()
        print("Next steps:")
        print("  1. Run: ./scripts/ci/demo_workflow_monitoring.sh")
        print("  2. Review: MONITORING_GUIDE.md")
        return 0
    else:
        print("⚠️ Some checks failed. Please address the issues above.")
        print()
        
        if not check_gh_cli():
            print("To install GitHub CLI:")
            print("  Visit: https://cli.github.com/")
        elif not check_gh_auth():
            print("To authenticate GitHub CLI:")
            print("  Run: gh auth login")
        
        print()
        print("For more information, see:")
        print("  - MONITORING_GUIDE.md")
        print("  - scripts/ci/WORKFLOW_MONITORING.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
