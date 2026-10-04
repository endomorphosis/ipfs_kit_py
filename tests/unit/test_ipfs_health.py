#!/usr/bin/env python3
"""
Test IPFS health check functionality.
"""

import anyio
from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
import pytest

pytestmark = pytest.mark.anyio


async def test_ipfs_health():
    """Test the IPFS health check directly."""
    print("🔍 Testing IPFS Health Check")
    print("=" * 40)
    
    # Initialize health monitor
    monitor = BackendHealthMonitor()
    
    # Get the IPFS backend
    ipfs_backend = monitor.backends.get('ipfs', {}).copy()
    print(f"📋 Initial IPFS backend status: {ipfs_backend.get('status', 'unknown')}")
    
    try:
        # Run the health check
        print("🏥 Running IPFS health check...")
        updated_backend = await monitor._check_ipfs_health(ipfs_backend)
        
        print(f"✅ Health check completed!")
        print(f"   Status: {updated_backend.get('status', 'unknown')}")
        print(f"   Health: {updated_backend.get('health', 'unknown')}")
        print(f"   PID: {updated_backend.get('daemon_pid', 'N/A')}")
        
        # Show metrics
        metrics = updated_backend.get('metrics', {})
        if metrics:
            print(f"📊 Metrics:")
            for key, value in metrics.items():
                print(f"   {key}: {value}")
        
        # Show errors if any
        errors = updated_backend.get('errors', [])
        if errors:
            print(f"❌ Errors ({len(errors)}):")
            for i, error in enumerate(errors[-3:], 1):  # Show last 3
                print(f"   {i}. {error.get('error', 'Unknown')}")
                print(f"      Timestamp: {error.get('timestamp', 'Unknown')}")
        
        # Show detailed info
        detailed = updated_backend.get('detailed_info', {})
        if detailed:
            print(f"🔧 Detailed Info:")
            for key, value in detailed.items():
                print(f"   {key}: {value}")
    
    except Exception as e:
        print(f"❌ Error during health check: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run the test."""
    anyio.run(test_ipfs_health)


if __name__ == "__main__":
    main()
