#!/usr/bin/env python3
"""
Script to migrate MCP test scripts to the appropriate test directories.

This script:
1. Identifies MCP-related test scripts in the root directory
2. Determines the appropriate test directory based on the script's purpose
3. Creates a properly named test file in the test directory
4. Adds a comment in the new file pointing to the original script
"""

import os
import sys
import shutil
import re

# Define test directories
TEST_DIR = "./test"
MCP_TEST_DIR = os.path.join(TEST_DIR, "mcp")
NETWORK_TEST_DIR = os.path.join(MCP_TEST_DIR, "network_tests")
SERVER_TEST_DIR = os.path.join(MCP_TEST_DIR, "server_tests")

# Mapping of script purposes to test directories
PURPOSE_DIRS = {
    "network": NETWORK_TEST_DIR,
    "server": SERVER_TEST_DIR,
    "general": MCP_TEST_DIR,
}

# Scripts to migrate
SCRIPTS_TO_MIGRATE = [
    # Network test scripts
    {
        "src": "run_mcp_asymmetric_partition_test.py",
        "dest": "test_mcp_asymmetric_partition.py",
        "purpose": "network"
    },
    {
        "src": "run_mcp_communication_test.py",
        "dest": "test_mcp_communication_runner.py",
        "purpose": "network"
    },
    {
        "src": "run_mcp_intermittent_connectivity_test.py",
        "dest": "test_mcp_intermittent_connectivity.py",
        "purpose": "network"
    },
    {
        "src": "run_mcp_network_tests.py",
        "dest": "test_mcp_network_runner.py",
        "purpose": "network"
    },
    {
        "src": "run_mcp_partial_partition_test.py",
        "dest": "test_mcp_partial_partition.py",
        "purpose": "network"
    },
    {
        "src": "run_mcp_partition_test.py",
        "dest": "test_mcp_partition.py",
        "purpose": "network"
    },
    {
        "src": "run_mcp_time_based_recovery_test.py",
        "dest": "test_mcp_time_based_recovery.py",
        "purpose": "network"
    },

    # Server test scripts
    {
        "src": "run_mcp_server_for_tests.py",
        "dest": "test_mcp_server_runner.py",
        "purpose": "server"
    },
    {
        "src": "run_mcp_server_real_apis.py",
        "dest": "test_mcp_server_real_apis.py",
        "purpose": "server"
    },
    {
        "src": "run_mcp_server_with_watcher.py",
        "dest": "test_mcp_server_with_watcher.py",
        "purpose": "server"
    },
    {
        "src": "run_mcp_simulation_server.py",
        "dest": "test_mcp_simulation_server.py",
        "purpose": "server"
    },

    # General test scripts
    {
        "src": "run_mcp_tests.py",
        "dest": "test_mcp_runner.py",
        "purpose": "general"
    },
    {
        "src": "run_mcp_tests.sh",
        "dest": "test_mcp_runner.sh",
        "purpose": "general"
    },
    {
        "src": "test_discovery/run_mcp_cascading_failures_test.py",
        "dest": "test_mcp_cascading_failures.py",
        "purpose": "network"
    }
]

def ensure_directory_exists(directory):
    """Ensure the specified directory exists."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")

def migrate_script(script_info):
    """Migrate a script to the appropriate test directory."""
    src_path = script_info["src"]
    purpose = script_info["purpose"]

    # Determine destination directory and full path
    dest_dir = PURPOSE_DIRS.get(purpose, MCP_TEST_DIR)
    dest_filename = script_info["dest"]
    dest_path = os.path.join(dest_dir, dest_filename)

    # Skip if source file doesn't exist
    if not os.path.exists(src_path):
        print(f"Warning: Source file not found: {src_path}")
        return False

    # Skip if destination file already exists
    if os.path.exists(dest_path):
        print(f"Warning: Destination file already exists: {dest_path}")
        return False

    # Read source file
    with open(src_path, 'r') as f:
        content = f.read()

    # Create redirection header
    header = f"""#!/usr/bin/env python3
\"\"\"
This test script is the properly named version of the original:
{src_path}

It has been moved to the appropriate test directory for better organization.
\"\"\"

# Original content follows:

"""

    # Write to destination file
    with open(dest_path, 'w') as f:
        f.write(header + content)

    print(f"Created test file: {dest_path}")
    return True

def main():
    """Main function to migrate all scripts."""
    print("Starting MCP test scripts migration...")

    # Ensure test directories exist
    for directory in [TEST_DIR, MCP_TEST_DIR, NETWORK_TEST_DIR, SERVER_TEST_DIR]:
        ensure_directory_exists(directory)

    # Migrate each script
    migrated_count = 0
    skipped_count = 0

    for script_info in SCRIPTS_TO_MIGRATE:
        if migrate_script(script_info):
            migrated_count += 1
        else:
            skipped_count += 1

    print(f"\nMigration complete: {migrated_count} scripts migrated, {skipped_count} skipped")

    # Suggestion for next steps
    print("\nNext steps:")
    print("1. Verify the migrated scripts work correctly")
    print("2. Optionally remove the original scripts if they are no longer needed")

    return 0

if __name__ == "__main__":
    sys.exit(main())
