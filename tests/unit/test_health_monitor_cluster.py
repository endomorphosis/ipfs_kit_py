#!/usr/bin/env python3
"""
Quick test of the health monitor to see cluster status
"""

import asyncio
from pathlib import Path

async def test_health_monitor():
    """Test the health monitor cluster status."""
    
    try:
        from mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        config_dir = Path("/tmp/test_health_config")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        health_monitor = BackendHealthMonitor(config_dir=config_dir)
        
        # Create a cluster backend for testing
        cluster_backend = {
            "name": "ipfs_cluster",
            "type": "cluster",
            "port": 9094,
            "status": "unknown",
            "health": "unknown",
            "detailed_info": {},
            "metrics": {},
            "errors": [],
            "last_check": None
        }
        
        print("🏥 Testing Cluster Health Monitor")
        print("=" * 40)
        
        # Test the cluster health check
        updated_backend = await health_monitor._check_ipfs_cluster_health(cluster_backend)
        
        print(f"Status: {updated_backend.get('status')}")
        print(f"Health: {updated_backend.get('health')}")
        print(f"Last Check: {updated_backend.get('last_check')}")
        
        # Show metrics
        metrics = updated_backend.get("metrics", {})
        if metrics:
            print("\\nMetrics:")
            for key, value in metrics.items():
                print(f"  {key}: {value}")
        
        # Show detailed info
        detailed = updated_backend.get("detailed_info", {})
        if detailed:
            print("\\nDetailed Info:")
            for key, value in detailed.items():
                if isinstance(value, (str, int, float, bool)):
                    print(f"  {key}: {value}")
        
        # Show any errors
        errors = updated_backend.get("errors", [])
        if errors:
            print("\\nErrors:")
            for error in errors[-3:]:  # Show last 3 errors
                print(f"  {error.get('timestamp', 'unknown')}: {error.get('error', 'unknown')}")
        
        if updated_backend.get('health') == 'healthy':
            print("\\n✅ Cluster is HEALTHY!")
        elif updated_backend.get('health') == 'degraded':
            print("\\n⚠️  Cluster is DEGRADED")
        else:
            print("\\n❌ Cluster is UNHEALTHY")
            
    except Exception as e:
        print(f"❌ Health monitor test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_health_monitor())
