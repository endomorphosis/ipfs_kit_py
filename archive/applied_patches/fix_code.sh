#!/bin/bash

# Script to fix all code issues in ipfs_kit_py/mcp folder
LOG_FILE="code_fixes.log"
echo "===== Starting Code Fixes $(date) =====" > $LOG_FILE

# Get current directory for reference
CURRENT_DIR=$(pwd)
MCP_DIR="$CURRENT_DIR/ipfs_kit_py/mcp"

echo "Working from directory: $CURRENT_DIR" | tee -a $LOG_FILE
echo "Target MCP directory: $MCP_DIR" | tee -a $LOG_FILE

# Check if the MCP directory exists
if [ ! -d "$MCP_DIR" ]; then
  echo "Error: MCP directory not found at $MCP_DIR" | tee -a $LOG_FILE
  exit 1
fi

# Focusing on problematic files first
echo "Focusing on problematic files first..." | tee -a $LOG_FILE

# Running initial Ruff fixes on all files
echo "Running initial Ruff fixes on all files..." | tee -a $LOG_FILE
ruff check --fix --quiet ipfs_kit_py/mcp >> $LOG_FILE 2>&1

# Now run Black in a more targeted manner, directory by directory
echo "Running Black on each directory..." | tee -a $LOG_FILE
directories=(
  "ipfs_kit_py/mcp/auth"
  "ipfs_kit_py/mcp/ha"
  "ipfs_kit_py/mcp/models" 
  "ipfs_kit_py/mcp/monitoring"
  "ipfs_kit_py/mcp/persistence"
  "ipfs_kit_py/mcp/routing"
  "ipfs_kit_py/mcp/security"
  "ipfs_kit_py/mcp/server"
  "ipfs_kit_py/mcp/services"
  "ipfs_kit_py/mcp/storage_manager"
  "ipfs_kit_py/mcp/tests"
  "ipfs_kit_py/mcp/utils"
)

# Process each directory with Black
for dir in "${directories[@]}"; do
  if [ -d "$dir" ]; then
    echo "Processing $dir with Black..." | tee -a $LOG_FILE
    black "$dir" --quiet >> $LOG_FILE 2>&1
  else
    echo "Directory $dir not found, skipping..." | tee -a $LOG_FILE
  fi
done

# Process the extensions directory separately (if it exists)
if [ -d "ipfs_kit_py/mcp/extensions" ]; then
  echo "Processing ipfs_kit_py/mcp/extensions with Black..." | tee -a $LOG_FILE
  black ipfs_kit_py/mcp/extensions --quiet >> $LOG_FILE 2>&1
fi

# Handle the controllers directory separately
if [ -d "ipfs_kit_py/mcp/controllers" ]; then
  echo "Processing the controllers directory more carefully..." | tee -a $LOG_FILE
  
  # Process all controllers files
  find ipfs_kit_py/mcp/controllers -name "*.py" -exec black {} --quiet \; >> $LOG_FILE 2>&1
fi

# Process the main init file
if [ -f "ipfs_kit_py/mcp/__init__.py" ]; then
  echo "Processing ipfs_kit_py/mcp/__init__.py with Black..." | tee -a $LOG_FILE
  black ipfs_kit_py/mcp/__init__.py --quiet >> $LOG_FILE 2>&1
fi

# Fix the remaining issues with Ruff
echo "Running final Ruff fixes on all directories..." | tee -a $LOG_FILE
ruff check --fix --quiet ipfs_kit_py/mcp >> $LOG_FILE 2>&1

# Summary of issues
echo "===== Fix Summary =====" | tee -a $LOG_FILE
echo "Fix process completed at $(date)" | tee -a $LOG_FILE

# Get statistics on remaining issues
echo "Remaining issues:" | tee -a $LOG_FILE
ruff check ipfs_kit_py/mcp --statistics >> $LOG_FILE 2>&1
ruff check ipfs_kit_py/mcp --statistics | tee -a /dev/tty

echo "Fixes applied. See $LOG_FILE for details." | tee -a /dev/tty