#!/bin/bash

# Script to identify files with syntax errors in ipfs_kit_py/mcp

echo "Identifying files with syntax errors..."
echo

# Create a temporary file to store the error output
ERROR_LOG=$(mktemp)
SYNTAX_ERR_FILES=$(mktemp)

# Run ruff to check for syntax errors and save the output
ruff check ipfs_kit_py/mcp --select E999 > "$ERROR_LOG" 2>&1

# Extract the filenames from the error output and count errors per file
grep -o 'ipfs_kit_py/mcp/[^:]*' "$ERROR_LOG" | sort | uniq -c | sort -rn > "$SYNTAX_ERR_FILES"

# Display the files with syntax errors
echo "Files with syntax errors (sorted by number of errors):"
echo "------------------------------------------------------"
cat "$SYNTAX_ERR_FILES"
echo
echo "Total files with syntax errors: $(wc -l < "$SYNTAX_ERR_FILES")"
echo
echo "Recommendation: Manually fix the syntax errors in these files first,"
echo "then run ruff again to fix the remaining issues."

# Clean up temporary files
rm -f "$ERROR_LOG" "$SYNTAX_ERR_FILES"