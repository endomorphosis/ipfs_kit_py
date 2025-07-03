#!/bin/bash

echo "=== Final MCP Server Testing ==="
echo "Current directory: $(pwd)"
echo "Python executable: $(which python3)"

# Test virtual environment
if [ -d ".venv" ]; then
    echo "✅ Virtual environment exists"
    echo "Python in venv: $(.venv/bin/python --version 2>&1 || echo 'Failed')"
else
    echo "❌ No virtual environment found"
fi

# Test server file
if [ -f "final_mcp_server.py" ]; then
    echo "✅ Server file exists"
    echo "File size: $(wc -l < final_mcp_server.py) lines"
else
    echo "❌ Server file missing"
fi

# Test syntax
echo "=== Testing Python syntax ==="
python3 -m py_compile final_mcp_server.py && echo "✅ Syntax OK" || echo "❌ Syntax Error"

# Test imports
echo "=== Testing imports ==="
python3 -c "
import sys
print(f'Python version: {sys.version}')
try:
    import fastapi
    print('✅ FastAPI available')
except ImportError:
    print('❌ FastAPI not available')
    
try:
    import uvicorn
    print('✅ Uvicorn available')
except ImportError:
    print('❌ Uvicorn not available')
"

echo "=== Testing server help ==="
timeout 10s python3 final_mcp_server.py --help || echo "Help command failed or timed out"

echo "=== End of test ==="
