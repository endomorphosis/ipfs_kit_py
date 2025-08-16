#!/usr/bin/env python3

import sys
import os

# Add the package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ipfs_kit_py'))

def test_install_ipfs_methods():
    """Test that install_ipfs methods exist and are callable."""
    try:
        # Import the module
        from install_ipfs import install_ipfs
        
        # Create an instance
        installer = install_ipfs()
        print("✓ install_ipfs instantiated successfully")
        
        # Test config methods
        config_methods = [
            'config_ipfs',
            'config_ipfs_cluster_follow', 
            'config_ipfs_cluster_ctl',
            'config_ipfs_cluster_service'
        ]
        
        missing_methods = []
        for method_name in config_methods:
            if hasattr(installer, method_name):
                method = getattr(installer, method_name)
                if callable(method):
                    print(f"✓ {method_name} - exists and callable")
                else:
                    print(f"⚠ {method_name} - exists but not callable")
                    missing_methods.append(method_name)
            else:
                print(f"✗ {method_name} - missing")
                missing_methods.append(method_name)
        
        # Test install methods
        install_methods = [
            'install_ipfs_daemon',
            'install_ipfs_cluster_follow',
            'install_ipfs_cluster_ctl',
            'install_ipfs_cluster_service'
        ]
        
        for method_name in install_methods:
            if hasattr(installer, method_name):
                method = getattr(installer, method_name)
                if callable(method):
                    print(f"✓ {method_name} - exists and callable")
                else:
                    print(f"⚠ {method_name} - exists but not callable")
                    missing_methods.append(method_name)
            else:
                print(f"✗ {method_name} - missing")
                missing_methods.append(method_name)
        
        if not missing_methods:
            print("\n🎉 All methods are present and callable!")
            return True
        else:
            print(f"\n❌ Missing or non-callable methods: {missing_methods}")
            return False
            
    except Exception as e:
        print(f"✗ Error testing install_ipfs: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Testing install_ipfs module...")
    success = test_install_ipfs_methods()
    
    if success:
        print("\n✅ All tests passed!")
        exit(0)
    else:
        print("\n❌ Some tests failed!")
        exit(1)
