#!/bin/bash
set -e

# Create a backup
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup of ipfs_kit_py/mcp to $BACKUP_DIR..."
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

# Log files
BLACK_LOG="logs/black_output_$(date +%Y%m%d_%H%M%S).log"
RUFF_LOG="logs/ruff_output_$(date +%Y%m%d_%H%M%S).log"

# Try running Black with special flags to be more lenient
echo "Running Black on ipfs_kit_py/mcp directory (logging to $BLACK_LOG)..."
black --quiet --target-version py310 ipfs_kit_py/mcp > "$BLACK_LOG" 2>&1 || {
  echo "Black encountered errors, but continuing with files it could process"
}

# Try running Ruff with options to skip unfixable issues
echo "Running Ruff on ipfs_kit_py/mcp directory (logging to $RUFF_LOG)..."
ruff check --fix --unsafe-fixes --ignore E999 ipfs_kit_py/mcp > "$RUFF_LOG" 2>&1 || {
  echo "Ruff encountered errors, but continuing with files it could process"
}

# Count how many files were modified by comparing with backup
CHANGED_FILES=$(diff -r ipfs_kit_py/mcp "$BACKUP_DIR" | grep -c "^Only in ipfs_kit_py/mcp" || true)
TOTAL_FILES=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)

echo "Formatting complete."
echo "Processed $TOTAL_FILES Python files"
echo "Changed approximately $CHANGED_FILES files"
echo "See $BLACK_LOG and $RUFF_LOG for details"
echo "Original files backed up to $BACKUP_DIR"