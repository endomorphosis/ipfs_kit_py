#!/usr/bin/env python3

"""
Simpler script to check for syntax errors in ai_ml_integration.py
"""

import os
import sys

filename = 'ipfs_kit_py/ai_ml_integration.py'

try:
    with open(filename, 'r') as f:
        source = f.read()
    
    # Try to compile the source code
    compile(source, filename, 'exec')
    print('Compilation successful!')
    
except SyntaxError as e:
    print(f'Syntax error at line {e.lineno}: {e.msg}')
    # Get several lines of context
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
            start = max(0, e.lineno - 5)
            end = min(len(lines), e.lineno + 5)
            print(f'\nContext around line {e.lineno}:')
            for i in range(start, end):
                prefix = '*' if i+1 == e.lineno else ' '
                print(f"{prefix} {i+1}: {lines[i].rstrip()}")
    except Exception as ex:
        print(f"Error getting context: {ex}")
        
except Exception as e:
    print(f'Error: {e}')