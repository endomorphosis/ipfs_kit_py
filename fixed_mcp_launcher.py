#!/usr/bin/env python3
"""
Fixed MCP Server Launcher

This script starts an MCP server with enhanced parameter handling for IPFS tools.
It applies all necessary parameter fixes before starting the server.
"""

import os
import sys
import logging
import argparse
import importlib
import signal
import time
import subprocess
import socket
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fixed-mcp-launcher")

def is_port_available(port, host='127.0.0.1'):
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except socket.error:
            return False

def stop_existing_server(pid_file='final_mcp_server.pid'):
    """Stop any existing MCP server."""
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            logger.info(f"Stopping existing MCP server with PID: {pid}")
            try:
                os.kill(pid, signal.SIGTERM)
                # Wait for process to terminate
                time.sleep(2)
            except ProcessLookupError:
                logger.info(f"Process {pid} not found, may have already terminated")
            except PermissionError:
                logger.warning(f"Permission denied when trying to stop process {pid}")
            
            # Remove PID file
            try:
                os.unlink(pid_file)
            except FileNotFoundError:
                pass
            
            return True
        except Exception as e:
            logger.error(f"Error stopping existing server: {e}")
    
    return False

def apply_parameter_fixes():
    """Apply all parameter fixes."""
    
    # Apply the direct parameter fix
    try:
        logger.info("Applying direct parameter fix")
        import direct_param_fix
        success = direct_param_fix.install_parameter_fix()
        if success:
            logger.info("✅ Successfully applied direct parameter fix")
        else:
            logger.warning("⚠️ Failed to apply direct parameter fix")
    except ImportError as e:
        logger.error(f"❌ Error importing direct_param_fix: {e}")
    
    # Apply enhanced parameter adapter
    try:
        logger.info("Setting up enhanced parameter adapter")
        # Make sure enhanced_parameter_adapter.py exists
        if not os.path.exists('enhanced_parameter_adapter.py'):
            logger.error("❌ enhanced_parameter_adapter.py not found")
        else:
            logger.info("✅ Enhanced parameter adapter found")
    except Exception as e:
        logger.error(f"❌ Error setting up enhanced parameter adapter: {e}")
    
    # Apply direct tool handlers
    try:
        logger.info("Setting up direct tool handlers")
        # Make sure ipfs_tool_adapters.py exists
        if not os.path.exists('ipfs_tool_adapters.py'):
            logger.error("❌ ipfs_tool_adapters.py not found")
        else:
            logger.info("✅ Direct tool handlers found")
    except Exception as e:
        logger.error(f"❌ Error setting up direct tool handlers: {e}")
    
    return True

def start_server(host='0.0.0.0', port=9998, debug=False):
    """Start the MCP server with all fixes applied."""
    
    # Stop any existing server
    stop_existing_server()
    
    # Check if port is available
    if not is_port_available(port, host):
        logger.error(f"Port {port} is not available. Another server might be running.")
        return False
    
    # Apply parameter fixes
    apply_parameter_fixes()
    
    # Prepare the command to start the server
    cmd = [
        sys.executable,
        'final_mcp_server.py',
        '--host', host,
        '--port', str(port)
    ]
    
    if debug:
        cmd.append('--debug')
    
    # Start the server
    try:
        logger.info(f"Starting MCP server on {host}:{port}")
        server_process = subprocess.Popen(cmd)
        
        # Wait briefly to allow server to start
        time.sleep(3)
        
        # Check if server is still running
        if server_process.poll() is None:
            logger.info(f"✅ MCP server started with PID: {server_process.pid}")
            
            # Save PID to file
            with open('final_mcp_server.pid', 'w') as f:
                f.write(str(server_process.pid))
            
            return True
        else:
            logger.error(f"❌ MCP server failed to start (exit code: {server_process.returncode})")
            return False
    except Exception as e:
        logger.error(f"❌ Error starting MCP server: {e}")
        return False

def main():
    """Main function to parse arguments and start the server."""
    parser = argparse.ArgumentParser(description="Start MCP server with enhanced parameter handling")
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind the server to')
    parser.add_argument('--port', type=int, default=9998, help='Port to run the server on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--stop', action='store_true', help='Stop existing server without starting a new one')
    
    args = parser.parse_args()
    
    # Stop existing server if requested
    if args.stop:
        stop_existing_server()
        logger.info("Stopped existing server")
        return
    
    # Start the server with fixes
    success = start_server(args.host, args.port, args.debug)
    
    if success:
        logger.info(f"✅ MCP server started successfully on {args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop")
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping server...")
            stop_existing_server()
    else:
        logger.error("❌ Failed to start MCP server")
        sys.exit(1)

if __name__ == "__main__":
    main()