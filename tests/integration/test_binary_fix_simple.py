#!/usr/bin/env python3
"""
Direct test of the binary detection logic fix
"""

import os
import platform

def test_os_system_behavior():
    """Test how os.system() works with which/where commands"""
    print("🔍 Testing os.system() Binary Detection Behavior")
    print("=" * 60)
    
    # Test with common binaries that should exist
    test_binaries = ["ls", "cat", "python3", "bash"]
    if platform.system() == "Windows":
        test_binaries = ["dir", "type", "python", "cmd"]
    
    print(f"Platform: {platform.system()}")
    print()
    
    for binary in test_binaries:
        if platform.system() == "Windows":
            cmd = f"where {binary}"
        else:
            cmd = f"which {binary}"
        
        exit_code = os.system(f"{cmd} >/dev/null 2>&1")
        status = "✅ FOUND (exit 0)" if exit_code == 0 else f"❌ NOT FOUND (exit {exit_code})"
        print(f"{binary:12} : {status}")
    
    print()
    print("🔧 Key Points:")
    print("- os.system() returns 0 when command succeeds (binary found)")
    print("- os.system() returns non-zero when command fails (binary not found)")
    print("- The bug was checking 'len(exit_code) > 0' instead of 'exit_code == 0'")
    print("- This caused the code to think binaries were NOT found when they WERE found")
    print("- Result: unnecessary downloads to /tmp even when binaries existed")

def test_ipfs_binaries():
    """Test specifically for IPFS-related binaries"""
    print("\n" + "=" * 60)
    print("🔍 Testing IPFS Binary Detection (After Fix)")
    print("=" * 60)
    
    ipfs_binaries = ["ipfs", "ipfs-cluster-service", "ipfs-cluster-follow", "ipfs-cluster-ctl", "ipget"]
    
    for binary in ipfs_binaries:
        if platform.system() == "Windows":
            cmd = f"where {binary}"
        else:
            cmd = f"which {binary}"
        
        exit_code = os.system(f"{cmd} >/dev/null 2>&1")
        
        # This is the FIXED logic
        binary_found = (exit_code == 0)
        
        status = "✅ FOUND - Will NOT download" if binary_found else "❌ NOT FOUND - Will download"
        print(f"{binary:20} : {status}")

if __name__ == "__main__":
    test_os_system_behavior()
    test_ipfs_binaries()
