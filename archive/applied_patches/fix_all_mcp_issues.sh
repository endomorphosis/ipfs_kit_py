#!/bin/bash

# Create a backup first
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

echo "Step 1: Fixing syntax issues that prevent Black from working properly..."

# Fix common syntax errors in all Python files
find ipfs_kit_py/mcp -name "*.py" | while read file; do
    # Replace tabs with spaces
    sed -i 's/\t/    /g' "$file"
    
    # Fix trailing commas in import parentheses
    sed -i 's/from \([^(]*\) import (\([^)]*\),)/from \1 import (\2)/g' "$file"
    
    # Fix empty parentheses in imports
    sed -i 's/from typing import (,/from typing import (/g' "$file"
    
    # Fix trailing commas in method definitions
    sed -i 's/^\([ ]*\)self,$/\1self/g' "$file"
    
    # Fix incomplete parameter definitions
    sed -i 's/^\([ ]*\)\([a-zA-Z0-9_]*\): \([a-zA-Z0-9_]*\[ *[a-zA-Z0-9_, ]*\] *\),$/\1\2: \3/g' "$file"
    
    # Fix missing parameter defaults
    sed -i 's/\([a-zA-Z0-9_]*\)=None$/\1 = None/g' "$file"
    
    # Fix function parameters with trailing commas
    sed -i 's/\([ ]*\)\([a-zA-Z0-9_]*\): *\([a-zA-Z0-9_]* *\),$/\1\2: \3/g' "$file"
    
    echo -n "."
done
echo " Done fixing syntax"

echo "Step 2: Running Black with --fast option for more lenient formatting..."
find ipfs_kit_py/mcp -name "*.py" | while read file; do
    black --quiet --fast "$file" 2>/dev/null || true
    echo -n "."
done
echo " Done with Black"

echo "Step 3: Running Ruff with fix option for linting issues..."
find ipfs_kit_py/mcp -name "*.py" | while read file; do
    ruff check --fix --quiet "$file" 2>/dev/null || true
    echo -n "."
done
echo " Done with Ruff"

echo "Step 4: Verifying results..."
working_files=0
total_files=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)

# Test each file with black --check in lenient mode
find ipfs_kit_py/mcp -name "*.py" | while read file; do
    if black --check --quiet --fast "$file" 2>/dev/null; then
        working_files=$((working_files+1))
    fi
done

echo "Successfully formatted: $working_files out of $total_files files"
echo "Formatting complete! Original files backed up in $BACKUP_DIR"