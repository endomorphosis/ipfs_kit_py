#!/bin/bash
#
# MCP Files Archive Script
#
# This script archives all redundant MCP files and leaves only
# the two main files: final_mcp_server.py and start_final_solution.sh

set -e

# Create archive directory
ARCHIVE_DIR="mcp_archive_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ARCHIVE_DIR"
echo "Created archive directory: $ARCHIVE_DIR"

# Files to keep (will NOT be archived)
KEEP_FILES=(
  "final_mcp_server.py"
  "start_final_solution.sh"
)

# Merge the append file into start_final_solution.sh
if [ -f "start_final_solution.sh.append" ]; then
  echo "Merging start_final_solution.sh.append into start_final_solution.sh..."
  # Remove the first line which is just a filepath comment
  tail -n +2 start_final_solution.sh.append >> start_final_solution.sh
  echo "Merge complete."
fi

# Move redundant files to archive
echo "Moving redundant files to archive..."
for file in updated_start_final_solution.sh start_final_solution.sh.append fix_all_mcp.sh final_mcp_server.py.backup_*; do
  if [ -f "$file" ]; then
    echo "  - Archiving $file"
    mv "$file" "$ARCHIVE_DIR/"
  fi
done

# Make start_final_solution.sh executable
chmod +x start_final_solution.sh

echo "Archive process complete. Redundant files moved to $ARCHIVE_DIR/"
echo "Keeping only:"
for file in "${KEEP_FILES[@]}"; do
  echo "  - $file"
done
