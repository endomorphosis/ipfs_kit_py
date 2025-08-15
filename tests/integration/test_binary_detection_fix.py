#!/usr/bin/env python3
"""
Test script to verify the binary detection fix in install_ipfs.py
"""

import os
import sys
import platform

# Add the ipfs_kit_py module to the path
sys.path.insert(0, '/home/runner/work/ipfs_kit_py/ipfs_kit_py')

from ipfs_kit_py.install_ipfs import install_ipfs

def test_binary_detection():
    """Test the fixed binary detection logic"""
    print("🔍 Testing Binary Detection Fix")
    print("=" * 50)
    
    # Create an installer instance
    installer = install_ipfs()
    
    # Test each detection method
    tests = [
        ("IPFS", installer.ipfs_test_install),
        ("IPFS Cluster Service", installer.ipfs_cluster_service_test_install),
        ("IPFS Cluster Follow", installer.ipfs_cluster_follow_test_install),
        ("IPFS Cluster CTL", installer.ipfs_cluster_ctl_test_install),
        ("IPGET", installer.ipget_test_install),
    ]
    
    print(f"Platform: {platform.system()}")
    print()
    
    for name, test_func in tests:
        try:
            result = test_func()
            status = "✅ FOUND" if result else "❌ NOT FOUND"
            print(f"{name:20} : {status}")
        except Exception as e:
            print(f"{name:20} : ⚠️  ERROR - {e}")
    
    print()
    print("🔧 Fix Details:")
    print("- Changed from checking 'len(detect) > 0' to 'detect == 0'")
    print("- os.system() returns 0 on success (binary found)")
    print("- os.system() returns non-zero on failure (binary not found)")
    print("- This prevents downloading binaries that are already installed")

if __name__ == "__main__":
    test_binary_detection()
