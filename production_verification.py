#!/usr/bin/env python3
"""
Production Verification Script for IPFS Kit MCP Server
======================================================

This script verifies that the production MCP server is ready for deployment.
"""

import os
import sys
import json
import subprocess
import requests
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

def check_file_exists(file_path: str) -> bool:
    """Check if a file exists."""
    return Path(file_path).exists()

def check_python_syntax(file_path: str) -> bool:
    """Check Python syntax of a file."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", file_path],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def check_docker_files() -> Dict[str, bool]:
    """Check Docker configuration files."""
    return {
        "Dockerfile": check_file_exists("Dockerfile"),
        "docker-compose.yml": check_file_exists("docker-compose.yml"),
    }

def check_package_files() -> Dict[str, bool]:
    """Check package configuration files."""
    return {
        "pyproject.toml": check_file_exists("pyproject.toml"),
        "setup.py": check_file_exists("setup.py"),
        "README.md": check_file_exists("README.md"),
        "LICENSE": check_file_exists("LICENSE"),
    }

def test_server_import() -> bool:
    """Test if the server can be imported."""
    try:
        import final_mcp_server_enhanced
        return True
    except Exception as e:
        print(f"Import error: {e}")
        return False

def run_production_verification():
    """Run complete production verification."""
    print("🚀 IPFS Kit MCP Server - Production Verification")
    print("=" * 60)
    
    # Track results
    results = {}
    
    # 1. Check core production server
    print("\n📋 1. Core Production Server")
    print("-" * 30)
    
    server_file = "final_mcp_server_enhanced.py"
    results["server_exists"] = check_file_exists(server_file)
    print(f"✅ Server file exists: {results['server_exists']}")
    
    if results["server_exists"]:
        results["server_syntax"] = check_python_syntax(server_file)
        print(f"✅ Server syntax valid: {results['server_syntax']}")
        
        results["server_import"] = test_server_import()
        print(f"✅ Server imports: {results['server_import']}")
    else:
        results["server_syntax"] = False
        results["server_import"] = False
    
    # 2. Check Docker files
    print("\n🐳 2. Docker Configuration")
    print("-" * 30)
    
    docker_results = check_docker_files()
    results.update(docker_results)
    for file, exists in docker_results.items():
        print(f"✅ {file}: {exists}")
    
    # 3. Check package files
    print("\n📦 3. Package Configuration")
    print("-" * 30)
    
    package_results = check_package_files()
    results.update(package_results)
    for file, exists in package_results.items():
        print(f"✅ {file}: {exists}")
    
    # 4. Check directory structure
    print("\n📁 4. Directory Structure")
    print("-" * 30)
    
    key_dirs = [
        "src/",
        "tests/",
        "docs/",
        "examples/",
        ".github/",
        "ipfs_kit_py/"
    ]
    
    for dir_name in key_dirs:
        exists = Path(dir_name).is_dir()
        results[f"dir_{dir_name.rstrip('/')}"] = exists
        print(f"✅ {dir_name}: {exists}")
    
    # 5. Overall assessment
    print("\n🎯 5. Overall Assessment")
    print("-" * 30)
    
    critical_checks = [
        "server_exists",
        "server_syntax",
        "server_import",
        "Dockerfile",
        "docker-compose.yml",
        "pyproject.toml",
        "README.md"
    ]
    
    critical_passed = sum(results.get(check, False) for check in critical_checks)
    total_critical = len(critical_checks)
    
    print(f"Critical checks passed: {critical_passed}/{total_critical}")
    
    if critical_passed == total_critical:
        print("🎉 PRODUCTION READY! All critical checks passed.")
        return True
    else:
        print("⚠️ Production readiness incomplete. Please address failed checks.")
        return False

if __name__ == "__main__":
    success = run_production_verification()
    sys.exit(0 if success else 1)
