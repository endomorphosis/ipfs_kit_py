#!/usr/bin/env python3
"""
IPFS Cluster API Test Script

This script tests the IPFS Cluster API endpoints to verify they're working correctly
and shows what the health monitor should be detecting.
"""

import anyio
import httpx
import json
import time
from datetime import datetime

async def test_cluster_api():
    """Test IPFS Cluster API endpoints."""
    
    port = 9094
    base_url = f"http://127.0.0.1:{port}"
    
    print("🧪 Testing IPFS Cluster API")
    print("=" * 50)
    print(f"Base URL: {base_url}")
    print()
    
    async with httpx.AsyncClient(timeout=10) as client:
        
        # Test 1: Health endpoint (no auth required)
        print("1. Testing /health endpoint...")
        try:
            response = await client.get(f"{base_url}/health")
            print(f"   Status: {response.status_code}")
            if response.status_code == 204:
                print("   ✅ Health check passed (204 No Content)")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
        print()
        
        # Test 2: Version endpoint
        print("2. Testing /version endpoint...")
        try:
            response = await client.get(f"{base_url}/version")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                version_data = response.json()
                print(f"   ✅ Version: {version_data}")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Version check failed: {e}")
        print()
        
        # Test 3: ID endpoint  
        print("3. Testing /id endpoint...")
        try:
            response = await client.get(f"{base_url}/id")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                id_data = response.json()
                print(f"   ✅ Peer ID: {id_data.get('id', 'unknown')[:16]}...")
                print(f"   Peername: {id_data.get('peername', 'unknown')}")
                print(f"   Addresses: {len(id_data.get('addresses', []))} addresses")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ ID check failed: {e}")
        print()
        
        # Test 4: Peers endpoint
        print("4. Testing /peers endpoint...")
        try:
            response = await client.get(f"{base_url}/peers")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                peers_data = response.json()
                print(f"   ✅ Found {len(peers_data)} cluster peers")
                for i, peer in enumerate(peers_data[:3]):  # Show first 3
                    print(f"     Peer {i+1}: {peer.get('id', 'unknown')[:16]}... ({peer.get('peername', 'unknown')})")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Peers check failed: {e}")
        print()
        
        # Test 5: Pins endpoint (might be large)
        print("5. Testing /pins endpoint...")
        try:
            response = await client.get(f"{base_url}/pins")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                # For streaming endpoints, we might get NDJSON
                content = response.text.strip()
                if content:
                    lines = content.split('\\n')
                    print(f"   ✅ Pins response: {len(lines)} lines")
                    if lines[0]:
                        try:
                            first_pin = json.loads(lines[0])
                            print(f"     Sample pin: {first_pin.get('cid', 'unknown')[:16]}...")
                        except:
                            print(f"     First line: {lines[0][:50]}...")
                else:
                    print("   ✅ No pins found (empty response)")
            else:
                print(f"   ⚠️  Unexpected status code: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
        except Exception as e:
            print(f"   ❌ Pins check failed: {e}")
        print()

async def test_health_manager_integration():
    """Test the health manager with the cluster."""
    
    print("🏥 Testing Health Manager Integration")
    print("=" * 50)
    
    try:
        from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager
        
        print("✅ Successfully imported cluster daemon manager")
        
        # Create manager
        manager = IPFSClusterDaemonManager()
        print(f"   API Port: {manager.config.api_port}")
        
        # Test API health check
        print("\\n📡 Testing API health check...")
        api_healthy = await manager._check_service_api_health()
        print(f"   API Responsive: {api_healthy}")
        
        if api_healthy:
            print("\\n📊 Getting cluster status...")
            status = await manager.get_cluster_service_status()
            
            print(f"   Running: {status.get('running', False)}")
            print(f"   API Responsive: {status.get('api_responsive', False)}")
            print(f"   PID: {status.get('pid', 'unknown')}")
            print(f"   Version: {status.get('version', 'unknown')}")
            print(f"   Peer Count: {status.get('peer_count', 0)}")
            
            if status.get("running") and status.get("api_responsive"):
                print("\\n✅ Cluster status: HEALTHY")
            elif status.get("running"):
                print("\\n⚠️  Cluster status: DEGRADED (API issues)")
            else:
                print("\\n❌ Cluster status: UNHEALTHY (not running)")
        else:
            print("\\n❌ API health check failed")
            
    except ImportError as e:
        print(f"❌ Failed to import cluster daemon manager: {e}")
    except Exception as e:
        print(f"❌ Health manager test failed: {e}")

async def main():
    """Run all tests."""
    
    print(f"IPFS Cluster API Test Suite")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    await test_cluster_api()
    print()
    await test_health_manager_integration()
    
    print("\\n🎯 Test Summary:")
    print("If all tests pass, the cluster API is working correctly")
    print("and the health monitor should detect it as healthy.")

if __name__ == "__main__":
    anyio.run(main)
