#!/usr/bin/env python3
"""
Add Initialize Endpoint to MCP Server

This script adds a direct initialize endpoint to the MCP server's FastAPI app.
The initialize endpoint is required for VS Code to establish a connection to the server.
"""

import os
import sys
import json
import logging
import time
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def add_initialize_endpoint(mcp_server_file_path=None, app_variable_name="app", register_path="/api/v0"):
    """
    Add initialize endpoint directly to the MCP server script.
    
    Args:
        mcp_server_file_path: Path to the MCP server script file
        app_variable_name: Name of the FastAPI app variable in the script
        register_path: Path prefix for the endpoint registration
        
    Returns:
        bool: True if successful, False otherwise
    """
    if mcp_server_file_path is None:
        # Try to find the enhanced MCP server script
        for filename in ["enhanced_mcp_server_fixed.py", "enhanced_mcp_server_with_jsonrpc.py",
                        "mcp_server_fixed_all.py", "run_mcp_server.py"]:
            if os.path.exists(filename):
                mcp_server_file_path = filename
                break
                
    if mcp_server_file_path is None or not os.path.exists(mcp_server_file_path):
        logger.error("Could not find MCP server script file")
        return False
        
    logger.info(f"Found MCP server script: {mcp_server_file_path}")
    
    # Backup the file
    backup_file = f"{mcp_server_file_path}.bak"
    try:
        with open(mcp_server_file_path, 'r') as f:
            original_content = f.read()
            
        with open(backup_file, 'w') as f:
            f.write(original_content)
            
        logger.info(f"Created backup of server script at {backup_file}")
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        return False
    
    # Check if the initialize endpoint already exists
    if "def initialize_endpoint" in original_content or f"{app_variable_name}.post('/api/v0/initialize'" in original_content:
        logger.info("Initialize endpoint already exists in script, no changes needed")
        return True
    
    # Find where to add our initialize endpoint
    import_index = original_content.find("from fastapi import")
    if import_index == -1:
        import_index = original_content.find("import fastapi")
    
    if import_index == -1:
        logger.error("Could not find FastAPI import in script")
        return False
    
    # Find the end of the imports section (usually blank line after imports)
    import_end = original_content.find("\n\n", import_index)
    if import_end == -1:
        import_end = original_content.find("\n", import_index)
    
    # Find where the app is defined
    app_def_index = original_content.find(f"{app_variable_name} = FastAPI(")
    if app_def_index == -1:
        app_def_index = original_content.find(f"{app_variable_name} = fastapi.FastAPI(")
    
    if app_def_index == -1:
        logger.error(f"Could not find app definition ({app_variable_name} = FastAPI()) in script")
        return False
    
    # Find the first code after app definition (usually endpoint definitions)
    app_def_end = original_content.find("\n\n", app_def_index)
    if app_def_end == -1:
        app_def_end = original_content.find("\n", app_def_index)
        
    # Prepare the initialize endpoint code
    initialize_endpoint_code = """
# Initialize endpoint for VS Code integration
@app.post('/api/v0/initialize', tags=["MCP"])
@app.get('/api/v0/initialize', tags=["MCP"])
async def initialize_endpoint():
    \"\"\"Initialize endpoint for VS Code MCP protocol.
    
    This endpoint is called by VS Code when it first connects to the MCP server.
    It returns information about the server's capabilities.
    \"\"\"
    logger.info("Received initialize request from VS Code")
    return {
        "capabilities": {
            "textDocumentSync": {
                "openClose": True,
                "change": 1
            },
            "completionProvider": {
                "resolveProvider": False,
                "triggerCharacters": ["/"]
            },
            "hoverProvider": True,
            "definitionProvider": True,
            "referencesProvider": True
        },
        "serverInfo": {
            "name": "MCP IPFS Tools Server",
            "version": "0.3.0"
        }
    }
"""
    
    # Insert the initialize endpoint code after app definition
    modified_content = original_content[:app_def_end] + initialize_endpoint_code + original_content[app_def_end:]
    
    # Write the modified content back to the file
    try:
        with open(mcp_server_file_path, 'w') as f:
            f.write(modified_content)
        
        logger.info(f"Added initialize endpoint to {mcp_server_file_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing modified content: {e}")
        
        # Try to restore the backup
        try:
            with open(backup_file, 'r') as f:
                backup_content = f.read()
            
            with open(mcp_server_file_path, 'w') as f:
                f.write(backup_content)
                
            logger.info(f"Restored backup after error")
        except Exception as restore_error:
            logger.error(f"Error restoring backup: {restore_error}")
            
        return False

