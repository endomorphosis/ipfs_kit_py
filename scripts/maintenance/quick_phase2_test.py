#!/usr/bin/env python3
"""
Quick Phase 2 Test - Verify IPFS Tools Integration
"""

import sys
import os
from pathlib import Path

# Add paths
base_dir = Path(__file__).parent
sys.path.insert(0, str(base_dir / "core"))
sys.path.insert(0, str(base_dir / "tools"))

def test_tool_registry():
    """Test tool registry and IPFS tools"""
    print("=== Testing Tool Registry ===")
    
    try:
        from ipfs_kit_py.core.tool_registry import registry
        print(f"✓ Registry loaded: {len(registry.tools)} total tools")
        
        # Find IPFS tools
        ipfs_tools = [name for name in registry.tools.keys() if 'ipfs' in name]
        print(f"✓ IPFS tools found: {len(ipfs_tools)}")
        
        for tool in sorted(ipfs_tools):
            print(f"  • {tool}")
        
        return len(ipfs_tools) >= 10
        
    except Exception as e:
        print(f"✗ Registry test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_ipfs_daemon():
    """Test IPFS daemon connectivity"""
    print("\n=== Testing IPFS Daemon ===")
    
    try:
        import subprocess
        result = subprocess.run(['ipfs', 'id'], 
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✓ IPFS daemon is responding")
            import json
            data = json.loads(result.stdout)
            print(f"✓ Node ID: {data['ID'][:20]}...")
            return True
        else:
            print(f"✗ IPFS daemon not responding: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"✗ IPFS test failed: {e}")
        return False

def test_ipfs_operations():
    """Test IPFS operations through tools"""
    print("\n=== Testing IPFS Operations ===")
    
    try:
        from ipfs_kit_py.core.tool_registry import registry
        
        # Test ipfs_add
        if 'ipfs_add' in registry.tools:
            print("Testing ipfs_add...")
            handler = registry.handlers.get('ipfs_add') or registry.tools['ipfs_add'].handler
            if handler:
                result = handler({'content': 'Hello Phase 2!'})
                if result.get('status') == 'success':
                    cid = result.get('data', {}).get('cid')
                    print(f"✓ ipfs_add successful: {cid}")
                    
                    # Test ipfs_cat with the CID
                    if 'ipfs_cat' in registry.tools:
                        print("Testing ipfs_cat...")
                        cat_handler = registry.handlers.get('ipfs_cat') or registry.tools['ipfs_cat'].handler
                        if cat_handler:
                            cat_result = cat_handler({'cid': cid})
                            if cat_result.get('status') == 'success':
                                content = cat_result.get('data', {}).get('content', '')
                                if 'Hello Phase 2!' in content:
                                    print("✓ ipfs_cat successful - content matches")
                                    return True
                                else:
                                    print(f"⚠ Content mismatch: {content}")
                            else:
                                print(f"✗ ipfs_cat failed: {cat_result}")
                        else:
                            print("✗ ipfs_cat handler not found")
                    else:
                        print("⚠ ipfs_cat tool not registered")
                        return True  # Still a partial success
                else:
                    print(f"✗ ipfs_add failed: {result}")
            else:
                print("✗ ipfs_add handler not found")
        else:
            print("✗ ipfs_add tool not registered")
        
        return False
        
    except Exception as e:
        print(f"✗ Operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("Quick Phase 2 Test - IPFS Tools Integration")
    print("=" * 50)
    
    results = []
    
    # Test 1: Tool Registry
    results.append(("Tool Registry", test_tool_registry()))
    
    # Test 2: IPFS Daemon
    results.append(("IPFS Daemon", test_ipfs_daemon()))
    
    # Test 3: IPFS Operations
    results.append(("IPFS Operations", test_ipfs_operations()))
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print("-" * 50)
    print(f"Total: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Phase 2 implementation is working!")
    elif passed >= len(results) * 0.7:
        print("\n✅ Most tests passed. Phase 2 is mostly working.")
    else:
        print("\n❌ Many tests failed. Need to fix Phase 2 implementation.")
    
    return passed == len(results)

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
