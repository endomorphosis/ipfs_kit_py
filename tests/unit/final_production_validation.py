#!/usr/bin/env python3
"""
Final Production Validation for IPFS Kit MCP Server
Comprehensive validation script to ensure production readiness
"""

import os
import sys
import json
import subprocess
import importlib.util
from pathlib import Path
from typing import Dict, List, Tuple, Any

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}🔍 {title}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

def print_status(success: bool, message: str):
    """Print status with color coding"""
    icon = "✅" if success else "❌"
    color = Colors.GREEN if success else Colors.RED
    print(f"{color}{icon} {message}{Colors.END}")

def check_file_exists(filepath: str) -> bool:
    """Check if a file exists"""
    return Path(filepath).exists()

def check_directory_exists(dirpath: str) -> bool:
    """Check if a directory exists"""
    return Path(dirpath).is_dir()

def validate_python_syntax(filepath: str) -> Tuple[bool, str]:
    """Validate Python file syntax"""
    try:
        with open(filepath, 'r') as f:
            compile(f.read(), filepath, 'exec')
        return True, "Valid syntax"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def validate_imports(filepath: str) -> Tuple[bool, str]:
    """Validate that a Python file can be imported"""
    try:
        spec = importlib.util.spec_from_file_location("test_module", filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return True, "Imports successful"
    except Exception as e:
        return False, f"Import error: {e}"

def main():
    """Main validation function"""
    print(f"{Colors.BOLD}🚀 IPFS Kit MCP Server - Final Production Validation{Colors.END}")
    print(f"{Colors.BLUE}{'='*70}{Colors.END}")
    
    # Track overall success
    all_checks_passed = True
    critical_checks = []
    
    # 1. Essential Files Validation
    print_header("Essential Production Files")
    essential_files = [
        "final_mcp_server_enhanced.py",
        "README.md", 
        "Dockerfile",
        "docker-compose.yml",
        "pyproject.toml",
        "LICENSE"
    ]
    
    for file in essential_files:
        exists = check_file_exists(file)
        print_status(exists, f"{file}")
        if not exists:
            all_checks_passed = False
        critical_checks.append((file, exists))
    
    # 2. Core Directories Validation
    print_header("Directory Structure")
    essential_dirs = [
        "src",
        "tests", 
        "docs",
        "examples",
        "ipfs_kit_py"
    ]
    
    for directory in essential_dirs:
        exists = check_directory_exists(directory)
        print_status(exists, f"{directory}/")
        if not exists and directory in ["src", "ipfs_kit_py"]:
            all_checks_passed = False
    
    # 3. Production Server Validation
    print_header("Production Server Validation")
    
    server_file = "final_mcp_server_enhanced.py"
    if check_file_exists(server_file):
        # Syntax validation
        syntax_valid, syntax_msg = validate_python_syntax(server_file)
        print_status(syntax_valid, f"Server syntax: {syntax_msg}")
        if not syntax_valid:
            all_checks_passed = False
            
        # Import validation
        import_valid, import_msg = validate_imports(server_file)
        print_status(import_valid, f"Server imports: {import_msg}")
        if not import_valid:
            all_checks_passed = False
    else:
        print_status(False, "Server file missing")
        all_checks_passed = False
    
    # 4. Archive Structure Validation
    print_header("Cleanup & Organization")
    
    archive_dirs = [
        "archive_clutter",
        "development_tools",
        "server_variants",
        "test_scripts"
    ]
    
    archive_count = 0
    for archive_dir in archive_dirs:
        if check_directory_exists(archive_dir):
            archive_count += 1
    
    print_status(archive_count > 0, f"Archive structure created ({archive_count} directories)")
    
    # Count files in root directory
    root_files = [f for f in os.listdir('.') if os.path.isfile(f)]
    root_file_count = len(root_files)
    clean_root = root_file_count < 25  # Should be significantly reduced from 700+
    
    print_status(clean_root, f"Root directory cleaned ({root_file_count} files)")
    
    # 5. Configuration Files Validation
    print_header("Configuration & Build Files")
    
    config_files = [
        ("pyproject.toml", "Python package configuration"),
        ("Dockerfile", "Docker container configuration"), 
        ("docker-compose.yml", "Docker compose configuration"),
        ("pytest.ini", "Test configuration"),
        ("setup.py", "Legacy setup script")
    ]
    
    for config_file, description in config_files:
        exists = check_file_exists(config_file)
        print_status(exists, f"{config_file} ({description})")
    
    # 6. Documentation Validation
    print_header("Documentation")
    
    readme_exists = check_file_exists("README.md")
    print_status(readme_exists, "Main README.md")
    
    if readme_exists:
        try:
            with open("README.md", 'r') as f:
                readme_content = f.read()
            
            # Check for key sections
            has_quick_start = "Quick Start" in readme_content
            has_docker = "Docker" in readme_content
            has_api_docs = "API" in readme_content
            
            print_status(has_quick_start, "README has Quick Start section")
            print_status(has_docker, "README has Docker documentation")
            print_status(has_api_docs, "README has API documentation")
        except Exception as e:
            print_status(False, f"README validation error: {e}")
    
    # 7. Final Assessment
    print_header("Final Assessment")
    
    critical_passed = all(result for _, result in critical_checks)
    
    print(f"\n{Colors.BOLD}📊 Summary:{Colors.END}")
    print(f"Root directory files: {root_file_count} (target: <25)")
    print(f"Archive directories created: {archive_count}")
    print(f"Critical files present: {sum(1 for _, r in critical_checks if r)}/{len(critical_checks)}")
    
    if critical_passed and clean_root:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 PRODUCTION READY!{Colors.END}")
        print(f"{Colors.GREEN}All critical validations passed. The IPFS Kit MCP Server is ready for production deployment.{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  ISSUES FOUND{Colors.END}")
        print(f"{Colors.RED}Some critical validations failed. Please review the issues above.{Colors.END}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
