#!/usr/bin/env python3
"""
Debug script for High-Level API
"""

import os
import sys
import traceback

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

try:
    # Import the High-Level API
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    
    print("Successfully imported IPFSSimpleAPI")
    
    # Try to instantiate the API
    try:
        api = IPFSSimpleAPI()
        print(f"Successfully instantiated IPFSSimpleAPI with role: {api.config.get('role')}")
        
        # Try basic operations
        try:
            # Add content
            content = b"Test content for debugging"
            result = api.add(content)
            print(f"Add result: {result}")
            
            if result.get("success"):
                cid = result.get("cid")
                
                # Get content
                try:
                    retrieved = api.get(cid)
                    print(f"Successfully retrieved content: {retrieved[:20]}...")
                except Exception as e:
                    print(f"Error retrieving content: {e}")
                    traceback.print_exc()
        except Exception as e:
            print(f"Error performing operations: {e}")
            traceback.print_exc()
    except Exception as e:
        print(f"Error instantiating IPFSSimpleAPI: {e}")
        traceback.print_exc()
except ImportError as e:
    print(f"Error importing IPFSSimpleAPI: {e}")
    traceback.print_exc()