#!/usr/bin/env python3

import sys
import os

# Add the package to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ipfs_kit_py'))

def debug_install_methods():
    """Debug what's happening with install methods."""
    try:
        from install_ipfs import install_ipfs
        installer = install_ipfs()
        
        # Check what these attributes actually are
        problem_methods = [
            'install_ipfs_cluster_follow',
            'install_ipfs_cluster_ctl', 
            'install_ipfs_cluster_service'
        ]
        
        for method_name in problem_methods:
            attr = getattr(installer, method_name, None)
            print(f"{method_name}:")
            print(f"  Type: {type(attr)}")
            print(f"  Value: {attr}")
            print(f"  Callable: {callable(attr)}")
            print(f"  Dir: {dir(attr)[:5]}...")  # First 5 attributes
            print()
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_install_methods()
