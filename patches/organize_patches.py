#!/usr/bin/env python3
"""
Script to organize patches into proper folders.

This script ensures that all MCP-related patches are placed in the patches/mcp directory,
while other patches remain in the main patches directory.
"""

import os
import shutil
from pathlib import Path
import sys
import re

# Ensure we're working from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

# Define source and destination directories
PATCHES_DIR = Path("patches")
MCP_PATCHES_DIR = PATCHES_DIR / "mcp"

# Make sure the MCP patches directory exists
os.makedirs(MCP_PATCHES_DIR, exist_ok=True)

def is_mcp_patch(filename):
    """Determine if a file is an MCP-related patch."""
    mcp_patterns = [
        r'mcp',
        r'libp2p',
        r'storage_backends',
        r'ipfs_controller'
    ]

    for pattern in mcp_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            return True
    return False

def organize_patches():
    """Move MCP-related patches to the MCP patches directory."""
    print("Starting patch organization...")

    # Keep track of files moved
    moved_files = []

    # Find all Python patch files in the main patches directory
    patch_files = list(PATCHES_DIR.glob("*.py"))

    for patch_file in patch_files:
        filename = patch_file.name

        # Skip already processed files or files in subdirectories
        if patch_file.parent != PATCHES_DIR:
            continue

        # If this is an MCP patch, move it to the MCP patches directory
        if is_mcp_patch(filename):
            dest_file = MCP_PATCHES_DIR / filename

            # Don't overwrite newer files
            if dest_file.exists() and dest_file.stat().st_mtime > patch_file.stat().st_mtime:
                print(f"Skipping {filename} as destination file is newer")
                continue

            # Copy the file to avoid issues with git tracking
            shutil.copy2(patch_file, dest_file)
            print(f"Copied {filename} to {MCP_PATCHES_DIR}")
            moved_files.append((patch_file, dest_file))

    print(f"Organization complete. Moved {len(moved_files)} patch files.")
    return moved_files

if __name__ == "__main__":
    # Execute the organization
    try:
        moved_files = organize_patches()
        print("Patch organization successful!")

        # Ask if original files should be removed
        if moved_files and input("Do you want to remove the original patch files? (y/n): ").lower() == 'y':
            for original, _ in moved_files:
                if original.exists():
                    original.unlink()
                    print(f"Removed original file: {original}")

    except Exception as e:
        print(f"Error during organization: {e}")
        sys.exit(1)
