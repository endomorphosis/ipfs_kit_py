#!/bin/bash
# Enhanced Workspace Cleanup Script for IPFS Kit Python
# This script completes the organization of remaining files

set -e  # Exit on any error

echo "🧹 Starting enhanced IPFS Kit Python workspace cleanup..."

# Create additional target directories
echo "📁 Creating additional target directories..."
mkdir -p archive
mkdir -p backup/logs
mkdir -p backup/old_versions
mkdir -p backup/test_results
mkdir -p config/deployment
mkdir -p examples/data
mkdir -p tools/migration
mkdir -p tools/utilities

# Move remaining Python server files to appropriate locations
echo "🐍 Moving server files..."
if [ -f "final_mcp_server.py" ]; then
    mv final_mcp_server.py src/ 2>/dev/null || true
fi
if [ -f "final_mcp_server_enhanced.py" ]; then
    mv final_mcp_server_enhanced.py src/ 2>/dev/null || true
fi
if [ -f "final_mcp_server_simplified.py" ]; then
    mv final_mcp_server_simplified.py src/ 2>/dev/null || true
fi

# Move test result files to backup
echo "📊 Moving test results to backup..."
for file in *test_results*.json mcp_test_results*.json ultimate_mcp_test_results.json; do
    if [ -f "$file" ]; then
        mv "$file" backup/test_results/ 2>/dev/null || true
    fi
done

# Move directories to appropriate locations
echo "📂 Organizing directories..."

# Archive old development directories
for dir in applied_patches archive_clutter backup_files backup_patches enhanced fixes \
          mcp_archive mcp_development mcp_final_* patches server_variants; do
    if [ -d "$dir" ]; then
        mv "$dir" archive/ 2>/dev/null || true
    fi
done

# Move development tool directories
for dir in development_tools migration_tools minimal_scripts pytest_scripts \
          run_scripts shell_scripts test_scripts tool_scripts utils; do
    if [ -d "$dir" ]; then
        mv "$dir" tools/ 2>/dev/null || true
    fi
done

# Move configuration directories
for dir in config_files helm kubernetes proxies; do
    if [ -d "$dir" ]; then
        mv "$dir" config/deployment/ 2>/dev/null || true
    fi
done

# Move data and test directories
for dir in ipfs_test_data test_discovery test_results; do
    if [ -d "$dir" ]; then
        mv "$dir" examples/data/ 2>/dev/null || true
    fi
done

# Move development/debug directories to archive
for dir in debug ipfs_development run static venv; do
    if [ -d "$dir" ]; then
        mv "$dir" archive/ 2>/dev/null || true
    fi
done

# Move remaining directories
for dir in bin data dist examples/src test; do
    if [ -d "$dir" ] && [ "$dir" != "src" ]; then
        if [[ "$dir" == *"test"* ]]; then
            mv "$dir" tests/ 2>/dev/null || true
        else
            mv "$dir" archive/ 2>/dev/null || true
        fi
    fi
done

# Remove empty directories
echo "🗑️  Removing empty directories..."
find . -maxdepth 1 -type d -empty -delete 2>/dev/null || true

# Clean up any remaining cache files
echo "🧽 Final cleanup..."
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

echo "✅ Enhanced workspace cleanup completed!"
echo ""
echo "📊 Final Summary:"
echo "   📚 Documentation: docs/"
echo "   🔧 Scripts: scripts/"
echo "   🧪 Tests: tests/"
echo "   🛠️  Tools: tools/"
echo "   🐳 Docker: docker/"
echo "   📦 Archive: archive/"
echo "   📄 Backup: backup/"
echo "   ⚙️  Config: config/"
echo "   📖 Examples: examples/"
echo "   🐍 Source: src/"
echo ""
echo "🏠 Essential files remaining in root:"
ls -la | grep "^-" | grep -v cleanup | head -10
echo ""
echo "🎉 Your workspace is now fully organized and clean!"
