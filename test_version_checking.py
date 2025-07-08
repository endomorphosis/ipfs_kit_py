#!/usr/bin/env python3
"""
Test script to verify the updated IPFS installation with version checking.
"""

import sys
import os
sys.path.insert(0, '/home/barberb/ipfs_kit_py')

from ipfs_kit_py.install_ipfs import install_ipfs

def test_version_checking():
    """Test the version checking functionality."""
    print("=== Testing IPFS Version Checking ===")
    
    try:
        # Initialize the installer
        installer = install_ipfs()
        
        # Test getting latest version
        print("\n1. Testing latest version fetch...")
        latest_version = installer.get_latest_kubo_version()
        print(f"Latest version: {latest_version}")
        
        # Test getting installed version
        print("\n2. Testing installed version detection...")
        current_version = installer.get_installed_kubo_version()
        print(f"Current version: {current_version}")
        
        # Test version comparison
        print("\n3. Testing version comparison...")
        if current_version:
            should_update = installer.should_update_kubo(current_version, latest_version)
            print(f"Should update from {current_version} to {latest_version}: {should_update}")
        else:
            print("No current version found, will install latest")
        
        # Test URL generation
        print("\n4. Testing URL generation...")
        installer.update_ipfs_dists_with_version(latest_version)
        dist = installer.dist_select()
        print(f"Selected distribution: {dist}")
        print(f"Download URL: {installer.ipfs_dists[dist]}")
        
        print("\n✅ Version checking tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_version_checking()
    sys.exit(0 if success else 1)
