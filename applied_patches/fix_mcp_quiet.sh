#!/bin/bash
set -e

# Create backup directory with timestamp
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup of ipfs_kit_py/mcp to $BACKUP_DIR..."
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# Create log directory
mkdir -p logs
LOG_FILE="logs/format_log_$(date +%Y%m%d_%H%M%S).log"

# Fix files with syntax issues first (using ruff's auto-fix capabilities)
echo "Step 1: Pre-fixing syntax issues with Ruff..."
find ipfs_kit_py/mcp -name "*.py" -exec ruff check --fix --unsafe-fixes --ignore E999 {} \; > "$LOG_FILE" 2>&1 || true

# Apply Black to all files in one go
echo "Step 2: Applying Black for consistent formatting..."
find ipfs_kit_py/mcp -name "*.py" -exec black --quiet --target-version py38 {} \; >> "$LOG_FILE" 2>&1 || true

# Apply Ruff with all fixes enabled
echo "Step 3: Applying Ruff fixes..."
find ipfs_kit_py/mcp -name "*.py" -exec ruff check --fix --unsafe-fixes {} \; >> "$LOG_FILE" 2>&1 || true

# Final pass with Black for consistent style
echo "Step 4: Final formatting pass with Black..."
find ipfs_kit_py/mcp -name "*.py" -exec black --quiet {} \; >> "$LOG_FILE" 2>&1 || true

# Look for changed files by comparing with backup
echo "Checking which files were successfully modified..."
echo "This may take a moment..."

# Create list of modified files
MODIFIED_FILES_LOG="logs/modified_files_$(date +%Y%m%d_%H%M%S).txt"
find ipfs_kit_py/mcp -name "*.py" -exec diff -q {} "$BACKUP_DIR"/{} \; 2>/dev/null | grep differ | sed 's/Files //g' | sed 's/ and .*differ//g' > "$MODIFIED_FILES_LOG" || true

# Count files
CHANGED_FILES=$(cat "$MODIFIED_FILES_LOG" | wc -l)
TOTAL_FILES=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)

echo ""
echo "✅ COMPLETED FORMATTING"
echo "------------------------"
echo "Total Python files: $TOTAL_FILES"
echo "Modified files: $CHANGED_FILES"
echo "Success rate: $((CHANGED_FILES * 100 / TOTAL_FILES))%"
echo ""
echo "Original files backed up to: $BACKUP_DIR"
echo "Log of formatting operations: $LOG_FILE"
echo "List of modified files: $MODIFIED_FILES_LOG"
echo "All possible formatting applied to ipfs_kit_py/mcp directory"