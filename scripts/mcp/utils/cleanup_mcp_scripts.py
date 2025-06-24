#!/usr/bin/env python3
"""
Cleanup script for redundant MCP server scripts.

This script renames redundant MCP server scripts to .bak files and adds a comment
at the top of each file pointing to the unified replacement.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Define the root directory
ROOT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# List of scripts to back up (these are now redundant)
REDUNDANT_SCRIPTS = [
    "run_mcp_server.py",
    "run_mcp_server_all_backends_fixed.py",
    "run_mcp_server_anyio_fixed.py",
    "run_mcp_server_anyio.py",
    "run_mcp_server_complete.py",
    "run_mcp_server_fixed.py",
    "run_mcp_server_real_apis.py",
    "run_mcp_server_real.py",
    "run_mcp_server_with_storage.py",
    "run_mcp_server_with_watcher.py",
]

# Scripts to leave alone (test-specific or might be imported)
PRESERVE_SCRIPTS = [
    "run_mcp_server_for_tests.py",  # Test-specific
    "ipfs_kit_py/run_mcp_server_real_storage.py",  # Inside package
]

def backup_script(script_path):
    """
    Backup a script by:
    1. Reading its content
    2. Creating a new version with a header comment
    3. Renaming the original to .bak
    """
    path = ROOT_DIR / script_path
    if not path.exists():
        print(f"Skipping {script_path} - file not found")
        return False

    # Read the original content
    with open(path, 'r') as f:
        content = f.read()

    # Create a backup with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_suffix(f".py.bak_{timestamp}")
    shutil.copy2(path, backup_path)
    print(f"Created backup: {backup_path}")

    # Create a new version with a header comment
    header = f'''#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by run_mcp_server_unified.py

This file is kept for reference only. Please use the unified script instead,
which provides all functionality with more options:

    python run_mcp_server_unified.py --help

Backup of the original script is at: {os.path.basename(backup_path)}
"""

# Original content follows:

'''

    with open(path, 'w') as f:
        f.write(header + content)

    print(f"Updated {script_path} with deprecation notice")
    return True

def main():
    """Main function to back up redundant scripts."""
    print("Backing up redundant MCP server scripts...")

    success_count = 0
    for script in REDUNDANT_SCRIPTS:
        if backup_script(script):
            success_count += 1

    print(f"\nBackup complete. Processed {success_count} of {len(REDUNDANT_SCRIPTS)} scripts.")
    print(f"The following scripts were preserved (not modified):")
    for script in PRESERVE_SCRIPTS:
        print(f"  - {script}")

    print("\nTo restore any file, rename the .bak version back to .py")
    print("To clean up completely, you can delete the .bak files once you're confident")
    print("that the unified script is working correctly.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
