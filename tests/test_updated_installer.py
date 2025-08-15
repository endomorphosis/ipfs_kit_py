#!/usr/bin/env python3
"""
Test script for the updated installer functionality.
"""

import sys
import os
sys.path.insert(0, '/home/runner/work/ipfs_kit_py/ipfs_kit_py')

print("Testing updated installer functionality...")

try:
    # Test importing the package with automatic installer
    import ipfs_kit_py
    print("✓ ipfs_kit_py imported successfully")
    
    # Test importing individual installers
    from ipfs_kit_py import install_ipfs, install_lotus, install_lassie
    print("✓ All installers imported successfully")
    
    # Test that they're available as attributes
    print(f"install_ipfs available: {ipfs_kit_py.INSTALL_IPFS_AVAILABLE}")
    print(f"install_lotus available: {ipfs_kit_py.INSTALL_LOTUS_AVAILABLE}")
    print(f"install_lassie available: {ipfs_kit_py.INSTALL_LASSIE_AVAILABLE}")
    
    # Test creating instances
    ipfs_installer = install_ipfs()
    lotus_installer = install_lotus()
    lassie_installer = install_lassie()
    
    print("✓ All installer instances created successfully")
    
    # Test bin directory creation
    bin_dir = os.path.join(os.path.dirname(ipfs_kit_py.__file__), "bin")
    print(f"Bin directory exists: {os.path.exists(bin_dir)}")
    
    # List current binaries
    if os.path.exists(bin_dir):
        binaries = os.listdir(bin_dir)
        print(f"Current binaries: {binaries}")
    
    print("✓ All tests passed!")
    
except Exception as e:
    print(f"✗ Test failed: {e}")
    import traceback
    traceback.print_exc()
