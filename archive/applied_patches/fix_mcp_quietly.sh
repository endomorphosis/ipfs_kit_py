#!/bin/bash

# Create a backup of the mcp directory
BACKUP_DIR="mcp_final_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# Common syntax fixes function
fix_syntax() {
    # Fix indentation, trailing commas, etc.
    sed -i 's/\t/    /g' "$1"
    sed -i 's/from \(.*\) import (\(.*\),)/from \1 import (\2)/g' "$1"
    sed -i 's/from typing import (, /from typing import /g' "$1"
    sed -i 's/self,$/self/g' "$1"
}

# Process files in batches to manage output
echo "Processing Python files in ipfs_kit_py/mcp..."
find ipfs_kit_py/mcp -name "*.py" | while read -r file; do
    # Apply syntax fixes
    fix_syntax "$file"
    
    # Apply Black (suppress most output)
    black --quiet "$file" 2>/dev/null || true
    
    # Apply Ruff (suppress most output)
    ruff check --fix --quiet "$file" 2>/dev/null || true
    
    echo -n "." # Progress indicator
done
echo " Done!"

echo "Process complete! The mcp directory has been processed with Black and Ruff."
echo "Original files are backed up in $BACKUP_DIR"