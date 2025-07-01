#!/usr/bin/env python3
"""
Script to fix common issues identified by Ruff in the ipfs_kit_py/mcp directory.
"""

import os
import re
import sys
from pathlib import Path

def fix_unused_imports(file_path, content):
    """Remove unused imports identified by F401."""
    # Pattern to match lines marked with F401
    lines = content.split("\n")
    new_lines = []
    skip_next = False

    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue

        # Skip lines that are marked as unused imports
        if i < len(lines) - 1 and "F401" in lines[i+1] and not line.strip().startswith("#"):
            # Check if this is part of a multi-line import with parentheses
            if "(" in line and ")" not in line:
                in_multiline = True
                # Find the closing parenthesis
                j = i + 1
                while j < len(lines) and ")" not in lines[j]:
                    j += 1
                if j < len(lines):
                    # Skip all lines in this import statement
                    skip_next = True
                    continue
            else:
                # Skip this line
                continue

        new_lines.append(line)

    return "\n".join(new_lines)

def fix_bare_except(file_path, content):
    """Replace bare except statements with 'except Exception:'."""
    return re.sub(r'except\s*:', 'except Exception:', content)

def fix_undefined_names(file_path, content):
    """Add imports for common undefined names."""
    fixes = {
        "traceback": "import traceback",
        "uuid": "import uuid",
        "asyncio": "import asyncio",
        "os": "import os",
        "aiofiles": "import aiofiles",
        "time": "import time",
    }

    lines = content.split("\n")
    for name, import_stmt in fixes.items():
        if f"F821 Undefined name `{name}`" in content and import_stmt not in content:
            # Find the right position to add the import
            # Try to add it after other imports
            import_pos = 0
            in_import_block = False
            for i, line in enumerate(lines):
                if line.startswith(("import ", "from ")) and not line.startswith("import sys"):
                    in_import_block = True
                    import_pos = i + 1
                elif in_import_block and not line.strip().startswith(("import ", "from ", "#")):
                    if line.strip():  # If not an empty line
                        break
                    import_pos = i

            lines.insert(import_pos, import_stmt)

    return "\n".join(lines)

def fix_ambiguous_names(file_path, content):
    """Replace ambiguous variable names like 'l' with more descriptive names."""
    if "enhanced_ipfs.py" in str(file_path) and "E741 Ambiguous variable name: `l`" in content:
        return content.replace("l: bool = Query(", "long_format: bool = Query(")
    return content

def process_file(file_path):
    """Process a single Python file to fix issues."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Apply fixes
        content = fix_unused_imports(file_path, content)
        content = fix_bare_except(file_path, content)
        content = fix_undefined_names(file_path, content)
        content = fix_ambiguous_names(file_path, content)

        # Write the fixed content back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"Fixed {file_path}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main(directory):
    """Process all Python files in a directory recursively."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                process_file(Path(root) / file)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
    else:
        target_dir = "ipfs_kit_py/mcp"

    main(target_dir)
