#!/usr/bin/env python3
"""
Fix docstring formatting issues in libp2p_model.py
"""

import re
import sys

def fix_docstrings(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    # Pattern: Find docstrings with a newline right after opening quotes
    # followed by "Async version" text
    pattern = r'"""(\s*)\n(\s*)Async version'
    replacement = r'"""\n\1\2Async version'

    # Apply the fix
    fixed_content = re.sub(pattern, replacement, content)

    # Write the fixed content back
    with open(file_path, 'w') as f:
        f.write(fixed_content)

    print(f"Fixed docstring formatting in {file_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        fix_docstrings(sys.argv[1])
    else:
        print("Please provide the file path as an argument")
        sys.exit(1)
