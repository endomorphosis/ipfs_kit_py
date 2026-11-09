#!/usr/bin/env python3
"""
Comprehensive code fixer for Python files using Black and Ruff.
This script handles specific syntax issues that prevent Black from running.
"""

import os
import re
import sys
import subprocess
from pathlib import Path

# Directory to process
TARGET_DIR = "ipfs_kit_py/mcp"
BACKUP_DIR = f"mcp_backup_{os.popen('date +%Y%m%d_%H%M%S').read().strip()}"

# Create backup
print(f"Creating backup in {BACKUP_DIR}")
os.system(f"cp -r {TARGET_DIR} {BACKUP_DIR}")

def run_command(cmd):
    """Run a shell command and return the result."""
    process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return process.returncode, process.stdout, process.stderr

def fix_imports(content):
    """Fix import statements."""
    # Fix trailing commas in import lists
    content = re.sub(r'from\s+(.*?)\s+import\s+\((.*?),\s*\)', r'from \1 import (\2)', content, flags=re.DOTALL)

    # Fix empty parentheses in imports
    content = re.sub(r'from typing import \(,', r'from typing import (', content)

    # Fix dangling imports
    content = re.sub(r'(from .*? import .*?)\s*\n\s*\.([a-zA-Z_]+)', r'\1.\2', content)

    return content

def fix_parameter_lists(content):
    """Fix parameter lists in function and method definitions."""
    # Fix trailing commas in method/function parameters
    content = re.sub(r'(\s+)self,$', r'\1self', content, flags=re.MULTILINE)

    # Fix parameters without default values
    content = re.sub(r'(\s+)([a-zA-Z0-9_]+)=None(\s*)(,|\))', r'\1\2 = None\3\4', content)

    # Fix parameter with trailing comma
    content = re.sub(r'(\s+)([a-zA-Z0-9_]+): ([a-zA-Z0-9_]+),$', r'\1\2: \3', content, flags=re.MULTILINE)

    return content

def fix_dictionaries(content):
    """Fix dictionary syntax issues."""
    # Fix trailing commas in dictionaries
    content = re.sub(r'(\s+)"([^"]+)":\s+([^,\n]+),(\s+)$', r'\1"\2": \3\4', content, flags=re.MULTILINE)

    # Fix missing commas in dictionaries
    content = re.sub(r'(\s+)"([^"]+)":\s+([^,\n]+)(\s+)"', r'\1"\2": \3,\4"', content)

    return content

def fix_type_annotations(content):
    """Fix common type annotation issues."""
    # Fix incomplete Union types
    content = re.sub(r'Union\[(.*?), \]', r'Union[\1]', content)

    # Fix incomplete Dict types
    content = re.sub(r'Dict\[(.*?), \]', r'Dict[\1]', content)

    # Fix incomplete List types
    content = re.sub(r'List\[(.*?), \]', r'List[\1]', content)

    # Fix broken type annotations
    content = re.sub(r'(.*?)-> Dict\[str, Any\]:(\s+)', r'\1-> dict[str, any]:\2', content)

    return content

def fix_indentation(content):
    """Fix indentation issues."""
    # Replace tabs with spaces
    content = content.replace('\t', '    ')

    # Fix docstring indentation
    content = re.sub(r'"""(?:\s*\n)+(\s+)(?!""")', r'"""\n\1', content)

    return content

def fix_multiline_strings(content):
    """Fix multiline string formatting."""
    # Fix triple quotes that start a multiline string but end improperly
    content = re.sub(r'"""(.*?)(?<!\n\s*""")\s*$', r'"""\1"""', content, flags=re.DOTALL)

    return content

def fix_json_formatting(content):
    """Fix JSON-like data structures in Python."""
    # Fix missing commas in JSON structures
    content = re.sub(r'(\s+)"([^"]+)":\s+(\{[^{}]*\})(\s+)"', r'\1"\2": \3,\4"', content)

    return content

def fix_syntax(file_path):
    """Apply all syntax fixes to a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Apply all fixes
        fixed_content = content
        fixed_content = fix_imports(fixed_content)
        fixed_content = fix_parameter_lists(fixed_content)
        fixed_content = fix_dictionaries(fixed_content)
        fixed_content = fix_type_annotations(fixed_content)
        fixed_content = fix_indentation(fixed_content)
        fixed_content = fix_multiline_strings(fixed_content)
        fixed_content = fix_json_formatting(fixed_content)

        # Additional specific fixes for common issues
        fixed_content = fixed_content.replace('self,,,', 'self')
        fixed_content = fixed_content.replace('= Field(None,', '= Field(None, ')

        # Write back if changed
        if fixed_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def apply_black_and_ruff(file_path):
    """Apply Black and Ruff formatting."""
    # Try with permissive Black first
    cmd = f"black --quiet --fast {file_path}"
    rc, _, _ = run_command(cmd)

    # If permissive Black fails, try with specific options
    if rc != 0:
        cmd = f"black --quiet --skip-string-normalization {file_path}"
        run_command(cmd)

    # Apply Ruff with fix option
    cmd = f"ruff check --fix --quiet {file_path}"
    run_command(cmd)

def process_files():
    """Process all Python files in the target directory."""
    python_files = list(Path(TARGET_DIR).glob("**/*.py"))
    total_files = len(python_files)

    print(f"Processing {total_files} Python files...")

    for i, file_path in enumerate(python_files, 1):
        if i % 10 == 0 or i == total_files:
            print(f"Processed {i}/{total_files} files")

        file_path_str = str(file_path)

        # Skip __pycache__ files
        if "__pycache__" in file_path_str:
            continue

        # Apply syntax fixes
        fix_syntax(file_path_str)

        # Apply Black and Ruff
        apply_black_and_ruff(file_path_str)

if __name__ == "__main__":
    process_files()
    print(f"\nProcessing complete! Files backed up in {BACKUP_DIR}")
