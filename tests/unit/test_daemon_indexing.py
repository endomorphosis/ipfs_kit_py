#!/usr/bin/env python3
"""
Test script for enhanced daemon manager with background indexing.
This script tests the background index updating functionality.
"""

import sys
import time
from pathlib import Path
import os

# Add the package to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pytest
from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager

def test_background_indexing():
    """Test the background indexing functionality."""
    pytest.skip("Background indexing integration test is slow; run manually when needed")
    print("🚀 Testing Enhanced Daemon Manager with Background Indexing")
    print("=" * 60)
    
    # Create daemon manager
    daemon_manager = EnhancedDaemonManager()
    
    print("📋 Initial State:")
    print(f"   Index update running: {daemon_manager.index_update_running}")
    print(f"   Update interval: {daemon_manager.index_update_interval} seconds")
    print(f"   IPFS Kit path: {daemon_manager.ipfs_kit_path}")
    
    # Check if IPFS daemon is running
    ipfs_running = daemon_manager._is_ipfs_daemon_running()
    print(f"   IPFS daemon status: {'Running' if ipfs_running else 'Not running'}")
    
    if ipfs_running:
        # Get current pin count
        pin_count = daemon_manager._get_pin_count()
        print(f"   Current IPFS pins: {pin_count}")
        
        # Get some real pins for testing
        real_pins = daemon_manager._get_real_ipfs_pins()
        print(f"   Real pins retrieved: {len(real_pins)}")
        
        if real_pins:
            print("   Sample pin:")
            sample_pin = real_pins[0]
            print(f"      CID: {sample_pin['cid']}")
            print(f"      Size: {sample_pin['size_bytes']} bytes")
            print(f"      Type: {sample_pin['pin_type']}")
    
    print("\n🔧 Testing Background Index Updates...")
    
    # Start background indexing
    daemon_manager.start_background_indexing()
    print("✅ Background indexing started")
    
    # Wait for a few updates
    print("⏳ Waiting for background updates (30 seconds)...")
    for i in range(6):
        time.sleep(5)
        print(f"   Update cycle {i+1}/6 - {(i+1)*5}/30 seconds")
        
        # Check if pin index file exists and was updated
        pin_file = daemon_manager.ipfs_kit_path / 'pin_metadata' / 'parquet_storage' / 'pins.parquet'
        if pin_file.exists():
            stat = pin_file.stat()
            print(f"      Pin index: {stat.st_size} bytes, modified: {time.ctime(stat.st_mtime)}")
        
        # Check program state files
        state_dir = daemon_manager.ipfs_kit_path / 'program_state' / 'parquet'
        if state_dir.exists():
            state_files = list(state_dir.glob('*.parquet'))
            print(f"      Program state files: {len(state_files)}")
    
    print("\n🛑 Stopping background indexing...")
    daemon_manager.stop_background_indexing()
    print("✅ Background indexing stopped")
    
    # Verify final state
    print("\n📊 Final Results:")
    pin_file = daemon_manager.ipfs_kit_path / 'pin_metadata' / 'parquet_storage' / 'pins.parquet'
    if pin_file.exists():
        print(f"✅ Pin index file exists: {pin_file}")
        stat = pin_file.stat()
        print(f"   Size: {stat.st_size} bytes")
        print(f"   Last modified: {time.ctime(stat.st_mtime)}")
    else:
        print("❌ Pin index file not found")
    
    state_dir = daemon_manager.ipfs_kit_path / 'program_state' / 'parquet'
    if state_dir.exists():
        state_files = list(state_dir.glob('*.parquet'))
        print(f"✅ Program state files: {len(state_files)}")
        for state_file in state_files:
            stat = state_file.stat()
            print(f"   {state_file.name}: {stat.st_size} bytes")
    else:
        print("❌ Program state directory not found")

if __name__ == "__main__":
    test_background_indexing()
