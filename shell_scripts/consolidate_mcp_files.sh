#!/bin/bash
#
# Consolidate MCP Files
# This script merges the additional functions from start_final_solution.sh.append into start_final_solution.sh
# and removes redundant files, leaving only the two main files.

set -e

echo "Starting MCP file consolidation process..."

# Create archive directory
ARCHIVE_DIR="mcp_archive_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ARCHIVE_DIR"
echo "Created archive directory: $ARCHIVE_DIR"

# Backup original files
cp final_mcp_server.py "$ARCHIVE_DIR/final_mcp_server.py.bak"
cp start_final_solution.sh "$ARCHIVE_DIR/start_final_solution.sh.bak"

echo "Files backed up to $ARCHIVE_DIR/"

# Update PORT in final_mcp_server.py from 3000 to 9997
echo "Updating PORT in final_mcp_server.py from 3000 to 9997..."
sed -i 's/PORT = 3000/PORT = 9997/' final_mcp_server.py

# Fix the merge by adding the append content right before the last main() function call
echo "Merging start_final_solution.sh.append into start_final_solution.sh..."
APPEND_CONTENT=$(cat start_final_solution.sh.append)
MAIN_LINE_NUMBER=$(grep -n "^main" start_final_solution.sh | tail -1 | cut -d: -f1)
BEFORE_MAIN=$((MAIN_LINE_NUMBER - 2))

# Split the file and insert the append content
head -n $BEFORE_MAIN start_final_solution.sh > temp_start.sh
echo "$APPEND_CONTENT" >> temp_start.sh
tail -n +$BEFORE_MAIN start_final_solution.sh >> temp_start.sh

# Replace the original file
mv temp_start.sh start_final_solution.sh
chmod +x start_final_solution.sh

# Archive redundant files
echo "Archiving redundant files..."
FILES_TO_ARCHIVE=(
  "start_final_solution.sh.append"
  "updated_start_final_solution.sh"
  "fix_all_mcp.sh"
  "final_mcp_server.py.backup_1746593426"
)

for file in "${FILES_TO_ARCHIVE[@]}"; do
  if [ -f "$file" ]; then
    echo "  - Moving $file to archive"
    mv "$file" "$ARCHIVE_DIR/"
  else
    echo "  - File $file not found, skipping"
  fi
done

echo ""
echo "Consolidation complete!"
echo "Primary files:"
echo "  1. start_final_solution.sh - Runner for MCP server with comprehensive testing"
echo "  2. final_mcp_server.py - The MCP server implementation with IPFS and VFS integration"
echo ""
echo "All other files have been archived to: $ARCHIVE_DIR/"
