#!/usr/bin/env python3
"""
Test script to verify installer functionality.
"""

import sys
from pathlib import Path


# Add repo root (not the package dir) to avoid shadowing external deps.
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

print("Testing installer imports...")

try:
    from ipfs_kit_py.install_ipfs import install_ipfs
    print("✓ install_ipfs imported successfully")
    
    installer = install_ipfs()
    print("✓ install_ipfs instance created")
    
    # Test distribution selection
    dist = installer.dist_select()
    print(f"✓ Distribution selected: {dist}")
    
    # Check if IPFS URLs are correct
    if dist in installer.ipfs_dists:
        url = installer.ipfs_dists[dist]
        print(f"✓ IPFS download URL: {url}")
        if "kubo" in url:
            print("✓ URL contains 'kubo' (correct IPFS distribution)")
        else:
            print("✗ URL does not contain 'kubo' (might be wrong)")
    else:
        print(f"✗ Distribution '{dist}' not found in ipfs_dists")
        
except Exception as e:
    print(f"✗ install_ipfs failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50 + "\n")

try:
    from ipfs_kit_py.install_lotus import install_lotus
    print("✓ install_lotus imported successfully")
    
    installer = install_lotus()
    print("✓ install_lotus instance created")
    
except Exception as e:
    print(f"✗ install_lotus failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50 + "\n")

try:
    from scripts.install.install_lassie import install_lassie
    print("✓ install_lassie imported successfully")
    
    installer = install_lassie()
    print("✓ install_lassie instance created")
    
except Exception as e:
    print(f"✗ install_lassie failed: {e}")
    import traceback
    traceback.print_exc()
