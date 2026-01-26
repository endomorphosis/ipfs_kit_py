#!/usr/bin/env python3
"""
Test the enhanced daemon manager lockfile functionality
======================================================

This script tests the new lockfile management and daemon lifecycle functionality.
"""

import sys
import logging
from pathlib import Path

# Add project root to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import the enhanced daemon manager
from ipfs_kit_py.enhanced_daemon_manager import EnhancedDaemonManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_cluster_lockfile_management():
    """Test cluster lockfile management functionality."""
    
    print("🔧 Testing Enhanced Daemon Manager - Cluster Lockfile Management")
    print("=" * 70)
    
    # Initialize the daemon manager
    daemon_manager = EnhancedDaemonManager()
    
    print("\n📋 Current cluster state:")
    cluster_config_dir = Path.home() / ".ipfs-cluster"
    lockfile_path = cluster_config_dir / "cluster.lock"
    
    print(f"Cluster config dir: {cluster_config_dir}")
    print(f"Lockfile exists: {lockfile_path.exists()}")
    print(f"Daemon running: {daemon_manager._is_cluster_daemon_running()}")
    if daemon_manager._is_cluster_daemon_running():
        print(f"API healthy: {daemon_manager._test_cluster_api_health()}")
    
    print("\n🔧 Testing lockfile management...")
    result = daemon_manager._manage_cluster_lockfile_and_daemon()
    
    print(f"Success: {result['success']}")
    print(f"Action taken: {result['action']}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    
    print("\n📋 State after lockfile management:")
    print(f"Lockfile exists: {lockfile_path.exists()}")
    print(f"Daemon running: {daemon_manager._is_cluster_daemon_running()}")
    if daemon_manager._is_cluster_daemon_running():
        print(f"API healthy: {daemon_manager._test_cluster_api_health()}")
    
    print("\n🚀 Testing cluster service startup...")
    startup_result = daemon_manager._start_ipfs_cluster_service()
    
    print(f"Startup success: {startup_result['success']}")
    print(f"Status: {startup_result['status']}")
    if startup_result.get('error'):
        print(f"Error: {startup_result['error']}")
    
    print("\n📋 Final state:")
    print(f"Lockfile exists: {lockfile_path.exists()}")
    print(f"Daemon running: {daemon_manager._is_cluster_daemon_running()}")
    if daemon_manager._is_cluster_daemon_running():
        print(f"API healthy: {daemon_manager._test_cluster_api_health()}")
    
    print("\n✨ Test complete!")
    return result

if __name__ == "__main__":
    result = test_cluster_lockfile_management()
