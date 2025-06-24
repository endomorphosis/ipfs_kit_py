#!/usr/bin/env python3

"""
Script to update the IPFSController class with the missing methods.
"""

import os
import re

def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

# Read the main controller file
ipfs_controller_path = 'ipfs_kit_py/mcp/controllers/ipfs_controller.py'
controller_content = read_file(ipfs_controller_path)

# Read the list_files method
list_files_path = 'ipfs_kit_py/mcp/controllers/ipfs_controller_list_files.py'
list_files_content = read_file(list_files_path)

# Read the MFS methods
mfs_methods_path = 'ipfs_kit_py/mcp/controllers/ipfs_controller_mfs_methods.py'
mfs_methods_content = read_file(mfs_methods_path)

# Find the position to insert the new methods (before the last closing brace)
last_brace_pos = controller_content.rfind('}')

if last_brace_pos == -1:
    print("Error: Could not find the last closing brace in the IPFSController class")
    exit(1)

# Insert the new methods before the last closing brace
updated_content = (
    controller_content[:last_brace_pos] +
    "\n    # List files method\n    " +
    list_files_content +
    "\n    # MFS methods\n    " +
    mfs_methods_content +
    controller_content[last_brace_pos:]
)

# Write the updated content back to the file
write_file(ipfs_controller_path, updated_content)

print(f"Updated {ipfs_controller_path} with the missing methods")
