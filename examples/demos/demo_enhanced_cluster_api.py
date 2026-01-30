#!/usr/bin/env python3
"""
Demo: Enhanced IPFS Cluster API with Configuration Management

This script demonstrates the comprehensive IPFS Cluster configuration management
system including:
- IPFS Cluster service configuration (service.json, identity.json)
- IPFS Cluster follow configuration
- REST API connectivity to networked hosts
- MCP API integration for dashboard access
"""

import anyio
import json
import logging
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import cluster configuration API
try:
    from ipfs_kit_py.mcp.ipfs_kit.api.cluster_config_api import cluster_config_api, CLUSTER_CONFIG_TOOLS, handle_cluster_config_tool
    from ipfs_kit_py.ipfs_cluster_daemon_manager import IPFSClusterConfig
    from ipfs_kit_py.ipfs_cluster_follow import ipfs_cluster_follow
    print("✅ Successfully imported cluster configuration modules")
except ImportError as e:
    print(f"❌ Failed to import cluster modules: {e}")
    print("Make sure you're running from the project root directory")
    exit(1)


async def demo_cluster_service_config():
    """Demonstrate IPFS Cluster service configuration management."""
    print("\n" + "="*60)
    print("📋 IPFS CLUSTER SERVICE CONFIGURATION DEMO")
    print("="*60)
    
    # Create cluster service configuration
    print("\n1. Creating IPFS Cluster service configuration...")
    create_result = await cluster_config_api.cluster_service_config_create(
        cluster_path="./examples/data/cluster_service",
        overwrite=True,
        custom_settings={
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
    )
    
    if create_result["success"]:
        print("✅ Cluster service configuration created successfully")
        print(f"   - Config directory: ./examples/data/cluster_service")
        print(f"   - Identity created: {create_result['identity_created']}")
        print(f"   - Service config created: {create_result['config_created']}")
        print(f"   - Peer ID: {create_result['identity_config'].get('id', 'N/A')[:20]}...")
    else:
        print(f"❌ Failed to create configuration: {create_result['errors']}")
        return
    
    # Get cluster service configuration
    print("\n2. Retrieving cluster service configuration...")
    get_result = await cluster_config_api.cluster_service_config_get(
        cluster_path="./examples/data/cluster_service"
    )
    
    if get_result["success"]:
        print("✅ Configuration retrieved successfully")
        service_config = get_result["service_config"]
        print(f"   - API port: {service_config.get('api', {}).get('restapi', {}).get('listen_multiaddress', 'N/A')}")
        print(f"   - Cluster secret: {service_config.get('cluster', {}).get('secret', 'N/A')[:16]}...")
        print(f"   - Replication factor: {service_config.get('cluster', {}).get('replication_factor_min', 'N/A')}-{service_config.get('cluster', {}).get('replication_factor_max', 'N/A')}")
    else:
        print(f"❌ Failed to retrieve configuration: {get_result['errors']}")
    
    # Update cluster service configuration
    print("\n3. Updating cluster service configuration...")
    update_result = await cluster_config_api.cluster_service_config_set(
        config_updates={
            "cluster": {
                "monitor_ping_interval": "10s",
                "state_sync_interval": "20s"
            },
            "api": {
                "restapi": {
                    "read_timeout": "30s"
                }
            }
        },
        cluster_path="./examples/data/cluster_service"
    )
    
    if update_result["success"]:
        print("✅ Configuration updated successfully")
        updated_config = update_result["updated_config"]
        print(f"   - Monitor ping interval: {updated_config.get('cluster', {}).get('monitor_ping_interval', 'N/A')}")
        print(f"   - State sync interval: {updated_config.get('cluster', {}).get('state_sync_interval', 'N/A')}")
        print(f"   - API read timeout: {updated_config.get('api', {}).get('restapi', {}).get('read_timeout', 'N/A')}")
    else:
        print(f"❌ Failed to update configuration: {update_result['errors']}")


async def demo_cluster_follow_config():
    """Demonstrate IPFS Cluster follow configuration management."""
    print("\n" + "="*60)
    print("📋 IPFS CLUSTER FOLLOW CONFIGURATION DEMO")
    print("="*60)
    
    # Create cluster follow configuration
    print("\n1. Creating IPFS Cluster follow configuration...")
    create_result = await cluster_config_api.cluster_follow_config_create(
        cluster_name="demo-cluster",
        bootstrap_peer="/ip4/127.0.0.1/tcp/9096/p2p/12D3KooWExample",
        cluster_path="./examples/data/cluster_follow",
        overwrite=True,
        custom_settings={
            "cluster": {
                "leave_on_shutdown": True
            },
            "informer": {
                "tags": {
                    "tags": {"role": "demo-follower", "region": "local"}
                }
            }
        }
    )
    
    if create_result["success"]:
        print("✅ Cluster follow configuration created successfully")
        print(f"   - Config directory: ./examples/data/cluster_follow")
        print(f"   - Cluster name: {create_result['service_config'].get('cluster_name', 'N/A')}")
        print(f"   - Identity created: {create_result['identity_created']}")
        print(f"   - Service config created: {create_result['config_created']}")
        print(f"   - Peer ID: {create_result['identity_config'].get('id', 'N/A')[:20]}...")
    else:
        print(f"❌ Failed to create follow configuration: {create_result['errors']}")
        return
    
    # Get cluster follow configuration
    print("\n2. Retrieving cluster follow configuration...")
    get_result = await cluster_config_api.cluster_follow_config_get(
        cluster_name="demo-cluster",
        cluster_path="./examples/data/cluster_follow"
    )
    
    if get_result["success"]:
        print("✅ Follow configuration retrieved successfully")
        service_config = get_result["service_config"]
        print(f"   - Cluster name: {service_config.get('cluster_name', 'N/A')}")
        print(f"   - API port: {service_config.get('api', {}).get('restapi', {}).get('listen_multiaddress', 'N/A')}")
        print(f"   - Bootstrap peers: {len(service_config.get('cluster', {}).get('bootstrap', []))}")
        print(f"   - Leave on shutdown: {service_config.get('cluster', {}).get('leave_on_shutdown', 'N/A')}")
    else:
        print(f"❌ Failed to retrieve follow configuration: {get_result['errors']}")
    
    # Update cluster follow configuration
    print("\n3. Updating cluster follow configuration...")
    update_result = await cluster_config_api.cluster_follow_config_set(
        cluster_name="demo-cluster",
        config_updates={
            "cluster": {
                "monitor_ping_interval": "12s"
            },
            "informer": {
                "tags": {
                    "tags": {"role": "demo-follower", "region": "local", "updated": "true"}
                }
            }
        },
        cluster_path="./examples/data/cluster_follow"
    )
    
    if update_result["success"]:
        print("✅ Follow configuration updated successfully")
        updated_config = update_result["updated_config"]
        print(f"   - Monitor ping interval: {updated_config.get('cluster', {}).get('monitor_ping_interval', 'N/A')}")
        tags = updated_config.get('informer', {}).get('tags', {}).get('tags', {})
        print(f"   - Tags: {tags}")
    else:
        print(f"❌ Failed to update follow configuration: {update_result['errors']}")


async def demo_mcp_api_integration():
    """Demonstrate MCP API integration for dashboard access."""
    print("\n" + "="*60)
    print("🔌 MCP API INTEGRATION DEMO")
    print("="*60)
    
    print("\n1. Available MCP tools for cluster configuration:")
    for i, tool in enumerate(CLUSTER_CONFIG_TOOLS, 1):
        print(f"   {i}. {tool['name']}")
        print(f"      Description: {tool['description']}")
    
    print(f"\n2. Total MCP tools available: {len(CLUSTER_CONFIG_TOOLS)}")
    
    # Test MCP tool handler
    print("\n3. Testing MCP tool handler...")
    test_args = {
        "cluster_path": "./examples/data/cluster_service"
    }
    
    mcp_result = await handle_cluster_config_tool("cluster_service_config_get", test_args)
    
    if mcp_result["success"]:
        print("✅ MCP tool handler working correctly")
        print("   - Tool can be called from dashboard/MCP client")
        print("   - Configuration accessible via API")
    else:
        print(f"❌ MCP tool handler failed: {mcp_result['errors']}")


async def demo_network_connectivity():
    """Demonstrate network connectivity features."""
    print("\n" + "="*60)
    print("🌐 NETWORK CONNECTIVITY DEMO")
    print("="*60)
    
    print("\n1. Testing connection to networked cluster...")
    print("   (This will fail if no cluster is running, which is expected)")
    
    # Try to connect to a networked cluster (will likely fail in demo)
    connect_result = await cluster_config_api.connect_to_networked_cluster(
        remote_host="127.0.0.1",
        remote_port=9094,
        cluster_path="./examples/data/cluster_service"
    )
    
    if connect_result["success"]:
        print("✅ Successfully connected to networked cluster")
        print(f"   - Remote cluster ID: {connect_result.get('remote_info', {}).get('id', {}).get('id', 'N/A')}")
        print(f"   - Remote peers: {len(connect_result.get('remote_info', {}).get('peers', []))}")
    else:
        print("⚠️  Network connection failed (expected if no cluster running)")
        print(f"   - Error: {connect_result['errors'][0] if connect_result.get('errors') else 'Unknown'}")
        print("   - This functionality works when clusters are running")
    
    print("\n2. Testing follow connection to leader...")
    print("   (This will also fail if no leader is running, which is expected)")
    
    # Try to connect follow to leader (will likely fail in demo)
    follow_connect_result = await cluster_config_api.connect_follow_to_leader(
        cluster_name="demo-cluster",
        leader_host="127.0.0.1",
        leader_port=9094,
        cluster_path="./examples/data/cluster_follow"
    )
    
    if follow_connect_result["success"]:
        print("✅ Successfully connected follow to leader")
        print(f"   - Leader cluster ID: {follow_connect_result.get('leader_info', {}).get('id', {}).get('id', 'N/A')}")
    else:
        print("⚠️  Follow connection failed (expected if no leader running)")
        print(f"   - Error: {follow_connect_result['errors'][0] if follow_connect_result.get('errors') else 'Unknown'}")
        print("   - This functionality works when cluster leader is running")


async def demo_configuration_files():
    """Show the generated configuration files."""
    print("\n" + "="*60)
    print("📁 GENERATED CONFIGURATION FILES")
    print("="*60)
    
    # Show cluster service files
    service_dir = Path("./examples/data/cluster_service")
    if service_dir.exists():
        print(f"\n1. Cluster Service Files ({service_dir}):")
        for file_path in service_dir.glob("*.json"):
            print(f"   📄 {file_path.name}")
            if file_path.stat().st_size < 2048:  # Show small files
                try:
                    with open(file_path, 'r') as f:
                        content = json.load(f)
                    print(f"      Keys: {list(content.keys())}")
                except Exception as e:
                    print(f"      Error reading: {e}")
    
    # Show cluster follow files  
    follow_dir = Path("./examples/data/cluster_follow")
    if follow_dir.exists():
        print(f"\n2. Cluster Follow Files ({follow_dir}):")
        for file_path in follow_dir.glob("*.json"):
            print(f"   📄 {file_path.name}")
            if file_path.stat().st_size < 2048:  # Show small files
                try:
                    with open(file_path, 'r') as f:
                        content = json.load(f)
                    print(f"      Keys: {list(content.keys())}")
                except Exception as e:
                    print(f"      Error reading: {e}")


async def main():
    """Run the complete demo."""
    print("🚀 Enhanced IPFS Cluster API Configuration Demo")
    print("This demo shows comprehensive cluster configuration management")
    
    try:
        # Run all demo sections
        await demo_cluster_service_config()
        await demo_cluster_follow_config()
        await demo_mcp_api_integration()
        await demo_network_connectivity()
        await demo_configuration_files()
        
        print("\n" + "="*60)
        print("🎉 DEMO COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nKey Features Demonstrated:")
        print("✅ IPFS Cluster service configuration (service.json, identity.json)")
        print("✅ IPFS Cluster follow configuration")
        print("✅ Configuration create, get, and set functions")
        print("✅ MCP API integration for dashboard access")
        print("✅ Network connectivity to remote clusters")
        print("✅ REST API client integration")
        
        print("\nNext Steps:")
        print("1. Use these configurations to start actual cluster services")
        print("2. Access config functions from the dashboard via MCP API")
        print("3. Connect to networked IPFS clusters")
        print("4. Monitor cluster health and status")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        logger.exception("Demo execution error")


if __name__ == "__main__":
    anyio.run(main)