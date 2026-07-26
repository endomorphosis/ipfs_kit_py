#!/bin/bash
# Final verification checklist for IPFS Kit MCP Server

echo "🎯 IPFS Kit MCP Server - Final Verification Checklist"
echo "===================================================="

# Function to check if a file exists
check_file() {
    if [ -f "$1" ]; then
        echo "✅ $1 exists"
        return 0
    else
        echo "❌ $1 missing"
        return 1
    fi
}

# Function to check Python syntax
check_python_syntax() {
    if python3 -m py_compile "$1" 2>/dev/null; then
        echo "✅ $1 syntax OK"
        return 0
    else
        echo "❌ $1 syntax error"
        return 1
    fi
}

echo ""
echo "📁 Checking core files..."
files_ok=0
total_files=0

# Core implementation files
core_files=(
    "final_mcp_server.py"
    "unified_ipfs_tools.py"
    "run_final_solution.sh"
    "fixed_ipfs_model.py"
    "ipfs_tools_registry.py"
)

for file in "${core_files[@]}"; do
    total_files=$((total_files + 1))
    if check_file "$file"; then
        files_ok=$((files_ok + 1))
    fi
done

echo ""
echo "🐍 Checking Python syntax..."
syntax_ok=0
total_syntax=0

python_files=(
    "final_mcp_server.py"
    "unified_ipfs_tools.py"
    "fixed_ipfs_model.py"
    "ipfs_tools_registry.py"
)

for file in "${python_files[@]}"; do
    if [ -f "$file" ]; then
        total_syntax=$((total_syntax + 1))
        if check_python_syntax "$file"; then
            syntax_ok=$((syntax_ok + 1))
        fi
    fi
done

echo ""
echo "🧪 Checking test files..."
test_files=(
    "comprehensive_ipfs_test.py"
    "test_edge_cases.py"
    "final_validation.py"
    "improved_run_solution.sh"
)

test_ok=0
total_tests=0

for file in "${test_files[@]}"; do
    total_tests=$((total_tests + 1))
    if check_file "$file"; then
        test_ok=$((test_ok + 1))
    fi
done

echo ""
echo "📋 Checking executability..."
executable_files=(
    "run_final_solution.sh"
    "improved_run_solution.sh"
)

exec_ok=0
total_exec=0

for file in "${executable_files[@]}"; do
    if [ -f "$file" ]; then
        total_exec=$((total_exec + 1))
        if [ -x "$file" ]; then
            echo "✅ $file is executable"
            exec_ok=$((exec_ok + 1))
        else
            echo "⚠️  $file not executable (fixing...)"
            chmod +x "$file"
            if [ -x "$file" ]; then
                echo "✅ $file now executable"
                exec_ok=$((exec_ok + 1))
            else
                echo "❌ $file could not be made executable"
            fi
        fi
    fi
done

echo ""
echo "📊 VERIFICATION SUMMARY"
echo "======================"
echo "Core files:      $files_ok/$total_files"
echo "Python syntax:   $syntax_ok/$total_syntax"
echo "Test files:      $test_ok/$total_tests"
echo "Executability:   $exec_ok/$total_exec"

total_checks=$((total_files + total_syntax + total_tests + total_exec))
total_passed=$((files_ok + syntax_ok + test_ok + exec_ok))

echo ""
echo "Overall score:   $total_passed/$total_checks"

if [ $total_passed -eq $total_checks ]; then
    echo ""
    echo "🎉 ALL VERIFICATIONS PASSED!"
    echo "✅ The IPFS Kit MCP Server is ready for use."
    echo ""
    echo "🚀 To start the server:"
    echo "   ./run_final_solution.sh --start"
    echo ""
    echo "🧪 To run tests:"
    echo "   python3 comprehensive_ipfs_test.py"
    echo "   python3 final_validation.py"
    exit 0
else
    echo ""
    echo "⚠️  Some verifications failed."
    echo "Please review the errors above."
    exit 1
fi
