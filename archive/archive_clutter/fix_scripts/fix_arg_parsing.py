#!/usr/bin/env python3
"""
This script finds and fixes issues with argument parsing in test files.
It modifies files to only parse command line arguments when run directly,
not when imported by pytest.
"""

import os
import re
import glob

# Search for all Python test files
test_files = glob.glob('test/**/*.py', recursive=True)

# Pattern to match parser.parse_args() that is not inside an if __name__ == "__main__" block
pattern = re.compile(r'^(\s*)args\s*=\s*parser\.parse_args\(\)(.*?)$', re.MULTILINE)

# Pattern to check if the file already has conditional arg parsing
conditional_pattern = re.compile(r'if\s+__name__\s*==\s*[\'"]__main__[\'"]\s*:\s*\n\s*args\s*=\s*parser\.parse_args\(\)', re.MULTILINE)

# Counter for modified files
modified_files = 0

for file_path in test_files:
    try:
        # Read file content
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Skip if file already has conditional arg parsing
        if conditional_pattern.search(content):
            continue
        
        # Check if the file has unconditional arg parsing
        if pattern.search(content):
            # Replace with conditional arg parsing
            modified_content = pattern.sub(r'''\1# Only parse args when running the script directly, not when imported by pytest
\1if __name__ == "__main__":
\1    args = parser.parse_args()
\1else:
\1    # When run under pytest, use default values
\1    args = parser.parse_args([])\2''', content)
            
            # Write back the modified content
            with open(file_path, 'w') as f:
                f.write(modified_content)
            
            modified_files += 1
            print(f"Fixed arg parsing in: {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

print(f"\nFixed argument parsing in {modified_files} test files.")