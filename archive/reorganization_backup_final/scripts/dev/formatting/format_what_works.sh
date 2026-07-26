#!/bin/bash

# Create a backup
BACKUP_DIR="mcp_working_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# Create directories for results
mkdir -p black_success ruff_success error_files

# Process each file individually
echo "Testing and formatting each file individually..."
find ipfs_kit_py/mcp -name "*.py" | while read file; do
    filename=$(basename "$file")
    
    # Try formatting with Black (with permissive options)
    if black --quiet --fast "$file" 2>/dev/null; then
        echo "$file" >> black_success/black_formatted.txt
    else
        echo "$file" >> error_files/black_failed.txt
    fi
    
    # Try fixing with Ruff
    if ruff check --fix --quiet "$file" 2>/dev/null; then
        echo "$file" >> ruff_success/ruff_fixed.txt
    else
        echo "$file" >> error_files/ruff_failed.txt
    fi
done

# Count results
black_count=$(wc -l < black_success/black_formatted.txt 2>/dev/null || echo 0)
ruff_count=$(wc -l < ruff_success/ruff_fixed.txt 2>/dev/null || echo 0)
total=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)

echo "Results:"
echo "- Files successfully formatted with Black: $black_count/$total"
echo "- Files successfully processed with Ruff: $ruff_count/$total"
echo "- Original files backed up in $BACKUP_DIR"