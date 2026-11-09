#!/usr/bin/env python3
"""
Fix syntax error in ipfs_controller.py file.
"""

import os
import re

# Controller file path
controller_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py'

# Read the file
with open(controller_path, 'r') as f:
    content = f.read()

# Find unmatched brace at line 2402
# Split into lines for easier processing
lines = content.split('\n')

# Check line 2402 and surrounding lines
line_number = 2402
start_line = max(0, line_number - 5)
end_line = min(len(lines), line_number + 5)

print(f"Lines {start_line} to {end_line} around the error:")
for i in range(start_line, end_line):
    print(f"{i+1}: {lines[i]}")

# Count the number of { and } to find imbalance
open_braces = content.count('{')
close_braces = content.count('}')
print(f"Open braces: {open_braces}, Close braces: {close_braces}")

# Remove the extra } at line 2402
if line_number < len(lines):
    lines[line_number-1] = lines[line_number-1].replace('}', '')
    
    # Write back the file
    with open(controller_path, 'w') as f:
        f.write('\n'.join(lines))
    print("Removed extra brace at line 2402")
else:
    print("Line number out of range")

# Verify the fix
os.system(f"python3 -m py_compile {controller_path}")
print("Compilation check completed.")