#!/usr/bin/env python3
"""
Quick diagnostic script to check MCP server dependencies
"""

import sys
import os
import importlib

print("=== MCP Server Quick Diagnostic ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# Check main dependencies
dependencies = [
    ("fastapi", "pip install fastapi"),
    ("uvicorn", "pip install uvicorn[standard]"),
    ("jsonrpcserver", "pip install jsonrpcserver")
]

for module_name, install_cmd in dependencies:
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", "unknown")
        print(f"✅ {module_name} is available (version: {version})")
    except ImportError as e:
        print(f"❌ {module_name} is not available: {e}")
        print(f"   To install: {install_cmd}")

# Check server script
server_script = "final_mcp_server.py"
if os.path.exists(server_script):
    print(f"✅ Server script {server_script} exists")
    # Check permissions
    if not os.access(server_script, os.X_OK):
        print(f"⚠️ Script {server_script} is not executable")
        print(f"   To fix: chmod +x {server_script}")
else:
    print(f"❌ Server script {server_script} not found")

# Check if server is running
pid_file = "final_mcp_server.pid"
if os.path.exists(pid_file):
    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
        
        try:
            os.kill(pid, 0)  # This doesn't kill the process, just checks if it exists
            print(f"✅ Server process with PID {pid} is running")
        except OSError:
            print(f"⚠️ PID file exists but process {pid} is not running")
    except Exception as e:
        print(f"❌ Error checking PID file: {e}")
else:
    print("ℹ️ No PID file found. Server is not running or was not properly started")
