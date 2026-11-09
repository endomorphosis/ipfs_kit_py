#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the project to Python path
sys.path.insert(0, '/home/devel/ipfs_kit_py')

async def debug_service_config():
    """Debug service configuration creation."""
    print("🔍 Debugging Service Config Creation")
    
    try:
        from mcp.ipfs_kit.api.enhanced_dashboard_api import DashboardController
        
        dashboard = DashboardController()
        
        print("📋 Creating service configuration with detailed debugging...")
        service_result = await dashboard.create_cluster_config(
            service_type="service",
            cluster_name="debug-cluster",
            api_listen_multiaddress="/ip4/127.0.0.1/tcp/9094",
            proxy_listen_multiaddress="/ip4/127.0.0.1/tcp/9095",
            ipfs_proxy_listen_multiaddress="/ip4/127.0.0.1/tcp/9096",
            replication_factor_min=2,
            replication_factor_max=5
        )
        
        print(f"📊 Service Result: {service_result}")
        print(f"✅ Success field: {service_result.get('success')}")
        print(f"📝 Keys in result: {list(service_result.keys())}")
        
        if 'errors' in service_result:
            print(f"❌ Errors: {service_result['errors']}")
            
        return service_result.get('success', False)
        
    except Exception as e:
        print(f"💥 Exception occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(debug_service_config())
    print(f"\n🎯 Final result: {'✅ SUCCESS' if success else '❌ FAILED'}")
