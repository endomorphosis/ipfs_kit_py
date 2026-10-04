#!/usr/bin/env python3
"""
Test script for the MCP server health API
"""

import anyio
import pytest
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

pytestmark = pytest.mark.anyio

async def test_health_api():
    """Test the health API functionality."""
    print("🏥 Testing MCP Server Health API")
    print("=" * 50)
    
    try:
        # Import and test the BackendHealthMonitor
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        # Initialize the health monitor
        print("📊 Initializing BackendHealthMonitor...")
        health_monitor = BackendHealthMonitor()
        
        # Test filesystem status from parquet
        print("\n📁 Testing filesystem status from parquet files...")
        filesystem_status = await health_monitor.get_filesystem_status_from_parquet()
        print(f"✓ Filesystem healthy: {filesystem_status.get('filesystem_healthy', False)}")
        print(f"✓ Enhanced pin data: {len(filesystem_status.get('enhanced_pin_data', {}))} fields")
        if filesystem_status.get('errors'):
            print(f"⚠️ Errors: {filesystem_status['errors']}")
        
        # Test comprehensive health status
        print("\n🔍 Testing comprehensive health status...")
        comprehensive_status = await health_monitor.get_comprehensive_health_status()
        print(f"✓ System healthy: {comprehensive_status.get('system_healthy', False)}")
        print(f"✓ Components checked: {list(comprehensive_status.get('components', {}).keys())}")
        
        # Test backend health check
        print("\n🖥️ Testing backend health check...")
        backend_health = await health_monitor.check_all_backends_health()
        print(f"✓ Backend check status: {backend_health.get('status', 'unknown')}")
        
        print("\n🎉 Health API tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Health API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = anyio.run(test_health_api)
    sys.exit(0 if success else 1)
