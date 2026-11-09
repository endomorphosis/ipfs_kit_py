#!/usr/bin/env python
"""
Check libp2p availability and dependencies.

This script verifies the availability of libp2p-py and its dependencies
in the current Python environment. It also tests the integration with
the high-level API to verify the peer discovery functionality.
"""

import sys
import importlib
import json

def check_libp2p_dependencies():
    """
    Check for libp2p dependencies and report their availability.
    """
    dependencies = {
        "libp2p": False,
        "multiaddr": False,
        "base58": False,
        "cryptography": False,
        "anyio": False,
        "protobuf": False,
    }
    
    # Check if we have libp2p
    try:
        import libp2p
        dependencies["libp2p"] = True
    except ImportError:
        pass
        
    # Check if we have multiaddr
    try:
        import multiaddr
        dependencies["multiaddr"] = True
    except ImportError:
        pass
        
    # Check if we have base58
    try:
        import base58
        dependencies["base58"] = True
    except ImportError:
        pass
        
    # Check if we have cryptography
    try:
        import cryptography
        dependencies["cryptography"] = True
    except ImportError:
        pass
        
    # Check if we have anyio
    try:
        import anyio
        dependencies["anyio"] = True
    except ImportError:
        pass
        
    # Check if we have protobuf
    try:
        import google.protobuf  # noqa: F401
        dependencies["protobuf"] = True
    except ImportError:
        pass
    
    # Check overall availability
    libp2p_available = dependencies["libp2p"] and dependencies["multiaddr"]
    
    return {
        "libp2p_available": libp2p_available,
        "dependencies": dependencies,
        "installation_command": "pip install 'libp2p @ git+https://github.com/libp2p/py-libp2p.git@main' multiaddr multiformats base58 cryptography 'protobuf>=5.26.0,<7.0.0'"
    }

def check_high_level_api_integration():
    """
    Check if the high-level API integration works.
    """
    try:
        # Try to import the high-level API and integration
        from ipfs_kit_py.high_level_api import IPFSSimpleAPI
        from ipfs_kit_py.libp2p.high_level_api_integration import apply_high_level_api_integration
        
        # Try to apply the integration
        apply_high_level_api_integration()
        
        # Create a simple API instance
        api = IPFSSimpleAPI(role="leecher")
        
        # Check if peer discovery methods are available
        has_discover_peers = hasattr(api, "discover_peers")
        has_connect_to_peer = hasattr(api, "connect_to_peer")
        has_get_connected_peers = hasattr(api, "get_connected_peers")
        
        # Check if all methods are available
        integration_success = has_discover_peers and has_connect_to_peer and has_get_connected_peers
        
        return {
            "high_level_api_available": True,
            "integration_success": integration_success,
            "methods_available": {
                "discover_peers": has_discover_peers,
                "connect_to_peer": has_connect_to_peer,
                "get_connected_peers": has_get_connected_peers
            }
        }
        
    except ImportError:
        return {
            "high_level_api_available": False,
            "integration_success": False,
            "error": "High-level API not available"
        }
    except Exception as e:
        return {
            "high_level_api_available": True,
            "integration_success": False,
            "error": str(e)
        }

def main():
    """
    Main function to check dependencies and report.
    """
    # Check libp2p dependencies
    dependency_check = check_libp2p_dependencies()
    
    # Check high-level API integration
    integration_check = check_high_level_api_integration()
    
    # Combine results
    result = {
        "libp2p_dependency_check": dependency_check,
        "high_level_api_integration": integration_check
    }
    
    # Print formatted JSON result
    print(json.dumps(result, indent=2))
    
    # Show summary
    print("\nSummary:")
    print(f"libp2p availability: {'Yes' if dependency_check['libp2p_available'] else 'No'}")
    
    if not dependency_check['libp2p_available']:
        print(f"\nInstall required dependencies with:")
        print(f"  {dependency_check['installation_command']}")
    
    if integration_check.get('high_level_api_available', False):
        print(f"High-level API integration: {'Yes' if integration_check['integration_success'] else 'No'}")
        
        if not integration_check['integration_success'] and 'error' in integration_check:
            print(f"Error: {integration_check['error']}")
    else:
        print("High-level API not available")
    
    # Return success if all dependencies are available
    return dependency_check['libp2p_available']

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
