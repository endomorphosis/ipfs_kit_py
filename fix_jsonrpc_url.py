#!/usr/bin/env python3
"""
Fix JSON-RPC URL in MCP Configuration

This script updates the JSON-RPC URL in the MCP configuration to match the actual endpoint
that the server is handling.
"""

import os
import sys
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fix_jsonrpc_url():
    """Fix the JSON-RPC URL in the MCP configuration."""
    # Define the path to the settings file
    settings_path = os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")

    if not os.path.exists(settings_path):
        logger.error(f"Settings file not found: {settings_path}")
        return False

    try:
        # Read existing settings
        with open(settings_path, 'r') as f:
            settings = json.load(f)

        # Make a backup of the original settings
        backup_path = settings_path + ".bak"
        with open(backup_path, 'w') as f:
            json.dump(settings, f, indent=2)
        logger.info(f"Backed up settings to {backup_path}")

        # Check if mcpServers exists and is an object
        if 'mcpServers' not in settings or not isinstance(settings['mcpServers'], dict):
            logger.error("mcpServers is not an object in the settings file")
            return False

        # Update jsonRpcUrl for each server
        updates_made = False
        for server_name, server in settings['mcpServers'].items():
            if 'jsonRpcUrl' in server:
                old_url = server['jsonRpcUrl']

                # Update URL, making sure to point to the correct endpoint based on server logs
                if '/api/v0/jsonrpc' in old_url:
                    # Extract the base URL (e.g., http://localhost:9994)
                    base_url = old_url.split('/api/v0/jsonrpc')[0]
                    # Update to the correct endpoint
                    server['jsonRpcUrl'] = f"{base_url}/jsonrpc"

                    logger.info(f"Updated jsonRpcUrl for server '{server_name}' from {old_url} to {server['jsonRpcUrl']}")
                    updates_made = True

        if not updates_made:
            logger.info("No URLs needed to be updated")
            return True

        # Write updated settings back
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)

        logger.info(f"Updated MCP settings at {settings_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating MCP settings: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function."""
    logger.info("Fixing JSON-RPC URL in MCP configuration...")

    if fix_jsonrpc_url():
        print("✅ JSON-RPC URL fixed successfully!")
        print("Please reload the VSCode window to apply changes.")
        sys.exit(0)
    else:
        print("❌ Failed to fix JSON-RPC URL. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
