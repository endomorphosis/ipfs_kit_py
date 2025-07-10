#!/usr/bin/env python3
"""
Project Structure Verification Script
=====================================

This script verifies that the reorganization was successful by checking
that key files are in their expected locations.
"""

import os
from pathlib import Path

def check_file_exists(filepath, description):
    """Check if a file exists and report status."""
    if os.path.exists(filepath):
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ {description}: {filepath} - NOT FOUND")
        return False

def verify_structure():
    """Verify the project structure is correct."""
    base_path = Path("/home/barberb/ipfs_kit_py")
    
    print("🔍 Verifying IPFS Kit Project Structure...")
    print("=" * 50)
    
    # Check key server files at root
    print("\n📁 Server Files (Root Level):")
    server_files = [
        "standalone_cluster_server.py",
        "start_3_node_cluster.py", 
        "containerized_mcp_server.py",
        "enhanced_mcp_server_with_daemon_init.py",
        "main.py"
    ]
    
    server_ok = 0
    for file in server_files:
        if check_file_exists(base_path / file, f"Server: {file}"):
            server_ok += 1
    
    # Check cluster files
    print("\n📁 Cluster Files:")
    cluster_files = [
        "cluster/enhanced_daemon_manager_with_cluster.py",
        "cluster/practical_cluster_setup.py",
        "cluster/__init__.py"
    ]
    
    cluster_ok = 0
    for file in cluster_files:
        if check_file_exists(base_path / file, f"Cluster: {file}"):
            cluster_ok += 1
    
    # Check package files
    print("\n📁 Package Files (ipfs_kit_py/):")
    package_files = [
        "ipfs_kit_py/ipfs_fsspec.py",
        "ipfs_kit_py/daemon_config_manager.py",
        "ipfs_kit_py/__init__.py"
    ]
    
    package_ok = 0
    for file in package_files:
        if check_file_exists(base_path / file, f"Package: {file}"):
            package_ok += 1
    
    # Check test files (sample)
    print("\n📁 Test Files (tests/):")
    test_files = [
        "tests/comprehensive_mcp_test.py",
        "tests/validate_test_infrastructure.py",
        "tests/quick_verify.py",
        "tests/ultimate_mcp_test.py",
        "tests/vfs_verification.py"
    ]
    
    test_ok = 0
    for file in test_files:
        if check_file_exists(base_path / file, f"Test: {file}"):
            test_ok += 1
    
    # Check tool files (sample)
    print("\n📁 Tool Files (tools/):")
    tool_files = [
        "tools/project_reorganization_summary.py",
        "tools/analyze_mcp_initialization.py",
        "tools/patch_ipfs_kit_targeted.py",
        "tools/FINAL_IMPLEMENTATION_SUMMARY.py"
    ]
    
    tool_ok = 0
    for file in tool_files:
        if check_file_exists(base_path / file, f"Tool: {file}"):
            tool_ok += 1
    
    # Check demonstration files (bin/)
    print("\n📁 Demonstration Files (bin/):")
    if os.path.exists(base_path / "bin"):
        bin_files = list((base_path / "bin").glob("*.py"))
        bin_ok = len(bin_files)
        print(f"✅ Found {bin_ok} demonstration files in bin/")
    else:
        bin_ok = 0
        print("❌ bin/ directory not found")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 VERIFICATION SUMMARY:")
    print(f"Server files: {server_ok}/{len(server_files)}")
    print(f"Cluster files: {cluster_ok}/{len(cluster_files)}")
    print(f"Package files: {package_ok}/{len(package_files)}")
    print(f"Test files: {test_ok}/{len(test_files)}")
    print(f"Tool files: {tool_ok}/{len(tool_files)}")
    print(f"Demonstration files: {bin_ok}")
    
    total_checked = len(server_files) + len(cluster_files) + len(package_files) + len(test_files) + len(tool_files)
    total_found = server_ok + cluster_ok + package_ok + test_ok + tool_ok
    
    print(f"\nOverall: {total_found}/{total_checked} key files found ({total_found/total_checked*100:.1f}%)")
    
    if total_found == total_checked:
        print("🎉 Reorganization verification PASSED!")
    else:
        print("⚠️  Some files may be missing or in wrong locations")
    
    return total_found == total_checked

if __name__ == "__main__":
    verify_structure()
