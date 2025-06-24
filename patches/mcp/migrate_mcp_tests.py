#!/usr/bin/env python3
"""
MCP Test Migration Script

This script identifies MCP-related tests and migrates them to the
appropriate test directory, ensuring proper organization:

1. Controller tests go to test/mcp/controller/
2. Model tests go to test/mcp/model/
3. LibP2P integration tests go to test/mcp/libp2p/
4. Server tests go to test/mcp/server/
5. General MCP tests go to test/mcp/

Run this script to organize all MCP-related tests.
"""

import os
import sys
import shutil
import logging
from pathlib import Path
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_test_migration")

# Root directory of the project
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Directories
MCP_DIR = PROJECT_ROOT / "ipfs_kit_py" / "mcp"
TEST_DIR = PROJECT_ROOT / "test"
MCP_TEST_DIR = TEST_DIR / "mcp"

def ensure_directory(directory):
    """Ensure the directory exists."""
    os.makedirs(directory, exist_ok=True)
    logger.info(f"Ensured directory exists: {directory}")

def find_mcp_tests():
    """Find all MCP-related test files in the project."""
    logger.info("Finding all MCP-related test files...")

    mcp_tests = []

    # Look in the main ipfs_kit_py module
    for root, _, files in os.walk(MCP_DIR):
        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                mcp_tests.append(os.path.join(root, file))

    # Look in the tests directory
    for root, _, files in os.walk(TEST_DIR):
        for file in files:
            if file.startswith("test_mcp") and file.endswith(".py"):
                mcp_tests.append(os.path.join(root, file))
            elif "mcp" in file and file.startswith("test_") and file.endswith(".py"):
                # Check if file content confirms it's an MCP test
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r") as f:
                        content = f.read()
                    if "import" in content and "mcp" in content.lower():
                        mcp_tests.append(file_path)
                except Exception as e:
                    logger.warning(f"Error reading {file_path}: {e}")

    logger.info(f"Found {len(mcp_tests)} MCP-related test files")
    return mcp_tests

def categorize_test(file_path):
    """
    Categorize a test file based on its name and content.

    Returns:
        A tuple of (category, target_directory)
    """
    filename = os.path.basename(file_path)

    # Check filename patterns
    if re.search(r'controller', filename, re.IGNORECASE):
        return "controller", MCP_TEST_DIR / "controller"
    elif re.search(r'model', filename, re.IGNORECASE):
        return "model", MCP_TEST_DIR / "model"
    elif re.search(r'server', filename, re.IGNORECASE):
        return "server", MCP_TEST_DIR / "server"
    elif re.search(r'libp2p.*integration|integration.*libp2p', filename, re.IGNORECASE):
        return "libp2p", MCP_TEST_DIR / "libp2p"

    # If not determined by filename, check content
    try:
        with open(file_path, "r") as f:
            content = f.read().lower()

        if "controller" in content and "test" in content:
            return "controller", MCP_TEST_DIR / "controller"
        elif "model" in content and "test" in content:
            return "model", MCP_TEST_DIR / "model"
        elif "server" in content and "test" in content:
            return "server", MCP_TEST_DIR / "server"
        elif "libp2p" in content and ("integration" in content or "test" in content):
            return "libp2p", MCP_TEST_DIR / "libp2p"
    except Exception as e:
        logger.warning(f"Error analyzing {file_path}: {e}")

    # Default category
    return "general", MCP_TEST_DIR

def migrate_tests(mcp_tests):
    """Migrate MCP tests to the appropriate directories."""
    logger.info("Migrating MCP tests to appropriate directories...")

    # Ensure all target directories exist
    ensure_directory(MCP_TEST_DIR)
    ensure_directory(MCP_TEST_DIR / "controller")
    ensure_directory(MCP_TEST_DIR / "model")
    ensure_directory(MCP_TEST_DIR / "server")
    ensure_directory(MCP_TEST_DIR / "libp2p")
    ensure_directory(MCP_TEST_DIR / "network_tests")

    # Keep track of migrations
    migrated = []
    skipped = []

    # Process each test file
    for test_file in mcp_tests:
        category, target_dir = categorize_test(test_file)

        # Special handling for network tests
        if "network" in os.path.basename(test_file).lower() or "network_tests" in test_file:
            target_dir = MCP_TEST_DIR / "network_tests"
            category = "network"

        # Create target path
        target_path = target_dir / os.path.basename(test_file)

        # Skip if target is the same as source
        if os.path.abspath(test_file) == os.path.abspath(target_path):
            logger.debug(f"Skipping {test_file} - already in correct location")
            skipped.append((test_file, "already in correct location"))
            continue

        # Skip if target exists and is newer
        if os.path.exists(target_path):
            source_mtime = os.path.getmtime(test_file)
            target_mtime = os.path.getmtime(target_path)

            if target_mtime > source_mtime:
                logger.debug(f"Skipping {test_file} - target is newer")
                skipped.append((test_file, "target is newer"))
                continue

        # Copy the file
        try:
            shutil.copy2(test_file, target_path)
            logger.info(f"Migrated {test_file} to {target_path} (category: {category})")
            migrated.append((test_file, target_path, category))
        except Exception as e:
            logger.error(f"Error migrating {test_file}: {e}")
            skipped.append((test_file, str(e)))

    return migrated, skipped

def create_test_init_files():
    """Create __init__.py files in test directories if needed."""
    logger.info("Creating __init__.py files in test directories...")

    test_dirs = [
        MCP_TEST_DIR,
        MCP_TEST_DIR / "controller",
        MCP_TEST_DIR / "model",
        MCP_TEST_DIR / "server",
        MCP_TEST_DIR / "libp2p",
        MCP_TEST_DIR / "network_tests"
    ]

    for directory in test_dirs:
        init_file = directory / "__init__.py"
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write(f'"""\nMCP {directory.name} tests.\n"""\n')
            logger.info(f"Created {init_file}")

def main():
    """Main function to migrate all MCP tests."""
    logger.info("Starting MCP test migration...")

    try:
        # Find all MCP tests
        mcp_tests = find_mcp_tests()

        # Migrate tests to appropriate directories
        migrated, skipped = migrate_tests(mcp_tests)

        # Create __init__.py files
        create_test_init_files()

        # Report results
        logger.info(f"Migration complete. {len(migrated)} files migrated, {len(skipped)} files skipped.")

        return True

    except Exception as e:
        logger.error(f"Error migrating MCP tests: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
