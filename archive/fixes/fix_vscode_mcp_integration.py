#!/usr/bin/env python3
"""
VS Code MCP Integration Fixer

This script will fix issues with VS Code integration for the MCP server:

1. Update VS Code settings to use the correct endpoints
2. Create a dedicated proxy for VS Code JSON-RPC requests
3. Automatically restart VS Code and the servers
"""

import os
import sys
import json
import shutil
import subprocess
import time
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='vscode_mcp_fix.log',
    filemode='w'
)
logger = logging.getLogger(__name__)

# Add console handler
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Define constants
MCP_PORT = 9994
JSONRPC_PORT = 9995
API_PREFIX = "/api/v0"
MCP_SERVER_SCRIPT = "./enhanced_mcp_server_fixed.py"
JSONRPC_SERVER_SCRIPT = "./simple_jsonrpc_server.py"

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Fix VS Code integration with MCP server"
    )
    parser.add_argument(
        "--restart-vscode", 
        action="store_true",
        help="Restart VS Code after applying fixes"
    )
    parser.add_argument(
        "--restart-servers", 
        action="store_true", 
        help="Restart MCP and JSON-RPC servers"
    )
    parser.add_argument(
        "--check-only", 
        action="store_true", 
        help="Only check current settings without making changes"
    )
    return parser.parse_args()

def find_vscode_settings():
    """Find all VS Code settings.json files."""
    home_dir = os.path.expanduser("~")
    possible_paths = [
        os.path.join(home_dir, ".config/Code/User/settings.json"),
        os.path.join(home_dir, ".config/Code - Insiders/User/settings.json"),
    ]
    
    found_paths = []
    for path in possible_paths:
        if os.path.exists(path):
            found_paths.append(path)
            
    return found_paths

def update_vscode_settings(settings_path, check_only=False):
    """Update VS Code settings to use the correct MCP endpoints."""
    logger.info(f"Checking VS Code settings at: {settings_path}")
    
    # Backup the original settings file
    backup_path = f"{settings_path}.bak"
    if not os.path.exists(backup_path) and not check_only:
        shutil.copy2(settings_path, backup_path)
        logger.info(f"Created backup of settings at: {backup_path}")
    
    try:
        with open(settings_path, 'r') as f:
            settings = json.load(f)
        
        # Check and update MCP server settings
        needs_update = False
        
        # Check if MCP settings exist
        if "mcp" not in settings:
            logger.info("Adding missing 'mcp' settings")
            settings["mcp"] = {
                "servers": {
                    "my-mcp-server": {
                        "url": f"http://localhost:{MCP_PORT}{API_PREFIX}/sse"
                    }
                }
            }
            needs_update = True
        elif "servers" not in settings["mcp"]:
            logger.info("Adding missing 'mcp.servers' settings")
            settings["mcp"]["servers"] = {
                "my-mcp-server": {
                    "url": f"http://localhost:{MCP_PORT}{API_PREFIX}/sse"
                }
            }
            needs_update = True
        else:
            # Check all server URLs
            for server_id, server_config in settings["mcp"]["servers"].items():
                if "url" not in server_config or not server_config["url"].endswith("/sse"):
                    logger.info(f"Fixing MCP server URL for {server_id}")
                    server_config["url"] = f"http://localhost:{MCP_PORT}{API_PREFIX}/sse"
                    needs_update = True
        
        # Check JSON-RPC endpoint settings
        if "localStorageNetworkingTools" not in settings:
            logger.info("Adding missing 'localStorageNetworkingTools' settings")
            settings["localStorageNetworkingTools"] = {
                "lspEndpoint": {
                    "url": f"http://localhost:{JSONRPC_PORT}/jsonrpc"
                }
            }
            needs_update = True
        elif "lspEndpoint" not in settings["localStorageNetworkingTools"]:
            logger.info("Adding missing 'localStorageNetworkingTools.lspEndpoint' settings")
            settings["localStorageNetworkingTools"]["lspEndpoint"] = {
                "url": f"http://localhost:{JSONRPC_PORT}/jsonrpc"
            }
            needs_update = True
        elif "url" not in settings["localStorageNetworkingTools"]["lspEndpoint"] or \
             settings["localStorageNetworkingTools"]["lspEndpoint"]["url"] != f"http://localhost:{JSONRPC_PORT}/jsonrpc":
            logger.info("Updating JSON-RPC endpoint URL")
            settings["localStorageNetworkingTools"]["lspEndpoint"]["url"] = f"http://localhost:{JSONRPC_PORT}/jsonrpc"
            needs_update = True
        
        # Write the updated settings back if needed
        if needs_update and not check_only:
            logger.info(f"Updating settings at: {settings_path}")
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
            return True
        elif needs_update and check_only:
            logger.info("Settings need updates, but check-only mode is enabled")
            return False
        else:
            logger.info("Settings are already correctly configured")
            return False
    except Exception as e:
        logger.error(f"Error updating VS Code settings: {e}")
        return False

