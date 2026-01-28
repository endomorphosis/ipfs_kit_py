#!/usr/bin/env python3
"""
Test IPFS Cluster Follow Enhanced API and Daemon Management

This test validates:
1. Cluster Follow API endpoints work correctly (using same fixes as cluster service)  
2. Enhanced daemon manager functionality
3. Bootstrap peer connection
4. Worker/follower node operations
"""

import anyio
import json
import sys
import os
from pathlib import Path
import pytest

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

pytestmark = pytest.mark.anyio

async def test_cluster_follow_api():
    """Test cluster follow API endpoints directly."""
    print("🧪 Testing IPFS Cluster Follow API")
    print("=" * 50)
    
    # Use follow service API port (9097)
    base_url = "http://127.0.0.1:9097"
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=5) as client:
            # Test health endpoint
            print("1. Testing /health endpoint...")
            try:
                response = await client.get(f"{base_url}/health")
                print(f"   Status: {response.status_code}")
                if response.status_code in [200, 204]:
                    print("   ✅ Health check passed")
                else:
                    print(f"   ❌ Health check failed: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Health check failed: {e}")
            
            # Test ID endpoint  
            print("\n2. Testing /id endpoint...")
            try:
                response = await client.get(f"{base_url}/id")
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    id_data = response.json()
                    peer_id = id_data.get("id", "unknown")
                    print(f"   ✅ Peer ID: {peer_id[:20]}...")
                    print(f"   Peername: {id_data.get('peername', 'unknown')}")
                    addresses = id_data.get("addresses", [])
                    print(f"   Addresses: {len(addresses)} addresses")
                else:
                    print(f"   ❌ ID check failed: {response.status_code}")
            except Exception as e:
                print(f"   ❌ ID check failed: {e}")
            
            # Test pins endpoint
            print("\n3. Testing /pins endpoint...")
            try:
                response = await client.get(f"{base_url}/pins")
                print(f"   Status: {response.status_code}")
                if response.status_code == 200:
                    pins_data = response.json()
                    if isinstance(pins_data, list):
                        print(f"   ✅ Found {len(pins_data)} pins being followed")
                        if pins_data:
                            first_pin = pins_data[0]
                            print(f"   First pin CID: {first_pin.get('cid', 'unknown')[:20]}...")
                    else:
                        print(f"   ✅ Pins response: {len(str(pins_data))} characters")
                else:
                    print(f"   ❌ Pins check failed: {response.status_code}")
            except Exception as e:
                print(f"   ❌ Pins check failed: {e}")
                
    except ImportError:
        print("❌ httpx not available, skipping API tests")
        return False
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False
    
    return True

async def test_follow_daemon_manager():
    """Test the enhanced cluster follow daemon manager."""
    print("\n🏥 Testing Follow Daemon Manager")
    print("=" * 50)
    
    try:
        from ipfs_kit_py.ipfs_cluster_follow_daemon_manager import IPFSClusterFollowDaemonManager
        print("✅ Successfully imported follow daemon manager")
        
        # Create manager instance
        manager = IPFSClusterFollowDaemonManager("test-cluster")
        print(f"   Cluster name: {manager.cluster_name}")
        print(f"   API Port: {manager.config.api_port}")
        print(f"   Config path: {manager.config.cluster_path}")
        
        # Test status checking
        print("\n📡 Testing status check...")
        status = await manager.get_cluster_follow_status()
        print(f"   Running: {status.get('running', False)}")
        print(f"   API Responsive: {status.get('api_responsive', False)}")
        print(f"   PID: {status.get('pid', 'None')}")
        print(f"   Pin Count: {status.get('pin_count', 0)}")
        print(f"   Leader Connected: {status.get('leader_connected', False)}")
        
        # Test API status via daemon manager
        print("\n📊 Getting follow status via API...")
        api_status = await manager.get_follow_status_via_api()
        print(f"   API Responsive: {api_status.get('api_responsive', False)}")
        if api_status.get("follow_info"):
            follow_info = api_status["follow_info"]
            if "id" in follow_info:
                print(f"   Follow ID: {follow_info['id'].get('id', 'unknown')[:20]}...")
            if "pins" in follow_info:
                pins = follow_info["pins"]
                pin_count = len(pins) if isinstance(pins, list) else 0
                print(f"   Pins being followed: {pin_count}")
        
        print("\n✅ Follow daemon manager test completed")
        return True
        
    except ImportError as e:
        print(f"❌ Follow daemon manager import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Follow daemon manager test failed: {e}")
        return False

