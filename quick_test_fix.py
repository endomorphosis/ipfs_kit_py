#!/usr/bin/env python3
"""Quick test for enhanced MCP server"""

import os
import sys
import traceback

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

print("🧪 Testing enhanced MCP server fix...")

try:
    print("📦 Step 1: Testing ipfs_kit import...")
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    print("✅ ipfs_kit imported successfully")
    
    print("📦 Step 2: Testing ipfs_kit instantiation...")
    metadata = {"role": "master"}
    kit = ipfs_kit(metadata=metadata)
    print(f"✅ ipfs_kit instantiated with role: {kit.role}")
    
    print("📦 Step 3: Testing enhanced MCP server import...")
    from enhanced_mcp_server_with_daemon_init import EnhancedMCPServer
    print("✅ EnhancedMCPServer imported successfully")
    
    print("📦 Step 4: Testing server initialization...")
    server = EnhancedMCPServer()
    print("✅ Server initialized successfully")
    
    print("🎉 All tests passed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("\n🔍 Full traceback:")
    traceback.print_exc()
