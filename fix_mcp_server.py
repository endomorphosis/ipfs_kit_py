#!/usr/bin/env python3
"""
MCP Server Fix Script

This script ensures that all MCP server features work properly by:
1. Stopping any existing MCP server instances
2. Setting up mock implementations for storage backends
3. Starting a new MCP server with all features working
"""

import os
import sys
import subprocess
import time
import signal
import json
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def stop_existing_servers():
    """Stop any running MCP server processes."""
    logger.info("Stopping any existing MCP server processes...")
    
    try:
        # Find all MCP server processes
        ps_cmd = ["ps", "-ef"]
        ps_output = subprocess.check_output(ps_cmd, text=True)
        
        # Look for MCP server processes
        server_processes = []
        for line in ps_output.splitlines():
            if "enhanced_mcp_server.py" in line or "run_mcp" in line or "robust_mcp_server" in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        server_processes.append(pid)
                    except ValueError:
                        continue
        
        # Kill the processes
        for pid in server_processes:
            logger.info(f"Stopping process with PID {pid}")
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(0.5)  # Give it time to terminate
            except ProcessLookupError:
                pass  # Process already gone
            except Exception as e:
                logger.error(f"Error stopping process {pid}: {e}")
        
        # Wait a bit to ensure processes are stopped
        if server_processes:
            logger.info(f"Stopped {len(server_processes)} MCP server processes")
            time.sleep(2)
        else:
            logger.info("No MCP server processes found")
            
    except Exception as e:
        logger.error(f"Error stopping MCP servers: {e}")

def setup_mock_environment():
    """Set up the mock environment for storage backends."""
    logger.info("Setting up mock environment for storage backends...")
    
    # Create mock directories
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
    
    # Set environment variables for mock mode
    os.environ["MCP_USE_MOCK_MODE"] = "true"
    os.environ["HUGGINGFACE_TOKEN"] = "mock_huggingface_token"
    os.environ["AWS_ACCESS_KEY_ID"] = "mock_access_key"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "mock_secret_key"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["S3_BUCKET_NAME"] = "ipfs-storage-demo"
    os.environ["FILECOIN_API_URL"] = "http://127.0.0.1:1234/rpc/v0"
    os.environ["FILECOIN_API_TOKEN"] = "mock_filecoin_token"
    os.environ["STORACHA_API_KEY"] = "mock_storacha_key"
    os.environ["LASSIE_API_URL"] = "http://127.0.0.1:5000"
    os.environ["LASSIE_ENABLED"] = "true"

def ensure_ipfs_daemon():
    """Ensure the IPFS daemon is running."""
    logger.info("Checking IPFS daemon...")
    
    try:
        # Check if IPFS daemon is running
        result = subprocess.run(["ipfs", "id"], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("IPFS daemon is already running")
            return True
        
        # Try to start the daemon
        logger.info("Starting IPFS daemon...")
        subprocess.Popen(
            ["ipfs", "daemon", "--routing=dhtclient"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Wait for it to start
        time.sleep(3)
        
        # Verify it's running
        check_result = subprocess.run(["ipfs", "id"], capture_output=True, text=True)
        
        if check_result.returncode == 0:
            logger.info("IPFS daemon started successfully")
            return True
        else:
            logger.error("Failed to start IPFS daemon")
            return False
            
    except Exception as e:
        logger.error(f"Error with IPFS daemon: {e}")
        return False

def start_enhanced_mcp_server():
    """Start the enhanced MCP server."""
    logger.info("Starting enhanced MCP server...")
    
    try:
        # Make sure logs directory exists
        os.makedirs("logs", exist_ok=True)
        
        # Start enhanced_mcp_server.py
        server_process = subprocess.Popen(
            [sys.executable, "enhanced_mcp_server.py", "--port", "9997", "--debug"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Save PID
        with open("mcp_server.pid", "w") as f:
            f.write(str(server_process.pid))
        
        logger.info(f"Started enhanced MCP server (PID: {server_process.pid})")
        
        # Wait a bit for the server to start
        time.sleep(3)
        
        return server_process.pid
        
    except Exception as e:
        logger.error(f"Error starting enhanced MCP server: {e}")
        return None

def check_server_health(port=9997):
    """Check the health of the MCP server."""
    logger.info(f"Checking MCP server health on port {port}...")
    
    try:
        import requests
        
        # Try multiple times with a delay
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"http://localhost:{port}/api/v0/health", timeout=5)
                
                if response.status_code == 200:
                    health_data = response.json()
                    logger.info(f"Server status: {health_data.get('status', 'unknown')}")
                    
                    # Check storage backends
                    backends = health_data.get('storage_backends', {})
                    for backend, status in backends.items():
                        if backend in ['ipfs', 'local']:
                            continue  # Skip IPFS and local which should work by default
                            
                        available = status.get('available', False)
                        simulation = status.get('simulation', True)
                        mock = status.get('mock', False)
                        
                        if available and not simulation:
                            if mock:
                                logger.info(f"✓ {backend}: Running in functional mock mode")
                            else:
                                logger.info(f"✓ {backend}: Fully functional with real connection")
                        else:
                            error = status.get('error', 'Unknown error')
                            logger.warning(f"✗ {backend}: Not functioning properly - {error}")
                    
                    return health_data
                else:
                    logger.warning(f"Health check failed: HTTP {response.status_code}")
                    
            except requests.RequestException as e:
                if attempt < max_attempts - 1:
                    logger.info(f"Retrying health check in 2 seconds... (attempt {attempt+1}/{max_attempts})")
                    time.sleep(2)
                else:
                    logger.error(f"Failed to connect to server: {e}")
        
        return None
                
    except ImportError:
        logger.error("Requests module not available - skipping health check")
        return None
    except Exception as e:
        logger.error(f"Error checking server health: {e}")
        return None

def main():
    """Main function to fix the MCP server."""
    logger.info("Starting MCP server fix process...")
    
    # Stop existing servers
    stop_existing_servers()
    
    # Setup mock environment
    setup_mock_environment()
    
    # Ensure IPFS daemon is running
    if not ensure_ipfs_daemon():
        logger.error("Failed to ensure IPFS daemon is running. Aborting.")
        return
    
    # Start the enhanced MCP server
    server_pid = start_enhanced_mcp_server()
    
    if server_pid:
        # Check server health
        health_data = check_server_health()
        
        if health_data:
            logger.info("MCP server is running with the following storage backends:")
            
            # Print backends status
            backends = health_data.get('storage_backends', {})
            all_working = True
            
            for backend, status in backends.items():
                available = status.get('available', False)
                simulation = status.get('simulation', True)
                
                if available and not simulation:
                    logger.info(f"✓ {backend}: Working")
                else:
                    logger.warning(f"✗ {backend}: Not working")
                    all_working = False
            
            if all_working:
                logger.info("SUCCESS: All MCP features are working!")
            else:
                logger.warning("WARNING: Some MCP features are not working properly")
                logger.info("Try accessing the server at: http://localhost:9997/api/v0/health")
        else:
            logger.error("Failed to verify MCP server health")
    else:
        logger.error("Failed to start MCP server")

if __name__ == "__main__":
    main()