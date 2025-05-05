#!/bin/bash
# Script to organize the codebase, archive obsolete files, and clean up the repository

echo "==== Organizing IPFS Kit Python Codebase ===="
echo "This script will organize the codebase and move obsolete files to an archive directory"

# Create archive directory if it doesn't exist
mkdir -p archive/deprecated_mcp_servers
mkdir -p archive/experiments
mkdir -p archive/fixes
mkdir -p archive/scripts

# List of files to keep (core files)
CORE_FILES=(
  "consolidated_final_mcp_server.py"
  "src/mcp/consolidated_final_mcp_server.py"
  "start_consolidated_mcp_server.sh"
  "stop_consolidated_mcp_server.sh"
  "test_consolidated_mcp_server.py"
  "tests/test_consolidated_mcp_server.py"
  "README_CONSOLIDATED_MCP_SERVER.md"
  "README.md"
  "LICENSE"
  "CONTRIBUTING.md"
  "CHANGELOG.md"
  ".gitignore"
  ".gitattributes"
  "setup.py"
  "requirements.txt"
)

# Files to archive because they've been replaced by consolidated_final_mcp_server.py
DEPRECATED_MCP_SERVERS=(
  "direct_mcp_server.py"
  "direct_mcp_server_with_tools.py"
  "enhanced_mcp_server_fixed.py"
  "final_mcp_server.py"
  "fixed_final_mcp_server.py"
  "minimal_mcp_server.py"
  "vfs_mcp_server.py"
)

# Integration scripts that are no longer needed
DEPRECATED_SCRIPTS=(
  "add_comprehensive_ipfs_tools.py"
  "add_initialize_endpoint.py"
  "add_mcp_initialize.py"
  "add_mcp_tools.py"
  "add_new_ipfs_tools.py"
  "apply_mcp_tool_enhancements.sh"
  "create_standalone_vfs_server.py"
  "direct_register_vfs_tools.py"
  "enhance_comprehensive_mcp_tools.py"
  "enhance_final_integration.py"
  "enhance_ipfs_fs_integration.py"
  "enhance_ipfs_mcp_tools.py"
  "enhance_mcp_tool_coverage.py"
  "enhance_mcp_tools.py"
  "enhance_tool_coverage.py"
  "enhance_vfs_mcp_integration.py"
  "implement_mcp_ipfs_tools.py"
  "integrate_all_mcp_tools.py"
  "integrate_features.py"
  "integrate_final_mcp_server.py"
  "integrate_vfs_to_final_mcp.py"
  "patch_vfs_functions.py"
  "restart_mcp_server_with_vfs.sh"
  "restart_mcp_with_vfs.sh"
  "restart_with_vfs_adapter.sh"
  "start_all_in_one_server.sh"
  "start_all_mcp_components.sh"
  "start_complete_mcp_stack.sh"
  "start_enhanced_mcp_stack.sh"
  "start_fixed_final_mcp_server.sh"
  "start_fixed_mcp_server.sh"
  "start_full_mcp_server.sh"
  "start_mcp_all.sh"
  "start_mcp_all_tools.sh"
  "start_mcp_complete.sh"
  "start_mcp_server.sh"
  "start_mcp_server_with_all_tools.sh"
  "start_mcp_stack.sh"
  "start_mcp_with_vfs.sh"
  "start_minimal_mcp_server.sh"
  "start_split_servers.sh"
  "start_vfs_mcp_server.sh"
  "update_mcp_with_vfs_tools.py"
  "verify_fixed_mcp_tools.py"
  "verify_mcp_setup.py"
  "verify_mcp_tools.py"
  "verify_mcp_tools_now.py"
  "verify_vfs_tools.py"
  "vfs_tools_adapter.py"
)

# Fixes that are no longer needed as they've been incorporated into the consolidated server
DEPRECATED_FIXES=(
  "fix_*"
  "direct_fix*"
  "ensure_*"
  "debug_*"
  "diagnose_*"
)

echo "Moving deprecated MCP server implementations to archive..."
for file in "${DEPRECATED_MCP_SERVERS[@]}"; do
  if [ -f "$file" ]; then
    echo "Archiving $file"
    mv "$file" archive/deprecated_mcp_servers/
  fi
done

echo "Moving deprecated integration scripts to archive..."
for file in "${DEPRECATED_SCRIPTS[@]}"; do
  # Use find to handle glob patterns
  find . -name "$file" -type f -not -path "./archive*" | while read f; do
    echo "Archiving $f"
    mkdir -p "archive/scripts/$(dirname "$f" | sed 's|^\./||')"
    mv "$f" "archive/scripts/$(dirname "$f" | sed 's|^\./||')/"
  done
done

echo "Moving deprecated fix scripts to archive..."
for pattern in "${DEPRECATED_FIXES[@]}"; do
  # Use find to handle glob patterns
  find . -name "$pattern" -type f -not -path "./archive*" | while read f; do
    echo "Archiving $f"
    mkdir -p "archive/fixes/$(dirname "$f" | sed 's|^\./||')"
    mv "$f" "archive/fixes/$(dirname "$f" | sed 's|^\./||')/"
  done
done

echo "Moving README files documenting old approaches to archive..."
find . -name "README_*" -not -name "README_CONSOLIDATED_MCP_SERVER.md" -type f -not -path "./archive*" | while read f; do
  echo "Archiving $f"
  mkdir -p "archive/docs/$(dirname "$f" | sed 's|^\./||')"
  mv "$f" "archive/docs/$(dirname "$f" | sed 's|^\./||')/"
done

echo "Checking for duplicate test files and archiving them..."
find . -name "test_*" -not -name "test_consolidated_mcp_server.py" -type f -not -path "./tests/*" -not -path "./archive*" | while read f; do
  echo "Archiving $f"
  mkdir -p "archive/tests/"
  mv "$f" "archive/tests/"
done

echo "Cleanup complete. All necessary files for the consolidated MCP server solution have been preserved."
echo "Archived files can be found in the 'archive' directory."
echo ""
echo "Summary:"
echo "- Core MCP server: consolidated_final_mcp_server.py"
echo "- Start script: start_consolidated_mcp_server.sh"
echo "- Stop script: stop_consolidated_mcp_server.sh"
echo "- Test script: test_consolidated_mcp_server.py"
echo "- Documentation: README_CONSOLIDATED_MCP_SERVER.md"
echo ""
echo "To start the server: ./start_consolidated_mcp_server.sh"
echo "To stop the server: ./stop_consolidated_mcp_server.sh"
echo "To test the server: python3 test_consolidated_mcp_server.py"
