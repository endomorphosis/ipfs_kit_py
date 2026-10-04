#!/usr/bin/env python3
"""
Test the enhanced daemon management system
Tests all the recent improvements to daemon startup and configuration reporting
"""

import sys
import os
import json
import traceback
from pathlib import Path
import pytest

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_daemon_config_manager():
    """Test the DaemonConfigManager enhancements"""
    print("=== Testing DaemonConfigManager Enhancements ===")
    
    try:
        from ipfs_kit_py.daemon_config_manager import DaemonConfigManager
        
        print("✅ Successfully imported DaemonConfigManager")
        
        # Initialize the manager
        manager = DaemonConfigManager()
        print("✅ Successfully initialized DaemonConfigManager")
        
        # Test daemon status checking
        print("\n--- Testing Daemon Status ---")
        ipfs_running = manager.is_daemon_running('ipfs')
        print(f"IPFS daemon running: {ipfs_running}")
        
        lotus_running = manager.is_daemon_running('lotus')
        print(f"Lotus daemon running: {lotus_running}")
        
        cluster_running = manager.is_daemon_running('cluster')
        print(f"Cluster daemon running: {cluster_running}")
        
        # Test detailed status report
        print("\n--- Testing Detailed Status Report ---")
        status_report = manager.get_detailed_status_report()
        print(f"Status report generated: {len(status_report)} sections")
        for section, data in status_report.items():
            print(f"  {section}: {type(data)} ({len(str(data))} chars)")
        
        # Test configuration check
        print("\n--- Testing Configuration Check ---")
        config_result = manager.check_and_configure_all_daemons()
        print(f"Configuration check success: {config_result.get('success', False)}")
        print(f"Configuration errors: {len(config_result.get('errors', []))}")
        
        # Test the new startup function
        print("\n--- Testing Daemon Startup ---")
        startup_result = manager.start_and_check_daemons()
        print(f"Startup success: {startup_result.get('success', False)}")
        print(f"Daemons started: {startup_result.get('daemons_started', [])}")
        print(f"Daemons failed: {startup_result.get('daemons_failed', [])}")
        print(f"Startup errors: {len(startup_result.get('errors', []))}")
        
        assert isinstance(status_report, dict)
        assert isinstance(config_result, dict)
        assert "success" in config_result
        assert isinstance(startup_result, dict)
        assert "success" in startup_result
        
    except Exception as e:
        print(f"❌ Error testing DaemonConfigManager: {str(e)}")
        traceback.print_exc()
        pytest.fail(f"DaemonConfigManager test failed: {e}")

def test_ipfs_kit_integration():
    """Test IPFSKit integration with enhanced daemon management"""
    print("\n=== Testing IPFSKit Integration ===")
    
    try:
        from ipfs_kit_py.ipfs_kit import IPFSKit
        
        print("✅ Successfully imported IPFSKit")
        
        # Initialize with minimal config
        config = {
            'ipfs': {'enabled': True},
            'enable_daemon_management': True
        }
        
        kit = IPFSKit(config)
        print("✅ Successfully initialized IPFSKit")
        
        # Test daemon startup
        print("\n--- Testing Daemon Startup Integration ---")
        startup_result = kit._start_required_daemons()
        print(f"Daemon startup success: {startup_result.get('success', False)}")
        
        # Check if we get a proper summary
        if hasattr(kit, 'daemon_manager') and kit.daemon_manager:
            status_report = kit.daemon_manager.get_detailed_status_report()
            print(f"Status report available: {len(status_report)} sections")
        
        assert isinstance(startup_result, dict)
        assert "success" in startup_result
        
    except Exception as e:
        print(f"❌ Error testing IPFSKit integration: {str(e)}")
        traceback.print_exc()
        pytest.fail(f"IPFSKit integration test failed: {e}")

def test_filesystem_integration():
    """Test filesystem integration with enhanced error handling"""
    print("\n=== Testing Filesystem Integration ===")
    
    try:
        from ipfs_kit_py.ipfs_fsspec import get_filesystem, IPFSFileSystem
        
        print("✅ Successfully imported filesystem modules")
        
        # Test filesystem creation with smart parameter detection
        print("\n--- Testing Filesystem Creation ---")
        fs = get_filesystem()
        print(f"✅ Successfully created filesystem: {type(fs)}")
        
        # Test IPFSFileSystem alias
        print("\n--- Testing IPFSFileSystem Alias ---")
        fs2 = IPFSFileSystem()
        print(f"✅ Successfully created IPFSFileSystem: {type(fs2)}")
        
        assert fs is not None
        assert fs2 is not None
        
    except Exception as e:
        print(f"❌ Error testing filesystem integration: {str(e)}")
        traceback.print_exc()
        pytest.fail(f"Filesystem integration test failed: {e}")

def main():
    """Run all enhancement tests"""
    print("Testing Enhanced Daemon Management System")
    print("=" * 50)
    
    results = []
    
    # Test each component
    results.append(("DaemonConfigManager", test_daemon_config_manager()))
    results.append(("IPFSKit Integration", test_ipfs_kit_integration()))
    results.append(("Filesystem Integration", test_filesystem_integration()))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)}")
    
    if passed == len(results):
        print("🎉 All enhancement tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
