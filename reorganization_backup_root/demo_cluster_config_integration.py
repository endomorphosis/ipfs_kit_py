#!/usr/bin/env python3
"""
Demo script showing how to use IPFS Cluster configuration functions
from the MCP API and dashboard integration.

This demonstrates:
1. Creating cluster service and follow configurations programmatically
2. Accessing config functions from MCP API
3. Dynamic service.json and identity.json generation
4. Integration with dashboard
"""

import asyncio
import json
import tempfile
import os

# Import the cluster configuration API
from mcp.ipfs_kit.api.cluster_config_api import cluster_config_api, handle_cluster_config_tool


async def demo_cluster_service_config():
    """Demonstrate cluster service configuration via MCP API."""
    print("🔧 Cluster Service Configuration Demo")
    print("=" * 50)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        cluster_path = os.path.join(temp_dir, "demo-cluster-service")
        
        print("1. Creating cluster service configuration...")
        
        # Use the MCP tool handler directly
        create_args = {
            "cluster_path": cluster_path,
            "overwrite": True,
            "custom_settings": {
                "cluster": {
                    "replication_factor_min": 1,
                    "replication_factor_max": 3
                },
                "api": {
                    "restapi": {
                        "listen_multiaddress": "/ip4/127.0.0.1/tcp/9094",
                        "cors_allowed_origins": ["http://localhost:3000"]
                    }
                }
            }
        }
        
        create_result = await handle_cluster_config_tool("cluster_service_config_create", create_args)
        print(f"   ✓ Configuration created: {create_result.get('success', False)}")
        
        # Show the generated files
        service_config_path = os.path.join(cluster_path, "service.json")
        identity_path = os.path.join(cluster_path, "identity.json")
        
        if os.path.exists(service_config_path):
            print(f"   ✓ service.json created at: {service_config_path}")
            with open(service_config_path) as f:
                service_config = json.load(f)
            print(f"   ✓ Peer ID: {service_config.get('id', 'unknown')[:20]}...")
            print(f"   ✓ API port: {service_config.get('api', {}).get('restapi', {}).get('listen_multiaddress', 'unknown')}")
        
        if os.path.exists(identity_path):
            print(f"   ✓ identity.json created at: {identity_path}")
        
        print("\n2. Retrieving configuration...")
        get_result = await handle_cluster_config_tool("cluster_service_config_get", {"cluster_path": cluster_path})
        print(f"   ✓ Configuration retrieved: {get_result.get('success', False)}")
        
        print("\n3. Updating configuration...")
        update_args = {
            "cluster_path": cluster_path,
            "config_updates": {
                "cluster": {
                    "monitor_ping_interval": "30s"
                },
                "api": {
                    "restapi": {
                        "cors_allowed_origins": ["*"]
                    }
                }
            }
        }
        
        update_result = await handle_cluster_config_tool("cluster_service_config_set", update_args)
        print(f"   ✓ Configuration updated: {update_result.get('success', False)}")
        
        print("✅ Cluster service configuration demo completed!\n")


async def demo_cluster_follow_config():
    """Demonstrate cluster follow configuration via MCP API."""
    print("🔧 Cluster Follow Configuration Demo")
    print("=" * 50)
    
    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        cluster_path = os.path.join(temp_dir, "demo-cluster-follow")
        
        print("1. Creating cluster follow configuration...")
        
        # Use the MCP tool handler directly
        create_args = {
            "cluster_name": "production-cluster",
            "bootstrap_peer": "/ip4/192.168.1.100/tcp/9096/p2p/12D3KooWExample",
            "cluster_path": cluster_path,
            "overwrite": True,
            "custom_settings": {
                "cluster": {
                    "state_sync_interval": "15s"
                },
                "api": {
                    "restapi": {
                        "listen_multiaddress": "/ip4/127.0.0.1/tcp/9097"
                    },
                    "ipfsproxy": {
                        "listen_multiaddress": "/ip4/127.0.0.1/tcp/9098"
                    }
                },
                "informer": {
                    "tags": {
                        "tags": {"role": "worker", "datacenter": "us-west"}
                    }
                }
            }
        }
        
        create_result = await handle_cluster_config_tool("cluster_follow_config_create", create_args)
        print(f"   ✓ Configuration created: {create_result.get('success', False)}")
        
        # Show the generated files
        service_config_path = os.path.join(cluster_path, "service.json")
        identity_path = os.path.join(cluster_path, "identity.json")
        cluster_config_path = os.path.join(cluster_path, "cluster.json")
        
        if os.path.exists(service_config_path):
            print(f"   ✓ service.json created at: {service_config_path}")
            with open(service_config_path) as f:
                service_config = json.load(f)
            print(f"   ✓ Cluster name: {service_config.get('cluster_name', 'unknown')}")
            print(f"   ✓ Bootstrap peers: {len(service_config.get('cluster', {}).get('bootstrap', []))}")
            print(f"   ✓ Worker tags: {service_config.get('informer', {}).get('tags', {}).get('tags', {})}")
        
        if os.path.exists(identity_path):
            print(f"   ✓ identity.json created at: {identity_path}")
        
        if os.path.exists(cluster_config_path):
            print(f"   ✓ cluster.json created at: {cluster_config_path}")
        
        print("\n2. Retrieving configuration...")
        get_result = await handle_cluster_config_tool("cluster_follow_config_get", {
            "cluster_name": "production-cluster",
            "cluster_path": cluster_path
        })
        print(f"   ✓ Configuration retrieved: {get_result.get('success', False)}")
        
        print("\n3. Updating configuration...")
        update_args = {
            "cluster_name": "production-cluster",
            "cluster_path": cluster_path,
            "config_updates": {
                "cluster": {
                    "monitor_ping_interval": "20s"
                },
                "informer": {
                    "tags": {
                        "tags": {"role": "worker", "datacenter": "us-west", "version": "v1.0.4"}
                    }
                }
            }
        }
        
        update_result = await handle_cluster_config_tool("cluster_follow_config_set", update_args)
        print(f"   ✓ Configuration updated: {update_result.get('success', False)}")
        
        print("✅ Cluster follow configuration demo completed!\n")


