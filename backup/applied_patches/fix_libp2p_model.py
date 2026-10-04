#!/usr/bin/env python3
"""
Fixes all syntax errors in libp2p_model.py including:
1. Extra closing parentheses after anyio.to_thread.run_sync()
2. Problems with incorrect parameters in methods
3. Missing closing parentheses in lambda expressions
4. Generic fixes for unclosed parentheses before function definitions
"""

import re
import py_compile

# Path to the file
file_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/models/libp2p_model.py'

# Read the file
with open(file_path, 'r') as file:
    content = file.read()

# First fix: Extra closing parentheses after anyio.to_thread.run_sync()
pattern1 = r'return await anyio\.to_thread\.run_sync\(([^)]+)\)\)'
fixed_content = re.sub(pattern1, r'return await anyio.to_thread.run_sync(\1)', content)

# Second fix: Incorrect parameter list in pubsub_publish
pattern2 = r'return LibP2PModel\.pubsub_publish\(self, topic, message, bytes, Dict\[str, Any\]\]'
fixed_content = re.sub(pattern2, r'return LibP2PModel.pubsub_publish(self, topic, message)', fixed_content)

# Third fix: Any other instances of lambda functions with extra commas
pattern3 = r'lambda: self\.[a-zA-Z_]+\(,\s*[a-zA-Z_][^)]*\)'
def fix_lambda_expression(match):
    """Fix lambda expressions with extra commas."""
    full_match = match.group(0)
    corrected = full_match.replace('(,', '(')
    return corrected
fixed_content = re.sub(pattern3, fix_lambda_expression, fixed_content)

# Fourth fix: Missing closing parenthesis in lambda _is_available_sync
pattern4 = r'return await anyio\.to_thread\.run_sync\(lambda: self\._is_available_sync\(\)'
fixed_content = re.sub(pattern4, r'return await anyio.to_thread.run_sync(lambda: self._is_available_sync())', fixed_content)

# Fifth fix: Missing closing parenthesis in get_connected_peers lambda
pattern5 = r'return await anyio\.to_thread\.run_sync\(lambda: self\.get_connected_peers\(\)'
fixed_content = re.sub(pattern5, r'return await anyio.to_thread.run_sync(lambda: self.get_connected_peers())', fixed_content)

# Sixth fix: Generic fix for unclosed parentheses at end of functions before next function def
pattern6 = r'(return await anyio\.to_thread\.run_sync.*?\([^)]*)\n\s*\n\s*def'
fixed_content = re.sub(pattern6, r'\1))\n\n    def', fixed_content)

# Seventh fix: Generic fix for unclosed parentheses at end of functions before empty lines
pattern7 = r'(return await anyio\.to_thread\.run_sync.*?\([^)]*)\n\s*\n\s*'
fixed_content = re.sub(pattern7, r'\1))\n\n    ', fixed_content)

# Write the fixed content back to the file
with open(file_path, 'w') as file:
    file.write(fixed_content)

print("Fixed potentially problematic syntax in libp2p_model.py.")

# Verify the fix
try:
    py_compile.compile(file_path)
    print("Compilation successful! The file is now syntactically correct.")
except py_compile.PyCompileError as e:
    print(f"Compilation error: {e}")
    print("Some syntax errors might still exist. Please check manually.")
