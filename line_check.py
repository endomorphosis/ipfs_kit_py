#!/usr/bin/env python3

"""
Script to check specific lines in ai_ml_integration.py
"""

import tokenize
from io import BytesIO

def check_indentation(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Check method structure around line 6033
        print("Content around line 6033:")
        for i in range(6025, 6041):
            if i < len(lines):
                indent_level = len(lines[i]) - len(lines[i].lstrip())
                print(f"Line {i+1} - Indent level: {indent_level} - {repr(lines[i].rstrip())}")
            
        # Check method start indentation
        method_start = 5423
        if method_start < len(lines):
            method_indent = len(lines[method_start]) - len(lines[method_start].lstrip())
            print(f"\nMethod start at line {method_start+1} has indent level: {method_indent}")
            print(f"Method line: {repr(lines[method_start].rstrip())}")
            
        # Check Pydantic class indentation
        pydantic_line = 6036
        if pydantic_line < len(lines):
            pydantic_indent = len(lines[pydantic_line]) - len(lines[pydantic_line].lstrip())
            print(f"\nPydantic class at line {pydantic_line+1} has indent level: {pydantic_indent}")
            print(f"Pydantic line: {repr(lines[pydantic_line].rstrip())}")
            
    except Exception as e:
        print(f"Error: {e}")
        
if __name__ == "__main__":
    file_path = 'ipfs_kit_py/ai_ml_integration.py'
    check_indentation(file_path)