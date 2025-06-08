#!/usr/bin/env python3
"""
VS Code MCP Integration Test
"""

import requests
import json
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_server_health():
    """Test basic server connectivity"""
    try:
        response = requests.get("http://localhost:3001", timeout=10)
        logger.info(f"✅ Server Health Check: Status {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ Server Health Check Failed: {e}")
        return False

def verify_vs_code_settings():
    """Verify VS Code settings are properly configured"""
    try:
        with open("/home/barberb/.config/Code - Insiders/User/settings.json", 'r') as f:
            settings = json.load(f)
        
        servers = settings.get("mcp", {}).get("servers", {})
        
        if "ipfs-kit-mcp-server" in servers:
            if servers["ipfs-kit-mcp-server"].get("url") == "http://localhost:3001":
                logger.info("✅ VS Code settings properly configured for MCP server")
                return True
        
        logger.error("❌ MCP server configuration issue in VS Code settings")
        return False
    except Exception as e:
        logger.error(f"❌ Error reading VS Code settings: {e}")
        return False

def main():
    logger.info("🔍 Testing MCP Server Integration with VS Code")
    health_ok = test_server_health()
    settings_ok = verify_vs_code_settings()
    
    if health_ok and settings_ok:
        logger.info("🎉 MCP Integration Ready!")
        logger.info("Use Ctrl+Shift+P and search for 'MCP' commands in VS Code")
        return True
    else:
        logger.error("❌ MCP Integration Issues Found")
        return False

if __name__ == "__main__":
    main()
