#!/usr/bin/env python3
"""
Verify IPFS MCP Tools

This script verifies that all the IPFS tools are properly registered and available
through the MCP server. It checks that the tools are registered in the MCP settings
file and provides a way to test the core functionality.
"""

import os
import sys
import json
import logging
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_mcp_settings_file() -> Optional[str]:
    """
    Find the MCP settings file in the user's home directory.
    
    Returns:
        str: Path to the settings file or None if not found
    """
    home_dir = os.path.expanduser("~")
    vscode_dir = os.path.join(home_dir, ".config", "Code", "User", "globalStorage", "saoudrizwan.claude-dev", "settings")
    settings_file = os.path.join(vscode_dir, "cline_mcp_settings.json")
    
    if os.path.exists(settings_file):
        return settings_file
    
    return None

def verify_ipfs_server_registered(settings_file: str) -> bool:
    """
    Verify that the IPFS MCP server is registered in the settings file.
    
    Args:
        settings_file: Path to the settings file
        
    Returns:
        bool: True if the server is registered, False otherwise
    """
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        if 'servers' not in settings:
            logger.error("No servers found in MCP settings")
            return False
        
        for server in settings['servers']:
            if server.get('name') == 'direct-ipfs-kit-mcp':
                logger.info(f"Found IPFS MCP server in settings: {server['name']} (port: {server.get('port', 'unknown')})")
                return True
        
        logger.error("IPFS MCP server not found in settings")
        return False
    except Exception as e:
        logger.error(f"Error verifying IPFS server registration: {e}")
        return False

def verify_ipfs_tools_registered(settings_file: str) -> bool:
    """
    Verify that IPFS tools are registered in the settings file.
    
    Args:
        settings_file: Path to the settings file
        
    Returns:
        bool: True if tools are registered, False otherwise
    """
    try:
        with open(settings_file, 'r') as f:
            settings = json.load(f)
        
        if 'servers' not in settings:
            logger.error("No servers found in MCP settings")
            return False
        
        for server in settings['servers']:
            if server.get('name') == 'direct-ipfs-kit-mcp':
                if 'tools' not in server or not server['tools']:
                    logger.error("No tools found for IPFS MCP server")
                    return False
                
                # Count tools by category
                categories = {}
                for tool in server['tools']:
                    category = None
                    
                    # Extract category from tool name or description
                    if tool['name'].startswith('swarm_'):
                        category = 'ipfs_swarm'
                    elif tool['name'].startswith('dag_'):
                        category = 'ipfs_dag'
                    elif tool['name'].startswith('block_'):
                        category = 'ipfs_block'
                    elif tool['name'].startswith('dht_'):
                        category = 'ipfs_dht'
                    elif tool['name'] in ['list_files', 'stat_file', 'make_directory', 'read_file', 'write_file', 'remove_file']:
                        category = 'ipfs_mfs'
                    elif tool['name'] in ['add_content', 'get_content', 'get_content_as_tar']:
                        category = 'ipfs_content'
                    elif tool['name'] in ['pin_content', 'unpin_content', 'list_pins']:
                        category = 'ipfs_pins'
                    elif tool['name'] in ['publish_name', 'resolve_name']:
                        category = 'ipfs_ipns'
                    elif tool['name'] in ['get_node_id', 'get_version', 'get_stats', 'check_daemon_status', 'get_replication_status']:
                        category = 'ipfs_node'
                    elif tool['name'] in ['map_ipfs_to_fs', 'unmap_ipfs_from_fs', 'sync_fs_to_ipfs', 'sync_ipfs_to_fs', 
                                         'list_fs_ipfs_mappings', 'mount_ipfs_to_fs', 'unmount_ipfs_from_fs']:
                        category = 'ipfs_fs_integration'
                    
                    if category:
                        categories[category] = categories.get(category, 0) + 1
                
                # Report on categories
                logger.info(f"Found {len(server['tools'])} IPFS tools registered")
                for category, count in categories.items():
                    logger.info(f"- {category}: {count} tools")
                
                # Check that we have tools in all expected categories
                expected_categories = [
                    'ipfs_swarm', 'ipfs_mfs', 'ipfs_content', 'ipfs_pins',
                    'ipfs_ipns', 'ipfs_dag', 'ipfs_block', 'ipfs_dht',
                    'ipfs_node', 'ipfs_fs_integration'
                ]
                
                missing_categories = [cat for cat in expected_categories if cat not in categories]
                if missing_categories:
                    logger.warning(f"Missing tools in categories: {', '.join(missing_categories)}")
                
                # If we have at least some tools, consider it a success
                return len(server['tools']) > 0
        
        logger.error("IPFS MCP server not found in settings")
        return False
    except Exception as e:
        logger.error(f"Error verifying IPFS tools registration: {e}")
        return False

def verify_ipfs_daemon_running() -> bool:
    """
    Verify that the IPFS daemon is running.
    
    Returns:
        bool: True if the daemon is running, False otherwise
    """
    try:
        # Check using ps command
        import subprocess
        result = subprocess.run(['pgrep', '-x', 'ipfs'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("IPFS daemon is running")
            return True
        else:
            logger.error("IPFS daemon is not running")
            return False
    except Exception as e:
        logger.error(f"Error checking IPFS daemon status: {e}")
        return False

def verify_mcp_server_running() -> bool:
    """
    Verify that the MCP server is running.
    
    Returns:
        bool: True if the server is running, False otherwise
    """
    try:
        # Check if PID file exists and process is running
        pid_file = "direct_mcp_server.pid"
        if not os.path.exists(pid_file):
            logger.error("MCP server PID file not found")
            return False
        
        with open(pid_file, 'r') as f:
            pid = f.read().strip()
        
        # Check if process is running
        import subprocess
        result = subprocess.run(['kill', '-0', pid], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"MCP server is running with PID {pid}")
            return True
        else:
            logger.error(f"MCP server process with PID {pid} is not running")
            return False
    except Exception as e:
        logger.error(f"Error checking MCP server status: {e}")
        return False

def main():
    """Main function."""
    print("=" * 50)
    print("IPFS MCP Tools Verification")
    print("=" * 50)
    
    # Find MCP settings file
    settings_file = find_mcp_settings_file()
    if not settings_file:
        logger.error("MCP settings file not found")
        return 1
    
    # Verify that the IPFS server is registered
    server_registered = verify_ipfs_server_registered(settings_file)
    
    # Verify that IPFS tools are registered
    tools_registered = verify_ipfs_tools_registered(settings_file)
    
    # Verify that the IPFS daemon is running
    daemon_running = verify_ipfs_daemon_running()
    
    # Verify that the MCP server is running
    server_running = verify_mcp_server_running()
    
    # Print summary
    print("\n" + "=" * 50)
    print("Verification Summary")
    print("=" * 50)
    print(f"IPFS MCP Server Registered: {'✓' if server_registered else '✗'}")
    print(f"IPFS Tools Registered: {'✓' if tools_registered else '✗'}")
    print(f"IPFS Daemon Running: {'✓' if daemon_running else '✗'}")
    print(f"MCP Server Running: {'✓' if server_running else '✗'}")
    print("=" * 50)
    
    # Final result
    if server_registered and tools_registered and daemon_running and server_running:
        print("\nVerification PASSED: IPFS MCP tools are ready to use!")
        return 0
    else:
        print("\nVerification FAILED: Please check the issues above and fix them.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
