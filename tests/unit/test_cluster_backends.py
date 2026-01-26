#!/usr/bin/env python3
"""
Test and start IPFS cluster backends
====================================

This script will test the IPFS cluster backends and start the daemons if needed.
"""

import anyio
import sys
import os
import subprocess
import logging
from pathlib import Path

# Add project root to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Import the backend health monitor
from mcp.ipfs_kit.backends import BackendHealthMonitor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_cluster_backends():
    """Test and diagnose IPFS cluster backends."""
    
    print("🔍 Testing IPFS Cluster backends...")
    print("=" * 50)
    
    # Initialize the health monitor
    health_monitor = BackendHealthMonitor()
    
    # Add bin directory to PATH
    project_bin = str(current_dir / "ipfs_kit_py" / "bin")
    os.environ["PATH"] = f"{project_bin}:{os.environ.get('PATH', '')}"
    
    # Test IPFS first
    print("\n📊 Checking IPFS daemon status...")
    ipfs_health = await health_monitor.check_backend_health("ipfs")
    print(f"IPFS Status: {ipfs_health.get('status', 'unknown')}")
    print(f"IPFS Health: {ipfs_health.get('health', 'unknown')}")
    if ipfs_health.get('errors'):
        print(f"IPFS Errors: {ipfs_health['errors'][-1]}")  # Show latest error
    
    # Test IPFS Cluster Service
    print("\n📊 Checking IPFS Cluster Service status...")
    cluster_health = await health_monitor.check_backend_health("ipfs_cluster")
    print(f"Cluster Status: {cluster_health.get('status', 'unknown')}")
    print(f"Cluster Health: {cluster_health.get('health', 'unknown')}")
    if cluster_health.get('errors'):
        print(f"Cluster Errors: {cluster_health['errors'][-1]}")  # Show latest error
    
    # Test IPFS Cluster Follow
    print("\n📊 Checking IPFS Cluster Follow status...")
    follow_health = await health_monitor.check_backend_health("ipfs_cluster_follow")
    print(f"Follow Status: {follow_health.get('status', 'unknown')}")
    print(f"Follow Health: {follow_health.get('health', 'unknown')}")
    if follow_health.get('errors'):
        print(f"Follow Errors: {follow_health['errors'][-1]}")  # Show latest error
        
    # Try to start daemons if they're not running
    if cluster_health.get('status') != 'running':
        print("\n🚀 Attempting to start IPFS Cluster Service...")
        try:
            # Initialize cluster service if needed
            init_result = subprocess.run(
                [f"{project_bin}/ipfs-cluster-service", "init"],
                capture_output=True, text=True, timeout=30
            )
            print(f"Cluster init result: {init_result.returncode}")
            if init_result.stdout:
                print(f"Init stdout: {init_result.stdout}")
            if init_result.stderr:
                print(f"Init stderr: {init_result.stderr}")
            
            # Start cluster service daemon
            cluster_proc = subprocess.Popen(
                [f"{project_bin}/ipfs-cluster-service", "daemon"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            print(f"Started cluster service daemon with PID: {cluster_proc.pid}")
            
            # Give it a moment to start
            await anyio.sleep(3)
            
            # Recheck health
            cluster_health = await health_monitor.check_backend_health("ipfs_cluster")
            print(f"Cluster Status after start: {cluster_health.get('status', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Failed to start cluster service: {e}")
    
    if follow_health.get('status') != 'running':
        print("\n🚀 Attempting to start IPFS Cluster Follow...")
        try:
            # Start cluster follow daemon - this needs a cluster to follow
            # For testing, we'll just show the command
            print("Cluster follow requires a target cluster to follow.")
            print(f"Example command: {project_bin}/ipfs-cluster-follow <cluster-name> run")
            print("You would need to specify a cluster name/address to follow.")
            
        except Exception as e:
            print(f"❌ Failed to start cluster follow: {e}")
    
    # Show final status
    print("\n📋 Final Backend Status Summary:")
    print("-" * 30)
    
    all_backends = await health_monitor.check_all_backends()
    for name, status in all_backends.items():
        if name in ['ipfs', 'ipfs_cluster', 'ipfs_cluster_follow']:
            health_emoji = "✅" if status.get('health') == 'healthy' else "❌"
            print(f"{health_emoji} {name.replace('_', ' ').title()}: {status.get('status', 'unknown')}")
    
    print("\n✨ Diagnosis complete!")
    return all_backends

if __name__ == "__main__":
    results = anyio.run(test_cluster_backends)
