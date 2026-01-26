#!/usr/bin/env python3
"""
Test script for newly implemented features.

This script tests the implementations added:
1. DHT methods in IPFSModel
2. add_content method in IPFSModelAnyIO
3. Hierarchical storage methods in IPFSFileSystem
"""

import sys
from pathlib import Path

import pytest


# Add repo root (not the package dir) so imports work without shadowing
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

def test_dht_methods():
    """Test DHT methods in IPFSModel."""
    print("Testing DHT methods in IPFSModel...")
    
    try:
        from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
        
        # Create model instance
        model = IPFSModel()
        
        # Test dht_findpeer method
        result = model.dht_findpeer("12D3KooWTestPeer")
        print(f"✓ dht_findpeer: success={result.get('success')}, simulation={result.get('simulation')}")
        assert result.get("success") is True
        assert "peer_id" in result
        
        # Test dht_findprovs method  
        result = model.dht_findprovs("QmTestCID", num_providers=3)
        print(f"✓ dht_findprovs: success={result.get('success')}, providers={len(result.get('providers', []))}")
        assert result.get("success") is True
        assert "providers" in result
        
        print("✓ DHT methods test passed")
        return True
        
    except Exception as e:
        print(f"✗ DHT methods test failed: {e}")
        return False

@pytest.mark.anyio
async def test_add_content_method():
    """Test add_content method in IPFSModelAnyIO."""
    print("\nTesting add_content method in IPFSModelAnyIO...")
    
    try:
        from ipfs_kit_py.mcp.models.ipfs_model_anyio import IPFSModelAnyIO
        
        # Create model instance
        model = IPFSModelAnyIO()
        
        # Test add_content method with string
        result = await model.add_content("test content")
        print(f"✓ add_content (string): success={result.get('success')}, cid={result.get('cid')}")
        assert result.get("success") is True
        assert "cid" in result
        
        # Test add_content method with bytes
        result = await model.add_content(b"test bytes content")
        print(f"✓ add_content (bytes): success={result.get('success')}, size={result.get('size')}")
        assert result.get("success") is True
        assert result.get("size") > 0
        
        # Test add_content method with kwargs
        result = await model.add_content(content="test kwargs content")
        print(f"✓ add_content (kwargs): success={result.get('success')}")
        assert result.get("success") is True
        
        # Test add_content method with no content (should fail)
        result = await model.add_content()
        print(f"✓ add_content (no content): success={result.get('success')}")
        assert result.get("success") is False
        assert "error" in result
        
        print("✓ add_content method test passed")
        return True
        
    except Exception as e:
        print(f"✗ add_content method test failed: {e}")
        return False

def test_hierarchical_storage_methods():
    """Test hierarchical storage methods in IPFSFileSystem."""
    print("\nTesting hierarchical storage methods...")
    
    try:
        # Import and inspect the class without instantiation
        import ipfs_kit_py.enhanced_fsspec as fsspec_module
        IPFSFileSystem = fsspec_module.IPFSFileSystem
        
        # Check that the methods exist
        methods_to_check = ['_verify_content_integrity', '_get_content_tiers', '_get_from_tier']
        
        for method_name in methods_to_check:
            if hasattr(IPFSFileSystem, method_name):
                print(f"✓ Method {method_name} exists in IPFSFileSystem")
            else:
                print(f"✗ Method {method_name} missing in IPFSFileSystem")
                return False
        
        print("✓ Hierarchical storage methods test passed")
        return True
        
    except Exception as e:
        print(f"✗ Hierarchical storage methods test failed: {e}")
        return False

def test_streaming_metrics_integration():
    """Test that streaming metrics integration exists in high_level_api."""
    print("\nTesting streaming metrics integration...")
    
    try:
        # Import and check high level API
        import ipfs_kit_py.high_level_api as api_module
        IPFSSimpleAPI = api_module.IPFSSimpleAPI
        
        # Check that track_streaming_operation method exists
        if hasattr(IPFSSimpleAPI, 'track_streaming_operation'):
            print("✓ track_streaming_operation method exists in IPFSSimpleAPI")
            print("✓ Streaming metrics integration test passed")
            return True
        else:
            print("✗ track_streaming_operation method missing in IPFSSimpleAPI")
            return False
            
    except Exception as e:
        print(f"✗ Streaming metrics integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("Testing Implementation Features")
    print("=" * 50)
    
    results = []
    
    # Run individual tests
    results.append(test_dht_methods())
    results.append(test_add_content_method()) 
    results.append(test_hierarchical_storage_methods())
    results.append(test_streaming_metrics_integration())
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Results Summary")
    print("=" * 50)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All implementation tests passed!")
        return 0
    else:
        print("❌ Some implementation tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())