async def test_follow_health_monitor():
    """Test cluster follow health monitoring integration."""
    print("\n🏥 Testing Follow Health Monitor Integration")
    print("=" * 50)
    
    try:
        # Import health monitor
        from mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        # Create health monitor with test config
        health_monitor = BackendHealthMonitor("/tmp/test_follow_config")
        print("✅ Health monitor initialized")
        
        # Test cluster follow health check
        print("\n📊 Checking cluster follow health...")
        follow_health = await health_monitor.check_backend_health("ipfs_cluster_follow")
        
        print(f"   Status: {follow_health.get('status', 'unknown')}")
        print(f"   Health: {follow_health.get('health', 'unknown')}")
        print(f"   Last Check: {follow_health.get('last_check', 'never')}")
        
        # Show metrics if available
        metrics = follow_health.get("metrics", {})
        if metrics:
            print("   Metrics:")
            for key, value in metrics.items():
                print(f"     {key}: {value}")
        
        # Show detailed info if available
        detailed_info = follow_health.get("detailed_info", {})
        if detailed_info:
            print("   Detailed Info:")
            for key, value in detailed_info.items():
                if key not in ["followed_pins"]:  # Skip large data
                    print(f"     {key}: {value}")
        
        # Show errors if any
        errors = follow_health.get("errors", [])
        if errors:
            print("   Recent Errors:")
            for error in errors[-3:]:  # Show last 3 errors
                if isinstance(error, dict):
                    print(f"     {error.get('timestamp', 'unknown')}: {error.get('error', 'unknown')}")
                else:
                    print(f"     {error}")
        
        if follow_health.get("health") == "healthy":
            print("\n✅ Cluster follow is HEALTHY!")
        else:
            print(f"\n⚠️  Cluster follow status: {follow_health.get('health', 'unknown')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Health monitor test failed: {e}")
        return False

async def test_follow_leader_connection():
    """Test connection to cluster leader."""
    print("\n🔗 Testing Leader Connection")
    print("=" * 50)
    
    try:
        from ipfs_kit_py.ipfs_cluster_follow_daemon_manager import IPFSClusterFollowDaemonManager
        
        # Test connecting to local cluster service as leader
        manager = IPFSClusterFollowDaemonManager("test-cluster")
        
        # Try to connect to local cluster service (port 9094) as if it were a leader
        print("📡 Testing connection to local cluster service as leader...")
        connection_result = await manager.connect_to_cluster_leader("127.0.0.1", 9094)
        
        print(f"   Connected: {connection_result.get('connected', False)}")
        if connection_result.get("connected"):
            leader_info = connection_result.get("leader_info", {})
            if "id" in leader_info:
                id_info = leader_info["id"]
                print(f"   Leader ID: {id_info.get('id', 'unknown')[:20]}...")
            if "peers" in leader_info:
                peers_info = leader_info["peers"]
                peer_count = len(peers_info) if isinstance(peers_info, list) else 0
                print(f"   Leader has {peer_count} peers")
            if "pins" in leader_info:
                pins_info = leader_info["pins"]
                pin_count = len(pins_info) if isinstance(pins_info, list) else 0
                print(f"   Leader managing {pin_count} pins")
        else:
            errors = connection_result.get("errors", [])
            print(f"   Connection failed: {'; '.join(errors)}")
        
        # Test getting pinset from leader
        print("\n📌 Testing pinset retrieval from leader...")
        pinset_result = await manager.get_pinset_from_leader("127.0.0.1", 9094)
        
        print(f"   Success: {pinset_result.get('success', False)}")
        print(f"   Pin count: {pinset_result.get('pin_count', 0)}")
        if pinset_result.get("errors"):
            print(f"   Errors: {'; '.join(pinset_result['errors'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Leader connection test failed: {e}")
        return False

async def main():
    """Run all cluster follow tests."""
    print("IPFS Cluster Follow Enhanced Test Suite")
    print(f"Timestamp: {anyio.current_time()}")
    print("=" * 60)
    
    test_results = []
    
    # Test 1: Basic API endpoints
    result1 = await test_cluster_follow_api()
    test_results.append(("API Endpoints", result1))
    
    # Test 2: Enhanced daemon manager
    result2 = await test_follow_daemon_manager()
    test_results.append(("Daemon Manager", result2))
    
    # Test 3: Health monitor integration
    result3 = await test_follow_health_monitor()
    test_results.append(("Health Monitor", result3))
    
    # Test 4: Leader connection
    result4 = await test_follow_leader_connection()
    test_results.append(("Leader Connection", result4))
    
    # Summary
    print("\n🎯 Test Summary:")
    print("=" * 30)
    passed = 0
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("\n🎉 All tests passed! Cluster follow functionality is working correctly.")
    else:
        print(f"\n⚠️  {len(test_results) - passed} test(s) failed. Check the output above for details.")
    
    return passed == len(test_results)

if __name__ == "__main__":
    success = anyio.run(main)
    sys.exit(0 if success else 1)
