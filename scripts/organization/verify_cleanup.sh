#!/bin/bash

# Final Cleanup Verification Script
# Verifies that the file reorganization was successful and files are functional

echo "=== IPFS Kit Python Cleanup Verification ==="
echo "Date: $(date)"
echo ""

# Check directory structure
echo "1. Verifying directory structure..."
EXPECTED_DIRS=(
    "patches/applied"
    "patches/mcp" 
    "patches/fixes"
    "patches/enhancements"
    "utils/check"
    "utils/debug"
    "utils/add_tools"
    "utils/maintenance"
    "utils/verify"
    "test/unit/basic"
    "test/functional/verification"
    "test/integration"
    "test/mcp"
    "test/pytest_configs"
    "test/results"
    "scripts/dev/patches"
    "scripts/dev/verification"
    "scripts/dev/maintenance"
    "scripts/organization"
    "scripts/start"
    "scripts/stop"
    "tools/ipfs"
    "tools/mcp"
    "tools/unified"
    "config/mcp"
    "config/vscode"
    "docs/readmes"
    "examples"
)

missing_dirs=0
for dir in "${EXPECTED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "❌ Missing directory: $dir"
        missing_dirs=$((missing_dirs + 1))
    else
        echo "✅ Found directory: $dir"
    fi
done

echo ""
echo "2. Checking file counts in organized directories..."

# Count files in major directories
echo "Patches directory: $(find patches -name "*.py" -o -name "*.sh" | wc -l) files"
echo "Utils directory: $(find utils -name "*.py" -o -name "*.sh" | wc -l) files"
echo "Test directory: $(find test -name "*.py" | wc -l) files"
echo "Scripts directory: $(find scripts -name "*.py" -o -name "*.sh" | wc -l) files"
echo "Tools directory: $(find tools -name "*.py" -o -name "*.sh" | wc -l) files"

echo ""
echo "3. Checking remaining files in root directory..."
root_files=$(ls -1 | grep -E '\.(py|sh)$' | wc -l)
echo "Python/Shell files remaining in root: $root_files"

if [ $root_files -gt 5 ]; then
    echo "⚠️  Warning: Many files still in root directory"
    ls -1 | grep -E '\.(py|sh)$'
else
    echo "✅ Root directory is clean"
fi

echo ""
echo "4. Verifying convenience symlinks..."
if [ -L "verify.py" ]; then
    echo "✅ verify.py symlink exists"
else
    echo "❌ verify.py symlink missing"
fi

if [ -L "check_vscode.py" ]; then
    echo "✅ check_vscode.py symlink exists"
else
    echo "❌ check_vscode.py symlink missing"
fi

if [ -L "register_tools.sh" ]; then
    echo "✅ register_tools.sh symlink exists"
else
    echo "❌ register_tools.sh symlink missing"
fi

echo ""
echo "5. Testing key functionality..."

# Test that Python files can be imported
echo "Testing Python file syntax..."
python_errors=0

# Check a few key moved files for syntax errors
test_files=(
    "test/unit/basic/basic_unit_tests.py"
    "utils/check/check_vscode_integration.py"
    "patches/fixes/fixed_pytest_patch.py"
)

for file in "${test_files[@]}"; do
    if [ -f "$file" ]; then
        if python -m py_compile "$file" 2>/dev/null; then
            echo "✅ $file: syntax OK"
        else
            echo "❌ $file: syntax error"
            python_errors=$((python_errors + 1))
        fi
    else
        echo "❌ $file: file not found"
        python_errors=$((python_errors + 1))
    fi
done

echo ""
echo "6. Summary..."
echo "Missing directories: $missing_dirs"
echo "Python syntax errors: $python_errors"
echo "Root cleanup status: $([ $root_files -le 5 ] && echo 'Clean' || echo 'Needs attention')"

if [ $missing_dirs -eq 0 ] && [ $python_errors -eq 0 ] && [ $root_files -le 5 ]; then
    echo ""
    echo "🎉 CLEANUP VERIFICATION SUCCESSFUL!"
    echo "✅ All directories created"
    echo "✅ Files moved successfully"
    echo "✅ Python syntax checks passed"
    echo "✅ Root directory cleaned"
else
    echo ""
    echo "⚠️  CLEANUP VERIFICATION FOUND ISSUES"
    echo "Please review the errors above"
fi

echo ""
echo "=== Verification Complete ==="
