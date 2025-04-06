#!/usr/bin/env python3
import os

def fix_tiered_cache():
    file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/tiered_cache.py'
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find where the method ends and duplicated code begins
    found_return = False
    duplicate_start = None
    
    for i, line in enumerate(lines):
        if 'return partitions' in line and not found_return:
            found_return = True
        elif found_return and 'try:' in line and line.strip() == 'try:':
            duplicate_start = i
            break
    
    if duplicate_start:
        # Find the next valid line after the duplicated code - typically the next method
        next_valid_line = None
        for i in range(duplicate_start, len(lines)):
            if lines[i].strip().startswith('def '):
                next_valid_line = i
                break
        
        # If we didn't find the next method, use the end of file
        if next_valid_line is None:
            next_valid_line = len(lines)
        
        # Remove the duplicated code block
        lines = lines[:duplicate_start] + lines[next_valid_line:]
        
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print(f"Successfully removed duplicated code from line {duplicate_start} to {next_valid_line}")
    else:
        print("No duplicated code found")

if __name__ == "__main__":
    fix_tiered_cache()
