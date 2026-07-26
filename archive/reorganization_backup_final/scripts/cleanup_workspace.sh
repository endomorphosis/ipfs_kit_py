#!/bin/bash
# Workspace Cleanup Script for IPFS Kit Python
# This script organizes files into proper subdirectories

set -e  # Exit on any error

echo "🧹 Starting IPFS Kit Python workspace cleanup..."

# Create target directories
echo "📁 Creating target directories..."
mkdir -p docs
mkdir -p scripts
mkdir -p tools
mkdir -p docker
mkdir -p backup
mkdir -p tests/integration
mkdir -p tests/unit

# Move documentation files
echo "📚 Moving documentation files to docs/..."
for file in *REPORT*.md *STATUS*.md *GUIDE*.md *COMPLETE*.md *SUMMARY*.md \
           ENHANCED_SOLUTION.md MCP_*.md VSCODE_*.md README_*.md WORKSPACE_*.md; do
    if [ -f "$file" ]; then
        mv "$file" docs/ 2>/dev/null || true
    fi
done

# Move shell scripts
echo "🔧 Moving shell scripts to scripts/..."
for file in *.sh; do
    if [ -f "$file" ] && [ "$file" != "cleanup_workspace.sh" ]; then
        mv "$file" scripts/ 2>/dev/null || true
    fi
done

# Move test files
echo "🧪 Moving test files to tests/..."
for file in test_*.py *test*.py comprehensive_*test*.py enhanced_*test*.py \
           final_*test*.py minimal_*test*.py production_*verification*.py \
           simple_*test*.py *validation*.py; do
    if [ -f "$file" ]; then
        # Determine if it's integration or unit test
        if [[ "$file" == *"integration"* || "$file" == *"comprehensive"* || "$file" == *"end_to_end"* ]]; then
            mv "$file" tests/integration/ 2>/dev/null || true
        else
            mv "$file" tests/unit/ 2>/dev/null || true
        fi
    fi
done

# Move development tools
echo "🛠️  Moving development tools to tools/..."
for file in apply_*.py binary_*.py check_*.py create_*.py debug_*.py \
           diagnose_*.py direct_*.py enhance_*.py enhanced_*.py fix_*.py \
           fixed_*.py fs_*.py generate_*.py ipfs_*tools*.py ipfs_*adapters*.py \
           launch_*.py mcp_*demo*.py mcp_*runner*.py organize_*.py \
           register_*.py run_enhanced*.py simple_tool*.py tool_*.py \
           unified_*.py validate_*.py verify_*.py multi_*.py; do
    if [ -f "$file" ] && [[ "$file" != *"test"* ]] && [[ "$file" != *"validation"* ]]; then
        mv "$file" tools/ 2>/dev/null || true
    fi
done

# Move Docker files
echo "🐳 Moving Docker files to docker/..."
for file in Dockerfile* docker-compose*.yml; do
    if [ -f "$file" ]; then
        mv "$file" docker/ 2>/dev/null || true
    fi
done

# Move backup and archive directories
echo "📦 Moving backup and archive directories to backup/..."
for dir in applied_patches archive* backup_* enhanced fixes mcp_archive mcp_final_* patches server_variants; do
    if [ -d "$dir" ]; then
        mv "$dir" backup/ 2>/dev/null || true
    fi
done

# Move log files to backup
echo "📄 Moving log files to backup/..."
for file in *.log; do
    if [ -f "$file" ]; then
        mv "$file" backup/ 2>/dev/null || true
    fi
done

# Clean up any remaining Python cache directories
echo "🗑️  Cleaning up cache directories..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Move root-level Python files that are tools/utilities
echo "🐍 Moving utility Python files to tools/..."
mv check_vscode.py tools/ 2>/dev/null || true
mv verify.py tools/ 2>/dev/null || true

echo "✅ Workspace cleanup completed!"
echo ""
echo "📊 Summary:"
echo "   📚 Documentation files moved to: docs/"
echo "   🔧 Shell scripts moved to: scripts/"
echo "   🧪 Test files moved to: tests/"
echo "   🛠️  Development tools moved to: tools/"
echo "   🐳 Docker files moved to: docker/"
echo "   📦 Backup/archive files moved to: backup/"
echo ""
echo "🏠 Remaining in root directory:"
ls -la | grep "^-" | grep -E "\.(md|py|toml|cfg|ini|txt)$|LICENSE|Makefile" | wc -l
echo "   files (essential project files only)"
echo ""
echo "🎉 Your workspace is now organized and clean!"
