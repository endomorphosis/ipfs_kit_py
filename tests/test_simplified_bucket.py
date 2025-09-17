#!/usr/bin/env python3
"""
Simple test of the simplified bucket manager
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing simplified bucket manager...")

try:
    from ipfs_kit_py.simplified_bucket_manager import SimplifiedBucketManager, get_global_simplified_bucket_manager
    print("✓ Import successful")
    
    # Test basic functionality
    manager = SimplifiedBucketManager(base_path="/tmp/test_buckets")
    print("✓ Manager created")
    
    # Test creating bucket
    import asyncio
    
    async def test_bucket():
        result = await manager.create_bucket("test-bucket", "dataset", "hybrid")
        print(f"Create bucket result: {result}")
        
        # List buckets
        result = await manager.list_buckets()
        print(f"List buckets result: {result}")
    
    asyncio.run(test_bucket())
    print("✓ Basic functionality works")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
