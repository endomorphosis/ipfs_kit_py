#!/bin/bash

# Directory to process
TARGET_DIR="ipfs_kit_py/mcp"
FIXED_COUNT=0
BACKUP_SUFFIX=".bak_$(date +%Y%m%d%H%M%S)"

# Create a backup of all files
echo "Creating backups of all Python files..."
find $TARGET_DIR -name "*.py" -exec cp {} {}.bak \;

# Function to fix import statements that use parentheses
fix_import_statements() {
    local file=$1
    # Only process files that don't have severe syntax errors
    if grep -q "^from .* import (" "$file"; then
        echo "Fixing import statements in $file"
        # Replace multi-line imports with single line imports
        TMP_FILE=$(mktemp)
        awk '
        BEGIN { in_import = 0; import_statement = ""; }
        {
            if ($0 ~ /^from .* import \(/ && !in_import) {
                in_import = 1;
                import_statement = $0;
                gsub(" *\\(.*$", "", import_statement);
                import_statement = import_statement " ";
            } else if (in_import && $0 ~ /\)/) {
                # End of import block
                in_import = 0;
                gsub("^[ ]*|[ ]*\\)[ ]*$", "", $0);
                if ($0 != "") {
                    import_statement = import_statement $0;
                }
                print import_statement;
            } else if (in_import) {
                # Middle of import block
                line = $0;
                gsub("^[ ]*|[ ]*,$", "", line);
                if (line != "") {
                    import_statement = import_statement line ", ";
                }
            } else {
                print $0;
            }
        }
        ' "$file" > "$TMP_FILE"
        mv "$TMP_FILE" "$file"
        ((FIXED_COUNT++))
    fi
}

# Function to fix missing imports
fix_missing_imports() {
    local file=$1
    modified=0
    
    # Check for time import
    if grep -q "time\\.time()" "$file" && ! grep -q "import time" "$file"; then
        echo "Adding missing 'time' import to $file"
        sed -i "1s/^/import time\n/" "$file"
        modified=1
    fi
    
    # Check for logging import
    if grep -q "logging\\.getLogger" "$file" && ! grep -q "import logging" "$file"; then
        echo "Adding missing 'logging' import to $file"
        sed -i "1s/^/import logging\n/" "$file"
        modified=1
    fi
    
    # Check for typing imports
    if (grep -q "Dict\\[" "$file" || grep -q ": Dict" "$file") && ! grep -q "from typing import Dict" "$file"; then
        echo "Adding missing 'Dict' import to $file"
        if grep -q "from typing import" "$file"; then
            # Add to existing typing import
            sed -i "s/from typing import \\(.*\\)/from typing import \\1, Dict, Any/" "$file"
        else
            # Add new import
            sed -i "1s/^/from typing import Dict, Any\n/" "$file"
        fi
        modified=1
    fi
    
    # Add other missing imports here as needed
    
    if [ $modified -eq 1 ]; then
        ((FIXED_COUNT++))
    fi
}

# Function to apply Black formatting to a file
apply_black() {
    local file=$1
    echo "Applying Black to $file"
    if black "$file" 2>/dev/null; then
        echo "✓ Black formatting successful for $file"
        return 0
    else
        echo "✗ Black formatting failed for $file"
        return 1
    fi
}

# Function to apply Ruff fixes to a file
apply_ruff() {
    local file=$1
    echo "Applying Ruff to $file"
    if ruff check "$file" --fix 2>/dev/null; then
        echo "✓ Ruff fixes successful for $file"
        return 0
    else
        echo "✗ Ruff fixes failed for $file"
        return 1
    fi
}

# Process files
echo "Processing files in $TARGET_DIR..."
TOTAL_FILES=0
SUCCESS_COUNT=0

for file in $(find $TARGET_DIR -name "*.py" | sort); do
    echo "Checking $file"
    ((TOTAL_FILES++))
    
    # Skip files with known severe syntax errors
    if grep -q "Cannot parse" "$file" 2>/dev/null; then
        echo "Skipping $file due to severe syntax errors"
        continue
    fi
    
    # Make a backup before modifications
    cp "$file" "$file$BACKUP_SUFFIX"
    
    # Fix common issues
    fix_import_statements "$file"
    fix_missing_imports "$file"
    
    # Try to apply Black and Ruff
    if apply_black "$file" && apply_ruff "$file"; then
        ((SUCCESS_COUNT++))
        echo "Successfully fixed and formatted $file"
    else
        # Restore from backup if formatting failed
        echo "Restoring $file from backup due to formatting errors"
        cp "$file$BACKUP_SUFFIX" "$file"
    fi
    
    echo "-----------------------------------"
done

echo "Finished processing $TOTAL_FILES files"
echo "Made fixes to $FIXED_COUNT files"
echo "Successfully formatted $SUCCESS_COUNT files"
echo "Backups created with suffix $BACKUP_SUFFIX"

# Run a final pass of Black and Ruff on files that were successfully processed
echo "Running final Black pass on $TARGET_DIR"
black "$TARGET_DIR" 2>/dev/null
echo "Running final Ruff pass on $TARGET_DIR"
ruff check "$TARGET_DIR" --fix 2>/dev/null

echo "Process complete! Check files manually for any remaining issues."