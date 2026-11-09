#!/usr/bin/env python3
"""
Test daemon manager functionality
"""
import sys
import os
import traceback
from pathlib import Path
import pytest

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_daemon_manager():
    """Test the daemon manager"""
    print("=== Testing Daemon Manager ===")
    
    try:
        # Test basic imports
        print("1. Testing imports...")
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
        print("   ✓ EnhancedDaemonManager imported")
        
        # Test initialization
        print("2. Testing initialization...")
        daemon_mgr = EnhancedDaemonManager()
        print("   ✓ EnhancedDaemonManager initialized")
        
        # Test daemon status
        print("3. Testing daemon status...")
        ipfs_running = daemon_mgr._is_ipfs_daemon_running()
        print(f"   IPFS daemon running: {ipfs_running}")
        
        # Test comprehensive daemon startup
        print("4. Testing daemon status report...")
        result = daemon_mgr.check_daemon_status()
        print(f"   Running: {result.get('running', False)}")
        
        print("=== Test Complete ===")
        assert isinstance(result, dict)
        assert "running" in result
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        pytest.fail(f"Daemon manager test failed: {e}")

if __name__ == "__main__":
    success = test_daemon_manager()
    sys.exit(0 if success else 1)
