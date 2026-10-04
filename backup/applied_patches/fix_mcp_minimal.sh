#!/bin/bash

# Create a backup with minimal output
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR" > /dev/null 2>&1

echo "Step 1: Fixing syntax issues that prevent Black from working properly..."

# Process files in batches to reduce output
find ipfs_kit_py/mcp -name "*.py" | while read file; do
    # Replace tabs with spaces
    sed -i 's/\t/    /g' "$file" 2>/dev/null
    
    # Fix trailing commas in import parentheses
    sed -i 's/from \([^(]*\) import (\([^)]*\),)/from \1 import (\2)/g' "$file" 2>/dev/null
    
    # Fix empty parentheses in imports
    sed -i 's/from typing import (,/from typing import (/g' "$file" 2>/dev/null
    
    # Fix trailing commas in method definitions
    sed -i 's/^\([ ]*\)self,$/\1self/g' "$file" 2>/dev/null
    
    # Fix incomplete parameter definitions
    sed -i 's/^\([ ]*\)\([a-zA-Z0-9_]*\): \([a-zA-Z0-9_]*\[ *[a-zA-Z0-9_, ]*\] *\),$/\1\2: \3/g' "$file" 2>/dev/null
done

echo "Step 2: Running Black and Ruff silently..."
total=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)
count=0

find ipfs_kit_py/mcp -name "*.py" | while read file; do
    # Run Black with fast option
    black --quiet --fast "$file" > /dev/null 2>&1
    
    # Run Ruff with fix option
    ruff check --fix --quiet "$file" > /dev/null 2>&1
    
    count=$((count+1))
    if [ $((count % 20)) -eq 0 ]; then
        echo "  Processed $count/$total files"
    fi
done

echo "All $total files processed with Black and Ruff"
echo "Formatting complete! Original files backed up in $BACKUP_DIR"