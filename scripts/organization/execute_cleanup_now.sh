#!/bin/bash
set -e

echo "🧹 EXECUTING IMMEDIATE ROOT DIRECTORY CLEANUP"
echo "=============================================="
echo "Found $(ls -1 *.py *.sh 2>/dev/null | wc -l) files to organize"

# Create backup with timestamp
BACKUP_DIR="root_cleanup_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "📦 Created backup directory: $BACKUP_DIR"

# Back up all files before moving
echo "💾 Backing up all files..."
for file in *.py *.sh *.txt *.json *.md; do
    [[ -f "$file" ]] && cp "$file" "$BACKUP_DIR/" 2>/dev/null || true
done

# Create organized directory structure
echo "🏗️  Creating organized directory structure..."
mkdir -p patches/{applied,mcp,fixes,enhancements}
mkdir -p utils/{check,debug,add_tools,maintenance,verify}
mkdir -p test/{unit/basic,functional/verification,integration,mcp}
mkdir -p scripts/{dev/{patches,verification,maintenance},organization,start,stop}
mkdir -p tools/{ipfs,mcp,unified}
mkdir -p config/{mcp,vscode}

echo "📁 Moving files to organized locations..."

# 1. MOVE TEST FILES
echo "Moving test files..."
mv basic_unit_tests.py test/unit/basic/ 2>/dev/null && echo "✓ basic_unit_tests.py → test/unit/basic/"
mv all_in_one_verify.py test/functional/verification/ 2>/dev/null && echo "✓ all_in_one_verify.py → test/functional/verification/"
mv conftest.py test/ 2>/dev/null && echo "✓ conftest.py → test/"
mv simple_conftest.py test/ 2>/dev/null && echo "✓ simple_conftest.py → test/"

# Move all test files
for file in test_*.py; do
    [[ -f "$file" ]] && mv "$file" test/unit/basic/ && echo "✓ $file → test/unit/basic/"
done

# Move verification files  
for file in *verify*.py simple_verify*.py; do
    [[ -f "$file" ]] && mv "$file" utils/verify/ && echo "✓ $file → utils/verify/"
done

# 2. MOVE CHECK AND DEBUG FILES
echo "Moving check and debug files..."
mv check_vscode_integration.py utils/check/ 2>/dev/null && echo "✓ check_vscode_integration.py → utils/check/"

for file in check_*.py; do
    [[ -f "$file" ]] && mv "$file" utils/check/ && echo "✓ $file → utils/check/"
done

for file in debug_*.py diagnose_*.py; do
    [[ -f "$file" ]] && mv "$file" utils/debug/ && echo "✓ $file → utils/debug/"
done

# 3. MOVE ADD TOOLS FILES
echo "Moving add tools files..."
for file in add_*.py; do
    [[ -f "$file" ]] && mv "$file" utils/add_tools/ && echo "✓ $file → utils/add_tools/"
done

# 4. MOVE FIX FILES TO PATCHES
echo "Moving fix files..."
for file in fix_*.py fix_*.sh; do
    [[ -f "$file" ]] && mv "$file" patches/fixes/ && echo "✓ $file → patches/fixes/"
done

# Move patch files
for file in patch_*.py; do
    [[ -f "$file" ]] && mv "$file" patches/applied/ && echo "✓ $file → patches/applied/"
done

# 5. MOVE MCP FILES
echo "Moving MCP files..."
for file in *mcp*.py *mcp*.sh *mcp*.json; do
    [[ -f "$file" ]] && mv "$file" patches/mcp/ && echo "✓ $file → patches/mcp/"
done

# Move direct mcp server files
for file in direct_mcp*.py; do
    [[ -f "$file" ]] && mv "$file" patches/mcp/ && echo "✓ $file → patches/mcp/"
done

# Move mcp backup files
for file in direct_mcp_server.py.bak.*; do
    [[ -f "$file" ]] && mv "$file" patches/mcp/ && echo "✓ $file → patches/mcp/"
