#!/bin/bash

# Create a backup directory
BACKUP_DIR="/home/barberb/ipfs_kit_py/mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
cp -r /home/barberb/ipfs_kit_py/ipfs_kit_py/mcp "$BACKUP_DIR"

echo "Starting to fix Python code issues in ipfs_kit_py/mcp with Black and Ruff..."

# Run Black formatter first on the entire directory
echo "Running Black formatter on all files..."
black /home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/

# Define all directories to process individually with Ruff
directories=(
  "ipfs_kit_py/mcp"
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

# Process each directory with Ruff
for dir in "${directories[@]}"; do
  if [ -d "$dir" ]; then
    echo "Fixing issues in $dir with Ruff..."
    ruff check --fix "$dir"
  else
    echo "Directory $dir not found, skipping..."
  fi
done

# Fix specific Python files with critical issues separately
echo "Fixing files with potential syntax errors..."
find /home/barberb/ipfs_kit_py/ipfs_kit_py/mcp -name "*.py" -type f -exec grep -l "except:" {} \; | xargs -I {} sed -i 's/except:/except Exception:/g' {}

# Fix specific import issues that Ruff might miss
echo "Fixing wildcard imports and other issues..."
find /home/barberb/ipfs_kit_py/ipfs_kit_py/mcp -name "*.py" -type f -exec grep -l "from .* import \*" {} \; | xargs -I {} sed -i 's/from \(.*\) import \*/from \1 import /' {}

# Run Black and Ruff again to ensure consistent formatting
echo "Final pass with Black and Ruff..."
black /home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/
ruff check --fix /home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/

echo "Completed fixes with Black and Ruff!"
echo "Backup of original files is in $BACKUP_DIR"
