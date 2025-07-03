#!/usr/bin/env python3

# MCP server with daemon support enabled

import os
import sys
import time
import subprocess
import logging

# Import helper functions
try:
    from fix_mcp_simple import start_ipfs_daemon, start_ipfs_cluster_service, start_lotus_daemon
except ImportError:
    print('Could not import daemon helper functions')
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_daemons():
    # Start IPFS daemon
    if not start_ipfs_daemon():
        logger.error('Failed to start IPFS daemon')
        return False

    # Start IPFS Cluster service
    if not start_ipfs_cluster_service():
        logger.warning('Failed to start IPFS Cluster service - continuing anyway')

    # Try to start Lotus daemon
    try:
        start_lotus_daemon()
    except Exception as e:
        logger.warning(f'Error starting Lotus daemon: {e} - continuing anyway')

    return True

def find_mcp_server_script():
    # Order of preference for server scripts
    script_candidates = [
        'run_mcp_server_anyio.py',
        'run_mcp_server_fixed.py',
        'run_mcp_server.py'
    ]

    # Check current directory and ipfs_kit_py subdirectory for each script
    search_paths = ['.', 'ipfs_kit_py']

    for path in search_paths:
        for script in script_candidates:
            script_path = os.path.join(path, script)
            if os.path.exists(script_path):
                return script_path

    return None

def start_mcp_server():
    # Find the best server script to use
    server_script = find_mcp_server_script()
    if not server_script:
        logger.error('Could not find an MCP server script to run')
        return False

    logger.info(f'Starting MCP server using {server_script}')

    # Build command line with appropriate parameters
    cmd = ['python', server_script, '--debug', '--isolation', '--port', '8002', '--host', 'localhost']

    # Start the server
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
        )

        # Give it a moment to start
        logger.info('Waiting for MCP server to start...')
        time.sleep(5)

        # Check if the server started successfully
        try:
            check_cmd = ['curl', '-s', 'http://localhost:8002/api/v0/mcp/health']
            result = subprocess.run(check_cmd, check=False, capture_output=True, text=True)

            if result.returncode == 0 and 'success' in result.stdout:
                logger.info('MCP server started successfully')
                return True
            else:
                logger.warning(f'MCP server may not have started properly: {result.stdout}')
                return False
        except Exception as e:
            logger.warning(f'Error checking MCP server: {e}')
            return False
    except Exception as e:
        logger.error(f'Error starting MCP server: {e}')
        return False

def main():
    logger.info('Setting up daemons and MCP server')

    # Set up daemons
    if not setup_daemons():
        logger.error('Failed to set up daemons, MCP server may not work properly')

    # Start MCP server
    if start_mcp_server():
        logger.info('MCP server is running with daemon support')
        print('\nMCP server is running with daemon support')
        print('API URL: http://localhost:8002/api/v0/mcp')
        print('Documentation: http://localhost:8002/docs')
    else:
        logger.error('Failed to start MCP server with daemon support')
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
