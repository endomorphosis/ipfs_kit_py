#!/usr/bin/env python3

"""
Script to fix indentation issues in Python files
"""

import re
import sys

def fix_tiered_cache_indentation():
    file_path = 'ipfs_kit_py/tiered_cache.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the problematic area around line 1847
    start_line = 1830  # Start a bit before the problematic section
    end_line = 1860    # End a bit after the problematic section
    
    # Export the chunk for inspection
    with open('tiered_cache_chunk.txt', 'w', encoding='utf-8') as f:
        for i in range(start_line-1, min(end_line, len(lines))):
            f.write(f"{i+1}: {lines[i]}")
            
    # Create a fixed version with corrected indentation
    with open(file_path, 'w', encoding='utf-8') as f:
        for i, line in enumerate(lines):
            # Special handling for the problematic section
            if i == 1846 or i == 1847:
                # Fix the indentation for these specific lines
                # This assumes we need 12 spaces (3 levels of indentation)
                if line.strip().startswith('except'):
                    f.write(' ' * 12 + line.strip() + '\n')
                elif 'logger.error' in line:
                    f.write(' ' * 16 + line.strip() + '\n')
            else:
                # Leave other lines unchanged
                f.write(line)
    
    print(f"Fixed indentation in {file_path} around lines 1847-1848")

if __name__ == "__main__":
    fix_tiered_cache_indentation()