#\!/usr/bin/env python3

import re

# Read the file
with open('ipfs_kit_py/mcp/models/ipfs_model.py', 'r') as f:
    content = f.read()

# Find the method
pattern = r'(def ipfs_name_resolve\([^)]*\):)\s+(""".*?)(\s+operation_id)'
match = re.search(pattern, content, re.DOTALL)

if not match:
    print("Couldn't find the pattern to replace.")
    exit(1)

# Fix indentation
fixed_content = content.replace(
    match.group(0),
    f"{match.group(1)}\n        {match.group(2).replace('"""', '"""').replace('\n', '\n        ')}{match.group(3)}"
)

# Write back
with open('ipfs_kit_py/mcp/models/ipfs_model.py', 'w') as f:
    f.write(fixed_content)

print("Fixed the docstring indentation in ipfs_name_resolve")