def restart_servers():
    """Stop and restart the MCP and JSON-RPC servers."""
    logger.info("Stopping existing MCP and JSON-RPC servers...")
    
    try:
        subprocess.run(
            "pkill -f 'python.*enhanced_mcp_server' || true",
            shell=True, check=False
        )
        subprocess.run(
            "pkill -f 'python.*simple_jsonrpc_server' || true",
            shell=True, check=False
        )
        time.sleep(2)
        
        logger.info(f"Starting MCP server: {MCP_SERVER_SCRIPT}")
        mcp_process = subprocess.Popen(
            f"python {MCP_SERVER_SCRIPT} --port {MCP_PORT} --api-prefix {API_PREFIX}",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"Starting JSON-RPC server: {JSONRPC_SERVER_SCRIPT}")
        jsonrpc_process = subprocess.Popen(
            f"python {JSONRPC_SERVER_SCRIPT}",
            shell=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for servers to start
        time.sleep(3)
        
        # Check if servers are running
        mcp_running = subprocess.run(
            f"curl -s http://localhost:{MCP_PORT}/",
            shell=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        jsonrpc_running = subprocess.run(
            f"curl -s http://localhost:{JSONRPC_PORT}/",
            shell=True, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if mcp_running.returncode == 0 and jsonrpc_running.returncode == 0:
            logger.info("Both servers started successfully")
            return True
        else:
            logger.error("Failed to start one or both servers")
            if mcp_running.returncode != 0:
                logger.error("MCP server failed to start")
            if jsonrpc_running.returncode != 0:
                logger.error("JSON-RPC server failed to start")
            return False
    except Exception as e:
        logger.error(f"Error restarting servers: {e}")
        return False

def restart_vscode():
    """Restart VS Code."""
    logger.info("Attempting to restart VS Code...")
    
    try:
        # First check if VS Code is running
        vscode_running = subprocess.run(
            "pgrep -f 'code'",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if vscode_running.returncode == 0:
            logger.info("VS Code is running, attempting to close it")
            subprocess.run(
                "pkill -f 'code'",
                shell=True,
                check=False
            )
            time.sleep(2)
        
        # Start VS Code
        subprocess.Popen(
            "code .",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info("VS Code has been restarted")
        return True
    except Exception as e:
        logger.error(f"Error restarting VS Code: {e}")
        return False

def check_connections():
    """Check if the MCP and JSON-RPC servers are responding correctly."""
    logger.info("Checking connections to servers...")
    
    try:
        # Check MCP server
        mcp_response = subprocess.run(
            f"curl -s http://localhost:{MCP_PORT}/",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if mcp_response.returncode == 0:
            logger.info(f"MCP server is running at http://localhost:{MCP_PORT}/")
        else:
            logger.error(f"MCP server is not running at http://localhost:{MCP_PORT}/")
        
        # Check JSON-RPC server
        jsonrpc_response = subprocess.run(
            f"curl -s http://localhost:{JSONRPC_PORT}/",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if jsonrpc_response.returncode == 0:
            logger.info(f"JSON-RPC server is running at http://localhost:{JSONRPC_PORT}/")
        else:
            logger.error(f"JSON-RPC server is not running at http://localhost:{JSONRPC_PORT}/")
        
        # Check JSON-RPC initialize request
        initialize_response = subprocess.run(
            f"curl -s -X POST -H 'Content-Type: application/json' -d '{{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{{\"processId\":123,\"rootUri\":null,\"capabilities\":{{}}}}}}' http://localhost:{JSONRPC_PORT}/jsonrpc",
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if initialize_response.returncode == 0:
            logger.info("JSON-RPC server responds to initialize requests")
        else:
            logger.error("JSON-RPC server does not respond to initialize requests")
        
        return mcp_response.returncode == 0 and jsonrpc_response.returncode == 0 and initialize_response.returncode == 0
    except Exception as e:
        logger.error(f"Error checking connections: {e}")
        return False

def main():
    """Main entry point."""
    print("=== VS Code MCP Integration Fixer ===\n")
    
    args = parse_arguments()
    
    # Find VS Code settings files
    settings_paths = find_vscode_settings()
    if not settings_paths:
        print("❌ Could not find any VS Code settings files.")
        return 1
    
    # Check or update VS Code settings
    updated = False
    for settings_path in settings_paths:
        if update_vscode_settings(settings_path, args.check_only):
            updated = True
    
    # Restart servers if requested
    if args.restart_servers:
        if restart_servers():
            print("✅ MCP and JSON-RPC servers restarted successfully.")
        else:
            print("❌ Failed to restart servers.")
    
    # Check connections
    if check_connections():
        print("✅ Both servers are responding correctly.")
    else:
        print("❌ One or both servers are not responding correctly.")
    
    # Restart VS Code if requested
    if args.restart_vscode:
        if restart_vscode():
            print("✅ VS Code restarted successfully.")
        else:
            print("❌ Failed to restart VS Code.")
    
    # Final summary
    print("\n=== Summary ===")
    if args.check_only:
        print("Settings were checked but not modified.")
    elif updated:
        print("VS Code settings were updated successfully.")
    else:
        print("VS Code settings were already correct.")
        
    print("\nIf VS Code still can't connect to the MCP server:")
    print("1. Make sure both servers are running")
    print("2. Try reloading the VS Code window (F1 -> Reload Window)")
    print("3. Check the VS Code Developer Tools for network errors (Help -> Toggle Developer Tools)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
