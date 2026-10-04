#!/bin/bash
set -e

# Create a backup
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup of ipfs_kit_py/mcp to $BACKUP_DIR..."
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# Try running Black with special flags to be more lenient
echo "Running Black on ipfs_kit_py/mcp directory..."
black --quiet --target-version py310 ipfs_kit_py/mcp || {
  echo "Black encountered errors, but continuing with files it could process"
}

# Try running Ruff with options to skip unfixable issues
echo "Running Ruff on ipfs_kit_py/mcp directory..."
ruff check --fix --unsafe-fixes --ignore E999 ipfs_kit_py/mcp || {
  echo "Ruff encountered errors, but continuing with files it could process"
}

echo "Formatting complete. Some files may have been skipped due to syntax errors."
echo "Original files backed up to $BACKUP_DIR"