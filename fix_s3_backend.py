#!/usr/bin/env python
"""
Fix script for S3 backend implementation.

This script locates and removes erroneous content that was
accidentally inserted in the s3_backend.py file.
"""

import os
import re
import sys

def fix_s3_backend_file():
    """Fix syntax errors in the S3 backend file."""
    # Path to the file
    s3_backend_path = "ipfs_kit_py/mcp/storage_manager/backends/s3_backend.py"
    full_path = os.path.join("/home/barberb/ipfs_kit_py", s3_backend_path)
    
    if not os.path.exists(full_path):
        print(f"Error: File not found at {full_path}")
        return False
    
    # Create backup
    backup_path = f"{full_path}.bak"
    if not os.path.exists(backup_path):
        with open(full_path, 'r') as src:
            with open(backup_path, 'w') as dst:
                dst.write(src.read())
        print(f"Created backup at {backup_path}")
    
    # Read the file content
    with open(full_path, 'r') as f:
        content = f.read()
    
    # Find where the erroneous content starts
    pattern = r"\.\.\/\.\.\/\.\.\/response_"
    match = re.search(pattern, content)
    
    if not match:
        print("Could not find erroneous content in the file.")
        return False
    
    # Get the good content before the error
    good_content = content[:match.start()]
    
    # Check for unbalanced parentheses and braces
    open_parentheses = good_content.count('(')
    close_parentheses = good_content.count(')')
    open_braces = good_content.count('{')
    close_braces = good_content.count('}')
    
    # Add missing closing parentheses and braces if needed
    if open_parentheses > close_parentheses:
        good_content += ')' * (open_parentheses - close_parentheses)
        print(f"Added {open_parentheses - close_parentheses} missing closing parentheses")
    
    if open_braces > close_braces:
        good_content += '}' * (open_braces - close_braces)
        print(f"Added {open_braces - close_braces} missing closing braces")
    
    # Write the corrected file
    with open(full_path, 'w') as f:
        f.write(good_content)
    
    print(f"Successfully fixed {full_path}")
    return True

if __name__ == "__main__":
    success = fix_s3_backend_file()
    sys.exit(0 if success else 1)