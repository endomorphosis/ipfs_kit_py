#!/usr/bin/env python3

import os

import re

def fix_discover_partitions():
    file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/tiered_cache.py'
    
    print(f"Reading file {file_path}")
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Look for the duplicate method pattern
    # This uses a regex pattern to find and fix the problematic area
    pattern = r'(\s+def _discover_partitions.*?\s+return partitions\n)(\s+try:)'
    
    # Check if we find this pattern
    if re.search(pattern, content, re.DOTALL):
        print("Found duplicate _discover_partitions pattern")
        # Replace it by keeping only one implementation
        fixed_content = re.sub(pattern, r'\1', content, flags=re.DOTALL)
        
        print(f"Writing fixed content back to {file_path}")
        with open(file_path, 'w') as f:
            f.write(fixed_content)
        
        print("Fixed the duplicate _discover_partitions method")
        return True
    else:
        print("Did not find the expected pattern. Maybe the file was already fixed?")
        return False

if __name__ == "__main__":
    fix_discover_partitions()
