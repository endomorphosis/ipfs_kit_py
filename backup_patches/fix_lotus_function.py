#!/usr/bin/env python3
"""
Fix the client_retrieve_legacy method in lotus_kit.py
"""
import re
import os
import sys
import shutil

def fix_specific_method():
    """Fix only the client_retrieve_legacy method."""
    file_path = "ipfs_kit_py/lotus_kit.py"
    backup_path = "ipfs_kit_py/lotus_kit.py.backup"

    # Backup the file
    shutil.copy2(file_path, backup_path)
    print(f"Created backup at {backup_path}")

    # Read the whole file as a single string
    with open(file_path, 'r') as f:
        content = f.read()

    # Define a regex pattern to match the problematic function
    pattern = r'(    def client_retrieve_legacy\(.*?\):\s*)(""".*?""".*?)(    def)'

    # Create the properly indented replacement
    replacement = r'\1\2        # Forward to the main implementation\n        return self.client_retrieve(data_cid, out_file, **kwargs)\n\n\3'

    # Replace the function
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    # Write back to the file
    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f"Fixed client_retrieve_legacy method in {file_path}")
    return True

if __name__ == "__main__":
    success = fix_specific_method()
    sys.exit(0 if success else 1)
