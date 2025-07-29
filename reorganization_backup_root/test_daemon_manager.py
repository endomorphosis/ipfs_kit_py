#!/usr/bin/env python3
"""
Test daemon manager functionality
"""
import sys
import os
import traceback
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_daemon_manager():
    """Test the daemon manager"""
    print("=== Testing Daemon Manager ===")
    
    try:
        # Test basic imports
        print("1. Testing imports...")
        from ipfs_kit_py import ipfs_kit
        print("   ✓ ipfs_kit imported")
        
        from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager
        print("   ✓ EnhancedDaemonManager imported")
        
        # Test initialization
        print("2. Testing initialization...")
        kit = ipfs_kit()
        print("   ✓ ipfs_kit initialized")
        
        daemon_mgr = EnhancedDaemonManager(kit)
        print("   ✓ EnhancedDaemonManager initialized")
        
        # Test daemon status
        print("3. Testing daemon status...")
        ipfs_running = daemon_mgr._is_daemon_running('ipfs')
        print(f"   IPFS daemon running: {ipfs_running}")
        
        # Test comprehensive daemon startup
        print("4. Testing comprehensive daemon startup...")
        result = daemon_mgr.ensure_daemon_running_comprehensive()
        print(f"   Success: {result.get('success', False)}")
        
        if result.get('errors'):
            print(f"   Errors: {result['errors']}")
        
        if result.get('warnings'):
            print(f"   Warnings: {result['warnings']}")
        
        print("=== Test Complete ===")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_daemon_manager()
    sys.exit(0 if success else 1)
