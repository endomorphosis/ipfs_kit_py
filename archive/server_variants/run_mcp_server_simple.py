#!/usr/bin/env python3
"""
Simple script to start the MCP server.

This is a minimal script that just starts the MCP server without any additional steps.
Use this if the more comprehensive shell script isn't working.
"""

import os
import sys
import time
import signal
import socket
import logging
import argparse
import subprocess
import atexit

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def stop_server(pid):
    """Stop the server process."""
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info(f"Stopped server with PID {pid}")
        except Exception as e:
            logger.error(f"Error stopping server: {e}")

def main():
    """Run the MCP server."""
    parser = argparse.ArgumentParser(description="Start the Enhanced MCP server")
    parser.add_argument("--port", type=int, default=9997, help="Port number to use")
    parser.add_argument("--debug", dest="debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-debug", dest="debug", action="store_false", help="Disable debug mode")
    parser.set_defaults(debug=True)
    
    args = parser.parse_args()
    
    # First, check for any existing processes
    try:
        subprocess.run(["pkill", "-f", "python.*enhanced_mcp_server_fixed.py"])
        time.sleep(1)
    except Exception as e:
        logger.warning(f"Error stopping existing server: {e}")
    
    # Check if port is available
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('localhost', args.port))
        s.close()
    except socket.error:
        logger.error(f"Port {args.port} is already in use")
        sys.exit(1)
    
    logger.info(f"Starting MCP server on port {args.port}...")
    
    # Start the server
    cmd = [
        "python", "enhanced_mcp_server_fixed.py",
        "--port", str(args.port),
        "--debug" if args.debug else "--no-debug"
    ]
    
    try:
        # Start server process
        server_process = subprocess.Popen(cmd)
        server_pid = server_process.pid
        
        # Register a function to stop the server when this script exits
        atexit.register(stop_server, server_pid)
        
        logger.info(f"Server started with PID {server_pid}")
        
        # Save PID to file
        with open('/tmp/mcp_server.pid', 'w') as f:
            f.write(str(server_pid))
        
        # Wait for server to start
        logger.info("Waiting for server to start...")
        time.sleep(5)
        
        # Check if server is responding
        try:
            import requests
            response = requests.get(f"http://localhost:{args.port}/")
            if response.status_code == 200:
                logger.info("Server is running and responding!")
                logger.info(f"Server root endpoint response: {response.status_code}")
            else:
                logger.warning(f"Server responded with status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error connecting to server: {e}")
        
        logger.info(f"MCP server is running on port {args.port}")
        logger.info("Press Ctrl+C to stop the server")
        
        # Update Claude MCP configuration
        try:
            logger.info("Updating Claude MCP configuration...")
            subprocess.run(["python", "fix_cline_mcp_tools.py"])
            logger.info("Claude MCP configuration updated")
        except Exception as e:
            logger.error(f"Error updating Claude MCP configuration: {e}")
        
        # Wait for the server process to finish
        server_process.wait()
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user, stopping server...")
        # Use a safer approach that doesn't rely on locals()
        try:
            if 'server_process' in locals() and server_process is not None:
                stop_server(server_process.pid)
        except:
            pass
    except Exception as e:
        logger.error(f"Error running server: {e}")
        # Use a safer approach that doesn't rely on locals()
        try:
            if 'server_process' in locals() and server_process is not None:
                stop_server(server_process.pid)
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
