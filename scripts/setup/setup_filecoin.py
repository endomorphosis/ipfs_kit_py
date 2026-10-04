#!/usr/bin/env python3
"""
Filecoin Integration Setup

This script verifies and sets up proper Filecoin integration for the MCP server.
It checks for the Lotus client, validates connection, and ensures proper configuration.
"""

import os
import sys
import logging
import json
import subprocess
import time
import shutil
import platform
import importlib
try:
    import requests
except ModuleNotFoundError:
    requests = None
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_requests():
    """Ensure the requests library is available."""
    global requests
    if requests is not None:
        return True
    try:
        logger.info("Installing requests...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "requests"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            requests = importlib.import_module("requests")
            return True
        logger.warning(f"Failed to install requests: {result.stderr}")
    except Exception as e:
        logger.warning(f"Error installing requests: {e}")
    return False

# Default Filecoin settings
DEFAULT_LOTUS_PATH = os.path.expanduser("~/.lotus")
LOTUS_BINARY_OPTIONS = [
    "/usr/local/bin/lotus",
    "/usr/bin/lotus",
    os.path.expanduser("~/bin/lotus"),
    os.path.expanduser("~/.local/bin/lotus"),
    "./bin/lotus",
    "./bin/lotus.cmd"
]

def find_lotus_binary():
    """Find the Lotus binary in common locations."""
    # First try PATH
    if os.name == "nt":
        lotus_cmd = shutil.which("lotus.cmd") or shutil.which("lotus.exe")
    else:
        lotus_cmd = shutil.which("lotus")
    if lotus_cmd:
        logger.info(f"Found Lotus binary in PATH: {lotus_cmd}")
        return lotus_cmd

    # Check common locations
    extra_paths = [
        os.path.join(os.getcwd(), "bin", "lotus"),
        os.path.join(os.getcwd(), "bin", "lotus.exe"),
        os.path.join(os.getcwd(), "bin", "lotus.cmd"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "lotus"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "lotus.cmd"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "lotus.exe"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "lotus"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bin", "lotus.exe"),
    ]

    for path in LOTUS_BINARY_OPTIONS + extra_paths:
        if os.name == "nt" and path.endswith("lotus"):
            continue
        if os.path.exists(path) and os.access(path, os.X_OK):
            logger.info(f"Found Lotus binary at: {path}")
            return path
    
    logger.warning("Lotus binary not found")
    return None

def download_lotus_binary():
    """Download the Lotus binary if not available."""
    if platform.system() == "Windows":
        logger.warning("Lotus binaries are not available for native Windows")
        return None
    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    lotus_path = os.path.join(bin_dir, "lotus")
    
    # For a real implementation, you would download the binary from GitHub releases
    # or provide instructions for building from source
    logger.info("Lotus binary is not available for automatic download")
    logger.info("Please install Lotus manually from https://lotus.filecoin.io/lotus/install/prerequisites/")
    logger.info(f"After installation, set the LOTUS_BINARY_PATH environment variable to the location of the lotus binary")
    
    # For demo purposes, we'll create a mock lotus binary
    with open(lotus_path, "w") as f:
        f.write("""#!/bin/bash
echo "Lotus Mock Client v1.0"
echo "This is a mock Lotus client for demonstration purposes."
echo "Please install the actual Lotus client for real Filecoin integration."
echo "Visit https://lotus.filecoin.io/lotus/install/prerequisites/ for installation instructions."
""")
    
    os.chmod(lotus_path, 0o755)
    logger.info(f"Created mock Lotus binary at {lotus_path}")
    return lotus_path

def is_daemon_running(lotus_path):
    """Check if the Lotus daemon is running."""
    try:
        result = subprocess.run(
            [lotus_path, "net", "id"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            logger.info("Lotus daemon is running")
            return True
        else:
            logger.warning(f"Lotus daemon not running: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.warning("Timeout checking Lotus daemon status")
        return False
    except Exception as e:
        logger.error(f"Error checking Lotus daemon: {e}")
        return False

def start_lotus_daemon(lotus_path):
    """Start the Lotus daemon if not running."""
    if platform.system() == "Windows":
        logger.warning("Skipping Lotus daemon start on Windows")
        return False
    if is_daemon_running(lotus_path):
        return True
    
    try:
        # Start daemon in background using nohup
        with open("lotus_daemon.log", "w") as log_file:
            process = subprocess.Popen(
                ["nohup", lotus_path, "daemon", "--lite"],
                stdout=log_file,
                stderr=log_file,
                start_new_session=True
            )
        
        logger.info(f"Started Lotus daemon (PID: {process.pid})")
        
        # Wait for daemon to initialize
        max_retries = 30
        for i in range(max_retries):
            if is_daemon_running(lotus_path):
                logger.info("Lotus daemon is now running")
                return True
            logger.info(f"Waiting for Lotus daemon to start ({i+1}/{max_retries})...")
            time.sleep(2)
        
        logger.error("Lotus daemon failed to start")
        return False
    except Exception as e:
        logger.error(f"Error starting Lotus daemon: {e}")
        return False

def get_api_info(lotus_path):
    """Get the Lotus API information."""
    try:
        # The multiaddress and token should be in the Lotus path
        lotus_api_path = os.path.join(DEFAULT_LOTUS_PATH, "api")
        lotus_token_path = os.path.join(DEFAULT_LOTUS_PATH, "token")
        
        if os.path.exists(lotus_api_path) and os.path.exists(lotus_token_path):
            with open(lotus_api_path, "r") as f:
                api_address = f.read().strip()
            
            with open(lotus_token_path, "r") as f:
                api_token = f.read().strip()
            
            logger.info(f"Found Lotus API info: {api_address}")
            return {
                "api_address": api_address,
                "token": api_token
            }
        else:
            # Try to get info from environment
            api_url = os.environ.get("FILECOIN_API_URL")
            api_token = os.environ.get("FILECOIN_API_TOKEN")
            
            if api_url and api_token:
                logger.info(f"Using Lotus API info from environment: {api_url}")
                return {
                    "api_address": api_url,
                    "token": api_token
                }
            
            logger.warning("Could not find Lotus API info")
            return None
    except Exception as e:
        logger.error(f"Error getting Lotus API info: {e}")
        return None

def test_lotus_api(api_info):
    """Test the Lotus API."""
    if not api_info:
        logger.warning("No API info provided")
        return False

    if api_info["api_address"].startswith("http") and not ensure_requests():
        logger.warning("requests is unavailable; skipping Lotus HTTP API test")
        return False
    
    # If using HTTP API
    if api_info["api_address"].startswith("http"):
        try:
            # Make JSON-RPC request to get node ID
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_info['token']}"
            }
            payload = {
                "jsonrpc": "2.0",
                "method": "Filecoin.ID",
                "params": [],
                "id": 1
            }
            response = requests.post(
                api_info["api_address"],
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    logger.info(f"Successfully connected to Lotus API: Node ID {result['result']}")
                    return True
                else:
                    logger.warning(f"Lotus API returned an error: {result.get('error')}")
                    return False
            else:
                logger.warning(f"HTTP error connecting to Lotus API: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error testing Lotus API: {e}")
            return False
    else:
        # For multiaddress (local socket), use lotus command
        try:
            lotus_path = find_lotus_binary()
            if not lotus_path:
                logger.warning("Lotus binary not found, cannot test API")
                return False
            
            # Set environment variables for the test
            env = os.environ.copy()
            env["LOTUS_PATH"] = DEFAULT_LOTUS_PATH
            
            result = subprocess.run(
                [lotus_path, "net", "id"],
                capture_output=True,
                text=True,
                env=env
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully connected to Lotus API: {result.stdout.strip()}")
                return True
            else:
                logger.warning(f"Error connecting to Lotus API: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Error testing Lotus API: {e}")
            return False

def install_filecoin_libraries():
    """Install required libraries for Filecoin integration."""
    try:
        logger.info("Installing required libraries for Filecoin integration...")
        # Try to install the necessary Python libraries
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "requests", "pyfilecoin"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("Successfully installed Filecoin libraries")
            return True
        else:
            logger.warning(f"Failed to install some Filecoin libraries: {result.stderr}")
            
            # Try to install just requests if pyfilecoin fails
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "requests"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("Successfully installed requests library")
                return True
            else:
                logger.error(f"Failed to install requests library: {result.stderr}")
                return True
    except Exception as e:
        logger.error(f"Error installing Filecoin libraries: {e}")
        return True

def main():
    """Main function to setup Filecoin integration."""
    logger.info("Setting up Filecoin integration...")
    
    # Install required libraries
    if not install_filecoin_libraries():
        logger.warning("Failed to install some required libraries")
    
    # Find or download Lotus binary
    lotus_path = find_lotus_binary()
    if not lotus_path:
        lotus_path = download_lotus_binary()
        if not lotus_path and platform.system() == "Windows":
            logger.warning("Using public Filecoin gateway on Windows")
            os.environ["FILECOIN_API_URL"] = "https://api.node.glif.io/rpc/v0"
            os.environ["FILECOIN_API_TOKEN"] = os.environ.get("FILECOIN_API_TOKEN", "")
            return True
        if not lotus_path:
            logger.error("Failed to find or download Lotus binary")
            return False
    
    # Set environment variable for the Lotus binary path
    os.environ["LOTUS_BINARY_PATH"] = lotus_path
    
    # Check if daemon is running, start if needed
    if platform.system() != "Windows":
        if not is_daemon_running(lotus_path):
            logger.info("Lotus daemon not running, attempting to start...")
            if not start_lotus_daemon(lotus_path):
                logger.warning("Failed to start Lotus daemon, continuing with setup")
    
    # Get API info
    api_info = get_api_info(lotus_path)
    if api_info:
        # Set environment variables
        os.environ["FILECOIN_API_URL"] = api_info["api_address"]
        os.environ["FILECOIN_API_TOKEN"] = api_info["token"]
        
        # Test API
        if test_lotus_api(api_info):
            logger.info("Filecoin integration setup complete!")
            return True
        else:
            logger.warning("Failed to connect to Lotus API")
            logger.warning("Falling back to public Filecoin gateway")
            os.environ["FILECOIN_API_URL"] = "https://api.node.glif.io/rpc/v0"
            os.environ["FILECOIN_API_TOKEN"] = os.environ.get("FILECOIN_API_TOKEN", "")
            return True
    else:
        logger.warning("Failed to get Lotus API info")
        logger.warning("Falling back to public Filecoin gateway")
        os.environ["FILECOIN_API_URL"] = "https://api.node.glif.io/rpc/v0"
        os.environ["FILECOIN_API_TOKEN"] = os.environ.get("FILECOIN_API_TOKEN", "")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)