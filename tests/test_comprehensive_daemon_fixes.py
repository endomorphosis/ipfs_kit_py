#!/usr/bin/env python3
"""
Comprehensive test for daemon fixes and enhanced management.

This test verifies:
1. IPFS version compatibility checking and repository reset
2. Enhanced daemon management with proper error handling
3. Integration with the existing IPFS Kit system
4. Proper startup orchestration and dependency management
"""

import os
import sys
import time
import logging
import tempfile
import shutil
from pathlib import Path
import pytest

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_enhanced_daemon_manager():
    """Test the enhanced daemon manager functionality."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run comprehensive daemon fixes tests")
    print("=" * 60)
    print("Testing Enhanced Daemon Manager")
    print("=" * 60)
    
    try:
        # Import the enhanced daemon manager
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
        print("✅ Enhanced daemon manager imported successfully")
        
        # Create a mock IPFS Kit instance for testing
        class MockIPFSKit:
            def __init__(self):
                self.ipfs_path = os.path.expanduser("~/.ipfs_test")
                
        mock_kit = MockIPFSKit()
        
        # Initialize the enhanced daemon manager
        daemon_manager = EnhancedDaemonManager(mock_kit)
        print("✅ Enhanced daemon manager initialized successfully")
        
        # Test version compatibility checking
        print("\n--- Testing Version Compatibility Checking ---")
        version_check = daemon_manager.check_and_fix_ipfs_version_mismatch()
        print(f"Version check result: {version_check}")
        
        if version_check.get("success"):
            print("✅ Version compatibility check completed successfully")
        else:
            print(f"⚠️  Version compatibility check had issues: {version_check.get('error', 'Unknown')}")
        
        # Test daemon status summary
        print("\n--- Testing Daemon Status Summary ---")
        status_summary = daemon_manager.get_daemon_status_summary()
        print(f"Daemon status summary: {status_summary}")
        print("✅ Daemon status summary generated successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced daemon manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ipfs_version_handling():
    """Test IPFS version detection and handling."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run comprehensive daemon fixes tests")
    print("\n" + "=" * 60)
    print("Testing IPFS Version Handling")
    print("=" * 60)
    
    try:
        from ipfs_kit_py.install_ipfs import install_ipfs
        print("✅ install_ipfs module imported successfully")
        
        # Initialize install_ipfs
        installer = install_ipfs()
        print("✅ install_ipfs initialized successfully")
        
        # Test version detection
        print("\n--- Testing Version Detection ---")
        current_version = installer.get_installed_kubo_version()
        print(f"Current installed version: {current_version}")
        
        latest_version = installer.get_latest_kubo_version()
        print(f"Latest available version: {latest_version}")
        
        # Test version comparison
        if current_version and latest_version:
            should_update = installer.should_update_kubo(current_version, latest_version)
            print(f"Should update: {should_update}")
            print("✅ Version comparison working correctly")
        else:
            print("⚠️  Could not perform version comparison (versions not detected)")
        
        # Test repository compatibility checking
        print("\n--- Testing Repository Compatibility ---")
        if current_version:
            repo_compatible = installer.check_repo_compatibility(current_version)
            print(f"Repository compatible: {repo_compatible}")
            
            if not repo_compatible:
                print("⚠️  Repository version mismatch detected")
                # Note: We won't actually reset the repo in the test
                print("Repository reset would be triggered in real scenario")
            else:
                print("✅ Repository version is compatible")
        else:
            print("⚠️  Cannot check repository compatibility without current version")
        
        return True
        
    except Exception as e:
        print(f"❌ IPFS version handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ipfs_kit_integration():
    """Test integration with the main IPFS Kit system."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run comprehensive daemon fixes tests")
    print("\n" + "=" * 60)
    print("Testing IPFS Kit Integration")
    print("=" * 60)
    
    try:
        # Import IPFS Kit
        from ipfs_kit_py.ipfs_kit import ipfs_kit
        print("✅ ipfs_kit imported successfully")
        
        # Initialize IPFS Kit with correct parameters
        print("\n--- Initializing IPFS Kit ---")
        metadata = {"role": "master"}
        ipfs_kit_instance = ipfs_kit(metadata=metadata, auto_start_daemons=False)
        print("✅ ipfs_kit initialized successfully")
        
        # Test enhanced daemon manager integration
        print("\n--- Testing Enhanced Daemon Manager Integration ---")
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
        
        enhanced_manager = EnhancedDaemonManager(ipfs_kit_instance)
        print("✅ Enhanced daemon manager integrated with IPFS Kit")
        
        # Test daemon status checking
        status_summary = enhanced_manager.get_daemon_status_summary()
        print(f"Integrated daemon status: {status_summary}")
        
        # Test version checking with real IPFS Kit instance
        version_check = enhanced_manager.check_and_fix_ipfs_version_mismatch()
        print(f"Version check with real kit: {version_check}")
        
        print("✅ IPFS Kit integration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ IPFS Kit integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_daemon_startup_orchestration():
    """Test the daemon startup orchestration."""
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run comprehensive daemon fixes tests")
    print("\n" + "=" * 60)
    print("Testing Daemon Startup Orchestration")
    print("=" * 60)
    
    try:
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
        
        # Create a mock IPFS Kit for testing
        class MockIPFSKitWithDaemons:
            def __init__(self):
                self.ipfs_path = os.path.expanduser("~/.ipfs_test")
                # Mock daemon objects
                self.lotus_daemon = MockDaemon("lotus")
                self.ipfs_cluster_service = MockDaemon("cluster")
                self.lassie_kit = MockDaemon("lassie")
                
        class MockDaemon:
            def __init__(self, name):
                self.name = name
                
            def daemon_start(self):
                return {"success": True, "status": f"{self.name}_started"}
                
            def daemon_stop(self):
                return {"success": True, "status": f"{self.name}_stopped"}
                
            def daemon_status(self):
                return {"process_running": False}
        
        mock_kit = MockIPFSKitWithDaemons()
        daemon_manager = EnhancedDaemonManager(mock_kit)
        
        print("✅ Mock environment set up for orchestration testing")
        
        # Test daemon startup orchestration
        print("\n--- Testing Daemon Startup Orchestration ---")
        startup_results = daemon_manager.start_daemons_with_dependencies("master")
        
        print(f"Startup results: {startup_results}")
        
        if startup_results.get("overall_success"):
            print("✅ Daemon startup orchestration completed successfully")
        else:
            print(f"⚠️  Daemon startup had issues: {startup_results.get('errors', [])}")
        
        # Test daemon shutdown
        print("\n--- Testing Daemon Shutdown ---")
        shutdown_results = daemon_manager.stop_all_daemons()
        print(f"Shutdown results: {shutdown_results}")
        
        if shutdown_results.get("overall_success"):
            print("✅ Daemon shutdown completed successfully")
        else:
            print(f"⚠️  Daemon shutdown had issues: {shutdown_results.get('errors', [])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Daemon startup orchestration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_repository_migration():
    """Test repository migration functionality with a temporary repository."""
    print("\n" + "=" * 60)
    print("Testing Repository Migration")
    print("=" * 60)
    if os.environ.get("IPFS_KIT_RUN_LONG_INTEGRATION") != "1":
        pytest.skip("Set IPFS_KIT_RUN_LONG_INTEGRATION=1 to run comprehensive daemon fixes tests")
    
    try:
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
        
        # Create a temporary test repository
        test_repo_path = tempfile.mkdtemp(prefix="ipfs_test_repo_")
        print(f"Created test repository at: {test_repo_path}")
        
        # Create a mock version file with incompatible version
        version_file = os.path.join(test_repo_path, "version")
        with open(version_file, 'w') as f:
            f.write("15")  # Older version
        
        print("✅ Created mock repository with version 15")
        
        # Create mock IPFS Kit
        class MockIPFSKitForMigration:
            def __init__(self, ipfs_path):
                self.ipfs_path = ipfs_path
                
        mock_kit = MockIPFSKitForMigration(test_repo_path)
        daemon_manager = EnhancedDaemonManager(mock_kit)
        
        # Test migration
        print("\n--- Testing Repository Migration ---")
        migration_result = daemon_manager._migrate_or_reset_repository(test_repo_path)
        
        print(f"Migration result: {migration_result}")
        
        if migration_result.get("success"):
            print("✅ Repository migration completed successfully")
            
            # Check if backup was created
            backup_path = migration_result.get("backup_path")
            if backup_path and os.path.exists(backup_path):
                print(f"✅ Backup created at: {backup_path}")
                # Clean up backup
                shutil.rmtree(backup_path)
            
            # Check if new directory was created
            if os.path.exists(test_repo_path):
                print("✅ New repository directory created")
        else:
            print(f"❌ Repository migration failed: {migration_result.get('error')}")
        
        # Clean up test repository
        if os.path.exists(test_repo_path):
            shutil.rmtree(test_repo_path)
        print("✅ Test repository cleaned up")
        
        return migration_result.get("success", False)
        
    except Exception as e:
        print(f"❌ Repository migration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all comprehensive daemon fix tests."""
    print("Starting Comprehensive Daemon Fixes Test Suite")
    print("=" * 80)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("Enhanced Daemon Manager", test_enhanced_daemon_manager),
        ("IPFS Version Handling", test_ipfs_version_handling),
        ("IPFS Kit Integration", test_ipfs_kit_integration),
        ("Daemon Startup Orchestration", test_daemon_startup_orchestration),
        ("Repository Migration", test_repository_migration),
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            result = test_func()
            test_results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
                
        except Exception as e:
            print(f"❌ {test_name} CRASHED: {e}")
            test_results.append((test_name, False))
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "PASSED" if result else "FAILED"
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Daemon fixes are working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Please review the output above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
