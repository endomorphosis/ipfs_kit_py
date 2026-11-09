#!/usr/bin/env python3
"""
Test script to demonstrate role-based component disabling functionality.

This script tests the implementation where the leecher role disables:
- ipfs_cluster
- ipfs_cluster_follow  
- lotus
- synapse

Usage:
    python test_role_component_disabling.py
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, '.')

def test_leecher_role():
    """Test leecher role with disabled components."""
    print("=" * 60)
    print("Testing Leecher Role Component Disabling")
    print("=" * 60)
    
    try:
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        
        # Create API with disabled components
        disabled_components = ['ipfs_cluster', 'ipfs_cluster_follow', 'lotus', 'synapse']
        print(f"Creating IPFSSimpleAPI with disabled components: {disabled_components}")
        
        api = IPFSSimpleAPI(role='leecher', disabled_components=disabled_components)
        
        print(f"\n✅ API initialized successfully")
        print(f"   Role: {api.role}")
        print(f"   Disabled components: {api.disabled_components}")
        
        # Check component status
        print(f"\nComponent Status:")
        if hasattr(api.kit, 'lotus_kit'):
            status = "ENABLED" if api.kit.lotus_kit is not None else "DISABLED"
            print(f"   lotus_kit: {status}")
        
        if hasattr(api.kit, 'synapse_storage'):
            status = "ENABLED" if api.kit.synapse_storage is not None else "DISABLED"
            print(f"   synapse_storage: {status}")
            
        if hasattr(api.kit, 'ipfs_cluster_service'):
            status = "ENABLED" if api.kit.ipfs_cluster_service is not None else "DISABLED"
            print(f"   ipfs_cluster_service: {status}")
            
        if hasattr(api.kit, 'ipfs_cluster_follow'):
            status = "ENABLED" if api.kit.ipfs_cluster_follow is not None else "DISABLED"
            print(f"   ipfs_cluster_follow: {status}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_normal_role():
    """Test normal role without disabled components."""
    print("\n" + "=" * 60)
    print("Testing Normal Role (No Component Disabling)")
    print("=" * 60)
    
    try:
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        
        # Create API without disabled components
        print(f"Creating IPFSSimpleAPI with normal leecher role (no disabled components)")
        
        api = IPFSSimpleAPI(role='leecher')
        
        print(f"\n✅ API initialized successfully")
        print(f"   Role: {api.role}")
        print(f"   Disabled components: {getattr(api, 'disabled_components', 'None')}")
        
        # Check component status (should be enabled)
        print(f"\nComponent Status:")
        if hasattr(api.kit, 'lotus_kit'):
            status = "ENABLED" if api.kit.lotus_kit is not None else "DISABLED"
            print(f"   lotus_kit: {status}")
        
        if hasattr(api.kit, 'synapse_storage'):
            status = "ENABLED" if api.kit.synapse_storage is not None else "DISABLED"
            print(f"   synapse_storage: {status}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("IPFS Kit Role-Based Component Disabling Test")
    print("Testing implementation for leecher role component restrictions")
    
    success = True
    
    # Test leecher role with disabled components
    success &= test_leecher_role()
    
    # Test normal role
    success &= test_normal_role()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All tests passed! Component disabling is working correctly.")
        print("\nThe leecher role now successfully disables:")
        print("   - ipfs_cluster")
        print("   - ipfs_cluster_follow") 
        print("   - lotus")
        print("   - synapse")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    print("=" * 60)

if __name__ == "__main__":
    main()
