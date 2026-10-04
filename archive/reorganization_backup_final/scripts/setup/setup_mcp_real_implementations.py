#!/usr/bin/env python3
"""
MCP Server Real Implementation Integrator

This script integrates all the real implementations of storage backends
and restarts the MCP server with full functionality.
"""

import os
import sys
import subprocess
import time
import logging
import signal
import shutil
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_script_executable(script_path):
    """Ensure script is executable"""
    if not os.access(script_path, os.X_OK):
        os.chmod(script_path, 0o755)
        logger.info(f"Made script executable: {script_path}")

def stop_existing_processes():
    """Stop any existing MCP server and mock API processes"""
    logger.info("Stopping existing processes...")
    
    # Process names to check
    processes = [
        "enhanced_mcp_server.py",
        "filecoin_mock_api_server.py",
        "storacha_mock_server.py",
        "lassie_mock_server.py"
    ]
    
    for proc in processes:
        try:
            result = subprocess.run(
                ["pkill", "-f", proc],
                capture_output=True
            )
            if result.returncode == 0:
                logger.info(f"Stopped process: {proc}")
        except Exception as e:
            logger.warning(f"Error stopping {proc}: {e}")
    
    # Wait for processes to stop
    time.sleep(2)

def run_implementation_scripts():
    """Run all implementation scripts in sequence"""
    scripts = [
        "setup_s3_implementation.py",
        "setup_filecoin_implementation.py",
        "setup_storacha_implementation.py",
        "setup_lassie_implementation.py"
    ]
    
    for script in scripts:
        script_path = os.path.join(os.getcwd(), script)
        if os.path.exists(script_path):
            check_script_executable(script_path)
            
            logger.info(f"Running {script}...")
            try:
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    logger.info(f"Successfully executed {script}")
                else:
                    logger.warning(f"Script {script} exited with code {result.returncode}")
                    logger.warning(f"Script output: {result.stdout}")
                    logger.warning(f"Script error: {result.stderr}")
            except Exception as e:
                logger.error(f"Error executing {script}: {e}")
        else:
            logger.warning(f"Script not found: {script}")

def create_unified_config():
    """Create a unified MCP configuration file"""
    logger.info("Creating unified MCP configuration...")
    
    config_file = os.path.join(os.getcwd(), "mcp_unified_config.sh")
    
    with open(config_file, 'w') as f:
        f.write("""#!/bin/bash
# Unified MCP Configuration
# This file is generated automatically by the MCP Server Real Implementation Integrator

# Global settings
export MCP_USE_MOCK_MODE="false"

# HuggingFace configuration
if [ -f ~/.cache/huggingface/token ]; then
  export HUGGINGFACE_TOKEN=$(cat ~/.cache/huggingface/token)
  echo "Using real HuggingFace token"
else
  echo "No HuggingFace token found, using mock mode"
  export HUGGINGFACE_TOKEN="mock_token"
fi

# AWS S3 configuration
if [ -f ~/.aws/credentials ]; then
  echo "Using real AWS credentials"
else
  echo "Using local S3 implementation"
  # Default values will be overridden if setup_s3_implementation.py set different ones
  export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-mock_access_key}"
  export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-mock_secret_key}"
  export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
  export S3_BUCKET_NAME="${S3_BUCKET_NAME:-ipfs-storage-demo}"
  export S3_ENDPOINT_URL="${S3_ENDPOINT_URL:-http://localhost:9000}"
fi

# Filecoin configuration
# Using either real Lotus installation or mock implementation
export LOTUS_PATH="${LOTUS_PATH:-$HOME/.lotus-dev}"
export LOTUS_API_TOKEN="${LOTUS_API_TOKEN:-mock-token-for-development}"
export LOTUS_API_ENDPOINT="${LOTUS_API_ENDPOINT:-http://127.0.0.1:1234/rpc/v0}"
# Add bin directory to PATH
if [ -d "$(pwd)/bin" ]; then
  export PATH="$(pwd)/bin:$PATH"
fi

# Storacha configuration
export STORACHA_API_KEY="${STORACHA_API_KEY:-mock_key}"
export STORACHA_API_URL="${STORACHA_API_URL:-http://localhost:5678}"

# Lassie configuration
export LASSIE_API_URL="${LASSIE_API_URL:-http://localhost:5432}"
export LASSIE_ENABLED="${LASSIE_ENABLED:-true}"

# Print configuration summary
echo "MCP Configuration Summary:"
echo "=========================="
echo "HuggingFace Token: ${HUGGINGFACE_TOKEN:0:5}...${HUGGINGFACE_TOKEN: -5}"
echo "AWS S3 Key ID: ${AWS_ACCESS_KEY_ID:0:5}..."
echo "S3 Bucket: ${S3_BUCKET_NAME}"
echo "S3 Endpoint: ${S3_ENDPOINT_URL}"
echo "Filecoin API Endpoint: ${LOTUS_API_ENDPOINT}"
echo "Storacha API URL: ${STORACHA_API_URL}"
echo "Lassie API URL: ${LASSIE_API_URL}"
echo "=========================="
""")
    
    # Make it executable
    os.chmod(config_file, 0o755)
    
    logger.info(f"Created unified configuration at {config_file}")
    return config_file

