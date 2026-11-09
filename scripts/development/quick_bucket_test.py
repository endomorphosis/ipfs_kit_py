#!/usr/bin/env python3
"""
Quick bucket functionality test with timeout handling.
"""

import anyio
import aiohttp
import json
import tempfile
import os
from pathlib import Path

async def quick_test():
    """Quick test of bucket API endpoints."""
    print("🧪 Quick bucket functionality test...")
    
    timeout = aiohttp.ClientTimeout(total=5)  # 5 second timeout
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Test 1: List buckets
            print("\n📝 Testing bucket listing...")
            async with session.get("http://127.0.0.1:8085/api/buckets") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Successfully listed buckets: {data}")
                else:
                    print(f"   ❌ Failed to list buckets: {resp.status}")
                    
            # Test 2: Create a bucket
            print("\n🔨 Testing bucket creation...")
            bucket_data = {"name": "test-bucket", "description": "Test bucket"}
            async with session.post("http://127.0.0.1:8085/api/buckets", json=bucket_data) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Successfully created bucket: {data}")
                else:
                    print(f"   ❌ Failed to create bucket: {resp.status}")
                    
            # Test 3: List buckets again
            print("\n📝 Testing bucket listing again...")
            async with session.get("http://127.0.0.1:8085/api/buckets") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Successfully listed buckets: {data}")
                else:
                    print(f"   ❌ Failed to list buckets: {resp.status}")
                    
    except TimeoutError:
        print("⏰ Test timed out - this is expected in some environments")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

if __name__ == "__main__":
    anyio.run(quick_test)
