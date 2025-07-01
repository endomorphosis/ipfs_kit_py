#!/usr/bin/env python3
"""
Fix any syntax errors in the ipfs_controller.py file.
This script reads the file, attempts to compile it to check for syntax errors,
and then fixes any issues it finds.
"""

import os
import sys
import re
import ast

def check_syntax(file_path):
    """Check a file for syntax errors."""
    print(f"Checking syntax of {file_path}")

    try:
        with open(file_path, 'r') as f:
            source = f.read()

        # Try to compile the source code to check for syntax errors
        ast.parse(source)
        print("No syntax errors found")
        return True, None
    except SyntaxError as e:
        print(f"Syntax error at line {e.lineno}, column {e.offset}: {e.msg}")
        return False, e

def fix_try_except_block(file_path, error_line):
    """Fix a try block that's missing an except or finally clause."""
    with open(file_path, 'r') as f:
        lines = f.readlines()

    # Find the try block at the error line
    if error_line > len(lines):
        print(f"Error line {error_line} is beyond the file length")
        return False

    # Start searching from the error line backwards to find the matching 'try:'
    line_idx = error_line - 1  # Convert to 0-indexed
    open_blocks = 0
    try_line = None

    # Loop backwards until we find the try statement that's missing the except/finally
    while line_idx >= 0:
        line = lines[line_idx]

        # Count indentation level by spaces (assuming 4 spaces per level)
        indent = len(line) - len(line.lstrip())

        # Check for block endings
        if re.match(r'^\s*\)\s*:\s*$', line):  # End of a complex condition block
            open_blocks += 1
        elif re.match(r'^\s*\S+.*:\s*$', line) and not line.strip().startswith('#'):  # Start of a new block
            if open_blocks > 0:
                open_blocks -= 1
            else:
                # This might be the try statement
                if re.match(r'^\s*try\s*:\s*$', line):
                    try_line = line_idx
                    break

        line_idx -= 1

    if try_line is None:
        print("Could not find the matching 'try:' statement")
        return False

    # Now we need to find where to insert the 'except' block
    # Go forward from the try line to find the end of the try block
    try_indent = len(lines[try_line]) - len(lines[try_line].lstrip())
    line_idx = try_line + 1
    while line_idx < len(lines):
        line = lines[line_idx]
        if line.strip() and len(line) - len(line.lstrip()) <= try_indent:
            # This line has the same or less indentation as the try block
            # so it's the end of the try block
            break
        line_idx += 1

    # Insert a basic except block at this position
    except_block = ' ' * try_indent + 'except Exception as e:\n'
    except_block += ' ' * (try_indent + 4) + 'logger.error(f"Error: {e}")\n'
    except_block += ' ' * (try_indent + 4) + 'return {"success": False, "error": str(e)}\n'

    lines.insert(line_idx, except_block)

    # Write back the fixed file
    with open(file_path, 'w') as f:
        f.writelines(lines)

    print(f"Fixed try-except block at line {try_line + 1}")
    return True

def main():
    """Main function."""
    controller_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py'

    # Check for syntax errors
    syntax_ok, error = check_syntax(controller_path)
    if syntax_ok:
        print("No syntax errors to fix")
        return 0

    # Fix the error if it's a missing except/finally block
    if error.msg == "expected 'except' or 'finally' block":
        if fix_try_except_block(controller_path, error.lineno):
            print("Fixed syntax error, checking again...")
            # Check if fix was successful
            syntax_ok, new_error = check_syntax(controller_path)
            if syntax_ok:
                print("All syntax errors fixed successfully")
                return 0
            else:
                print(f"New syntax error after fix: {new_error}")
                return 1
    else:
        print(f"Unhandled syntax error: {error.msg}")
        return 1

    return 1

if __name__ == "__main__":
    sys.exit(main())