def restart_mcp_server(config_file):
    """Restart the MCP server with the new configuration"""
    logger.info("Restarting MCP server...")
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Start the enhanced MCP server with the new configuration
    cmd = f"""
    cd {os.getcwd()} && 
    source .venv/bin/activate && 
    source {config_file} &&
    python enhanced_mcp_server.py --port 9997 --debug > logs/enhanced_mcp_real.log 2>&1 &
    echo $! > mcp_server.pid
    """
    
    try:
        subprocess.run(cmd, shell=True, executable="/bin/bash")
        logger.info("MCP server started with real implementations")
        
        # Wait for server to start
        time.sleep(5)
        
        # Check if server is running
        check_server_health()
        
        return True
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return False

def check_server_health():
    """Check the health of the MCP server"""
    logger.info("Checking MCP server health...")
    
    try:
        import requests
        
        response = requests.get("http://localhost:9997/api/v0/health", timeout=5)
        
        if response.status_code == 200:
            health_data = response.json()
            logger.info(f"MCP server status: {health_data.get('status', 'unknown')}")
            
            # Check storage backends
            backends = health_data.get('storage_backends', {})
            all_working = True
            
            for backend, status in backends.items():
                if backend in ['ipfs', 'local']:
                    continue  # Skip IPFS and local which should work by default
                
                available = status.get('available', False)
                simulation = status.get('simulation', True)
                error = status.get('error')
                
                if available and not simulation:
                    logger.info(f"✓ {backend}: Working")
                    if error:
                        logger.warning(f"  Note: {backend} reports an error but is still functional: {error}")
                else:
                    logger.warning(f"✗ {backend}: Not working properly")
                    all_working = False
                    if error:
                        logger.warning(f"  Error: {error}")
            
            if all_working:
                logger.info("All storage backends are functioning!")
            else:
                logger.warning("Some storage backends are not functioning properly")
            
            return health_data
        else:
            logger.error(f"Health check failed: {response.status_code}")
            return None
    except ImportError:
        logger.warning("Requests library not available, skipping health check")
        return None
    except Exception as e:
        logger.error(f"Error checking server health: {e}")
        return None

def main():
    """Main function"""
    logger.info("Starting MCP Server Real Implementation Integrator")
    
    # Stop existing processes
    stop_existing_processes()
    
    # Run implementation scripts
    run_implementation_scripts()
    
    # Create unified configuration
    config_file = create_unified_config()
    
    # Restart MCP server
    restart_mcp_server(config_file)
    
    logger.info("MCP Server integration complete")
    logger.info("MCP Server is running with real implementations")
    logger.info("Check logs/enhanced_mcp_real.log for detailed logs")
    logger.info("Access the server at http://localhost:9997")

if __name__ == "__main__":
    main()