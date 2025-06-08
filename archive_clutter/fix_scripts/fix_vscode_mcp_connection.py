#!/usr/bin/env python3
"""
Fix VS Code MCP Connection

This script updates the VS Code MCP configuration to ensure proper connection
to the MCP server, specifically adding the jsonRpcUrl field required for
the initialize request to complete.
"""

import os
import json
import logging
import glob
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_mcp_settings():
    """Find all possible locations of MCP settings files."""
    possible_paths = [
        # For VS Code stable
        os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"),
        # For VS Code Insiders
        os.path.expanduser("~/.config/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"),
        # For VS Code on macOS
        os.path.expanduser("~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"),
        # For VS Code Insiders on macOS
        os.path.expanduser("~/Library/Application Support/Code - Insiders/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json"),
    ]
    
    # Also try to find by globbing
    try:
        home = os.path.expanduser("~")
        for pattern in [
            f"{home}/.config/Code*/User/globalStorage/*/settings/cline_mcp_settings.json",
            f"{home}/Library/Application Support/Code*/User/globalStorage/*/settings/cline_mcp_settings.json"
        ]:
            possible_paths.extend(glob.glob(pattern))
    except Exception as e:
        logger.warning(f"Error searching for settings files: {e}")
    
    found_paths = [p for p in possible_paths if os.path.exists(p)]
    return found_paths

def fix_mcp_settings(settings_path):
    """Fix MCP settings by adding jsonRpcUrl and ensuring proper configuration."""
    try:
        # Read existing settings
        with open(settings_path, 'r') as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in {settings_path}, creating new settings")
                settings = {"mcpServers": {}}
    except FileNotFoundError:
        logger.info(f"Settings file {settings_path} not found, creating new settings")
        # Create default settings
        settings = {"mcpServers": {}}
    
    # Check if mcpServers exists and ensure it's a dictionary
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}
    
    # Handle case where mcpServers is a list instead of a dict
    if isinstance(settings["mcpServers"], list):
        logger.warning("mcpServers is a list, converting to dictionary")
        # Convert to dictionary using server name as key
        converted = {}
        for server in settings["mcpServers"]:
            if isinstance(server, dict) and "name" in server:
                converted[server["name"]] = server
            else:
                # If there's no name, generate a unique key
                converted[f"server_{id(server)}"] = server
        settings["mcpServers"] = converted if converted else {"ipfs-kit-mcp": {}}
    
    # Find the first MCP server or create one
    server_key = next(iter(settings["mcpServers"].keys()), "ipfs-kit-mcp")
    if server_key not in settings["mcpServers"]:
        settings["mcpServers"][server_key] = {}
    
    server_config = settings["mcpServers"][server_key]
    
    # Update configuration with required fields
    server_config.update({
        "disabled": False,
        "timeout": 60,
        "url": "http://localhost:9994/api/v0/sse",
        "transportType": "sse",
        "jsonRpcUrl": "http://localhost:9994/api/v0/jsonrpc"
    })
    
    # Write updated settings back
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=2)
    
    logger.info(f"Updated MCP settings at {settings_path}")
    return True

def restart_mcp_server():
    """Restart the MCP server to apply changes."""
    try:
        # Stop existing processes
        subprocess.run(["pkill", "-f", "enhanced_mcp_server_fixed.py"], stderr=subprocess.DEVNULL)
        
        # Start enhanced MCP server
        subprocess.Popen(["python", "./enhanced_mcp_server_fixed.py", "--port", "9994", "--api-prefix", "/api/v0"])
        
        logger.info("Restarted MCP server")
        return True
    except Exception as e:
        logger.error(f"Error restarting MCP server: {e}")
        return False

def main():
    """Main function."""
    print("🔍 Searching for VS Code MCP settings files...")
    settings_paths = find_mcp_settings()
    
    if not settings_paths:
        logger.warning("No existing MCP settings files found, creating a new one")
        # Create default path
        settings_paths = [os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")]
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(settings_paths[0]), exist_ok=True)
    
    success = False
    for path in settings_paths:
        print(f"🔧 Fixing MCP settings at {path}")
        if fix_mcp_settings(path):
            success = True
    
    if success:
        print("🔄 Restarting MCP server...")
        restart_mcp_server()
        
        print("\n✅ VS Code MCP connection fixed successfully!")
        print("   Please reload VS Code or restart the extension host to apply changes.")
    else:
        print("\n❌ Failed to fix VS Code MCP connection.")
        print("   Please check the logs for details.")

if __name__ == "__main__":
    main()