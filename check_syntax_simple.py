#!/usr/bin/env python3

"""
Simpler script to check for syntax errors in high_level_api.py
"""

import os
import sys

try:
    with open('ipfs_kit_py/high_level_api.py', 'r') as f:
        source = f.read()
    
    # Try to compile the source code
    compile(source, 'high_level_api.py', 'exec')
    print('Compilation successful!')
    
except SyntaxError as e:
    print(f'Syntax error at line {e.lineno}: {e.msg}')
    # Get several lines of context
    try:
        with open('ipfs_kit_py/high_level_api.py', 'r') as f:
            lines = f.readlines()
            start = max(0, e.lineno - 3)
            end = min(len(lines), e.lineno + 3)
            print(f'\nContext around line {e.lineno}:')
            for i in range(start, end):
                prefix = '*' if i+1 == e.lineno else ' '
                print(f"{prefix} {i+1}: {lines[i].rstrip()}")
    except Exception as ex:
        print(f"Error getting context: {ex}")
        
except Exception as e:
    print(f'Error: {e}')