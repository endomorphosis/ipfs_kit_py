#!/usr/bin/env python3
"""Fix MCP code issues and run Black and Ruff."""

import os
import sys
import subprocess
import shutil
import tempfile
from datetime import datetime

MCP_DIR = "ipfs_kit_py/mcp"
BACKUP_DIR = f"mcp_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

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
    return sorted(python_files)

def fix_common_syntax_issues(content):
    """Fix common syntax issues in Python files."""
    # Remove special markers that might cause parsing issues
    for marker in ['</final_file_content>', '<line number missing in source>']:
        content = content.replace(marker, '')
    
    # Fix indentation issues (convert tabs to spaces)
    lines = content.splitlines()
    fixed_lines = []
    for line in lines:
        if '\t' in line:
            fixed_line = line.replace('\t', '    ')
            fixed_lines.append(fixed_line)
        else:
            fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    # Ensure the file ends with a newline
    if not content.endswith('\n'):
        content += '\n'
    
    return content

def try_fix_file(file_path):
    """Try to fix a Python file."""
    print(f"Checking {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Apply common syntax fixes
        fixed_content = fix_common_syntax_issues(content)
        
        # Create a temporary file to test if black can parse it
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as temp:
            temp_path = temp.name
            temp.write(fixed_content.encode('utf-8'))
        
        try:
            # Test if Black can parse the fixed file
            subprocess.run(['black', '--check', temp_path], 
                          check=True, capture_output=True)
            # If we got here, Black can parse it
            success = True
        except subprocess.CalledProcessError:
            # Black still can't parse it, but at least we tried
            success = False
        
        # Clean up the temporary file
        os.unlink(temp_path)
        
        # If the content was changed and Black can now parse it, save the changes
        if content != fixed_content and success:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            print(f"✓ Fixed syntax issues in {file_path}")
            return True
        elif success:
            print(f"✓ No syntax issues found in {file_path}")
            return True
        else:
            print(f"✗ Could not fix all issues in {file_path}")
            return False
    
    except Exception as e:
        print(f"✗ Error processing {file_path}: {str(e)}")
        return False

def apply_black_to_file(file_path):
    """Apply Black to a single file."""
    try:
        print(f"Applying Black to {file_path}...")
        result = subprocess.run(['black', file_path], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Black successfully formatted {file_path}")
            return True
        else:
            print(f"✗ Black failed on {file_path}: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Error running Black on {file_path}: {str(e)}")
        return False

def apply_ruff_to_file(file_path):
    """Apply Ruff to a single file."""
    try:
        print(f"Applying Ruff to {file_path}...")
        result = subprocess.run(['ruff', 'check', '--fix', file_path], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Ruff successfully fixed {file_path}")
            return True
        else:
            print(f"✗ Ruff found issues in {file_path}: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ Error running Ruff on {file_path}: {str(e)}")
        return False

def main():
    """Main function to fix code issues and apply formatting."""
    create_backup()
    
    python_files = find_python_files()
    print(f"Found {len(python_files)} Python files")
    
    # First pass: Fix syntax issues in files
    fixed_files = []
    unfixed_files = []
    
    for file_path in python_files:
        if try_fix_file(file_path):
            fixed_files.append(file_path)
        else:
            unfixed_files.append(file_path)
    
    print(f"\nFixed syntax issues in {len(fixed_files)} files")
    print(f"Could not fix {len(unfixed_files)} files")
    
    # Second pass: Apply Black and Ruff to files we managed to fix
    formatted_files = []
    
    for file_path in fixed_files:
        success = True
        if apply_black_to_file(file_path):
            if apply_ruff_to_file(file_path):
                formatted_files.append(file_path)
            else:
                success = False
        else:
            success = False
        
        if not success:
            print(f"✗ Could not complete formatting of {file_path}")
    
    # Report results
    print("\n--- SUMMARY ---")
    print(f"Total Python files: {len(python_files)}")
    print(f"Files with fixed syntax: {len(fixed_files)}")
    print(f"Files successfully formatted: {len(formatted_files)}")
    print(f"Files requiring manual attention: {len(unfixed_files)}")
    
    if unfixed_files:
        print("\nFiles requiring manual fixes:")
        for file in unfixed_files:
            print(f"  - {file}")
    
    print(f"\nOriginal files were backed up to {BACKUP_DIR}")

if __name__ == "__main__":
    main()