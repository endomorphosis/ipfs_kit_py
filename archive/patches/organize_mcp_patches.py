#!/usr/bin/env python3
"""
Organize MCP patches by moving them from the root patches directory to the patches/mcp directory.
"""

import os
import shutil
import sys
from pathlib import Path

def organize_mcp_patches():
    """Move MCP-related patch files to the patches/mcp directory."""
    # Ensure we're in the project root
    script_dir = Path(__file__).resolve().parent
    
    # Define paths
    patches_dir = script_dir
    mcp_patches_dir = script_dir / "mcp"
    
    # Create the MCP patches directory if it doesn't exist
    os.makedirs(mcp_patches_dir, exist_ok=True)
    
    # Find all MCP-related patch files in the root patches directory
    mcp_patch_files = []
    for filename in os.listdir(patches_dir):
        if filename.endswith(".py") and "mcp" in filename.lower() and os.path.isfile(os.path.join(patches_dir, filename)):
            # Skip the current script and files already in the mcp directory
            if filename != "organize_mcp_patches.py" and filename != "organize_patches.py":
                mcp_patch_files.append(filename)
    
    # Move the files to the MCP patches directory
    for filename in mcp_patch_files:
        src_path = os.path.join(patches_dir, filename)
        dst_path = os.path.join(mcp_patches_dir, filename)
        
        # Check if destination file already exists
        if os.path.exists(dst_path):
            print(f"Warning: File {dst_path} already exists. Skipping.")
            continue
        
        try:
            shutil.move(src_path, dst_path)
            # Make the file executable
            os.chmod(dst_path, 0o755)
            print(f"Moved {filename} to patches/mcp/")
        except Exception as e:
            print(f"Error moving {filename}: {e}")
    
    print(f"Moved {len(mcp_patch_files)} MCP patch files to patches/mcp/")

if __name__ == "__main__":
    organize_mcp_patches()