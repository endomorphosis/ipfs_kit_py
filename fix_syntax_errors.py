#!/usr/bin/env python3

"""
Script to fix common syntax errors in Python files across the project.
"""

import os
import re
import sys
from pathlib import Path

def fix_syntax_errors_in_file(file_path):
    """Fix common syntax errors in a Python file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Fix 1: Missing commas in function parameter lists
    # Pattern: "def function_name(\n    self\n    param1: type,"
    # Replace with: "def function_name(\n    self,\n    param1: type,"
    content = re.sub(r'def\s+(\w+)\s*\(\s*\n\s*self\s*\n\s+', r'def \1(\n    self,\n    ', content)
    
    # Fix 2: Trailing commas in if statements
    # Pattern: "if condition:"
    # Replace with: "if condition:"
    content = re.sub(r'if\s+([^:]+):\s*,', r'if \1:', content)
    
    # Fix 3: Incomplete function definitions
    # This is harder to fix with regex, might need manual intervention
    
    # Fix 4: Fix incorrectly organized imports
    # Pattern: "from fastapi import (\nfrom pydantic"
    # Replace with: "from fastapi import (\n    APIRouter,\n    HTTPException,\n    ...)\nfrom pydantic"
    if "from fastapi import (" in content and "from pydantic" in content:
        # This is a more complex fix that might need manual intervention
        print(f"Warning: Complex import pattern found in {file_path}")
    
    # Only write back if changes were made
    if content != original_content:
        print(f"Fixing syntax errors in {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False

def find_and_fix_python_files(directory):
    """Find all Python files in directory and fix syntax errors."""
    fixed_count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                if fix_syntax_errors_in_file(file_path):
                    fixed_count += 1
    return fixed_count

if __name__ == "__main__":
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = "."
    
    print(f"Scanning for Python files in {directory}")
    fixed_count = find_and_fix_python_files(directory)
    print(f"Fixed syntax errors in {fixed_count} files")