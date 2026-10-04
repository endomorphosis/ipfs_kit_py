#!/usr/bin/env python3
"""Test the enhanced MCP server after the fix"""

import os
import sys
import traceback

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

print("🧪 Testing enhanced MCP server after fix...")

try:
    print("📦 Importing enhanced MCP server...")
    from enhanced_mcp_server_with_daemon_init import EnhancedMCPServer, DaemonManager
    print("✅ Enhanced MCP server imported successfully")
    
    print("📦 Creating daemon manager...")
    daemon_manager = DaemonManager()
    print("✅ Daemon manager created")
    
    print("📦 Creating enhanced MCP server...")
    server = EnhancedMCPServer()
    print("✅ Enhanced MCP server created")
    
    print("🎉 All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n🔍 Full traceback:")
    traceback.print_exc()
