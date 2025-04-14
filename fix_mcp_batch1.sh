#!/bin/bash
set -e

# Target specific subdirectories to process in manageable chunks
DIRS=(
    "ipfs_kit_py/mcp/__init__.py"
    "ipfs_kit_py/mcp/models"
)

echo "Creating a backup of the MCP directory..."
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR
cp -r ipfs_kit_py/mcp/* $BACKUP_DIR/
echo "Backup created in $BACKUP_DIR"

# Fix common issues and apply Black + Ruff to files
for target in "${DIRS[@]}"; do
    echo "Processing $target..."
    
    # Find Python files in the target directory
    if [[ -d $target ]]; then
        files=$(find $target -name "*.py")
    else
        files=$target
    fi
    
    # Process each file
    for file in $files; do
        echo "Working on $file"
        
        # 1. Fix missing imports
        if grep -q "time\.time()" $file && ! grep -q "import time" $file; then
            sed -i '1s/^/import time\n/' $file
            echo "  - Added missing time import"
        fi
        
        if grep -q "logging\.getLogger" $file && ! grep -q "import logging" $file; then
            sed -i '1s/^/import logging\n/' $file
            echo "  - Added missing logging import"
        fi
        
        # 2. Fix import with parentheses issue
        sed -i 's/from \(.*\) import (/from \1 import /g' $file
        sed -i 's/^[[:space:]]*\([^[:space:]]*\),$/\1/g' $file
        sed -i '/^[[:space:]]*)/d' $file
        
        # 3. Apply Black and Ruff
        echo "  - Applying Black..."
        black $file || echo "    Black failed, continuing anyway"
        
        echo "  - Applying Ruff with auto-fix..."
        ruff check $file --fix || echo "    Ruff failed, continuing anyway"
        
        echo "  - Done with $file"
        echo "-----------------------"
    done
done

echo "First batch of files processed!"