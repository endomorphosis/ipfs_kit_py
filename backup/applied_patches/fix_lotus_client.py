#!/usr/bin/env python3
"""
Fix indentation errors in lotus_kit.py file.

This script identifies and fixes indentation errors in the lotus_kit.py file,
specifically in the client_retrieve_legacy method where incorrectly indented
code was causing syntax errors.
"""

import os
import re
import shutil
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("fix_lotus_client")

def fix_lotus_client():
    """Fix indentation issues in lotus_kit.py file."""
    file_path = "ipfs_kit_py/lotus_kit.py"
    backup_path = "ipfs_kit_py/lotus_kit.py.bak"

    logger.info(f"Creating backup of original file: {backup_path}")
    shutil.copy2(file_path, backup_path)

    with open(file_path, "r") as f:
        content = f.read()

    # Find the problematic method
    method_pattern = re.compile(
        r"def client_retrieve_legacy\(self, data_cid, out_file, \*\*kwargs\):(.*?)def",
        re.DOTALL
    )

    match = method_pattern.search(content)
    if not match:
        logger.error("Could not find client_retrieve_legacy method")
        return False

    # Extract method body
    method_body = match.group(1)

    # Create fixed method body
    fixed_method = """    def client_retrieve_legacy(self, data_cid, out_file, **kwargs):
        \"\"\"Legacy retrieve data method - use client_retrieve instead.

        Args:
            data_cid (str): The CID of the data to retrieve.
            out_file (str): The path to save the retrieved data.
            **kwargs: Additional parameters:
                - correlation_id (str): ID for tracking operations

        Returns:
            dict: Result dictionary with retrieval status.
        \"\"\"
        # Forward to the main implementation
        return self.client_retrieve(data_cid, out_file, **kwargs)

    def"""

    # Replace the method in the content
    fixed_content = content.replace(match.group(0), fixed_method)

    # Write the fixed content
    with open(file_path, "w") as f:
        f.write(fixed_content)

    logger.info(f"Fixed client_retrieve_legacy method in {file_path}")
    return True

if __name__ == "__main__":
    success = fix_lotus_client()
    if success:
        logger.info("Successfully fixed lotus_kit.py")
    else:
        logger.error("Failed to fix lotus_kit.py")
