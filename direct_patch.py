#!/usr/bin/env python3
"""
Direct patching script for MCP server compatibility issues
"""
import sys
import os
import importlib

def patch_asyncio():
    """Patch asyncio to handle the 'async' keyword issue"""
    try:
        import asyncio
        
        # Use safer dictionary approach to avoid syntax errors with 'async' keyword
        if 'async' in asyncio.__dict__:
            # Get the function without directly using the keyword
            async_func = asyncio.__dict__['async']
            # Add it under the new name
            asyncio.__dict__['ensure_future'] = async_func
            # Delete the old name
            del asyncio.__dict__['async']
            print("Patched asyncio.async -> asyncio.ensure_future")
        
        return True
    except Exception as e:
        print(f"Error patching asyncio: {e}")
        return False

def patch_multiaddr():
    """Add multiaddr.exceptions if it doesn't exist"""
    try:
        import multiaddr
        if not hasattr(multiaddr, 'exceptions'):
            class Exceptions:
                class Error(Exception):
                    pass
            multiaddr.exceptions = Exceptions
            print("Added mock exceptions to multiaddr module")
        return True
    except ImportError:
        print("multiaddr module not found, skipping patch")
        return False

if __name__ == "__main__":
    # Apply patches
    patch_asyncio()
    patch_multiaddr()
    
    # Continue with normal execution
    print("Patches applied, starting MCP server...")
