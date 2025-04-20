#!/bin/bash

# Create a backup of the mcp directory
BACKUP_DIR="mcp_final_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup in $BACKUP_DIR"
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# First, let's fix common syntax errors that prevent Black from running
echo "Fixing common syntax errors..."
find ipfs_kit_py/mcp -name "*.py" | while read -r file; do
    # Fix indentation issues
    sed -i 's/\t/    /g' "$file"
    
    # Fix trailing commas in import lists
    sed -i 's/from \(.*\) import (\(.*\),)/from \1 import (\2)/g' "$file"
    
    # Fix incomplete imports
    sed -i 's/from typing import (, /from typing import /g' "$file"
    
    # Fix dangling commas at end of lines
    sed -i 's/self,$/self/g' "$file"
done

# Now run Black with a more permissive approach
echo "Running Black in permissive mode..."
find ipfs_kit_py/mcp -name "*.py" | while read -r file; do
    echo "Formatting $file with Black"
    # Use --fast to be more lenient with parsing errors
    black --quiet --fast "$file" || echo "Black still failed on $file"
done

# Finally run Ruff with automatic fixes
echo "Running Ruff to fix linting issues..."
find ipfs_kit_py/mcp -name "*.py" | while read -r file; do
    echo "Fixing $file with Ruff"
    ruff check --fix --quiet "$file" || echo "Ruff failed on $file"
done

echo "Processing complete!"
echo "The mcp directory has been processed with Black and Ruff"
echo "Original files are backed up in $BACKUP_DIR"