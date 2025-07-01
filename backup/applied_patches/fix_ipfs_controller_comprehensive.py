#!/usr/bin/env python3
"""
Comprehensive fix for the IPFS controller syntax errors.
"""

import os
import re
import sys

def fix_controller_file():
    """Apply a comprehensive fix to the IPFS controller file."""
    file_path = "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/controllers/ipfs_controller.py"

    # Create a backup of the original file
    backup_path = f"{file_path}.bak_comprehensive_fix"
    os.system(f"cp {file_path} {backup_path}")
    print(f"Created backup at {backup_path}")

    # Read the original content
    with open(file_path, 'r') as f:
        content = f.read()

    # Fix common indent issues
    content = re.sub(r'else:\s+#\s*Standard IPFS daemon check\s+#\s*Handle daemon type specific checks',
                    'else:\n                    # Standard IPFS daemon check\n                    result = self.ipfs_model.check_daemon_status(daemon_type)',
                    content)

    # Fix any incomplete try-except blocks
    content = re.sub(r'try:\s+([^\n]+)\s+(?!except|finally)',
                    r'try:\n                    \1\n                except Exception as e:\n                    logger.error(f"Error: {e}")\n                    return {"success": False, "error": str(e)}',
                    content)

    # Write the fixed content back to the file
    with open(file_path, 'w') as f:
        f.write(content)

    # Additional specific fixes for issues that regex might miss
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        # Find and fix any specific issues we know about
        for i in range(len(lines)):
            if i+1 < len(lines) and "else:" in lines[i] and "# Standard" in lines[i+1] and not "result" in lines[i+1]:
                # We found an else block without proper content
                indent = len(lines[i]) - len(lines[i].lstrip())
                indent_str = " " * (indent + 4)
                lines.insert(i+2, indent_str + "result = self.ipfs_model.check_daemon_status(daemon_type)\n")
                print(f"Fixed specific else block issue at line {i+1}")

        # Write fixed lines back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"Error during specific fixes: {e}")

    # Try to validate the syntax
    try:
        import ast
        with open(file_path, 'r') as f:
            file_content = f.read()
        ast.parse(file_content)
        print("Syntax validation successful!")
        return True
    except SyntaxError as e:
        print(f"Syntax error remains: {e}")
        # Get context around the error
        line_num = e.lineno
        with open(file_path, 'r') as f:
            lines = f.readlines()
        start = max(0, line_num - 5)
        end = min(len(lines), line_num + 5)
        print("Context around error:")
        for i in range(start, end):
            print(f"{i+1}: {lines[i].rstrip()}")
        return False

if __name__ == "__main__":
    success = fix_controller_file()
    sys.exit(0 if success else 1)
