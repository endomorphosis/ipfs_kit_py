#!/usr/bin/env python3
"""
Test the unified MCP dashboard bucket functionality directly.
"""

import anyio
import sys
from pathlib import Path

# Add the package to the path
sys.path.insert(0, str(Path(__file__).parent))

from ipfs_kit_py.unified_mcp_dashboard import UnifiedMCPDashboard

async def test_bucket_api():
    """Test bucket API methods."""
    print("🧪 Testing unified MCP dashboard bucket functionality...")
    
    config = {
        'host': '127.0.0.1',
        'port': 8004,
        'data_dir': '~/.ipfs_kit',
        'debug': True,
        'update_interval': 3
    }
    
    dashboard = UnifiedMCPDashboard(config)
    
    try:
        # Test listing buckets
        print("\n📝 Testing bucket listing...")
        buckets = await dashboard._get_buckets_data()
        print(f"   ✅ Buckets data: {buckets}")
        
        # Test creating a bucket
        print("\n🔨 Testing bucket creation...")
        result = await dashboard._create_bucket('test-unified-bucket', 'general', 'Test bucket for unified API testing')
        print(f"   ✅ Create bucket result: {result}")
        
        # Test getting bucket details
        print("\n📂 Testing bucket details...")
        details = await dashboard._get_bucket_details('test-unified-bucket')
        print(f"   ✅ Bucket details: {details}")
        
        # Test deleting bucket
        print("\n🗑️  Testing bucket deletion...")
        delete_result = await dashboard._delete_bucket('test-unified-bucket')
        print(f"   ✅ Delete result: {delete_result}")
        
        print("\n✅ All unified MCP dashboard bucket API tests completed!")
        
    except Exception as e:
        print(f"❌ Error during bucket API tests: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    anyio.run(test_bucket_api)
