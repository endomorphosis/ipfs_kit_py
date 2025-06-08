#!/usr/bin/env python3
"""
Final MCP Server Verification Script
Comprehensive testing of MCP server integration with VS Code
"""

import requests
import json
import logging
import sys
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)

def check_server_health():
    """Check if MCP server is running and responding"""
    try:
        response = requests.get("http://localhost:3001", timeout=5)
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ MCP Server Status: Running (PID: {data.get('pid', 'unknown')})")
            logger.info(f"✅ Server Version: {data.get('version', 'unknown')}")
            logger.info(f"✅ Available Endpoints: {', '.join(data.get('endpoints', {}).keys())}")
            return True
        else:
            logger.error(f"❌ Server returned status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Cannot connect to MCP server: {e}")
        return False

def test_mcp_endpoints():
    """Test various MCP endpoints"""
    endpoints = [
        ("/api/v0/health", "Health check"),
        ("/api/v0/initialize", "VS Code initialize"),
        ("/jsonrpc", "JSON-RPC endpoint")
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"http://localhost:3001{endpoint}", timeout=5)
            status = "✅" if response.status_code in [200, 405] else "❌"
            logger.info(f"{status} {description}: Status {response.status_code}")
        except Exception as e:
            logger.error(f"❌ {description}: {e}")

def check_vscode_settings():
    """Check VS Code settings for MCP configuration"""
    settings_path = Path.home() / ".config/Code - Insiders/User/settings.json"
    
    if not settings_path.exists():
        logger.error(f"❌ VS Code settings not found at: {settings_path}")
        return False
    
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        mcp_config = settings.get('mcp', {})
        servers = mcp_config.get('servers', {})
        
        if 'ipfs-kit-mcp-server' in servers:
            server_config = servers['ipfs-kit-mcp-server']
            logger.info(f"✅ VS Code MCP Configuration Found")
            logger.info(f"✅ Server URL: {server_config.get('url', 'Not set')}")
            return True
        else:
            logger.error("❌ IPFS Kit MCP server not configured in VS Code settings")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error reading VS Code settings: {e}")
        return False

def check_extensions():
    """Check for VS Code extensions"""
    extensions_dir = Path.home() / ".vscode-insiders/extensions"
    
    if not extensions_dir.exists():
        logger.warning("⚠️  VS Code Insiders extensions directory not found")
        return False
    
    extensions = list(extensions_dir.iterdir())
    copilot_extensions = [ext for ext in extensions if 'copilot' in ext.name.lower()]
    
    logger.info(f"✅ Found {len(copilot_extensions)} Copilot extensions:")
    for ext in copilot_extensions:
        logger.info(f"   • {ext.name}")
    
    return len(copilot_extensions) > 0

def test_sample_workspace():
    """Check if sample workspace exists and is properly set up"""
    workspace_path = Path("/tmp/mcp_sample_workspace")
    
    if workspace_path.exists():
        files = list(workspace_path.iterdir())
        logger.info(f"✅ Sample workspace exists with {len(files)} files:")
        for file in files:
            logger.info(f"   • {file.name}")
        return True
    else:
        logger.warning("⚠️  Sample workspace not found at /tmp/mcp_sample_workspace")
        return False

def create_usage_commands():
    """Create a script with usage commands for VS Code"""
    commands_script = """#!/bin/bash
# VS Code MCP Integration Usage Commands

echo "🚀 VS Code MCP Integration - Quick Start Commands"
echo "=================================================="
echo ""

echo "1. 📂 Open Sample Workspace:"
echo "   code-insiders /tmp/mcp_sample_workspace"
echo ""

echo "2. 🔧 Test MCP Server Connection:"
echo "   curl http://localhost:3001"
echo ""

echo "3. 📋 In VS Code, press Ctrl+Shift+P and try:"
echo "   • Search for 'MCP' commands"
echo "   • Search for 'Copilot' commands"
echo "   • Open Copilot Chat (Ctrl+Shift+I)"
echo ""

echo "4. 💬 In Copilot Chat, try these prompts:"
echo "   • 'Connect to MCP server at http://localhost:3001'"
echo "   • 'Use MCP tools to track this file for changes'"
echo "   • 'Show me available MCP tools'"
echo ""

echo "5. 🛠️  Available MCP Tool Categories:"
echo "   • FS Journal Tools (file tracking & history)"
echo "   • IPFS Bridge Tools (filesystem to IPFS mapping)"
echo "   • Multi-Backend Tools (multiple storage backends)"
echo ""

echo "📝 For detailed instructions, see:"
echo "   VSCODE_MCP_READY.md"
echo "   VSCODE_MCP_INTEGRATION_GUIDE.md"
"""
    
    with open("/home/barberb/ipfs_kit_py/vscode_mcp_commands.sh", "w") as f:
        f.write(commands_script)
    
    os.chmod("/home/barberb/ipfs_kit_py/vscode_mcp_commands.sh", 0o755)
    logger.info("✅ Created usage commands script: vscode_mcp_commands.sh")

def main():
    """Run comprehensive MCP integration verification"""
    logger.info("🔍 Final MCP Server Integration Verification")
    logger.info("=" * 60)
    
    all_checks = []
    
    # Check server health
    all_checks.append(check_server_health())
    
    # Test MCP endpoints  
    test_mcp_endpoints()
    
    # Check VS Code settings
    all_checks.append(check_vscode_settings())
    
    # Check extensions
    all_checks.append(check_extensions())
    
    # Check sample workspace
    all_checks.append(test_sample_workspace())
    
    # Create usage commands
    create_usage_commands()
    
    logger.info("=" * 60)
    
    if all(all_checks):
        logger.info("🎉 ALL SYSTEMS GO! MCP Integration Complete!")
        logger.info("")
        logger.info("🚀 Next Steps:")
        logger.info("1. Run: ./vscode_mcp_commands.sh")
        logger.info("2. Open VS Code: code-insiders /tmp/mcp_sample_workspace")
        logger.info("3. Press Ctrl+Shift+P and search for 'MCP' or 'Copilot'")
        logger.info("4. Try MCP tools through Copilot Chat")
        logger.info("")
        logger.info("📖 Documentation:")
        logger.info("   • VSCODE_MCP_READY.md - Quick start guide")
        logger.info("   • VSCODE_MCP_INTEGRATION_GUIDE.md - Detailed setup")
        return 0
    else:
        logger.error("❌ Some checks failed. Review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
