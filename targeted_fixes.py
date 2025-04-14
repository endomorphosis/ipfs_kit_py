#!/usr/bin/env python3
"""
Script for targeted fixes of specific issues in Python files.
This addresses issues that the automated script couldn't fix.
"""

import os
import re
import sys
import glob

def fix_undefined_names(file_path):
    """Fix undefined name issues by adding imports."""
    print(f"Fixing undefined names in {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Common undefined names and their imports
    common_imports = {
        'logging': 'import logging',
        'logger': 'logger = logging.getLogger(__name__)',
        'APIRouter': 'from fastapi import APIRouter',
        'HTTPException': 'from fastapi import HTTPException',
        'Request': 'from fastapi import Request',
        'Response': 'from fastapi import Response',
        'Body': 'from fastapi import Body',
        'Query': 'from fastapi import Query',
        'Path': 'from fastapi import Path',
        'Optional': 'from typing import Optional',
        'List': 'from typing import List',
        'Dict': 'from typing import Dict',
        'Any': 'from typing import Any',
        'BaseModel': 'from pydantic import BaseModel',
        'Field': 'from pydantic import Field',
        'Enum': 'from enum import Enum',
        'json': 'import json',
        'time': 'import time',
        'os': 'import os',
        'sys': 'import sys',
        'asyncio': 'import asyncio',
        'traceback': 'import traceback',
    }
    
    # Add missing imports
    for name, import_stmt in common_imports.items():
        # Check if name is used but not imported
        if re.search(r'\b' + re.escape(name) + r'\b', content) and import_stmt not in content:
            # Add import at the top of the file
            content = import_stmt + '\n' + content
            print(f"  Added import: {import_stmt}")
    
    with open(file_path, 'w') as f:
        f.write(content)

def fix_bare_excepts(file_path):
    """Replace bare excepts with specific exception types."""
    print(f"Fixing bare excepts in {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace bare 'except:' with 'except Exception:'
    fixed_content = re.sub(r'except\s*:', 'except Exception:', content)
    
    if fixed_content != content:
        with open(file_path, 'w') as f:
            f.write(fixed_content)
        print(f"  Fixed bare except statements")

def main():
    """Main function to process files."""
    if len(sys.argv) < 2:
        print("Usage: python targeted_fixes.py <file_or_directory>")
        return
    
    target = sys.argv[1]
    
    if os.path.isfile(target):
        files = [target]
    elif os.path.isdir(target):
        files = glob.glob(os.path.join(target, '**', '*.py'), recursive=True)
    else:
        print(f"Error: {target} is not a valid file or directory")
        return
    
    for file_path in files:
        print(f"\nProcessing {file_path}")
        fix_undefined_names(file_path)
        fix_bare_excepts(file_path)

if __name__ == "__main__":
    main()
