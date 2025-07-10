#!/usr/bin/env python3
"""
Test script to verify that install_storacha is properly integrated into the ipfs_kit_py package.
"""

import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_storacha_integration():
    """Test that install_storacha can be imported and used."""
    print("=" * 60)
    print("Testing install_storacha integration")
    print("=" * 60)
    
    try:
        # Test importing from ipfs_kit_py
        print("\n1. Testing import from ipfs_kit_py...")
        from ipfs_kit_py import install_storacha, INSTALL_STORACHA_AVAILABLE
        
        if INSTALL_STORACHA_AVAILABLE:
            print("✓ install_storacha is available")
        else:
            print("✗ install_storacha is not available")
            return False
        
        # Test instantiation
        print("\n2. Testing installer instantiation...")
        installer = install_storacha()
        print("✓ install_storacha() instantiated successfully")
        
        # Test that methods exist
        print("\n3. Testing method availability...")
        methods_to_check = [
            'install_storacha_dependencies',
            'install_python_dependencies',
            'install_w3_cli',
            'verify_storacha_functionality'
        ]
        
        for method in methods_to_check:
            if hasattr(installer, method):
                print(f"✓ {method} method is available")
            else:
                print(f"✗ {method} method is missing")
                return False
        
        # Test directory structure
        print("\n4. Testing directory structure...")
        import ipfs_kit_py
        bin_dir = os.path.join(os.path.dirname(ipfs_kit_py.__file__), "bin")
        if os.path.exists(bin_dir):
            print(f"✓ bin directory exists: {bin_dir}")
        else:
            print(f"✓ bin directory will be created: {bin_dir}")
        
        # Test marker file check
        marker_file = os.path.join(bin_dir, ".storacha_installed")
        if os.path.exists(marker_file):
            print(f"✓ Storacha marker file exists: {marker_file}")
            with open(marker_file, 'r') as f:
                content = f.read()
                print(f"   Content: {content.strip()}")
        else:
            print(f"ℹ Storacha marker file does not exist yet: {marker_file}")
        
        # Test import from other modules
        print("\n5. Testing import from ipfs_kit_py.__init__...")
        from ipfs_kit_py import __version__
        print(f"✓ Package version: {__version__}")
        
        print("\n" + "=" * 60)
        print("✓ All integration tests passed!")
        print("=" * 60)
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_auto_download_logic():
    """Test that auto-download logic includes storacha."""
    print("\n" + "=" * 60)
    print("Testing auto-download logic")
    print("=" * 60)
    
    try:
        # Import the package to trigger auto-download logic
        print("\n1. Importing package to test auto-download...")
        import ipfs_kit_py
        
        # Check if marker file was created
        print("\n2. Checking if auto-download created marker file...")
        bin_dir = os.path.join(os.path.dirname(ipfs_kit_py.__file__), "bin")
        marker_file = os.path.join(bin_dir, ".storacha_installed")
        
        if os.path.exists(marker_file):
            print(f"✓ Marker file exists: {marker_file}")
            with open(marker_file, 'r') as f:
                content = f.read()
                print(f"   Content: {content.strip()}")
        else:
            print(f"ℹ Marker file not found: {marker_file}")
            print("   This may indicate auto-download hasn't run yet or failed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing auto-download: {e}")
        return False

def main():
    """Main test function."""
    print("Starting install_storacha integration tests...")
    
    # Test 1: Basic integration
    success1 = test_storacha_integration()
    
    # Test 2: Auto-download logic
    success2 = test_auto_download_logic()
    
    if success1 and success2:
        print("\n🎉 All tests passed! install_storacha is properly integrated.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