done

# 6. MOVE ENHANCEMENT FILES
echo "Moving enhancement files..."
for file in enhance_*.py enhanced_*.py; do
    [[ -f "$file" ]] && mv "$file" patches/enhancements/ && echo "✓ $file → patches/enhancements/"
done

# 7. MOVE COMPLETION AND INTEGRATION FILES
echo "Moving completion files..."
for file in complete_*.py; do
    [[ -f "$file" ]] && mv "$file" scripts/dev/patches/ && echo "✓ $file → scripts/dev/patches/"
done

for file in integrate_*.py integration_*.py; do
    [[ -f "$file" ]] && mv "$file" scripts/dev/patches/ && echo "✓ $file → scripts/dev/patches/"
done

for file in final_*.py; do
    [[ -f "$file" ]] && mv "$file" scripts/dev/patches/ && echo "✓ $file → scripts/dev/patches/"
done

# 8. MOVE APPLY SCRIPTS
echo "Moving apply scripts..."
for file in apply_*.sh; do
    [[ -f "$file" ]] && mv "$file" scripts/dev/patches/ && echo "✓ $file → scripts/dev/patches/"
done

# 9. MOVE DIRECT AND RUN FILES
echo "Moving direct and run files..."
for file in direct_*.py; do
    [[ -f "$file" ]] && mv "$file" scripts/dev/verification/ && echo "✓ $file → scripts/dev/verification/"
done

for file in run_*.py; do
    [[ -f "$file" ]] && mv "$file" scripts/dev/verification/ && echo "✓ $file → scripts/dev/verification/"
done

# 10. MOVE START/STOP SCRIPTS
echo "Moving start/stop scripts..."
for file in start_*.sh start_*.py; do
    [[ -f "$file" ]] && mv "$file" scripts/start/ && echo "✓ $file → scripts/start/"
done

for file in stop_*.sh; do
    [[ -f "$file" ]] && mv "$file" scripts/stop/ && echo "✓ $file → scripts/stop/"
done

for file in restart_*.sh; do
    [[ -f "$file" ]] && mv "$file" scripts/start/ && echo "✓ $file → scripts/start/"
done

# 11. MOVE TOOL FILES
echo "Moving tool files..."
for file in *tools*.py; do
    [[ -f "$file" ]] && mv "$file" tools/ipfs/ && echo "✓ $file → tools/ipfs/"
done

for file in unified_*.py; do
    [[ -f "$file" ]] && mv "$file" tools/unified/ && echo "✓ $file → tools/unified/"
done

# 12. MOVE CONFIG FILES
echo "Moving config files..."
for file in *config*.py *settings*.json; do
    [[ -f "$file" ]] && mv "$file" config/vscode/ && echo "✓ $file → config/vscode/"
done

# 13. MOVE REMAINING SPECIFIC FILES
echo "Moving remaining files..."
for file in load_*.py register_*.py implement_*.py install_*.py; do
    [[ -f "$file" ]] && mv "$file" utils/maintenance/ && echo "✓ $file → utils/maintenance/"
done

for file in update_*.py ensure_*.py standardize_*.py; do
    [[ -f "$file" ]] && mv "$file" utils/maintenance/ && echo "✓ $file → utils/maintenance/"
done

for file in make_*.sh; do
    [[ -f "$file" ]] && mv "$file" scripts/organization/ && echo "✓ $file → scripts/organization/"
done

for file in *example*.py working_*.py; do
    [[ -f "$file" ]] && mv "$file" examples/ && echo "✓ $file → examples/"
done

# 14. MOVE REMAINING TEXT FILES
echo "Moving remaining text files..."
for file in *.txt; do
    [[ -f "$file" ]] && mv "$file" test/results/ && echo "✓ $file → test/results/"
done

# Create missing directories for moved files
mkdir -p test/results examples

