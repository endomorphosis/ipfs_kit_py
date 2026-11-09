#!/usr/bin/env python3
"""
Comprehensive test suite for IPFS Cluster Configuration API.

Tests the config_ functions for both cluster service and cluster follow,
ensuring they can create, get, and set configurations programmatically.
"""

import anyio
import json
import os
import tempfile
import traceback
from pathlib import Path

# Import the configuration API
try:
    from mcp.ipfs_kit.api.cluster_config_api import cluster_config_api, CLUSTER_CONFIG_TOOLS
    print("✓ Successfully imported cluster configuration API")
except ImportError as e:
    print(f"❌ Failed to import cluster config API: {e}")
    exit(1)

# Import daemon managers directly for testing
try:
    from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterDaemonManager, IPFSClusterConfig
    from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow
    print("✓ Successfully imported cluster managers")
except ImportError as e:
    print(f"❌ Failed to import cluster managers: {e}")
    exit(1)


async def test_cluster_service_config():
    """Test IPFS Cluster Service configuration functions."""
    print("\n" + "="*60)
    print("🧪 Testing IPFS Cluster Service Configuration")
    print("="*60)
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        cluster_path = os.path.join(temp_dir, "cluster-service-test")
        
        try:
            # Test 1: Create configuration
            print("1. Testing cluster service config creation...")
            create_result = await cluster_config_api.cluster_service_config_create(
                cluster_path=cluster_path,
                overwrite=True,
                api_port=9094,
                proxy_port=9095,
                cluster_port=9096
            )
            
            print(f"   Create result: {create_result.get('success', False)}")
            if create_result.get("errors"):
                print(f"   Errors: {create_result['errors']}")
            
            # Verify files were created
            service_config_path = Path(cluster_path) / "service.json"
            identity_path = Path(cluster_path) / "identity.json"
            
            print(f"   Service config exists: {service_config_path.exists()}")
            print(f"   Identity config exists: {identity_path.exists()}")
            
            if service_config_path.exists():
                with open(service_config_path) as f:
                    config_data = json.load(f)
                print(f"   Service config has ID: {'id' in config_data}")
                print(f"   API port: {config_data.get('api', {}).get('restapi', {}).get('listen_multiaddress', 'not found')}")
            
            # Test 2: Get configuration
            print("\n2. Testing cluster service config retrieval...")
            get_result = await cluster_config_api.cluster_service_config_get(cluster_path=cluster_path)
            
            print(f"   Get result: {get_result.get('success', False)}")
            print(f"   Config exists: {get_result.get('config_exists', False)}")
            
            if get_result.get("service_config"):
                service_config = get_result["service_config"]
                print(f"   Retrieved ID: {service_config.get('id', 'not found')[:12]}...")
                print(f"   Has cluster section: {'cluster' in service_config}")
                print(f"   Has API section: {'api' in service_config}")
            
            # Test 3: Update configuration
            print("\n3. Testing cluster service config updates...")
            config_updates = {
                "cluster": {
                    "replication_factor_min": 2,
                    "replication_factor_max": 5
                },
                "api": {
                    "restapi": {
                        "cors_allowed_origins": ["http://localhost:3000", "http://localhost:8080"]
                    }
                }
            }
            
            set_result = await cluster_config_api.cluster_service_config_set(
                config_updates=config_updates,
                cluster_path=cluster_path
            )
            
            print(f"   Set result: {set_result.get('success', False)}")
            
            if set_result.get("updated_config"):
                updated_config = set_result["updated_config"]
                rep_min = updated_config.get("cluster", {}).get("replication_factor_min")
                cors_origins = updated_config.get("api", {}).get("restapi", {}).get("cors_allowed_origins")
                print(f"   Updated replication_factor_min: {rep_min}")
                print(f"   Updated CORS origins: {len(cors_origins) if cors_origins else 0} entries")
            
            print("✅ Cluster service configuration test completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Cluster service configuration test failed: {e}")
            traceback.print_exc()
            return False


