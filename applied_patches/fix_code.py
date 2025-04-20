#!/usr/bin/env python3
"""Fix MCP code issues and run Black and Ruff."""

import os
import sys
import subprocess
import ast
import shutil
from datetime import datetime

MCP_DIR = "ipfs_kit_py/mcp"
BACKUP_DIR = f"mcp_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def is_valid_python(file_path):
    """Check if a file contains valid Python syntax."""
    try:
        with open(file_path, 'r') as f:
            ast.parse(f.read())
        return True
    except SyntaxError:
        return False

def create_backup():
    """Create a backup of the MCP directory."""
    print(f"Creating backup of {MCP_DIR} to {BACKUP_DIR}...")
    shutil.copytree(MCP_DIR, BACKUP_DIR)

def find_python_files():
    """Find all Python files in the MCP directory."""
    python_files = []
    for root, _, files in os.walk(MCP_DIR):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

def fix_file(file_path):
    """Fix common issues in Python files."""
    print(f"Checking {file_path}...")
    
    if is_valid_python(file_path):
        print(f"✓ {file_path} is valid Python")
        return True
    
    print(f"✗ {file_path} has syntax issues, attempting to fix...")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix common issues
    fixed_content = content.replace('</final_file_content>', '')
    
    # Ensure the file ends with a newline
    if not fixed_content.endswith('\n'):
        fixed_content += '\n'
    
    # Write the fixed content
    with open(file_path, 'w') as f:
        f.write(fixed_content)
    
    # Check if file is now valid
    if is_valid_python(file_path):
        print(f"✓ Fixed {file_path}")
        return True
    else:
        print(f"✗ Could not fix {file_path}")
        return False

def run_black(file_path):
    """Run Black on a file."""
    try:
        subprocess.run(['black', file_path], check=True, capture_output=True)
        print(f"✓ Black formatted {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Black failed on {file_path}: {e.stderr.decode()}")
        return False

def run_ruff(file_path):
    """Run Ruff on a file."""
    try:
        subprocess.run(['ruff', 'check', '--fix', file_path], check=True, capture_output=True)
        print(f"✓ Ruff fixed {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Ruff had issues with {file_path}: {e.stderr.decode()}")
        return False

def main():
    """Main function."""
    create_backup()
    
    python_files = find_python_files()
    print(f"Found {len(python_files)} Python files")
    
    # Process problematic files first
    problematic_files = [
        "ipfs_kit_py/mcp/models/ipfs_model_anyio.py",
        "ipfs_kit_py/mcp/models/storage/filecoin_model_anyio.py"
    ]
    
    for problem_file in problematic_files:
        if os.path.exists(problem_file) and problem_file in python_files:
            print(f"\nHandling known problematic file: {problem_file}")
            if fix_file(problem_file):
                run_black(problem_file)
                run_ruff(problem_file)
            python_files.remove(problem_file)
    
    # Process remaining files
    for file_path in python_files:
        print(f"\nProcessing: {file_path}")
        if fix_file(file_path):
            run_black(file_path)
            run_ruff(file_path)
    
    print("\nAll done! Code in MCP has been formatted with Black and fixed with Ruff.")
    print(f"Original files were backed up to {BACKUP_DIR}")

if __name__ == "__main__":
    main()