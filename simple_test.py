import sys
import os
sys.path.insert(0, '.')

try:
    import ipfs_kit_py.ipfs_kit
    print(f"HAS_LOTUS: {getattr(ipfs_kit_py.ipfs_kit, 'HAS_LOTUS', 'NOT_FOUND')}")
    
    kit = ipfs_kit_py.ipfs_kit.ipfs_kit()
    print(f"Has lotus_kit: {hasattr(kit, 'lotus_kit')}")
    
    if hasattr(kit, 'lotus_kit'):
        print("SUCCESS")
    else:
        print("FAILED - no lotus_kit")
        
except Exception as e:
    print(f"ERROR: {e}")
