#!/usr/bin/env python3
"""
Organize MCP tests by moving them from the root test/mcp directory to appropriate subdirectories.
"""

import os
import shutil
import sys
from pathlib import Path
import re

def categorize_test_file(filename):
    """Categorize a test file based on its name."""
    categories = {
        "controller": [
            "controller", "api", "endpoint", "credential", "ipfs_controller", 
            "libp2p_controller", "storage_manager_controller", "webrtc_controller",
            "lassie_controller", "s3_controller", "storacha_controller", 
            "huggingface_controller", "aria2_controller", "fs_journal_controller",
            "peer_websocket_controller", "filecoin_controller", "discovery_controller",
            "distributed_controller"
        ],
        "server": [
            "server", "daemon_management", "health", "shutdown", "blue_green", "runner"
        ],
        "model": [
            "model", "metadata", "storage_backends", "storage_manager", "filecoin_model"
        ],
        "network_tests": [
            "communication", "distributed", "peer_websocket", "webrtc_metadata", 
            "webrtc_buffer", "mfs_operations", "discovery", "prefetching"
        ],
        "libp2p": [
            "libp2p_integration", "libp2p_server", "libp2p_mcp"
        ],
        "integration": [
            "comprehensive", "features", "advanced", "dht_operations", "dag_operations",
            "block_operations", "ipns_operations", "normalized_ipfs", "tiered_cache",
            "fs_journal", "performance"
        ]
    }
    
    # Try to match the filename to a category
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in filename.lower():
                return category
    
    # If no specific category is found, put it in "integration"
    return "integration"

def organize_mcp_tests():
    """Move MCP test files to their appropriate subdirectories."""
    # Define paths
    test_dir = Path("/home/runner/work/ipfs_kit_py/ipfs_kit_py/test")
    mcp_test_dir = test_dir / "mcp"
    
    # Ensure all necessary subdirectories exist
    categories = ["controller", "server", "model", "network_tests", "libp2p", "integration"]
    for category in categories:
        os.makedirs(mcp_test_dir / category, exist_ok=True)
    
    # Find all test files in the root MCP test directory
    test_files = []
    for filename in os.listdir(mcp_test_dir):
        filepath = mcp_test_dir / filename
        if filename.endswith(".py") and os.path.isfile(filepath) and filename != "__init__.py":
            test_files.append(filename)
    
    # Move the files to their appropriate subdirectories
    moved_files = 0
    for filename in test_files:
        category = categorize_test_file(filename)
        src_path = mcp_test_dir / filename
        dst_dir = mcp_test_dir / category
        dst_path = dst_dir / filename
        
        # Check if destination file already exists
        if os.path.exists(dst_path):
            print(f"Warning: File {dst_path} already exists. Skipping.")
            continue
        
        try:
            # Create __init__.py in the destination directory if it doesn't exist
            init_file = dst_dir / "__init__.py"
            if not os.path.exists(init_file):
                with open(init_file, 'w') as f:
                    f.write("# Test module for MCP " + category)
            
            # Move the file
            shutil.move(src_path, dst_path)
            # Make the file executable if it was executable before
            if os.access(src_path, os.X_OK):
                os.chmod(dst_path, 0o755)
            
            print(f"Moved {filename} to test/mcp/{category}/")
            moved_files += 1
        except Exception as e:
            print(f"Error moving {filename}: {e}")
    
    print(f"Moved {moved_files} MCP test files to appropriate subdirectories.")

if __name__ == "__main__":
    organize_mcp_tests()