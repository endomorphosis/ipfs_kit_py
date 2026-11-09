#!/usr/bin/env python3
"""
Script to migrate MCP tests to their proper locations in the test directory.

This script ensures that all MCP-related tests are organized in the proper
structure with controller tests, model tests, and server tests in their
respective directories.
"""

import os
import shutil
import sys
from pathlib import Path
import re

# Ensure we're working from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
os.chdir(PROJECT_ROOT)

# Define source and destination directories
SOURCE_DIRS = [
    Path("test/mcp"),
    Path("ipfs_kit_py/tests"),
    Path("ipfs_kit_py/mcp/tests")
]

# Define destination structure
TEST_ROOT = Path("test")
MCP_TEST_DIR = TEST_ROOT / "mcp"
CONTROLLER_TEST_DIR = MCP_TEST_DIR / "controller"
MODEL_TEST_DIR = MCP_TEST_DIR / "model"
SERVER_TEST_DIR = MCP_TEST_DIR / "server"
UNIT_TEST_DIR = TEST_ROOT / "unit" / "mcp"
INTEGRATION_TEST_DIR = TEST_ROOT / "integration" / "mcp"

# Create destination directories if they don't exist
DIRS_TO_CREATE = [
    MCP_TEST_DIR,
    CONTROLLER_TEST_DIR,
    MODEL_TEST_DIR, 
    SERVER_TEST_DIR,
    UNIT_TEST_DIR,
    INTEGRATION_TEST_DIR
]

for dir_path in DIRS_TO_CREATE:
    os.makedirs(dir_path, exist_ok=True)
    # Create __init__.py files if they don't exist
    init_file = dir_path / "__init__.py"
    if not init_file.exists():
        with open(init_file, "w") as f:
            f.write("# Test directory for MCP components\n")

def is_controller_test(filename):
    """Determine if a file is a controller test."""
    controller_patterns = [
        r'controller', 
        r'test_mcp_aria2', 
        r'test_mcp_ipfs',
        r'test_mcp_libp2p',
        r'test_mcp_storage',
        r'test_mcp_filecoin',
        r'test_mcp_lassie',
        r'test_mcp_storacha',
        r'test_mcp_s3',
        r'test_mcp_peer',
        r'test_mcp_discovery',
        r'test_mcp_huggingface',
        r'test_mcp_webrtc'
    ]
    
    for pattern in controller_patterns:
        if re.search(pattern, filename):
            return True
    return False

def is_model_test(filename):
    """Determine if a file is a model test."""
    model_patterns = [
        r'model', 
        r'test_mcp_metadata', 
        r'test_mcp_dht_operations',
        r'test_mcp_ipns_operations',
        r'test_mcp_block_operations',
        r'test_mcp_dag_operations',
        r'test_mcp_files_operations',
    ]
    
    for pattern in model_patterns:
        if re.search(pattern, filename):
            return True
    return False

def is_server_test(filename):
    """Determine if a file is a server test."""
    server_patterns = [
        r'server',
        r'test_mcp_server_anyio',
        r'test_mcp_communication',
        r'test_mcp_component',
        r'test_mcp_shutdown',
        r'test_mcp_distributed',
        r'test_mcp_api',
        r'test_mcp_unified',
        r'test_mcp_endpoint',
    ]
    
    for pattern in server_patterns:
        if re.search(pattern, filename):
            return True
    return False

def is_integration_test(filename):
    """Determine if a file is an integration test."""
    integration_patterns = [
        r'integration',
        r'test_mcp_comprehensive',
        r'test_mcp_advanced',
        r'test_mcp_end_to_end',
        r'test_mcp_unified',
        r'test_mcp_features'
    ]
    
    for pattern in integration_patterns:
        if re.search(pattern, filename):
            return True
    return False

def update_imports(file_path):
    """Update imports in the file to reflect the new structure."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Update imports for the new structure
    content = content.replace('from ipfs_kit_py.mcp.', 'from ipfs_kit_py.mcp_server.')
    
    # Update imports for test fixtures
    content = content.replace('from test.mcp.', 'from test.mcp.')
    
    with open(file_path, 'w') as f:
        f.write(content)

def migrate_test_files():
    """Migrate test files to their appropriate directories."""
    print("Starting MCP test migration...")
    
    # Keep track of files moved
    moved_files = []
    
    # Process each source directory
    for source_dir in SOURCE_DIRS:
        if not source_dir.exists():
            print(f"Source directory {source_dir} does not exist, skipping...")
            continue
            
        # Find all Python test files
        test_files = list(source_dir.glob("test_mcp*.py"))
        
        for test_file in test_files:
            filename = test_file.name
            
            # Determine destination directory
            if is_controller_test(filename):
                dest_dir = CONTROLLER_TEST_DIR
            elif is_model_test(filename):
                dest_dir = MODEL_TEST_DIR
            elif is_server_test(filename):
                dest_dir = SERVER_TEST_DIR
            elif is_integration_test(filename):
                dest_dir = INTEGRATION_TEST_DIR
            else:
                dest_dir = UNIT_TEST_DIR
            
            # Copy the file to destination
            dest_file = dest_dir / filename
            
            # Don't overwrite newer files
            if dest_file.exists() and dest_file.stat().st_mtime > test_file.stat().st_mtime:
                print(f"Skipping {filename} as destination file is newer")
                continue
                
            shutil.copy2(test_file, dest_file)
            print(f"Copied {filename} to {dest_dir}")
            moved_files.append((test_file, dest_file))
            
            # Update imports in the copied file
            update_imports(dest_file)
    
    print(f"Migration complete. Moved {len(moved_files)} test files.")
    return moved_files

if __name__ == "__main__":
    # Execute the migration
    try:
        moved_files = migrate_test_files()
        print("Test migration successful!")
        
        # Ask if original files should be removed
        if moved_files and input("Do you want to remove the original test files? (y/n): ").lower() == 'y':
            for original, _ in moved_files:
                if original.exists():
                    original.unlink()
                    print(f"Removed original file: {original}")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)