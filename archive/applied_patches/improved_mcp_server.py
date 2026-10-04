#!/usr/bin/env python3
"""
Improved MCP Server with Full Feature Support

This script starts an improved MCP server that supports all storage backends
using either real credentials or functional mock implementations.
"""

import os
import sys
import subprocess
import signal
import time
import logging
import argparse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/improved_mcp_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Parse arguments
parser = argparse.ArgumentParser(description="Start Improved MCP Server")
parser.add_argument("--port", type=int, default=9998, 
                    help="Port to run the server on (default: 9998)")
parser.add_argument("--host", type=str, default="0.0.0.0", 
                    help="Host to bind to (default: 0.0.0.0)")
parser.add_argument("--mock", action="store_true", 
                    help="Force mock mode for all backends")
parser.add_argument("--real", action="store_true", 
                    help="Attempt to use real credentials only (no mock fallback)")
parser.add_argument("--restart", action="store_true", 
                    help="Restart any running MCP server")
args = parser.parse_args()

def setup_environment():
    """Set up the environment for the MCP server."""
    # Create necessary directories
    os.makedirs("logs", exist_ok=True)
    
    # Mock directories for storage backends
    mock_dirs = [
        os.path.expanduser("~/.ipfs_kit/mock_huggingface"),
        os.path.expanduser("~/.ipfs_kit/mock_s3/ipfs-storage-demo"),
        os.path.expanduser("~/.ipfs_kit/mock_filecoin/deals"),
        os.path.expanduser("~/.ipfs_kit/mock_storacha"),
        os.path.expanduser("~/.ipfs_kit/mock_lassie")
    ]
    
    for directory in mock_dirs:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"Created mock directory: {directory}")
    
    # Set environmental variables for mock mode if requested
    if args.mock:
        logger.info("Forcing mock mode for all backends")
        os.environ["MCP_USE_MOCK_MODE"] = "true"
    
    # Source the credentials script if it exists
    credentials_script = Path("mcp_credentials.sh")
    if credentials_script.exists():
        logger.info("Sourcing credentials from mcp_credentials.sh")
        # Execute the script and capture the exported variables
        result = subprocess.run(
            ["bash", "-c", f"source {credentials_script} && env"],
            capture_output=True,
            text=True
        )
        
        # Update environment with the variables from the script
        for line in result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                os.environ[key] = value

def find_running_mcp_servers():
    """Find running MCP server processes."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "mcp_server|enhanced_mcp_server|run_mcp"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return [int(pid) for pid in result.stdout.strip().split()]
        return []
    except Exception as e:
        logger.error(f"Error finding running MCP servers: {e}")
        return []

def stop_running_servers(pids):
    """Stop running MCP server processes."""
    for pid in pids:
        try:
            logger.info(f"Stopping MCP server with PID {pid}")
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            # Process already gone
            pass
        except Exception as e:
            logger.error(f"Error stopping MCP server with PID {pid}: {e}")

def check_ipfs_daemon():
    """Check if IPFS daemon is running and start it if needed."""
    try:
        result = subprocess.run(
            ["ipfs", "version"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("IPFS daemon is already running")
            return True
        
        # Try to start the daemon
        logger.info("Starting IPFS daemon...")
        subprocess.Popen(
            ["ipfs", "daemon", "--routing=dhtclient"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for daemon to start
        time.sleep(3)
        
        # Verify it started
        check_result = subprocess.run(
            ["ipfs", "version"],
            capture_output=True,
            text=True
        )
        
        if check_result.returncode == 0:
            logger.info("IPFS daemon started successfully")
            return True
        
        logger.error("Failed to start IPFS daemon")
        return False
    except Exception as e:
        logger.error(f"Error with IPFS daemon: {e}")
        return False

def start_enhanced_mcp_server():
    """Start the enhanced MCP server."""
    try:
        # Use the enhanced_mcp_server.py script
        cmd = [
            "python", 
            "enhanced_mcp_server.py",
            "--port", str(args.port),
            "--host", args.host
        ]
        
        if args.mock:
            cmd.append("--debug")
        
        logger.info(f"Starting enhanced MCP server: {' '.join(cmd)}")
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Write PID file
        with open("improved_mcp_server.pid", "w") as f:
            f.write(str(proc.pid))
        
        logger.info(f"Enhanced MCP server started with PID {proc.pid}")
        
        # Wait briefly to ensure it starts properly
        time.sleep(2)
        
        # Check if the process is still running
        if proc.poll() is None:
            logger.info("Server started successfully")
            return True
        else:
            stdout, stderr = proc.communicate()
            logger.error(f"Server failed to start: {stderr.decode('utf-8')}")
            return False
    except Exception as e:
        logger.error(f"Error starting enhanced MCP server: {e}")
        return False

def verify_server_health():
    """Verify that the MCP server is healthy and all backends are working."""
    try:
        import requests
        import time
        
        # Give the server a moment to fully initialize
        time.sleep(3)
        
        # Check server health
        response = requests.get(f"http://localhost:{args.port}/api/v0/health")
        
        if response.status_code == 200:
            health_data = response.json()
            logger.info(f"Server health check: {health_data['status']}")
            
            # Check if any backends are in simulation mode
            simulation_backends = []
            for backend, status in health_data.get('storage_backends', {}).items():
                if status.get('simulation', False):
                    simulation_backends.append(backend)
            
            if simulation_backends:
                logger.warning(f"Backends in simulation mode: {', '.join(simulation_backends)}")
                return False
            
            return True
        else:
            logger.error(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error verifying server health: {e}")
        return False

def main():
    """Main function to start the improved MCP server."""
    # Set up the environment
    setup_environment()
    
    # Check if any MCP servers are running
    running_servers = find_running_mcp_servers()
    
    if running_servers:
        if args.restart:
            logger.info(f"Found {len(running_servers)} running MCP servers, stopping them...")
            stop_running_servers(running_servers)
            time.sleep(2)  # Give them time to stop
        else:
            logger.info(f"MCP servers already running: {running_servers}")
            logger.info("Use --restart to stop existing servers and start a new one")
            return
    
    # Check IPFS daemon
    if not check_ipfs_daemon():
        logger.error("Failed to ensure IPFS daemon is running")
        return
    
    # Start the enhanced MCP server
    if start_enhanced_mcp_server():
        logger.info(f"MCP server started successfully on port {args.port}")
        
        # Verify server health
        if verify_server_health():
            logger.info("All MCP features are working properly!")
        else:
            logger.warning("Some MCP features may not be working optimally")
            logger.info("Check logs or server health endpoint for details")
    else:
        logger.error("Failed to start MCP server")

if __name__ == "__main__":
    main()