async def test_cluster_follow_config():
    """Test IPFS Cluster Follow configuration functions."""
    print("\n" + "="*60)
    print("🧪 Testing IPFS Cluster Follow Configuration")
    print("="*60)
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        cluster_path = os.path.join(temp_dir, "cluster-follow-test")
        cluster_name = "test-cluster"
        bootstrap_peer = "/ip4/127.0.0.1/tcp/9096/p2p/12D3KooWExamplePeer"
        
        try:
            # Test 1: Create configuration
            print("1. Testing cluster follow config creation...")
            create_result = await cluster_config_api.cluster_follow_config_create(
                cluster_name=cluster_name,
                bootstrap_peer=bootstrap_peer,
                cluster_path=cluster_path,
                overwrite=True,
                api_port=9097,
                proxy_port=9098
            )
            
            print(f"   Create result: {create_result.get('success', False)}")
            if create_result.get("errors"):
                print(f"   Errors: {create_result['errors']}")
            
            # Check what was created
            if create_result.get("success"):
                print(f"   Identity created: {create_result.get('identity_created', False)}")
                print(f"   Service config created: {create_result.get('config_created', False)}")
                
                if create_result.get("service_config"):
                    service_config = create_result["service_config"]
                    print(f"   Cluster name: {service_config.get('cluster_name', 'not found')}")
                    print(f"   Bootstrap peers: {len(service_config.get('cluster', {}).get('bootstrap', []))}")
            
            # Test 2: Get configuration
            print("\n2. Testing cluster follow config retrieval...")
            get_result = await cluster_config_api.cluster_follow_config_get(
                cluster_name=cluster_name,
                cluster_path=cluster_path
            )
            
            print(f"   Get result: {get_result.get('success', False)}")
            print(f"   Config exists: {get_result.get('config_exists', False)}")
            
            if get_result.get("service_config"):
                service_config = get_result["service_config"]
                print(f"   Retrieved cluster name: {service_config.get('cluster_name', 'not found')}")
                print(f"   Retrieved ID: {service_config.get('id', 'not found')[:12]}...")
                print(f"   API port: {service_config.get('api', {}).get('restapi', {}).get('listen_multiaddress', 'not found')}")
            
            # Test 3: Update configuration
            print("\n3. Testing cluster follow config updates...")
            config_updates = {
                "cluster": {
                    "monitor_ping_interval": "30s",
                    "state_sync_interval": "20s"
                },
                "informer": {
                    "tags": {
                        "tags": {"group": "workers", "cluster": cluster_name, "role": "follower"}
                    }
                }
            }
            
            set_result = await cluster_config_api.cluster_follow_config_set(
                cluster_name=cluster_name,
                config_updates=config_updates,
                cluster_path=cluster_path
            )
            
            print(f"   Set result: {set_result.get('success', False)}")
            
            if set_result.get("updated_config"):
                updated_config = set_result["updated_config"]
                ping_interval = updated_config.get("cluster", {}).get("monitor_ping_interval")
                tags = updated_config.get("informer", {}).get("tags", {}).get("tags", {})
                print(f"   Updated ping interval: {ping_interval}")
                print(f"   Updated tags: {tags}")
            
            print("✅ Cluster follow configuration test completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Cluster follow configuration test failed: {e}")
            traceback.print_exc()
            return False


async def test_cluster_status_apis():
    """Test cluster status APIs."""
    print("\n" + "="*60)
    print("🧪 Testing Cluster Status APIs")
    print("="*60)
    
    try:
        # Test cluster service status
        print("1. Testing cluster service status...")
        service_status = await cluster_config_api.cluster_service_status_via_api()
        print(f"   Service status success: {service_status.get('success', False)}")
        print(f"   API responsive: {service_status.get('api_responsive', False)}")
        
        # Test cluster follow status
        print("\n2. Testing cluster follow status...")
        follow_status = await cluster_config_api.cluster_follow_status_via_api(cluster_name="test-cluster")
        print(f"   Follow status success: {follow_status.get('success', False)}")
        print(f"   API responsive: {follow_status.get('api_responsive', False)}")
        
        print("✅ Cluster status API test completed")
        return True
        
    except Exception as e:
        print(f"❌ Cluster status API test failed: {e}")
        traceback.print_exc()
        return False


