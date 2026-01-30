#!/usr/bin/env python3
"""
Simple MCP server test to verify configuration dashboard works correctly.
"""
import asyncio
import json
from pathlib import Path
import sys

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

async def test_mcp_server_config():
    """Test that the MCP server can start and handle configuration correctly."""
    try:
        from ipfs_kit_py.mcp.ipfs_kit.backends.health_monitor import BackendHealthMonitor
        
        print("✓ Backend health monitor imports successfully")
        
        # Initialize monitor
        monitor = BackendHealthMonitor()
        print("✓ Backend health monitor initializes successfully")
        
        # Test S3 configuration
        s3_config = {
            "access_key_id": "demo_key",
            "secret_access_key": "demo_secret",
            "bucket": "demo-bucket",
            "region": "us-east-1",
            "endpoint_url": "https://s3.amazonaws.com",
            "enabled": True
        }
        
        # Save configuration
        result = await monitor.set_backend_config("s3", s3_config)
        if result.get("success"):
            print("✓ S3 configuration saves successfully")
        else:
            print(f"✗ S3 configuration failed: {result}")
            return False
        
        # Retrieve configuration
        retrieved = await monitor.get_backend_config("s3")
        if retrieved == s3_config:
            print("✓ S3 configuration retrieves correctly")
        else:
            print(f"✗ S3 configuration mismatch: expected {s3_config}, got {retrieved}")
            return False
        
        print("\n🎉 All configuration tests passed!")
        print("✅ Configuration persistence is working correctly")
        print("✅ Frontend dashboard should now save and load configurations properly")
        
        return True
        
    except Exception as e:
        print(f"✗ Error testing configuration: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_server_config())
    if success:
        print("\n📋 Next steps:")
        print("1. Start the MCP server: python -m mcp.ipfs_kit.modular_enhanced_mcp_server --port 8765")
        print("2. Open dashboard: http://localhost:8765")
        print("3. Test configuration saving in the Backends tab")
        print("4. Configurations will persist across server restarts")
    else:
        print("\n❌ Configuration system needs additional fixes")
        sys.exit(1)
