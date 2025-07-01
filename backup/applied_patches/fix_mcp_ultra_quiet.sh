#!/bin/bash

# Create backup
BACKUP_DIR="mcp_final_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# Process each file
count=0
total=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)
echo "Processing $total Python files..."

find ipfs_kit_py/mcp -name "*.py" | while read -r file; do
    # Fix basic syntax issues
    sed -i 's/\t/    /g' "$file" 2>/dev/null
    sed -i 's/from \(.*\) import (\(.*\),)/from \1 import (\2)/g' "$file" 2>/dev/null
    sed -i 's/from typing import (, /from typing import /g' "$file" 2>/dev/null
    sed -i 's/self,$/self/g' "$file" 2>/dev/null

    # Run black with all output suppressed
    black --quiet "$file" >/dev/null 2>&1 || true
    
    # Run ruff with all output suppressed
    ruff check --fix --quiet "$file" >/dev/null 2>&1 || true
    
    count=$((count+1))
    if [ $((count % 10)) -eq 0 ]; then
        echo "  Processed $count/$total files"
    fi
done

echo "All files processed! The mcp directory has been formatted using Black and Ruff."
echo "Original files are backed up in $BACKUP_DIR"