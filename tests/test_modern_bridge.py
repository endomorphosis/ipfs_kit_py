#!/usr/bin/env python3
"""
Test script for the Modern MCP Feature Bridge.
"""
import anyio
import sys
import os
from pathlib import Path
import pytest

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

pytestmark = pytest.mark.anyio

from ipfs_kit_py.mcp.modern_mcp_feature_bridge import ModernMCPFeatureBridge

async def test_modern_bridge():
    """Test the modern bridge with proper async initialization."""
    print("🚀 Testing Modern MCP Feature Bridge")
    print("=" * 50)
    
    try:
        # Create bridge instance
        bridge = ModernMCPFeatureBridge()
        print("✅ Bridge instance created")
        
        # Initialize async components
        await bridge.initialize_async()
        print("✅ Async initialization completed")
        
        # Test system status
        print("\n📊 Testing system status...")
        status = bridge.get_system_status()
        print(f"Status result: {status.get('success', False)}")
        if status.get('data'):
            print(f"System uptime: {status['data'].get('uptime', 'unknown')}")
            print(f"Active directories: {len(status['data'].get('directories', []))}")
        
        # Test system health
        print("\n🏥 Testing system health...")
        health = bridge.get_system_health()
        print(f"Health result: {health.get('success', False)}")
        if health.get('data'):
            print(f"Overall health: {health['data'].get('overall_health', 'unknown')}")
        
        # Test bucket operations
        print("\n🪣 Testing bucket operations...")
        buckets = bridge.get_buckets()
        print(f"Buckets result: {buckets.get('success', False)}")
        if buckets.get('data'):
            print(f"Found {len(buckets['data'])} buckets")
            for bucket in buckets['data'][:3]:  # Show first 3
                print(f"  - {bucket.get('name', 'unnamed')}: {bucket.get('status', 'unknown')}")
        
        # Test backend operations
        print("\n⚙️ Testing backend operations...")
        backends = bridge.get_backends()
        print(f"Backends result: {backends.get('success', False)}")
        if backends.get('data'):
            print(f"Found {len(backends['data'])} backends")
        
        # Test MCP status
        print("\n🔧 Testing MCP status...")
        mcp_status = bridge.get_mcp_status()
        print(f"MCP status result: {mcp_status.get('success', False)}")
        
        # Test comprehensive feature mapping
        print("\n🎯 Testing comprehensive feature mapping...")
        features = bridge.get_available_comprehensive_features()
        print(f"Feature mapping result: {features.get('success', False)}")
        if features.get('data'):
            categories = features['data'].get('categories', {})
            total_features = sum(len(features) for features in categories.values())
            print(f"Total mapped features: {total_features}")
            print(f"Feature categories: {list(categories.keys())}")
        
        print("\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = anyio.run(test_modern_bridge)
    sys.exit(0 if success else 1)
