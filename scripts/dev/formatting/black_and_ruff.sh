#!/bin/bash

# Comprehensive script to fix Python code issues using both Black and Ruff
# First formats with Black, then runs multiple Ruff fixing passes

LOG_DIR="/home/barberb/ipfs_kit_py/fix_logs"
mkdir -p "$LOG_DIR"

echo "===== Starting Comprehensive Code Fixing Process ====="
echo "Detailed logs will be saved to $LOG_DIR"

# First check how many issues we have before starting
echo "Initial issue count:"
ruff check --statistics ipfs_kit_py/mcp > "$LOG_DIR/initial_check.log" 2>&1
cat "$LOG_DIR/initial_check.log" | tail -10

# Step 1: Run Black to format all Python files
echo -e "\n===== Step 1: Formatting with Black ====="
black ipfs_kit_py/mcp/ > "$LOG_DIR/black_format.log" 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Black formatting completed successfully!"
    grep "reformatted" "$LOG_DIR/black_format.log" | head -1
else
    echo "✗ Black encountered issues. Check $LOG_DIR/black_format.log for details."
    tail -5 "$LOG_DIR/black_format.log"
fi

# Check issues after Black
echo -e "\nIssues after Black formatting:"
ruff check --statistics ipfs_kit_py/mcp > "$LOG_DIR/after_black.log" 2>&1
cat "$LOG_DIR/after_black.log" | tail -10

# Step 2: Run multiple passes of Ruff to fix issues
echo -e "\n===== Step 2: Fixing issues with Ruff ====="

# First pass - focus on syntax and import issues
echo "Running first pass (focusing on imports and basic issues)..."
ruff check --fix --select=F401,F403,E402,F811,E741 --exit-zero ipfs_kit_py/mcp > "$LOG_DIR/ruff_pass1.log" 2>&1

# Second pass - focus on undefined names and variables
echo "Running second pass (focusing on undefined names and variables)..."
ruff check --fix --select=F821,F823 --exit-zero ipfs_kit_py/mcp > "$LOG_DIR/ruff_pass2.log" 2>&1

# Third pass - focus on bare excepts and other remaining issues
echo "Running third pass (focusing on bare excepts and remaining issues)..."
ruff check --fix --select=E722 --exit-zero ipfs_kit_py/mcp > "$LOG_DIR/ruff_pass3.log" 2>&1

# Final pass - run ruff with all rules
echo "Running final pass (all rules)..."
ruff check --fix --exit-zero ipfs_kit_py/mcp > "$LOG_DIR/ruff_final.log" 2>&1

# Step 3: Check results and provide summary
echo -e "\n===== Step 3: Results ====="
echo "Checking remaining issues..."
ruff check --statistics ipfs_kit_py/mcp > "$LOG_DIR/final_check.log" 2>&1
cat "$LOG_DIR/final_check.log" | tail -10

echo -e "\n===== Process Completed ====="
echo "Check $LOG_DIR for detailed logs"