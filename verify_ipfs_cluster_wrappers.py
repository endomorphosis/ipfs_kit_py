#!/usr/bin/env python3
"""
IPFS Cluster Wrapper Verification Script

This script provides a quick verification that both the ipfs_cluster_service
and ipfs_cluster_follow wrapper scripts are properly configured and working.
It tests basic imports and module functionality.
"""

import os
import sys
import subprocess
import importlib.util
from typing import Dict, Any, Tuple

def print_header(text: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)

def run_command(cmd: list) -> Tuple[int, str, str]:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    process = subprocess.run(cmd, capture_output=True, text=True)
    return process.returncode, process.stdout, process.stderr

def check_module_import(module_name: str) -> Dict[str, Any]:
    """Check if a module can be imported."""
    result = {"name": module_name, "importable": False, "error": None}
    
    try:
        # Try to import the module
        if "." in module_name:
            # For submodules, use importlib
            parent_module, child_module = module_name.rsplit(".", 1)
            importlib.import_module(module_name)
        else:
            # For top-level modules, use standard import
            exec(f"import {module_name}")
        
        result["importable"] = True
        print(f"✅ Successfully imported {module_name}")
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ Failed to import {module_name}: {e}")
    
    return result

def verify_wrapper_script(script_path: str) -> Dict[str, Any]:
    """Verify a wrapper script."""
    result = {
        "script": script_path,
        "exists": os.path.exists(script_path),
        "executable": os.access(script_path, os.X_OK),
        "help_works": False,
        "fake_daemon_works": False,
        "debug_works": False,
        "errors": []
    }
    
    if not result["exists"]:
        result["errors"].append(f"Script does not exist: {script_path}")
        return result
        
    # Test help flag
    returncode, stdout, stderr = run_command(["python", script_path, "--help"])
    result["help_works"] = returncode == 0 and "usage:" in stdout
    if not result["help_works"]:
        result["errors"].append("Help flag failed")
    else:
        print(f"✅ Help flag works")
        
    # Test fake daemon mode
    returncode, stdout, stderr = run_command(["python", script_path, "--fake-daemon"])
    result["fake_daemon_works"] = returncode == 0 and "Running in fake daemon mode" in stdout
    if not result["fake_daemon_works"]:
        result["errors"].append("Fake daemon mode failed")
    else:
        print(f"✅ Fake daemon mode works")
        
    # Test debug mode
    returncode, stdout, stderr = run_command(["python", script_path, "--debug", "--fake-daemon"])
    result["debug_works"] = returncode == 0 and "Debug logging enabled" in stdout
    if not result["debug_works"]:
        result["errors"].append("Debug mode failed")
    else:
        print(f"✅ Debug mode works")
        
    return result

def main():
    """Main verification function."""
    print_header("IPFS Cluster Wrapper Verification")
    
    # Ensure current directory is in path
    sys.path.insert(0, os.getcwd())
    
    # Check for required modules
    print_header("Checking Module Imports")
    modules = [
        "ipfs_kit_py",
        "ipfs_kit_py.ipfs_cluster_service",
        "ipfs_kit_py.ipfs_cluster_follow"
    ]
    import_results = {module: check_module_import(module) for module in modules}
    
    # Verify wrapper scripts
    print_header("Checking Wrapper Scripts")
    scripts = [
        "run_ipfs_cluster_service.py",
        "run_ipfs_cluster_follow.py"
    ]
    script_results = {script: verify_wrapper_script(script) for script in scripts}
    
    # Check for daemon binaries
    print_header("Checking Binary Availability")
    binaries = [
        "ipfs-cluster-service",
        "ipfs-cluster-follow",
        "ipfs-cluster-ctl"
    ]
    
    binary_results = {}
    for binary in binaries:
        returncode, stdout, stderr = run_command(["which", binary])
        available = returncode == 0
        binary_results[binary] = {
            "available": available,
            "path": stdout.strip() if available else None
        }
        status = "✅ Available" if available else "❌ Not available"
        path_info = f" at {stdout.strip()}" if available else ""
        print(f"{status}: {binary}{path_info}")
    
    # Print summary
    print_header("Verification Summary")
    
    # Module import summary
    all_imports_ok = all(result["importable"] for result in import_results.values())
    print(f"Module imports: {'✅ All OK' if all_imports_ok else '❌ Some failed'}")
    
    # Script verification summary
    all_scripts_ok = all(
        result["exists"] and result["help_works"] and 
        result["fake_daemon_works"] and result["debug_works"]
        for result in script_results.values()
    )
    print(f"Wrapper scripts: {'✅ All OK' if all_scripts_ok else '❌ Some failed'}")
    
    # Binary availability summary
    any_binary_available = any(result["available"] for result in binary_results.values())
    print(f"Binaries: {'✅ Some available' if any_binary_available else '❌ None available'}")
    
    # Overall verification status
    overall_ok = all_imports_ok and all_scripts_ok
    print(f"\nOverall wrapper verification: {'✅ PASSED' if overall_ok else '❌ FAILED'}")
    
    return 0 if overall_ok else 1

if __name__ == "__main__":
    sys.exit(main())