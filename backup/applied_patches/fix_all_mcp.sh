#!/bin/bash
set -e

# Create backup directory with timestamp
BACKUP_DIR="mcp_backup_$(date +%Y%m%d_%H%M%S)"
echo "Creating backup of ipfs_kit_py/mcp to $BACKUP_DIR..."
cp -r ipfs_kit_py/mcp "$BACKUP_DIR"

# Create log directory
mkdir -p logs

# Fix files with syntax issues first (using ruff's auto-fix capabilities)
echo "Step 1: Pre-fixing syntax issues with Ruff..."
find ipfs_kit_py/mcp -name "*.py" -exec ruff check --fix --unsafe-fixes --ignore E999 {} \; 2>/dev/null || true

# Apply Black to all files in one go
echo "Step 2: Applying Black for consistent formatting..."
find ipfs_kit_py/mcp -name "*.py" -exec black --quiet --target-version py38 {} \; 2>/dev/null || true

# Apply Ruff with all fixes enabled
echo "Step 3: Applying Ruff fixes..."
find ipfs_kit_py/mcp -name "*.py" -exec ruff check --fix --unsafe-fixes {} \; 2>/dev/null || true

# Final pass with Black for consistent style
echo "Step 4: Final formatting pass with Black..."
find ipfs_kit_py/mcp -name "*.py" -exec black --quiet {} \; 2>/dev/null || true

# Look for changed files by comparing with backup
echo "Checking which files were successfully modified..."
CHANGED_FILES=$(find ipfs_kit_py/mcp -name "*.py" -exec diff -q {} "$BACKUP_DIR"/{} \; 2>/dev/null | wc -l)
TOTAL_FILES=$(find ipfs_kit_py/mcp -name "*.py" | wc -l)

echo ""
echo "✅ COMPLETED FORMATTING"
echo "------------------------"
echo "Total Python files: $TOTAL_FILES"
echo "Modified files: $CHANGED_FILES"
echo "Success rate: $((CHANGED_FILES * 100 / TOTAL_FILES))%"
echo ""
echo "Original files backed up to: $BACKUP_DIR"
echo "All possible formatting applied to ipfs_kit_py/mcp directory"