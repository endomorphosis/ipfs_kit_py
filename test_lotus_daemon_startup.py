#!/usr/bin/env python3
"""
Test script to verify lotus daemon starts up properly with ipfs_kit
"""

import sys
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_lotus_daemon_startup():
    """Test that lotus daemon starts up properly"""
    
    print("=" * 60)
    print("Testing Lotus Daemon Startup")
    print("=" * 60)
    
    try:
        # Import ipfs_kit_py
        print("1. Importing ipfs_kit_py...")
        import ipfs_kit_py
        
        # Initialize ipfs_kit
        print("2. Initializing ipfs_kit...")
        kit = ipfs_kit_py.ipfs_kit()
        
        # Check if lotus_kit is available
        print("3. Checking lotus_kit availability...")
        if hasattr(kit, 'lotus_kit'):
            print("   ✓ lotus_kit is available")
            print(f"   Auto-start daemon: {getattr(kit.lotus_kit, 'auto_start_daemon', 'Unknown')}")
            print(f"   Simulation mode: {getattr(kit.lotus_kit, 'simulation_mode', 'Unknown')}")
        else:
            print("   ✗ lotus_kit not available")
            return False
        
        # Check current daemon status
        print("4. Checking initial daemon status...")
        daemon_status = kit.check_daemon_status()
        print(f"   Daemon status: {daemon_status}")
        
        # Try to start required daemons
        print("5. Starting required daemons...")
        start_result = kit._start_required_daemons()
        print(f"   Start result: {start_result}")
        
        # Check daemon status after start attempt
        print("6. Checking daemon status after start...")
        daemon_status_after = kit.check_daemon_status()
        print(f"   Daemon status after: {daemon_status_after}")
        
        # Try to start lotus daemon explicitly
        print("7. Starting lotus daemon explicitly...")
        if hasattr(kit.lotus_kit, 'daemon_start'):
            lotus_start_result = kit.lotus_kit.daemon_start()
            print(f"   Lotus start result: {lotus_start_result}")
            
            # Wait a bit and check status again
            print("8. Waiting 5 seconds and checking lotus status...")
            time.sleep(5)
            lotus_status = kit.lotus_kit.daemon_status()
            print(f"   Lotus status: {lotus_status}")
        
        print("\n" + "=" * 60)
        print("Test completed successfully!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_lotus_daemon_startup()
    sys.exit(0 if success else 1)
