#\!/usr/bin/env python3
"""
Script to fix indentation in the ipfs_name_resolve method.
"""

file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/ipfs_model.py'

with open(file_path, 'r') as f:
    lines = f.readlines()

# Find the ipfs_name_resolve method
start_line = None
for i, line in enumerate(lines):
    if 'def ipfs_name_resolve(' in line:
        start_line = i
        break

if start_line is None:
    print("Could not find ipfs_name_resolve method")
    exit(1)

# Fix indentation for the docstring
for i in range(start_line + 1, start_line + 14):  # Assuming docstring is around 13 lines
    if lines[i].strip() and not lines[i].startswith('    '):
        lines[i] = '    ' + lines[i]

# Write back to file
with open(file_path, 'w') as f:
    f.writelines(lines)

print("Fixed indentation in ipfs_name_resolve method")