async def demo_mcp_integration():
    """Demonstrate MCP API integration for dashboard access."""
    print("🌐 MCP API Integration Demo")
    print("=" * 50)
    
    print("1. Available cluster configuration tools:")
    from mcp.ipfs_kit.api.cluster_config_api import CLUSTER_CONFIG_TOOLS
    
    for i, tool in enumerate(CLUSTER_CONFIG_TOOLS, 1):
        print(f"   {i}. {tool['name']}")
        print(f"      📋 {tool['description']}")
        
        # Show required parameters
        schema = tool.get("inputSchema", {})
        required = schema.get("required", [])
        if required:
            print(f"      🔧 Required: {', '.join(required)}")
        print()
    
    print("2. Testing cluster status via API...")
    try:
        # Test cluster service status
        service_status = await handle_cluster_config_tool("cluster_service_status_via_api", {})
        print(f"   ✓ Cluster service API responsive: {service_status.get('api_responsive', False)}")
        
        # Test cluster follow status
        follow_status = await handle_cluster_config_tool("cluster_follow_status_via_api", {
            "cluster_name": "test-cluster"
        })
        print(f"   ✓ Cluster follow API responsive: {follow_status.get('api_responsive', False)}")
        
    except Exception as e:
        print(f"   ⚠️  Status check failed (expected if services not running): {e}")
    
    print("\n3. Network connection capabilities...")
    print("   📡 Available network tools:")
    print("      - connect_to_networked_cluster: Connect to remote clusters")
    print("      - connect_follow_to_leader: Connect worker to cluster leader")
    
    print("✅ MCP API integration demo completed!\n")


async def demo_dashboard_integration():
    """Show how configuration would integrate with dashboard."""
    print("📊 Dashboard Integration Demo")
    print("=" * 50)
    
    print("Dashboard access patterns:")
    print()
    
    print("1. 🌐 Web Dashboard Access:")
    print("   URL: http://127.0.0.1:8765/")
    print("   Tools available via: /api/tools endpoint")
    print("   Real-time config: WebSocket integration")
    print()
    
    print("2. 🔧 Configuration Management:")
    print("   Create Service Config: POST /api/mcp/cluster_service_config_create")
    print("   Create Follow Config:  POST /api/mcp/cluster_follow_config_create")
    print("   Get Configurations:    GET  /api/mcp/cluster_*_config_get")
    print("   Update Configurations: PUT  /api/mcp/cluster_*_config_set")
    print()
    
    print("3. 📈 Status Monitoring:")
    print("   Service Status: GET /api/mcp/cluster_service_status_via_api")
    print("   Follow Status:  GET /api/mcp/cluster_follow_status_via_api")
    print("   Backend Health: GET /api/backends")
    print()
    
    print("4. 🚀 Kubernetes Deployment:")
    print("   • Create worker node configs programmatically")
    print("   • Bootstrap worker nodes to cluster leaders")
    print("   • Monitor and manage distributed cluster configurations")
    print("   • Dynamic configuration updates across the cluster")
    print()
    
    print("✅ Dashboard integration overview completed!\n")


async def main():
    """Run all configuration demos."""
    print("🎯 IPFS Cluster Configuration API Demo")
    print("=" * 80)
    print("This demo shows how to use cluster configuration functions")
    print("from the MCP API and dashboard integration.")
    print("=" * 80)
    print()
    
    # Run all demos
    await demo_cluster_service_config()
    await demo_cluster_follow_config()
    await demo_mcp_integration()
    await demo_dashboard_integration()
    
    print("🎉 All demos completed successfully!")
    print()
    print("📋 Summary of capabilities:")
    print("   ✓ Programmatic service.json and identity.json generation")
    print("   ✓ Dynamic configuration management via MCP API")
    print("   ✓ Dashboard integration for web-based config")
    print("   ✓ Kubernetes-ready worker/follower node setup")
    print("   ✓ Network cluster management and connectivity")
    print()
    print("🚀 Ready for production deployment!")


if __name__ == "__main__":
    asyncio.run(main())
