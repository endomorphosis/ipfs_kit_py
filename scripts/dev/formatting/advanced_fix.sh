#!/bin/bash

# Advanced script to systematically fix issues in ipfs_kit_py/mcp

# Colors for better output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== MCP Python Code Fixer =====${NC}"
echo "This will systematically fix issues in the ipfs_kit_py/mcp folder"
echo ""

# Define error types in order of priority
ERROR_TYPES=(
  "E999"  # SyntaxError
  "F821"  # undefined-name
  "F823"  # undefined-local
  "F401"  # unused-import
  "F811"  # redefined-while-unused
  "E722"  # bare-except
  "E402"  # module-import-not-at-top-of-file
  "F403"  # undefined-local-with-import-star
  "E741"  # ambiguous-variable-name
)

# Error descriptions for better reporting
declare -A ERROR_DESCRIPTIONS=(
  ["E999"]="Syntax errors"
  ["F821"]="Undefined names"
  ["F823"]="Undefined local variables"
  ["F401"]="Unused imports"
  ["F811"]="Redefined names"
  ["E722"]="Bare except clauses"
  ["E402"]="Import not at top of file"
  ["F403"]="Star imports"
  ["E741"]="Ambiguous variable names"
)

# Function to count errors of a specific type
count_errors() {
  local error_code=$1
  local count=$(ruff check ipfs_kit_py/mcp --select "$error_code" --quiet | wc -l)
  echo "$count"
}

# Function to get list of files with a specific error
get_files_with_error() {
  local error_code=$1
  local output_file=$2
  
  # Use ruff to check for the error code and extract unique filenames
  ruff check ipfs_kit_py/mcp --select "$error_code" | grep -o '/home/barberb/ipfs_kit_py/ipfs_kit_py/mcp/[^:]*' | sort | uniq > "$output_file"
}

# Function to fix specific error type in a file
fix_file() {
  local file=$1
  local error_code=$2
  
  echo -e "   ${YELLOW}Fixing${NC} $file"
  ruff check --fix --select "$error_code" "$file" --quiet --exit-zero
  return $?
}

# Process each error type
for error_code in "${ERROR_TYPES[@]}"; do
  echo -e "\n${BLUE}Processing ${ERROR_DESCRIPTIONS[$error_code]} ($error_code)${NC}"
  
  # Count initial errors
  initial_count=$(count_errors "$error_code")
  echo -e "${YELLOW}Found $initial_count issues${NC}"
  
  if [ "$initial_count" -gt 0 ]; then
    # Get files with this error
    FILES_LIST=$(mktemp)
    get_files_with_error "$error_code" "$FILES_LIST"
    file_count=$(wc -l < "$FILES_LIST")
    
    echo -e "${YELLOW}Affected files: $file_count${NC}"
    
    # Process each file
    while IFS= read -r file; do
      fix_file "$file" "$error_code"
    done < "$FILES_LIST"
    
    # Count remaining errors
    remaining_count=$(count_errors "$error_code")
    fixed_count=$((initial_count - remaining_count))
    
    echo -e "${GREEN}Fixed $fixed_count out of $initial_count issues${NC}"
    echo -e "${YELLOW}Remaining: $remaining_count${NC}"
    
    # Clean up temp file
    rm -f "$FILES_LIST"
  else
    echo -e "${GREEN}No issues found!${NC}"
  fi
done

echo -e "\n${BLUE}===== Final Report =====${NC}"
echo "Remaining issues by type:"
ruff check ipfs_kit_py/mcp --statistics

echo -e "\n${GREEN}Processing complete!${NC}"
echo "Note: Some issues may require manual intervention."