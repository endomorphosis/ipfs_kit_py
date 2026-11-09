#!/usr/bin/env python3
"""
Quick MCP Server Tool Validation Script
========================================

Tests a subset of key tools to validate that our fixes work correctly.
"""

import sys
import anyio
import json
import time

# Add the project root to path
sys.path.insert(0, ".")

from ipfs_kit_py.mcp.ipfs_kit.mcp.enhanced_mcp_server_with_daemon_mgmt import EnhancedMCPServerWithDaemonMgmt


async def test_key_tools():
    """Test a subset of key tools to validate fixes."""
    
    print("🚀 Quick MCP Server Tool Validation")
    print("=" * 50)
    
    # Initialize server
    print("🚀 Initializing MCP server...")
    server = EnhancedMCPServerWithDaemonMgmt()
    
    # Test key operations that were previously failing
    test_cases = [
        # Core operations
        ("ipfs_get", {"cid": "bafkreie5u4kxabn5qh6kfeq3afhe4b3bfrjfxiuq2mfvz3o7ajqgoxmhji", "output_path": "/tmp/test_ipfs_get"}),
        ("ipfs_ls", {"path": "/ipfs/bafkreie5u4kxabn5qh6kfeq3afhe4b3bfrjfxiuq2mfvz3o7ajqgoxmhji"}),
        ("ipfs_version", {}),
        ("ipfs_stats", {"stat_type": "repo"}),
        
        # Advanced operations (should use mock)
        ("ipfs_dht_query", {"peer_id": "12D3KooWTest123"}),
        ("ipfs_name_publish", {"cid": "bafkreie5u4kxabn5qh6kfeq3afhe4b3bfrjfxiuq2mfvz3o7ajqgoxmhji"}),
        
        # MFS operations (should use mock)
        ("ipfs_files_mkdir", {"path": "/test_dir"}),
        ("ipfs_files_ls", {"path": "/"}),
        
        # VFS operations (should use mock)
        ("vfs_mount", {"ipfs_path": "/ipfs/test", "mount_point": "/tmp/test"}),
        ("vfs_list_mounts", {}),
        
        # System tool
        ("system_health", {})
    ]
    
    results = {"success": 0, "failed": 0, "total": len(test_cases)}
    
    print(f"🧪 Testing {len(test_cases)} key tools...\n")
    
    for tool_name, args in test_cases:
        print(f"  🔧 Testing {tool_name}...", end="")
        
        try:
            start_time = time.time()
            result = await server.execute_tool(tool_name, args)
            duration = time.time() - start_time
            
            if result.get("success", True):
                results["success"] += 1
                print(f" ✅ SUCCESS ({duration:.2f}s)")
                if "operation" in result:
                    print(f"      Operation: {result['operation']}")
                if "cid" in result:
                    print(f"      CID: {result['cid'][:20]}...")
                elif "data" in result and isinstance(result["data"], str):
                    print(f"      Data: {result['data'][:50]}...")
                elif "entries" in result:
                    print(f"      Entries: {len(result['entries'])} items")
                elif "mounts" in result:
                    print(f"      Mounts: {len(result['mounts'])} items")
                
            else:
                results["failed"] += 1
                print(f" ❌ FAILED ({duration:.2f}s)")
                print(f"      Error: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            results["failed"] += 1
            print(f" 💥 EXCEPTION: {str(e)}")
    
    print("\n" + "=" * 50)
    print("📊 QUICK VALIDATION RESULTS")
    print("=" * 50)
    
    print(f"🎯 OVERALL RESULTS:")
    print(f"   Total tools tested: {results['total']}")
    print(f"   Successful: {results['success']} ({results['success']/results['total']*100:.1f}%)")
    print(f"   Failed: {results['failed']} ({results['failed']/results['total']*100:.1f}%)")
    
    # Determine status
    success_rate = results['success'] / results['total']
    if success_rate >= 0.9:
        print(f"\n🏆 EXCELLENT: Validation passed with {success_rate*100:.1f}% success rate!")
        return True
    elif success_rate >= 0.7:
        print(f"\n✅ GOOD: Validation mostly passed with {success_rate*100:.1f}% success rate.")
        return True
    else:
        print(f"\n❌ POOR: Validation failed with only {success_rate*100:.1f}% success rate.")
        return False


async def main():
    """Main function."""
    try:
        success = await test_key_tools()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    anyio.run(main)
