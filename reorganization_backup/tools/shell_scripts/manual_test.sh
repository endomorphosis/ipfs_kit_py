#!/bin/bash
# Manual test of the final MCP server

echo "=== FINAL MCP SERVER TEST ==="
echo "Date: $(date)"
echo "Directory: $(pwd)"
echo ""

# Test 1: Check virtual environment
echo "Test 1: Virtual Environment Check"
if [ -d ".venv" ]; then
    echo "✅ Virtual environment exists"
    .venv/bin/python --version > venv_version.txt 2>&1
    echo "Python version: $(cat venv_version.txt)"
else
    echo "❌ No virtual environment found"
fi
echo ""

# Test 2: Check server file
echo "Test 2: Server File Check"
if [ -f "final_mcp_server.py" ]; then
    size=$(stat -c%s final_mcp_server.py)
    echo "✅ Server file exists (${size} bytes)"
else
    echo "❌ Server file missing"
fi
echo ""

# Test 3: Import test
echo "Test 3: Module Import Test"
.venv/bin/python -c "
try:
    import final_mcp_server
    print('✅ Module imports successfully')
    print(f'Server version: {final_mcp_server.__version__}')
except Exception as e:
    print(f'❌ Import failed: {e}')
" > import_result.txt 2>&1
cat import_result.txt
echo ""

# Test 4: Help command
echo "Test 4: Help Command Test"
timeout 10s .venv/bin/python final_mcp_server.py --help > help_result.txt 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Help command succeeded"
    echo "Help output preview:"
    head -5 help_result.txt
else
    echo "❌ Help command failed"
    echo "Error output:"
    cat help_result.txt
fi
echo ""

# Test 5: Version command
echo "Test 5: Version Command Test"
timeout 10s .venv/bin/python final_mcp_server.py --version > version_result.txt 2>&1
if [ $? -eq 0 ]; then
    echo "✅ Version command succeeded"
    cat version_result.txt
else
    echo "❌ Version command failed"
    cat version_result.txt
fi
echo ""

echo "=== TEST SUMMARY ==="
echo "All manual tests completed. Check individual result files for details."
