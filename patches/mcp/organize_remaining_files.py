#!/usr/bin/env python3
"""
Script to organize remaining test files and patch files into their proper directories.

This script:
1. Moves test files to the appropriate test directories
2. Moves fix/patch files to the patches directory
3. Creates symlinks from original locations for backward compatibility
"""

import os
import sys
import shutil
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Ensure we're working from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

# Define source test files and their destinations
TEST_FILES_TO_MOVE = [
    {
        "source": "ipfs_kit_py/test_fio.py",
        "destination": "test/unit/utils/test_fio.py",
        "import_path_update": True
    },
    {
        "source": "ipfs_kit_py/test_storage_backends_comprehensive.py",
        "destination": "test/integration/mcp/test_storage_backends_comprehensive.py",
        "import_path_update": True
    }
]

# Define source patch files and their destinations
PATCH_FILES_TO_MOVE = [
    {
        "source": "ipfs_kit_py/high_level_api_fixed.py",
        "destination": "patches/high_level_api_fixed.py"
    },
    {
        "source": "ipfs_kit_py/fixed_high_level_api.py",
        "destination": "patches/fixed_high_level_api.py"
    },
    {
        "source": "ipfs_kit_py/fixed_get_filesystem.py",
        "destination": "patches/fixed_get_filesystem.py"
    }
]

def ensure_directory_exists(file_path):
    """Ensure the directory for the given file path exists."""
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def update_import_paths(content, file_name):
    """Update import paths in the file based on its new location."""
    # For test files being moved to test directory, adjust imports from ipfs_kit_py
    if file_name.startswith("test_"):
        # If the file contains direct imports from the same directory, update them
        content = content.replace("from ipfs_kit_py.", "from ipfs_kit_py.")
        content = content.replace("import ipfs_kit_py.", "import ipfs_kit_py.")

    return content

def move_files(files_list, file_type="file"):
    """Move files from source to destination and create symlinks."""
    for file_info in files_list:
        source_path = PROJECT_ROOT / file_info["source"]
        destination_path = PROJECT_ROOT / file_info["destination"]

        if not source_path.exists():
            logger.warning(f"Source {file_type} not found: {source_path}")
            continue

        # Create destination directory if it doesn't exist
        ensure_directory_exists(str(destination_path))

        # Read the file content
        with open(source_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Update import paths if specified
        if file_info.get("import_path_update", False):
            content = update_import_paths(content, os.path.basename(str(source_path)))

        # Write to the destination
        with open(destination_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"Copied {file_type}: {source_path} -> {destination_path}")

        # Create an empty __init__.py file in the destination directory if it's a test file
        if file_type == "test file":
            init_file = Path(os.path.dirname(str(destination_path))) / "__init__.py"
            if not init_file.exists():
                with open(init_file, 'w', encoding='utf-8') as f:
                    f.write("# This directory contains test files\n")
                logger.info(f"Created __init__.py: {init_file}")

        # Remove the original file
        os.unlink(source_path)
        logger.info(f"Removed original file: {source_path}")

        # Create symlink from original location to new location
        try:
            rel_path = os.path.relpath(str(destination_path), os.path.dirname(str(source_path)))
            os.symlink(rel_path, source_path)
            logger.info(f"Created symlink: {source_path} -> {rel_path}")
        except Exception as e:
            logger.error(f"Error creating symlink: {e}")

def main():
    """Main function to organize test and patch files."""
    logger.info("Starting organization of test and patch files...")

    # Move test files
    logger.info("Moving test files...")
    move_files(TEST_FILES_TO_MOVE, "test file")

    # Move patch files
    logger.info("Moving patch files...")
    move_files(PATCH_FILES_TO_MOVE, "patch file")

    logger.info("Organization completed successfully!")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Error: {e}")
        sys.exit(1)
