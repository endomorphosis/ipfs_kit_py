#!/bin/bash

# Create minimal backup
BACKUP_DIR="mcp_backup_$(date +%s)"
mkdir -p "$BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

echo "1. Running Ruff first to fix basic issues..."
find ipfs_kit_py/mcp -name "*.py" -print0 | xargs -0 -n1 ruff check --fix --ignore E999 > /dev/null 2>&1 || true

echo "2. Applying Black to files with valid syntax..."
find ipfs_kit_py/mcp -name "*.py" -print0 | while IFS= read -r -d '' file; do
  black --quiet "$file" > /dev/null 2>&1 || true
done

echo "Done! Files that could be fixed have been formatted."
echo "Original files backed up to $BACKUP_DIR"