# 15. CREATE CONVENIENCE SYMLINKS
echo "🔗 Creating convenience symlinks..."
[[ -f test/unit/basic/basic_unit_tests.py ]] && ln -sf test/unit/basic/basic_unit_tests.py basic_unit_tests.py && echo "✓ Created basic_unit_tests.py symlink"
[[ -f test/functional/verification/all_in_one_verify.py ]] && ln -sf test/functional/verification/all_in_one_verify.py verify.py && echo "✓ Created verify.py symlink"
[[ -f utils/check/check_vscode_integration.py ]] && ln -sf utils/check/check_vscode_integration.py check_vscode.py && echo "✓ Created check_vscode.py symlink"

# 16. CREATE README FILES
echo "📚 Creating README files..."
cat > patches/README.md << 'EOF'
# Patches Directory

Applied patches, fixes, and enhancements for the IPFS Kit Python project.

## Structure
- `applied/`: Applied patch scripts
- `mcp/`: MCP server integration patches  
- `fixes/`: Bug fixes and syntax corrections
- `enhancements/`: Feature enhancements and improvements

## Usage
```bash
cd patches/fixes
python3 fix_all_syntax_errors.py
```
EOF

cat > utils/README.md << 'EOF'
# Utilities Directory

Development utilities organized by purpose.

## Structure
- `check/`: Validation and checking scripts
- `debug/`: Debugging and diagnostic tools
- `add_tools/`: Scripts for adding new functionality
- `maintenance/`: Maintenance and update scripts
- `verify/`: Verification and testing utilities

## Usage
```bash
python3 utils/check/check_vscode_integration.py
python3 utils/debug/debug_vscode_connection.py
```
EOF

cat > test/README.md << 'EOF'
# Test Directory

Comprehensive test suite for the IPFS Kit Python project.

## Structure
- `unit/basic/`: Basic unit tests
- `functional/verification/`: Functional verification tests
- `integration/`: Integration tests
- `mcp/`: MCP-specific tests
- `results/`: Test output and results

## Running Tests
```bash
python3 test/unit/basic/basic_unit_tests.py
python3 -m pytest test/
```
EOF

cat > scripts/README.md << 'EOF'
# Scripts Directory

Development and operational scripts.

## Structure
- `dev/patches/`: Development patch scripts
- `dev/verification/`: Development verification scripts
- `dev/maintenance/`: Development maintenance scripts
- `start/`: Server and service start scripts
- `stop/`: Server and service stop scripts
- `organization/`: Project organization scripts

## Usage
```bash
./scripts/start/start_mcp_server.sh
./scripts/stop/stop_mcp_server.sh
```
EOF

cat > tools/README.md << 'EOF'
# Tools Directory

Tool implementations and integrations.

## Structure
- `ipfs/`: IPFS-specific tools and integrations
- `mcp/`: MCP server tools
- `unified/`: Unified tool implementations

## Usage
```bash
python3 tools/ipfs/ipfs_tools_registry.py
python3 tools/unified/unified_ipfs_tools.py
```
EOF

echo ""
echo "✅ CLEANUP COMPLETED!"
echo "===================="
echo "📊 Summary:"
echo "  - Created organized directory structure"
echo "  - Moved $(find patches utils test scripts tools config -name "*.py" -o -name "*.sh" | wc -l) files to organized locations"
echo "  - Created convenience symlinks"
echo "  - Added README files for documentation"
echo "  - Backed up all files to: $BACKUP_DIR"

echo ""
echo "📁 Current root directory:"
ls -la

echo ""
echo "🏗️ Organized structure:"
find . -type d -not -path "./.git*" -not -path "./$BACKUP_DIR*" | head -20 | sort

echo ""
echo "🔗 Test the symlinks:"
echo "  ./basic_unit_tests.py --help"
echo "  ./verify.py --help"
echo "  ./check_vscode.py --help"

echo ""
echo "💾 To restore if needed: cp $BACKUP_DIR/* ."
