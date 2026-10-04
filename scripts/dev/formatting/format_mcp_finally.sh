#!/bin/bash

# Create a backup
BACKUP_DIR="mcp_final_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

echo "Applying basic syntax fixes..."

# Find all Python files
find ipfs_kit_py/mcp -name "*.py" | while read file; do
    # Fix tabs
    sed -i 's/\t/    /g' "$file"
    
    # Fix trailing commas in imports
    sed -i 's/from \([^)]*\) import (\([^)]*\),)/from \1 import (\2)/g' "$file"
    
    # Fix parameter assignments
    sed -i 's/\([a-zA-Z0-9_]*\)=None/\1 = None/g' "$file"
    
    # Fix JSON commas
    sed -i 's/"\([^"]*\)":\s*\([^,{}\n]*\)$/"\1": \2,/g' "$file"
    
    # Fix trailing commas in parameters
    sed -i 's/\([ ]*\)self,$/\1self/g' "$file"
    
    # Fix self parameters
    sed -i 's/self,,,/self/g' "$file"
done

# Create a list of files to format
FILELIST=$(mktemp)
find ipfs_kit_py/mcp -name "*.py" > "$FILELIST"

echo "Running Black with lenient options..."
while read file; do
    # Run Black with fast option (more lenient)
    black --quiet --fast "$file" >/dev/null 2>&1 || true
done < "$FILELIST"

echo "Running Ruff to fix linting issues..."
while read file; do
    # Run Ruff with fix option
    ruff check --fix --quiet "$file" >/dev/null 2>&1 || true
done < "$FILELIST"

rm "$FILELIST"

# Count files that are now valid
echo "Validating results..."
total=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)
valid_count=0

find ipfs_kit_py/mcp -name "*.py" | while read file; do
    if python3 -m py_compile "$file" 2>/dev/null; then
        ((valid_count++))
    fi
done

echo "Successfully formatted $valid_count/$total Python files"
echo "Complete! Original files are backed up in $BACKUP_DIR"