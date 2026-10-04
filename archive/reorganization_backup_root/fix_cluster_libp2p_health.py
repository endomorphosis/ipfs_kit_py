#!/usr/bin/env python3
"""
Fix IPFS Cluster and LibP2P Health Issues

This script diagnoses and fixes the current issues with:
1. IPFS Cluster service connectivity
2. LibP2P peer network
3. IPFS daemon responsiveness
"""

import os
import sys
import json
import time
import asyncio
import subprocess
import logging
from pathlib import Path

# Add the project to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ipfs_kit_py.ipfs_daemon_manager import IPFSDaemonManager, IPFSConfig
from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class ClusterHealthFixer:
    """Comprehensive cluster and libp2p health fixer."""
    
    def __init__(self):
        self.ipfs_config = IPFSConfig()
        self.ipfs_manager = IPFSDaemonManager(self.ipfs_config)
        self.cluster_manager = IPFSClusterDaemonManager()
        
    async def diagnose_and_fix(self):
        """Run comprehensive diagnosis and fix."""
        print("🔍 Starting comprehensive IPFS Cluster and LibP2P health diagnosis...")
        
        # Step 1: Check IPFS daemon health
        print("\n1️⃣ Checking IPFS daemon health...")
        await self.check_and_fix_ipfs()
        
        # Step 2: Check and fix cluster configuration
        print("\n2️⃣ Checking IPFS Cluster configuration...")
        await self.check_and_fix_cluster_config()
        
        # Step 3: Start cluster service
        print("\n3️⃣ Starting IPFS Cluster service...")
        await self.start_cluster_service()
        
        # Step 4: Check LibP2P network
        print("\n4️⃣ Checking LibP2P peer network...")
        await self.check_and_fix_libp2p()
        
        # Step 5: Final health check
        print("\n5️⃣ Final health verification...")
        await self.verify_final_health()
        
    async def check_and_fix_ipfs(self):
        """Check and fix IPFS daemon."""
        try:
            status = self.ipfs_manager.get_daemon_status()
            
            if status.get("running") and status.get("api_responsive"):
                print(f"✅ IPFS daemon is healthy (PID: {status.get('pid')})")
                
                # Check actual port
                port_usage = status.get("port_usage", {})
                api_port = port_usage.get("api", {}).get("port", self.ipfs_config.api_port)
                print(f"   📡 IPFS API available on port {api_port}")
                return api_port
            else:
                print("⚠️  IPFS daemon not healthy, attempting to fix...")
                result = self.ipfs_manager.start_daemon()
                
                if result.get("success"):
                    # Wait for startup
                    await asyncio.sleep(3)
                    new_status = self.ipfs_manager.get_daemon_status()
                    
                    if new_status.get("running") and new_status.get("api_responsive"):
                        print(f"✅ IPFS daemon fixed and now healthy (PID: {new_status.get('pid')})")
                        port_usage = new_status.get("port_usage", {})
                        api_port = port_usage.get("api", {}).get("port", self.ipfs_config.api_port)
                        return api_port
                    else:
                        print("❌ Failed to make IPFS daemon healthy")
                        return None
                else:
                    print(f"❌ Failed to start IPFS daemon: {result.get('error')}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error checking IPFS daemon: {e}")
            return None
    
    async def check_and_fix_cluster_config(self):
        """Check and fix cluster configuration."""
        try:
            # Get IPFS API port
            status = self.ipfs_manager.get_daemon_status()
            if not status.get("running"):
                print("❌ IPFS not running, cannot configure cluster")
                return False
                
            port_usage = status.get("port_usage", {})
            ipfs_api_port = port_usage.get("api", {}).get("port", 5001)
            
            # Check cluster configuration
            config_path = Path("~/.ipfs-cluster/service.json").expanduser()
            
            if config_path.exists():
                print(f"📄 Found cluster config at {config_path}")
                
                # Read and check config
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                # Check IPFS connector configuration
                ipfshttp_config = config.get("ipfshttp", {})
                node_multiaddress = ipfshttp_config.get("node_multiaddress", "")
                
                expected_multiaddr = f"/ip4/127.0.0.1/tcp/{ipfs_api_port}"
                
                if expected_multiaddr not in node_multiaddress:
                    print(f"🔧 Fixing cluster config - updating IPFS port to {ipfs_api_port}")
                    
                    # Update configuration
                    ipfshttp_config["node_multiaddress"] = expected_multiaddr
                    config["ipfshttp"] = ipfshttp_config
                    
                    # Write back configuration
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    print("✅ Cluster configuration updated")
                else:
                    print(f"✅ Cluster configuration already correct ({expected_multiaddr})")
                    
                return True
            else:
                print("⚠️  Cluster config not found, initializing...")
                
                # Initialize cluster with correct IPFS port
                binary_path = self.cluster_manager.config.cluster_service_bin
                if binary_path and Path(binary_path).exists():
                    env = os.environ.copy()
                    env["PATH"] = f"{Path(binary_path).parent}:{env.get('PATH', '')}"
                    
                    # Initialize with custom IPFS endpoint
                    init_cmd = [
                        binary_path, "init",
                        "--ipfs-api", f"/ip4/127.0.0.1/tcp/{ipfs_api_port}"
                    ]
                    
                    result = subprocess.run(
                        init_cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=30,
                        env=env
                    )
                    
                    if result.returncode == 0:
                        print("✅ Cluster initialized with correct IPFS endpoint")
                        return True
                    else:
                        print(f"❌ Failed to initialize cluster: {result.stderr}")
                        return False
                else:
                    print("❌ Cluster binary not found")
                    return False
                    
        except Exception as e:
            print(f"❌ Error checking cluster config: {e}")
            return False
    
    async def start_cluster_service(self):
        """Start the cluster service."""
        try:
            # Check if already running
            cluster_status = await self.cluster_manager.get_cluster_service_status()
            
            if cluster_status.get("running") and cluster_status.get("api_responsive"):
                print(f"✅ Cluster service already running and healthy (PID: {cluster_status.get('pid')})")
                return True
                
            print("🚀 Starting cluster service...")
            start_result = await self.cluster_manager.start_cluster_service()
            
            if start_result.get("success"):
                print(f"✅ Cluster service started successfully")
                
                # Wait for API to become responsive
                print("⏳ Waiting for cluster API to become responsive...")
                for i in range(10):
                    await asyncio.sleep(2)
                    status = await self.cluster_manager.get_cluster_service_status()
                    
                    if status.get("api_responsive"):
                        print(f"✅ Cluster API is now responsive (attempt {i+1})")
                        return True
                    else:
                        print(f"⏳ API not yet responsive (attempt {i+1}/10)")
                
                print("⚠️  Cluster started but API not responsive")
                return False
            else:
                errors = start_result.get("errors", ["Unknown error"])
                print(f"❌ Failed to start cluster: {errors}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting cluster service: {e}")
            return False
    
    async def check_and_fix_libp2p(self):
        """Check and fix LibP2P network."""
        try:
            print("🌐 Initializing LibP2P peer manager...")
            
            # Try to import and initialize peer manager
            try:
                from ipfs_kit_py.libp2p.peer_manager import get_peer_manager
                
                config_dir = Path("/tmp/ipfs_kit_config/libp2p")
                config_dir.mkdir(parents=True, exist_ok=True)
                
                peer_manager = get_peer_manager(config_dir=config_dir)
                
                # Start peer manager if not already started
                if not peer_manager.discovery_active:
                    print("🚀 Starting LibP2P peer discovery...")
                    await peer_manager.start()
                    
                    # Wait for discovery to initialize
                    await asyncio.sleep(5)
                
                # Get peer statistics
                stats = peer_manager.get_peer_statistics()
                
                print(f"📊 LibP2P Network Status:")
                print(f"   🔍 Discovery Active: {stats['discovery_active']}")
                print(f"   👥 Total Peers: {stats['total_peers']}")
                print(f"   🔗 Connected Peers: {stats['connected_peers']}")
                print(f"   📁 Accessible Files: {stats['total_files']}")
                print(f"   📌 Accessible Pins: {stats['total_pins']}")
                
                if stats["discovery_active"] and stats["total_peers"] > 0:
                    print("✅ LibP2P peer network is healthy")
                    return True
                elif stats["discovery_active"]:
                    print("⚠️  LibP2P discovery active but no peers found yet")
                    return True
                else:
                    print("❌ LibP2P discovery not active")
                    return False
                    
            except ImportError as e:
                print(f"⚠️  LibP2P peer manager not available: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Error checking LibP2P: {e}")
            return False
    
    async def verify_final_health(self):
        """Verify final health status."""
        print("🏥 Final health verification...")
        
        # Check IPFS
        ipfs_status = self.ipfs_manager.get_daemon_status()
        ipfs_healthy = ipfs_status.get("running") and ipfs_status.get("api_responsive")
        print(f"   IPFS: {'✅ Healthy' if ipfs_healthy else '❌ Unhealthy'}")
        
        # Check Cluster
        cluster_status = await self.cluster_manager.get_cluster_service_status()
        cluster_healthy = cluster_status.get("running") and cluster_status.get("api_responsive")
        print(f"   Cluster: {'✅ Healthy' if cluster_healthy else '❌ Unhealthy'}")
        
        # Summary
        if ipfs_healthy and cluster_healthy:
            print("\n🎉 All services are now healthy!")
            return True
        else:
            print("\n⚠️  Some services still have issues")
            return False

async def main():
    """Main execution function."""
    fixer = ClusterHealthFixer()
    success = await fixer.diagnose_and_fix()
    
    if success:
        print("\n✅ Health fix completed successfully!")
    else:
        print("\n⚠️  Health fix completed with some issues")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())
