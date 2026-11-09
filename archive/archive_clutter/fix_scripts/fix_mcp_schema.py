#!/usr/bin/env python3
"""
Fix MCP Schema

This script fixes the invalid MCP schema by converting the mcpServers array
back to an object with server names as keys.
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

def fix_mcp_schema():
    """Convert mcpServers from array to object with server names as keys."""
    # Define the path to the settings file
    settings_path = os.path.expanduser("~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json")
    
    if not os.path.exists(settings_path):
        logger.error(f"Settings file not found: {settings_path}")
        return False
    
    try:
        # Read existing settings
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        # Check if mcpServers is an array (which is invalid)
        if 'mcpServers' in settings and isinstance(settings['mcpServers'], list):
            # Convert array to object
            servers_object = {}
            for server in settings['mcpServers']:
                if 'name' in server:
                    # Remove name field and use it as key
                    name = server.pop('name')
                    servers_object[name] = server
                else:
                    # Use a generated name if no name field
                    import uuid
                    name = f"server-{str(uuid.uuid4())[:8]}"
                    servers_object[name] = server
            
            # Replace the array with the object
            settings['mcpServers'] = servers_object
            
            # Write the updated settings back to the file
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
            
            logger.info(f"Fixed MCP schema by converting mcpServers array to object with {len(servers_object)} server entries")
            return True
        else:
            logger.info("MCP schema is already valid (mcpServers is not an array)")
            return True
    
    except Exception as e:
        logger.error(f"Error fixing MCP schema: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function."""
    logger.info("Starting MCP schema fix...")
    
    if fix_mcp_schema():
        logger.info("Successfully fixed MCP schema")
        print("✅ MCP schema fixed successfully!")
        print("Please reload the VSCode window or restart the server to apply changes.")
        sys.exit(0)
    else:
        logger.error("Failed to fix MCP schema")
        print("❌ Failed to fix MCP schema. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