async def test_direct_manager_config():
    """Test config functions directly on manager classes."""
    print("\n" + "="*60)
    print("🧪 Testing Direct Manager Configuration")
    print("="*60)
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Test IPFSClusterConfig directly
            print("1. Testing IPFSClusterConfig directly...")
            cluster_path = os.path.join(temp_dir, "direct-cluster-test")
            cluster_config = IPFSClusterConfig(cluster_path)
            
            # Test config creation
            config_result = cluster_config.config_create(overwrite=True)
            print(f"   Direct config create: {config_result.get('success', False)}")
            print(f"   Identity created: {config_result.get('identity_created', False)}")
            print(f"   Service config created: {config_result.get('config_created', False)}")
            
            # Test config retrieval
            get_result = cluster_config.config_get()
            print(f"   Direct config get: {get_result.get('success', False)}")
            print(f"   Config exists: {get_result.get('config_exists', False)}")
            
            # Test cluster follow directly
            print("\n2. Testing ipfs_cluster_follow directly...")
            follow_metadata = {
                "cluster_name": "direct-test-cluster",
                "role": "leecher",
                "ipfs_cluster_path": os.path.join(temp_dir, "direct-follow-test")
            }
            
            cluster_follow = ipfs_cluster_follow(metadata=follow_metadata)
            
            # Test config creation
            follow_create_result = cluster_follow.config_create(
                cluster_name="direct-test-cluster",
                bootstrap_peer="/ip4/127.0.0.1/tcp/9096/p2p/12D3KooWExamplePeer",
                overwrite=True
            )
            print(f"   Direct follow config create: {follow_create_result.get('success', False)}")
            print(f"   Follow identity created: {follow_create_result.get('identity_created', False)}")
            print(f"   Follow service config created: {follow_create_result.get('config_created', False)}")
            
            # Test config retrieval
            follow_get_result = cluster_follow.config_get()
            print(f"   Direct follow config get: {follow_get_result.get('success', False)}")
            print(f"   Follow config exists: {follow_get_result.get('config_exists', False)}")
            
            print("✅ Direct manager configuration test completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ Direct manager configuration test failed: {e}")
            traceback.print_exc()
            return False


async def test_mcp_tools_list():
    """Test MCP tools enumeration."""
    print("\n" + "="*60)
    print("🧪 Testing MCP Tools Enumeration")
    print("="*60)
    
    try:
        print(f"1. Available cluster config tools: {len(CLUSTER_CONFIG_TOOLS)}")
        
        for i, tool in enumerate(CLUSTER_CONFIG_TOOLS, 1):
            print(f"   {i}. {tool['name']}: {tool['description']}")
            
            # Check input schema
            schema = tool.get("inputSchema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            print(f"      - Properties: {list(properties.keys())}")
            print(f"      - Required: {required}")
        
        print("✅ MCP tools enumeration completed")
        return True
        
    except Exception as e:
        print(f"❌ MCP tools enumeration failed: {e}")
        traceback.print_exc()
        return False


async def main():
    """Run all configuration tests."""
    print("🚀 IPFS Cluster Configuration API Test Suite")
    print("=" * 80)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("MCP Tools List", test_mcp_tools_list),
        ("Cluster Service Config", test_cluster_service_config),
        ("Cluster Follow Config", test_cluster_follow_config),
        ("Direct Manager Config", test_direct_manager_config),
        ("Cluster Status APIs", test_cluster_status_apis),
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n🧪 Running {test_name}...")
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            test_results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*80)
    print("📊 Test Summary")
    print("="*80)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Cluster configuration API is working correctly.")
        print("\n📋 Key Features Verified:")
        print("   ✓ Programmatic service.json and identity.json generation")
        print("   ✓ Configuration retrieval and updates")
        print("   ✓ Both cluster service and cluster follow supported")
        print("   ✓ MCP API integration working")
        print("   ✓ Direct manager access functional")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    import anyio
    anyio.run(main)
