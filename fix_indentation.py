#!/usr/bin/env python3

import os
import re

def fix_tiered_cache_indentation():
    file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/tiered_cache.py'
    
    print(f"Reading file {file_path}")
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    print(f"File has {len(lines)} lines")
    
    # Fix indentation for @staticmethod around line 5498
    for i in range(5495, 5510):
        if i < len(lines) and '@staticmethod' in lines[i]:
            # Check context
            if '    def __del__' in lines[i-2]:
                indent = '    '  # Match class-level indentation
                print(f"Fixing @staticmethod indentation at line {i+1}")
                lines[i] = indent + '@staticmethod\n'
                # Also fix the next line (method definition)
                if i+1 < len(lines) and 'def ' in lines[i+1]:
                    lines[i+1] = indent + 'def ' + lines[i+1].lstrip().lstrip('def ')
                    print(f"Fixing method definition indentation at line {i+2}")
    
    # Save the initially fixed lines
    fixed_lines = lines
    
    # First fix any indentation issues at the beginning of the file
    # Look for an improperly indented __init__ method not attached to a class
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Look for indented __init__ without a class
        if re.match(r'^\s+def __init__', line) and (i == 0 or not re.match(r'^\s*class\s+', lines[i-1])):
            print(f"Found misplaced __init__ method at line {i+1}")
            
            # Find the class this method belongs to (scan backwards)
            class_line = -1
            for j in range(i-1, -1, -1):
                if re.match(r'^\s*class\s+ARCache', lines[j]):
                    class_line = j
                    print(f"Found ARCache class definition at line {j+1}")
                    break
            
            if class_line != -1:
                # Fix the indentation by adding the method to the class
                # First add all lines before the method
                fixed_lines.extend(lines[:i])
                
                # Then add the method with proper indentation
                in_method = True
                while i < len(lines) and in_method:
                    if lines[i].strip() and not lines[i].startswith(' '):
                        in_method = False
                    else:
                        fixed_lines.append(lines[i])
                        i += 1
            else:
                # If we can't find the class, just add the line as-is
                fixed_lines.append(line)
                i += 1
        else:
            # Add normal lines as-is
            fixed_lines.append(line)
            i += 1
    
    # Fix duplicate _discover_partitions method
    content = ''.join(fixed_lines)
    pattern = r'(\s+def _discover_partitions.*?\s+return partitions\n)(\s+try:)'
    if re.search(pattern, content, re.DOTALL):
        print("Found and fixing duplicate _discover_partitions pattern")
        content = re.sub(pattern, r'\1', content, flags=re.DOTALL)
    
    # Write the fixed content back
    print(f"Writing fixed content back to {file_path}")
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("Fixed indentation issues in tiered_cache.py")
    return True

if __name__ == "__main__":
    fix_tiered_cache_indentation()
