#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ipfs_kit_py'))

import install_ipfs

def test_install_ipfs():
    """Test that install_ipfs can be imported and instantiated."""
    try:
        # Test instantiation
        installer = install_ipfs.install_ipfs()
        print("✓ install_ipfs class instantiated successfully")
        
        # Test that config methods exist
        config_methods = [
            'config_ipfs',
            'config_ipfs_cluster_follow', 
            'config_ipfs_cluster_ctl',
            'config_ipfs_cluster_service'
        ]
        
        for method_name in config_methods:
            if hasattr(installer, method_name):
                print(f"✓ {method_name} method exists")
            else:
                print(f"✗ {method_name} method missing")
                return False
        
        # Test that install methods exist
        install_methods = [
            'install_ipfs_daemon',
            'install_ipfs_cluster_follow',
            'install_ipfs_cluster_ctl', 
            'install_ipfs_cluster_service'
        ]
        
        for method_name in install_methods:
            if hasattr(installer, method_name):
                print(f"✓ {method_name} method exists")
            else:
                print(f"✗ {method_name} method missing")
                return False
                
        print("✓ All required methods are present")
        return True
        
    except Exception as e:
        print(f"✗ Error testing install_ipfs: {e}")
        return False

if __name__ == "__main__":
    success = test_install_ipfs()
    if success:
        print("\n🎉 install_ipfs tests passed!")
        sys.exit(0)
    else:
        print("\n❌ install_ipfs tests failed!")
        sys.exit(1)
