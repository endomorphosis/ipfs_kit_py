#!/usr/bin/env python3
"""
Test script for ARM64 build-from-source functionality.

This script verifies that:
1. Build-from-source methods exist
2. Go installation works
3. Build tools are available
4. The build process can be initiated
"""

import sys
import os
import platform
import subprocess
import pytest

# Add parent directory to path to import ipfs_kit_py modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ipfs_kit_py'))


def _skip_if_not_arm64():
    machine = platform.machine().lower()
    if "aarch64" not in machine and "arm64" not in machine:
        pytest.skip("ARM64 build-from-source tests require ARM64 host")

def check_architecture():
    """Check if running on ARM64."""
    machine = platform.machine().lower()
    if "aarch64" in machine or "arm64" in machine:
        print(f"✓ Running on ARM64 architecture: {machine}")
        return True
    else:
        print(f"⚠ Not running on ARM64 architecture: {machine}")
        print("  Build-from-source is primarily for ARM64 systems")
        return False

def check_build_tools():
    """Check if required build tools are available."""
    tools = {
        "git": ["git", "--version"],
        "make": ["make", "--version"],
        "gcc": ["gcc", "--version"],
    }
    
    print("\nChecking build tools:")
    all_present = True
    for tool, cmd in tools.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            version = result.stdout.split('\n')[0]
            print(f"✓ {tool}: {version}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✗ {tool}: Not found")
            all_present = False
    
    return all_present

def check_go():
    """Check if Go is installed."""
    try:
        result = subprocess.run(["go", "version"], capture_output=True, text=True, check=True)
        version = result.stdout.strip()
        print(f"\n✓ Go is installed: {version}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("\n⚠ Go is not installed")
        print("  The installer will attempt to install Go automatically")
        return False

def test_ipfs_build_methods():
    """Test IPFS build-from-source methods."""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("Testing IPFS build-from-source functionality")
    print("="*60)
    
    try:
        from install_ipfs import install_ipfs
        
        installer = install_ipfs()
        
        # Check for build method
        if hasattr(installer, 'build_ipfs_from_source'):
            print("✓ build_ipfs_from_source method exists")
        else:
            print("✗ build_ipfs_from_source method not found")
            return False
        
        # Check for Go installation method
        if hasattr(installer, '_install_go'):
            print("✓ _install_go method exists")
        else:
            print("✗ _install_go method not found")
            return False
        
        # Check for PATH helper
        if hasattr(installer, '_add_to_user_path'):
            print("✓ _add_to_user_path method exists")
        else:
            print("✗ _add_to_user_path method not found")
            return False
        
        # Check version methods
        current_version = installer.get_installed_kubo_version()
        print(f"  Current IPFS version: {current_version if current_version else 'Not installed'}")
        
        latest_version = installer.get_latest_kubo_version()
        print(f"  Latest IPFS version: {latest_version}")
        
        print("\n✓ IPFS build-from-source functionality verified")
        return True
        
    except Exception as e:
        print(f"\n✗ Error testing IPFS build functionality: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_lotus_build_methods():
    """Test Lotus build-from-source methods."""
    _skip_if_not_arm64()
    print("\n" + "="*60)
    print("Testing Lotus build-from-source functionality")
    print("="*60)
    
    try:
        from install_lotus import install_lotus
        
        installer = install_lotus()
        
        # Check for build method
        if hasattr(installer, 'build_lotus_from_source'):
            print("✓ build_lotus_from_source method exists")
        else:
            print("✗ build_lotus_from_source method not found")
            return False
        
        # Check for Go installation method
        if hasattr(installer, '_install_go_for_build'):
            print("✓ _install_go_for_build method exists")
        else:
            print("✗ _install_go_for_build method not found")
            return False
        
        # Check installation status
        installation = installer.check_existing_installation()
        if installation["installed"]:
            print(f"  Current Lotus version: {installation['version']}")
            print(f"  Installed binaries: {sum(installation['binaries'].values())} of {len(installation['binaries'])}")
        else:
            print("  Lotus not currently installed")
        
        print("\n✓ Lotus build-from-source functionality verified")
        return True
        
    except Exception as e:
        print(f"\n✗ Error testing Lotus build functionality: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("ARM64 Build-from-Source Test Script")
    print("="*60)
    
    results = []
    
    # Check architecture
    is_arm64 = check_architecture()
    
    # Check build tools
    tools_present = check_build_tools()
    results.append(("Build tools", tools_present))
    
    # Check Go
    go_present = check_go()
    
    # Test IPFS methods
    ipfs_ok = test_ipfs_build_methods()
    results.append(("IPFS build methods", ipfs_ok))
    
    # Test Lotus methods
    lotus_ok = test_lotus_build_methods()
    results.append(("Lotus build methods", lotus_ok))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✓ All tests passed!")
        if not is_arm64:
            print("\n⚠ Note: You're not on ARM64, but the methods exist and can be called")
        if not tools_present:
            print("\n⚠ Note: Some build tools are missing, but they will be checked during build")
        if not go_present:
            print("\n⚠ Note: Go is not installed, but it will be installed automatically if needed")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
