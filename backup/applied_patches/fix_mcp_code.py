#!/usr/bin/env python3
"""
Script to fix syntax issues in Python files and then apply Black and Ruff formatting.
"""

import os
import re
import sys
import subprocess
from pathlib import Path

# Directory to process
TARGET_DIR = "ipfs_kit_py/mcp"

# Create a backup
backup_dir = f"mcp_backup_{os.popen('date +%Y%m%d_%H%M%S').read().strip()}"
print(f"Creating backup in {backup_dir}")
os.system(f"cp -r {TARGET_DIR} {backup_dir}")

def fix_file(file_path):
    """Fix common syntax issues in Python files."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Fix common syntax issues
        fixed_content = content

        # Fix trailing commas in import lists
        fixed_content = re.sub(r'from\s+(.*?)\s+import\s+\((.*?),\s*\)', r'from \1 import (\2)', fixed_content, flags=re.DOTALL)

        # Fix incomplete imports with typing
        fixed_content = re.sub(r'from typing import \(,', r'from typing import (', fixed_content)

        # Fix trailing commas in function parameters
        fixed_content = re.sub(r'(\s+)self,$', r'\1self', fixed_content, flags=re.MULTILINE)

        # Fix dangling commas in parameter definitions
        fixed_content = re.sub(r'(\s+)([a-zA-Z0-9_]+):\s+([a-zA-Z0-9_\[\], .]+),(\s+)$', r'\1\2: \3\4', fixed_content, flags=re.MULTILINE)

        # Fix multiline strings with mixed indentation
        fixed_content = re.sub(r'"""(?:\s*\n)+(\s+)(?!""")', r'"""\n\1', fixed_content)

        # Fix indentation issues
        fixed_content = fixed_content.replace('\t', '    ')

        # Fix issues with Union types
        fixed_content = re.sub(r'Union\[(.*?), \]', r'Union[\1]', fixed_content)

        # Write back the fixed content if changes were made
        if fixed_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            return True
        return False
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return False

def apply_black(file_path):
    """Apply Black formatting to a file."""
    try:
        result = subprocess.run(
            ["black", "--quiet", file_path],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error applying Black to {file_path}: {e}")
        return False

def apply_ruff(file_path):
    """Apply Ruff fixes to a file."""
    try:
        result = subprocess.run(
            ["ruff", "check", "--fix", "--quiet", file_path],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error applying Ruff to {file_path}: {e}")
        return False

def process_files():
    """Process all Python files in the target directory."""
    python_files = list(Path(TARGET_DIR).glob("**/*.py"))
    total_files = len(python_files)

    print(f"Processing {total_files} Python files...")

    fixed_syntax = 0
    black_success = 0
    ruff_success = 0

    for i, file_path in enumerate(python_files, 1):
        file_path_str = str(file_path)

        # Skip __pycache__ files
        if "__pycache__" in file_path_str:
            continue

        # Fix syntax issues
        if fix_file(file_path_str):
            fixed_syntax += 1

        # Apply Black
        if apply_black(file_path_str):
            black_success += 1

        # Apply Ruff
        if apply_ruff(file_path_str):
            ruff_success += 1

        # Print progress
        if i % 10 == 0 or i == total_files:
            print(f"Processed {i}/{total_files} files")

    print("\nSummary:")
    print(f"Files with syntax fixes: {fixed_syntax}")
    print(f"Files successfully formatted with Black: {black_success}")
    print(f"Files successfully fixed with Ruff: {ruff_success}")

if __name__ == "__main__":
    process_files()
    print("\nProcessing complete! The mcp directory has been cleaned and formatted.")
