#!/usr/bin/env python3
"""Process Python files with Black and Ruff individually."""

import os
import sys
import subprocess
import shutil
from datetime import datetime

# Constants
MCP_DIR = "ipfs_kit_py/mcp"
BACKUP_DIR = f"mcp_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
LOG_DIR = "logs"
SUCCESS_LOG = f"{LOG_DIR}/formatted_files.log"
FAILED_LOG = f"{LOG_DIR}/failed_files.log"

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

def find_python_files():
    """Find all Python files in the directory."""
    python_files = []
    for root, _, files in os.walk(MCP_DIR):
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    return sorted(python_files)

def create_backup():
    """Create a backup of the directory."""
    print(f"Creating backup of {MCP_DIR} to {BACKUP_DIR}...")
    shutil.copytree(MCP_DIR, BACKUP_DIR)
    print(f"Backup created successfully.")

def process_file(file_path):
    """Process a single Python file with Black and Ruff."""
    print(f"Processing {file_path}...")

    # Attempt to format with Black
    black_result = subprocess.run(
        ["black", "--quiet", "--target-version", "py38", file_path],
        capture_output=True, text=True
    )

    # Attempt to fix with Ruff (even if Black failed)
    ruff_result = subprocess.run(
        ["ruff", "check", "--fix", "--ignore", "E999", file_path],
        capture_output=True, text=True
    )

    # Return success if either tool succeeded
    return black_result.returncode == 0 or ruff_result.returncode == 0, file_path

def main():
    """Main function to process files."""
    # Create backup first
    create_backup()

    # Find all Python files
    python_files = find_python_files()
    print(f"Found {len(python_files)} Python files to process.")

    # Process files and track results
    successful_files = []
    failed_files = []

    for file_path in python_files:
        success, path = process_file(file_path)
        if success:
            successful_files.append(path)
        else:
            failed_files.append(path)

    # Log results
    with open(SUCCESS_LOG, "w") as f:
        f.write("\n".join(successful_files))

    with open(FAILED_LOG, "w") as f:
        f.write("\n".join(failed_files))

    # Print summary
    print("\nResults:")
    print(f"- Successfully processed: {len(successful_files)} files")
    print(f"- Failed to process: {len(failed_files)} files")
    print(f"- Success rate: {len(successful_files)/len(python_files)*100:.1f}%")
    print(f"\nSuccessful files logged to: {SUCCESS_LOG}")
    print(f"Failed files logged to: {FAILED_LOG}")
    print(f"Original files backed up to: {BACKUP_DIR}")

if __name__ == "__main__":
    main()
