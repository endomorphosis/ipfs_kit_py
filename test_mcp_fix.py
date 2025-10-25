#!/usr/bin/env python3
"""
Test script to demonstrate the MCP server fix for list_bucket_files tool.
This script shows the difference between the broken state and the fixed state.
"""

import asyncio
import aiohttp
import json
import sys

async def test_mcp_tool(session, tool_name, params=None):
    """Test a specific MCP tool and return the result."""
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": params or {}
        },
        "id": 1
    }
    
    try:
        async with session.post('http://127.0.0.1:8004/mcp/tools/call', 
                               json=payload,
                               headers={'Content-Type': 'application/json'}) as response:
            result = await response.json()
            return result
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}

async def main():
    """Run comprehensive tests of the MCP server fix."""
    print("🔧 MCP Server Fix Test Suite")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Health Check
        print("\n1. Testing health_check tool...")
        result = await test_mcp_tool(session, "health_check")
        if "error" in result:
            print(f"   ❌ FAILED: {result['error']}")
        else:
            print(f"   ✅ SUCCESS: {result['result']['status']}")
        
        # Test 2: List Buckets 
        print("\n2. Testing list_buckets tool...")
        result = await test_mcp_tool(session, "list_buckets", {"include_metadata": True})
        if "error" in result:
            print(f"   ❌ FAILED: {result['error']}")
        else:
            bucket_count = len(result['result']['items'])
            print(f"   ✅ SUCCESS: Found {bucket_count} buckets")
            for bucket in result['result']['items']:
                print(f"      - {bucket['name']} ({bucket.get('type', 'unknown')}) - {bucket.get('file_count', 0)} files")
        
        # Test 3: List Bucket Files (the main fix)
        print("\n3. Testing list_bucket_files tool (THE MAIN FIX)...")
        result = await test_mcp_tool(session, "list_bucket_files", {
            "bucket": "media",
            "path": "",
            "metadata_first": True
        })
        
        if "error" in result:
            print(f"   ❌ FAILED: {result['error']}")
            print("   This would show 'Unknown tool: list_bucket_files' before the fix")
        else:
            files = result['result']['files']
            directories = result['result']['directories']
            print(f"   ✅ SUCCESS: Found {len(files)} files and {len(directories)} directories")
            for file in files:
                print(f"      📄 {file['name']} ({file['size']} bytes)")
            for directory in directories:
                print(f"      📁 {directory['name']}/")
        
        # Test 4: Invalid tool (should still fail gracefully)
        print("\n4. Testing invalid tool (should fail gracefully)...")
        result = await test_mcp_tool(session, "nonexistent_tool")
        if "error" in result:
            print(f"   ✅ CORRECTLY FAILED: {result['error']['message']}")
        else:
            print(f"   ❌ UNEXPECTED SUCCESS: {result}")
    
    print("\n" + "=" * 50)
    print("🎉 Test suite completed!")
    print("\nBEFORE FIX: list_bucket_files would return 'Unknown tool' error")
    print("AFTER FIX:  list_bucket_files returns proper file/directory listings")

if __name__ == "__main__":
    asyncio.run(main())
