#!/usr/bin/env python3
"""
Wrapper script to start/stop the MCP server for testing.

This script manages the MCP server process for tests.
"""

import os
import sys
import time
import logging
import subprocess
import signal
import atexit

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default server port
SERVER_PORT = 8001
SERVER_PID_FILE = "mcp_server.pid"
SERVER_LOG_FILE = "mcp_server.log"

def check_server_running():
    """Check if server is already running."""
    if os.path.exists(SERVER_PID_FILE):
        try:
            with open(SERVER_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            
            # Check if process is running
            try:
                os.kill(pid, 0)
                logger.info(f"Server already running with PID {pid}")
                return pid
            except OSError:
                logger.info(f"Found stale PID file for {pid}, will start new server")
                os.remove(SERVER_PID_FILE)
                return None
        except (ValueError, FileNotFoundError):
            logger.info("Invalid PID file, will start new server")
            try:
                os.remove(SERVER_PID_FILE)
            except FileNotFoundError:
                pass
            return None
    return None

def start_server():
    """Start the MCP server."""
    # Check if server is already running
    existing_pid = check_server_running()
    if existing_pid:
        return existing_pid
    
    # Start the server as a subprocess
    logger.info(f"Starting MCP server on port {SERVER_PORT}...")
    
    with open(SERVER_LOG_FILE, "w") as log_file:
        process = subprocess.Popen(
            [sys.executable, "run_mcp_server_for_tests.py", "--port", str(SERVER_PORT)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True  # Detach from parent process
        )
    
    # Save PID to file
    with open(SERVER_PID_FILE, "w") as f:
        f.write(str(process.pid))
    
    # Wait for server to start
    logger.info(f"Server started with PID {process.pid}, waiting for it to initialize...")
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            # Try to connect to the server's health endpoint
            import requests
            response = requests.get(f"http://localhost:{SERVER_PORT}/api/v0/mcp/health")
            if response.status_code == 200:
                logger.info(f"Server is ready after {attempt + 1} attempts")
                return process.pid
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(1)
        
        # Check if process is still running
        if process.poll() is not None:
            logger.error(f"Server process exited with code {process.returncode}")
            logger.error("Check server.log for details")
            return None
    
    logger.error(f"Server did not initialize after {max_attempts} attempts")
    return None

def stop_server(pid=None):
    """Stop the MCP server."""
    if pid is None:
        # Try to get PID from file
        if os.path.exists(SERVER_PID_FILE):
            try:
                with open(SERVER_PID_FILE, "r") as f:
                    pid = int(f.read().strip())
            except (ValueError, FileNotFoundError):
                logger.warning("Could not read PID file")
                return False
        else:
            logger.warning("No PID file found")
            return False
    
    # Send termination signal
    try:
        logger.info(f"Stopping server with PID {pid}...")
        # Try to send SIGTERM to process group
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        
        # Wait for process to terminate
        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                logger.info(f"Server with PID {pid} has been stopped")
                break
        else:
            # Process didn't terminate, try SIGKILL
            logger.warning(f"Server did not stop gracefully, sending SIGKILL...")
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        
        # Clean up PID file
        if os.path.exists(SERVER_PID_FILE):
            os.remove(SERVER_PID_FILE)
            
        return True
    except OSError as e:
        logger.error(f"Failed to stop server: {e}")
        return False

def cleanup():
    """Cleanup function to stop server at exit."""
    if os.path.exists(SERVER_PID_FILE):
        try:
            with open(SERVER_PID_FILE, "r") as f:
                pid = int(f.read().strip())
            stop_server(pid)
        except (ValueError, FileNotFoundError):
            pass

def main():
    """Main entry point."""
    # Register cleanup function
    atexit.register(cleanup)
    
    # Handle command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            pid = start_server()
            if pid:
                logger.info(f"Server started with PID {pid}")
                return 0
            else:
                logger.error("Failed to start server")
                return 1
        elif sys.argv[1] == "stop":
            if stop_server():
                logger.info("Server stopped")
                return 0
            else:
                logger.error("Failed to stop server")
                return 1
        elif sys.argv[1] == "restart":
            stop_server()
            pid = start_server()
            if pid:
                logger.info(f"Server restarted with PID {pid}")
                return 0
            else:
                logger.error("Failed to restart server")
                return 1
        else:
            logger.error(f"Unknown command: {sys.argv[1]}")
            print(f"Usage: {sys.argv[0]} [start|stop|restart]")
            return 1
    else:
        # Default to start
        pid = start_server()
        if pid:
            logger.info(f"Server started with PID {pid}")
            return 0
        else:
            logger.error("Failed to start server")
            return 1

if __name__ == "__main__":
    sys.exit(main())