#!/usr/bin/env python3
"""
Fix all try blocks without corresponding except blocks in the controller file.
"""

import os
import re
import sys

def is_try_statement(line):
    """Check if a line is a 'try:' statement."""
    return re.match(r'^\s*try\s*:\s*$', line.strip())

def is_except_or_finally(line):
    """Check if a line is an 'except:' or 'finally:' statement."""
    return (re.match(r'^\s*except\s*.*:\s*$', line.strip()) or
            re.match(r'^\s*finally\s*:\s*$', line.strip()))

def find_matching_indentation(lines, start_idx, indentation):
    """Find the next line with matching or less indentation."""
    for i in range(start_idx, len(lines)):
        line = lines[i]
        if line.strip() and len(line) - len(line.lstrip()) <= indentation:
            return i
    return len(lines)

def add_except_blocks(file_path):
    """Find all try blocks without except blocks and add them."""
    with open(file_path, 'r') as f:
        lines = f.readlines()

    modifications = 0
    line_idx = 0

    while line_idx < len(lines):
        line = lines[line_idx]

        # Check if this is a try statement
        if is_try_statement(line):
            # Calculate indentation level
            indentation = len(line) - len(line.lstrip())

            # Look ahead to see if there's a matching except or finally
            next_idx = line_idx + 1
            has_except = False

            # Find the next line with the same or less indentation
            next_same_indent = find_matching_indentation(lines, next_idx, indentation)

            # Check all lines in the try block for an except statement
            for i in range(line_idx + 1, next_same_indent):
                if i < len(lines) and is_except_or_finally(lines[i]):
                    has_except = True
                    break

            # If no except/finally found, add one
            if not has_except and next_same_indent < len(lines):
                # Create a basic except block
                except_block = ' ' * indentation + 'except Exception as e:\n'
                except_block += ' ' * (indentation + 4) + 'logger.error(f"Error: {e}")\n'
                except_block += ' ' * (indentation + 4) + 'return {"success": False, "error": str(e), "error_type": type(e).__name__}\n'

                # Insert the except block before the next line with same indentation
                lines.insert(next_same_indent, except_block)

                print(f"Added missing except block after try statement at line {line_idx + 1}")
                modifications += 1

                # Adjust index to account for inserted lines
                line_idx = next_same_indent + 3
                continue

        line_idx += 1

    # Write back the modified file if changes were made
    if modifications > 0:
        with open(file_path, 'w') as f:
            f.writelines(lines)
        print(f"Fixed {modifications} try blocks")
    else:
        print("No missing except blocks found")

    return modifications

def main():
    """Main function."""
    controller_path = '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py'

    # Add missing except blocks
    modifications = add_except_blocks(controller_path)

    # Check syntax after modifications
    if modifications > 0:
        print("Verifying syntax...")
        exit_code = os.system(f"python3 -m py_compile {controller_path}")
        if exit_code == 0:
            print("Syntax verification successful")
            return 0
        else:
            print("Syntax verification failed")
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
