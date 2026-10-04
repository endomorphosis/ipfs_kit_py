#!/usr/bin/env python3

"""
Script to fix the IPFSController class by adding the missing methods correctly.
"""

import re

def main():
    # Read the controller file
    with open('ipfs_kit_py/mcp/controllers/ipfs_controller.py', 'r') as f:
        content = f.read()
    
    # Read the list_files method
    with open('ipfs_kit_py/mcp/controllers/ipfs_controller_list_files.py', 'r') as f:
        list_files_content = f.read()
    
    # Read the MFS methods
    with open('ipfs_kit_py/mcp/controllers/ipfs_controller_mfs_methods.py', 'r') as f:
        mfs_methods_content = f.read()
    
    # Find the position to insert - just before the last closing brace of the class
    # We'll look for the last function definition and add after that 
    pattern = r'(\s+def [^(]+\([^)]*\):(?:.|\n)*?)(\n\s*})'
    last_method_match = re.search(pattern, content)
    
    if not last_method_match:
        print("Error: Could not find the pattern to insert after")
        return
    
    # Split the content at the last method's end
    insert_pos = last_method_match.end(1)
    
    # Insert the new methods
    new_content = (
        content[:insert_pos] + 
        "\n\n    # Files API (MFS) methods\n    " + 
        list_files_content + 
        "\n\n    # Additional MFS methods\n    " + 
        mfs_methods_content +
        content[insert_pos:]
    )
    
    # Write the updated content back to the file
    with open('ipfs_kit_py/mcp/controllers/ipfs_controller.py', 'w') as f:
        f.write(new_content)
    
    print("Successfully added the missing methods to IPFSController.")

if __name__ == "__main__":
    main()
