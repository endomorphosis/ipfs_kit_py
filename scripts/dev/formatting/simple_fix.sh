#!/bin/bash

# Simple script to fix issues with ruff in ipfs_kit_py/mcp

echo "Starting simple fix process..."

# First run: Fix as many issues as possible in one go
echo "Running first pass of fixes..."
ruff check --fix --exit-zero ipfs_kit_py/mcp

# Second run: Try to fix more issues that might be fixable after the first run
echo "Running second pass of fixes..."
ruff check --fix --exit-zero ipfs_kit_py/mcp

# Final run: Check remaining issues
echo "Checking remaining issues..."
ruff check --statistics ipfs_kit_py/mcp

echo "Fix process completed."