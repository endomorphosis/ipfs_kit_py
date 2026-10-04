#!/usr/bin/env python3
"""
Fix for syntax error in libp2p_model.py

This patch fixes the syntax error found in the libp2p_model.py files
that's preventing the MCP server from starting properly.
"""

import os
import sys
from pathlib import Path

# Ensure we're working from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

# Paths to the files with the error
LIBP2P_MODEL_PATHS = [
    PROJECT_ROOT / "ipfs_kit_py" / "mcp" / "models" / "libp2p_model.py",
    PROJECT_ROOT / "ipfs_kit_py" / "mcp_server" / "models" / "libp2p_model.py"
]

def fix_syntax_error():
    """Fix the syntax error in libp2p_model.py files."""
    fixed_files = 0

    for model_path in LIBP2P_MODEL_PATHS:
        print(f"Checking file: {model_path}")

        if not model_path.exists():
            print(f"Skipping: {model_path} does not exist!")
            continue

        # Read the file content
        with open(model_path, 'r') as f:
            content = f.read()

        # Check for lines with incorrect docstring indentation
        lines = content.splitlines()
        fixed_content = []
        fixed = False
        fixed_lines = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for docstring lines
            if line.strip().startswith('"""') and i+1 < len(lines):
                # Add the current line
                fixed_content.append(line)

                # Check if next line has the issue (empty with just a dash)
                next_line = lines[i+1]
                indent_level = len(line) - len(line.lstrip())

                if next_line.strip() == '-':
                    # This is a problematic line - replace with proper docstring
                    method_name = None
                    for j in range(i-1, max(0, i-10), -1):
                        if "def " in lines[j]:
                            method_name = lines[j].split("def ")[1].split("(")[0].strip()
                            break

                    proper_docstring = " " * indent_level + "Async version of "
                    if method_name:
                        proper_docstring += f"{method_name} for use with async controllers."
                    else:
                        proper_docstring += "method for use with async controllers."

                    fixed_content.append(proper_docstring)
                    fixed = True
                    fixed_lines += 1
                    i += 1  # Skip the bad line
                    print(f"  Fixed docstring at line {i+1}")
                else:
                    fixed_content.append(next_line)
                    i += 1
            else:
                fixed_content.append(line)

            i += 1

        # Only write if we made changes
        if fixed:
            # Create backup
            backup_path = str(model_path) + ".bak"
            with open(backup_path, 'w') as f:
                f.write(content)
            print(f"  Created backup at {backup_path}")

            # Write fixed content
            with open(model_path, 'w') as f:
                f.write("\n".join(fixed_content))

            print(f"  Successfully fixed {fixed_lines} syntax errors in {model_path}")
            fixed_files += 1
        else:
            print(f"  No syntax errors found in {model_path}")

    return fixed_files > 0

if __name__ == "__main__":
    if fix_syntax_error():
        print("Patch applied successfully!")
        sys.exit(0)
    else:
        print("No files were fixed (either no errors found or files don't exist)")
        sys.exit(1)
