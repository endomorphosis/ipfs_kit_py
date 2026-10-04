#!/usr/bin/env python3
"""
Fix all instances of extra parentheses in the libp2p_model.py file.
"""

import re

file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/libp2p_model.py'

with open(file_path, 'r') as file:
    content = file.read()

# Fix all instances of extra parentheses at the end of a line
pattern = r'return await anyio\.to_thread\.run_sync\(([^)]+)\)\)'
replacement = r'return await anyio.to_thread.run_sync(\1)'

# Use re.sub to replace all matches
fixed_content = re.sub(pattern, replacement, content)

# Write the fixed content back to the file
with open(file_path, 'w') as file:
    file.write(fixed_content)

print(f"Fixed all extra parentheses in {file_path}")