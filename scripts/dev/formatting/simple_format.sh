#!/bin/bash

# Create backup
BACKUP="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup to $BACKUP..."
cp -r ipfs_kit_py/mcp "$BACKUP"

# Run Black
echo "Running Black on directory..."
black ipfs_kit_py/mcp || echo "Black completed with some issues"

# Run Ruff
echo "Running Ruff on directory..."
ruff check --fix ipfs_kit_py/mcp || echo "Ruff completed with some issues"

echo "Formatting complete. Original files backed up to $BACKUP"