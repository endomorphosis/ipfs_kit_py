#!/bin/bash

# Script to fix code issues using both Black and Ruff
LOG_FILE="code_formatting_fixes.log"

echo "=============================================" > $LOG_FILE
echo "Starting code fixes with Black and Ruff at $(date)" | tee -a $LOG_FILE
echo "=============================================" | tee -a $LOG_FILE

# First run Black for code formatting
echo -e "\n\nApplying Black formatter to all Python files in ipfs_kit_py/mcp..." | tee -a $LOG_FILE
black ipfs_kit_py/mcp --quiet 2>&1 | tee -a $LOG_FILE

# Then run Ruff to fix additional issues
echo -e "\n\nApplying Ruff to fix linting issues in ipfs_kit_py/mcp..." | tee -a $LOG_FILE
directories=(
  "ipfs_kit_py/mcp/__init__.py"
  "ipfs_kit_py/mcp/auth"
  "ipfs_kit_py/mcp/controllers"
  "ipfs_kit_py/mcp/extensions"
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

# Process each directory
for dir in "${directories[@]}"; do
  echo "Running Ruff on $dir..." | tee -a $LOG_FILE
  ruff check --fix --quiet "$dir" >> $LOG_FILE 2>&1
done

# Run Black one more time to ensure consistent formatting after Ruff's changes
echo -e "\n\nFinal pass with Black for consistent formatting..." | tee -a $LOG_FILE
black ipfs_kit_py/mcp --quiet 2>&1 | tee -a $LOG_FILE

echo -e "\n\n=============================================" | tee -a $LOG_FILE
echo "Code formatting and linting completed at $(date)" | tee -a $LOG_FILE
echo "See $LOG_FILE for complete details" | tee -a $LOG_FILE
echo "=============================================" | tee -a $LOG_FILE

# Run Ruff check for statistics on remaining issues
echo -e "\n\nRemaining issues after fixes:" | tee -a $LOG_FILE
cd ipfs_kit_py && ruff check mcp --statistics 2>&1 | tee -a $LOG_FILE