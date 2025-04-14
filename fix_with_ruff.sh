#!/bin/bash

# Quieter version of the fix script
echo "Starting to fix Python code issues in ipfs_kit_py/mcp with Ruff..."

# Fix the main module first
ruff check --fix --quiet ipfs_kit_py/mcp/__init__.py
echo "Fixed ipfs_kit_py/mcp/__init__.py"

# Fix each subdirectory - quietly
directories=(
  "ipfs_kit_py/mcp/auth"
  "ipfs_kit_py/mcp/controllers"
  "ipfs_kit_py/mcp/extensions"
  "ipfs_kit_py/mcp/ha"
  "ipfs_kit_py/mcp/models"
  "ipfs_kit_py/mcp/monitoring"
  "ipfs_kit_py/mcp/persistence"
  "ipfs_kit_py/mcp/routing"
  "ipfs_kit_py/mcp/security"
  "ipfs_kit_py/mcp/server"
  "ipfs_kit_py/mcp/services"
  "ipfs_kit_py/mcp/storage_manager"
  "ipfs_kit_py/mcp/tests"
  "ipfs_kit_py/mcp/utils"
)

# Process each directory
for dir in "${directories[@]}"; do
  echo "Fixing issues in $dir..."
  ruff check --fix --quiet "$dir"
done

echo "Finished fixing all directories with Ruff!"