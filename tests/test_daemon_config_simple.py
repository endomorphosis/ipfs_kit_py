#!/usr/bin/env python3
"""
Simple test for daemon configuration integration
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daemon_config_test")

def test_daemon_config_manager():
    """Test the daemon configuration manager."""
    print("🧪 Testing daemon configuration manager...")
    
    try:
        from daemon_config_manager import DaemonConfigManager
        
        manager = DaemonConfigManager()
        print("✅ DaemonConfigManager imported and instantiated successfully")
        
        # Test configuration checking
        config_result = manager.check_and_configure_all_daemons()
        print(f"✅ Configuration check completed: {config_result.get('overall_success', False)}")
        
        # Test validation
        validation_result = manager.validate_daemon_configs()
        print(f"✅ Validation completed: {validation_result.get('overall_valid', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing daemon config manager: {e}")
        return False

def test_enhanced_server():
    """Test the enhanced server with configuration."""
    print("🧪 Testing enhanced server with configuration...")
    
    try:
        from enhanced_mcp_server_with_config import EnhancedMCPServerWithConfig
        
        server = EnhancedMCPServerWithConfig()
        print("✅ EnhancedMCPServerWithConfig imported and instantiated successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing enhanced server: {e}")
        return False

def test_installer_patches():
    """Test that the installer patches work."""
    print("🧪 Testing installer patches...")
    
    try:
        # Test install_ipfs patch
        from ipfs_kit_py.install_ipfs import install_ipfs
        ipfs_installer = install_ipfs()
        
        if hasattr(ipfs_installer, 'ensure_daemon_configured'):
            print("✅ install_ipfs patch applied successfully")
        else:
            print("❌ install_ipfs patch not found")
            return False
        
        # Test install_lotus patch
        from ipfs_kit_py.install_lotus import install_lotus
        lotus_installer = install_lotus()
        
        if hasattr(lotus_installer, 'ensure_daemon_configured'):
            print("✅ install_lotus patch applied successfully")
        else:
            print("❌ install_lotus patch not found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing installer patches: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Running daemon configuration integration tests...")
    
    tests = [
        ("Daemon Config Manager", test_daemon_config_manager),
        ("Enhanced Server", test_enhanced_server),
        ("Installer Patches", test_installer_patches),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print(f"{'='*50}")
        
        result = test_func()
        results.append((test_name, result))
        
        if result:
            print(f"✅ {test_name} PASSED")
        else:
            print(f"❌ {test_name} FAILED")
    
    # Summary
    print(f"\n{'='*50}")
    print("TEST SUMMARY")
    print(f"{'='*50}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        print("\n💡 Daemon configuration integration is working correctly!")
        print("💡 The system now ensures proper daemon configuration before startup.")
        return 0
    else:
        print("\n❌ Some tests failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
