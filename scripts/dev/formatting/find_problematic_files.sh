#!/bin/bash

# Script to identify problematic Python files in ipfs_kit_py/mcp

echo "Scanning for problematic Python files..."

# Create a temporary directory for reports
TEMP_DIR=$(mktemp -d)
SYNTAX_FILES="$TEMP_DIR/syntax_files.txt"
ERROR_COUNT="$TEMP_DIR/error_counts.txt"

# Get a list of all Python files
ALL_FILES="$TEMP_DIR/all_python_files.txt"
find /home/barberb/ipfs_kit_py/ipfs_kit_py/mcp -name "*.py" > "$ALL_FILES"
total_files=$(wc -l < "$ALL_FILES")
echo "Found $total_files Python files to check"

# Function to check if a file has syntax errors using python -m py_compile
check_syntax() {
  local file=$1
  python -m py_compile "$file" 2>/dev/null
  return $?
}

# Check each file for syntax errors
echo "Checking for syntax errors..."
count=0
syntax_error_count=0

while IFS= read -r file; do
  ((count++))
  if ! check_syntax "$file"; then
    echo "$file" >> "$SYNTAX_FILES"
    ((syntax_error_count++))
  fi
  
  # Show progress every 10 files
  if ((count % 10 == 0)); then
    echo -ne "Processed $count/$total_files files ($syntax_error_count with syntax errors)\r"
  fi
done < "$ALL_FILES"

echo -e "\nCompleted syntax check: $syntax_error_count files have syntax errors"

# Display the top 10 files with syntax errors
if [[ -s "$SYNTAX_FILES" ]]; then
  echo -e "\nTop files with syntax errors:"
  cat "$SYNTAX_FILES" | sort | head -10
fi

# Now use ruff to count errors per file
echo -e "\nRunning ruff to identify files with most linting issues..."
tmp_ruff_output="$TEMP_DIR/ruff_output.txt"

# Run ruff and capture the output
ruff check --format=github ipfs_kit_py/mcp > "$tmp_ruff_output" 2>/dev/null || true

# Count errors per file
grep -o "/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/[^:]*" "$tmp_ruff_output" | sort | uniq -c | sort -nr > "$ERROR_COUNT"

# Show the top 15 files with most errors
echo -e "\nTop 15 files with most linting issues:"
head -15 "$ERROR_COUNT"

# Try to run black on specific files in verbose mode
echo -e "\nAttempting to format a problematic file with black in verbose mode..."
# Take the file with the most errors
top_file=$(head -1 "$ERROR_COUNT" | sed 's/^ *[0-9]* *//')

if [[ -n "$top_file" ]]; then
  echo "Trying to format: $top_file"
  black --verbose "$top_file" || echo "Black failed to format this file"
fi

# Clean up
rm -rf "$TEMP_DIR"

echo -e "\nAnalysis complete!"