def restart_mcp_server():
    """
    Restart the MCP server to apply the changes.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info("Attempting to restart MCP server...")
        
        # Find and kill any existing MCP server processes
        server_process_patterns = [
            "python.*enhanced_mcp_server",
            "python.*mcp_server_fixed_all",
            "python.*run_mcp_server"
        ]
        
        for pattern in server_process_patterns:
            try:
                subprocess.run(["pkill", "-f", pattern], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        
        # Wait for processes to terminate
        time.sleep(2)
        
        # Try to find the MCP server script
        mcp_server_script = None
        for filename in ["enhanced_mcp_server_fixed.py", "mcp_server_fixed_all.py", "run_mcp_server.py"]:
            if os.path.exists(filename):
                mcp_server_script = filename
                break
                
        if not mcp_server_script:
            logger.error("Could not find MCP server script to restart")
            return False
            
        # Start the MCP server
        subprocess.Popen(
            ["python3", mcp_server_script, "--port", "9994", "--api-prefix", "/api/v0"],
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        
        logger.info(f"Started MCP server using {mcp_server_script}")
        
        # Wait for server to start
        time.sleep(3)
        
        # Check if server is running
        import requests
        try:
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    response = requests.get("http://localhost:9994/", timeout=2)
                    if response.status_code == 200:
                        logger.info(f"MCP server is running (status code: {response.status_code})")
                        return True
                except requests.RequestException:
                    if attempt < max_attempts - 1:
                        logger.info(f"Server not responding yet, waiting ({attempt + 1}/{max_attempts})")
                        time.sleep(2)
                    else:
                        raise
            
            logger.error("Server did not respond after maximum attempts")
            return False
            
        except Exception as e:
            logger.error(f"Error checking server status: {e}")
            return False
    
    except Exception as e:
        logger.error(f"Error restarting MCP server: {e}")
        return False

def check_initialize_endpoint():
    """
    Check if the initialize endpoint is working.
    
    Returns:
        bool: True if working, False otherwise
    """
    try:
        import requests
        response = requests.post("http://localhost:9994/api/v0/initialize", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            if "capabilities" in data and "serverInfo" in data:
                logger.info("Initialize endpoint is working correctly")
                return True
            else:
                logger.error(f"Initialize endpoint response missing required fields: {data}")
                return False
        else:
            logger.error(f"Initialize endpoint returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error checking initialize endpoint: {e}")
        return False

def main():
    """Main function."""
    logger.info("Adding initialize endpoint to MCP server...")
    
    if add_initialize_endpoint():
        logger.info("Successfully added initialize endpoint to server script")
        
        # Restart the server
        if restart_mcp_server():
            logger.info("Successfully restarted MCP server")
            
            # Check if the initialize endpoint is working
            if check_initialize_endpoint():
                print("✅ Initialize endpoint added and verified!")
                print("VS Code should now be able to connect to the MCP server.")
                sys.exit(0)
            else:
                print("⚠️ Initialize endpoint added but not responding correctly.")
                print("Please check the server logs for more information.")
                sys.exit(1)
        else:
            print("⚠️ Initialize endpoint added but failed to restart server.")
            print("Please manually restart the MCP server to apply changes.")
            sys.exit(1)
    else:
        print("❌ Failed to add initialize endpoint. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
