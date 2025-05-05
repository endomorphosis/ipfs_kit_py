#!/bin/bash
# Finalize Consolidated MCP Solution
# This script prepares the consolidated MCP server solution by:
# 1. Setting proper permissions
# 2. Identifying and organizing files
# 3. Running final checks

echo "Finalizing Consolidated MCP Server Solution..."

# Set executable permissions
echo "Setting executable permissions..."
chmod +x start_consolidated_mcp_server.sh
chmod +x test_consolidated_mcp_server.py
chmod +x consolidated_final_mcp_server.py

# Create archive directory if it doesn't exist
if [ ! -d "archive" ]; then
  echo "Creating archive directory..."
  mkdir -p archive
fi

# Move old or redundant MCP server files to archive
echo "Organizing files..."
for file in $(find . -maxdepth 1 -name "*.py" | grep -v "consolidated_final_mcp_server.py" | grep -v "test_consolidated_mcp_server.py"); do
  if [[ $file == *"mcp_server"* || $file == *"ipfs"* || $file == *"vfs"* ]]; then
    echo "  Moving $file to archive/"
    mv "$file" archive/
  fi
done

for file in $(find . -maxdepth 1 -name "start_*.sh" | grep -v "start_consolidated_mcp_server.sh"); do
  echo "  Moving $file to archive/"
  mv "$file" archive/
done

# Update MCP settings if they exist
if [ -f ".config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json" ]; then
  echo "Updating MCP settings..."
  cp fixed_mcp_settings.json .config/Code\ -\ Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json
fi

# Verify essential files exist
echo "Verifying essential files..."
essential_files=(
  "consolidated_final_mcp_server.py"
  "start_consolidated_mcp_server.sh"
  "test_consolidated_mcp_server.py"
  "README_CONSOLIDATED_MCP_SERVER.md"
)

all_files_present=true
for file in "${essential_files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "  ERROR: Essential file missing: $file"
    all_files_present=false
  else
    echo "  OK: $file present"
  fi
done

# Final report
echo ""
echo "Final setup complete!"
if [ "$all_files_present" = true ]; then
  echo "All essential files are present."
else
  echo "WARNING: Some essential files are missing. Please check the errors above."
fi

echo ""
echo "To start the server, run:"
echo "  ./start_consolidated_mcp_server.sh"
echo ""
echo "To test the server, run:"
echo "  python3 test_consolidated_mcp_server.py"
echo ""
echo "For more information, refer to:"
echo "  README_CONSOLIDATED_MCP_SERVER.md"
