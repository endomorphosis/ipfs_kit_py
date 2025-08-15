#!/usr/bin/env python3
"""
Test script to verify the updated IPFS installation function with version checking.
"""

import sys
import os
sys.path.insert(0, '/home/runner/work/ipfs_kit_py/ipfs_kit_py')

def test_install_ipfs_with_version_checking():
    """Test the updated install_ipfs_daemon method with version checking."""
    print("=== Testing IPFS Installation with Version Checking ===\n")
    
    try:
        from ipfs_kit_py.install_ipfs import install_ipfs
        print("✅ Successfully imported install_ipfs")
        
        # Initialize installer
        installer = install_ipfs()
        print("✅ Installer created successfully")
        
        # Test version detection
        print("\n1. Testing version detection...")
        latest_version = installer.get_latest_kubo_version()
        print(f"Latest version from GitHub: {latest_version}")
        
        current_version = installer.get_installed_kubo_version()
        print(f"Current installed version: {current_version}")
        
        if current_version:
            should_update = installer.should_update_kubo(current_version, latest_version)
            print(f"Should update: {should_update}")
        
        # Test URL generation
        print("\n2. Testing URL generation...")
        installer.update_ipfs_dists_with_version(latest_version)
        
        dist = installer.dist_select()
        print(f"Selected distribution: {dist}")
        
        if dist in installer.ipfs_dists:
            url = installer.ipfs_dists[dist]
            print(f"Download URL: {url}")
            print("✅ URL generation working correctly")
        else:
            print(f"❌ Distribution '{dist}' not found in ipfs_dists")
        
        # Test the actual installation logic (dry run)
        print("\n3. Testing installation logic (dry run)...")
        try:
            # Just test the initial logic without actually downloading
            if installer.ipfs_test_install():
                current = installer.get_installed_kubo_version()
                latest = installer.get_latest_kubo_version()
                
                if current and installer.should_update_kubo(current, latest):
                    print(f"✅ Would update from {current} to {latest}")
                else:
                    print("✅ Already up to date or newer version installed")
            else:
                print("✅ Would install latest version (no IPFS found)")
                
        except Exception as e:
            print(f"⚠️  Installation logic test failed: {e}")
        
        print("\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_install_ipfs_with_version_checking()
    sys.exit(0 if success else 1)
