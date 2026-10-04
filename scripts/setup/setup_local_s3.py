#!/usr/bin/env python3
"""
Local S3 Server Setup

This script sets up a local S3-compatible server using MinIO, which can
replace the need for actual AWS credentials for development and testing.
"""

import os
import sys
import logging
import json
import subprocess
import time
import shutil
import importlib
try:
    import requests
except ModuleNotFoundError:
    requests = None
import tempfile
import platform
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

# MinIO configuration
MINIO_PORT = 9000
MINIO_CONSOLE_PORT = 9001
MINIO_ROOT_USER = "minioadmin"
MINIO_ROOT_PASSWORD = "minioadmin"
MINIO_DATA_DIR = os.path.expanduser("~/.ipfs_kit/minio/data")
MINIO_CONFIG_DIR = os.path.expanduser("~/.ipfs_kit/minio/config")

def is_minio_installed():
    """Check if MinIO server is installed."""
    try:
        result = subprocess.run(
            ["minio", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info(f"MinIO is installed: {result.stdout.strip()}")
            return True
        else:
            logger.warning(f"MinIO version check failed: {result.stderr}")
            return False
    except FileNotFoundError:
        logger.warning("MinIO is not installed")
        return False
    except Exception as e:
        logger.error(f"Error checking MinIO installation: {e}")
        return False

def download_minio():
    """Download MinIO server binary."""
    if not ensure_requests():
        logger.warning("requests is unavailable; skipping MinIO download")
        return None
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Map architecture names
    if machine in ['x86_64', 'amd64']:
        arch = 'amd64'
    elif machine in ['aarch64', 'arm64']:
        arch = 'arm64'
    else:
        logger.error(f"Unsupported architecture: {machine}")
        return None
    
    # Create bin directory if it doesn't exist
    bin_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    minio_path = os.path.join(bin_dir, "minio")
    
    # Download URL based on system and architecture
    if system == 'linux':
        download_url = f"https://dl.min.io/server/minio/release/linux-{arch}/minio"
    elif system == 'darwin':  # macOS
        download_url = f"https://dl.min.io/server/minio/release/darwin-{arch}/minio"
    else:
        logger.error(f"Unsupported operating system: {system}")
        return None
    
    try:
        logger.info(f"Downloading MinIO from {download_url}")
        
        # Download the binary
        response = requests.get(download_url, stream=True)
        if response.status_code == 200:
            with open(minio_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Make it executable
            os.chmod(minio_path, 0o755)
            logger.info(f"MinIO downloaded to {minio_path}")
            return minio_path
        else:
            logger.error(f"Failed to download MinIO: HTTP {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error downloading MinIO: {e}")
        return None

def find_minio_binary():
    """Find the MinIO binary in common locations."""
    # First try using 'which'
    try:
        result = subprocess.run(
            ["which", "minio"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            minio_path = result.stdout.strip()
            logger.info(f"Found MinIO at: {minio_path}")
            return minio_path
    except Exception:
        pass
    
    # Check common locations
    common_paths = [
        "/usr/local/bin/minio",
        "/usr/bin/minio",
        os.path.expanduser("~/bin/minio"),
        os.path.expanduser("~/.local/bin/minio"),
        "./bin/minio",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin/minio")
    ]
    
    for path in common_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            logger.info(f"Found MinIO at: {path}")
            return path
    
    logger.warning("MinIO not found in common locations")
    return None

def install_boto3():
    """Install boto3 library."""
    try:
        logger.info("Installing boto3...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "boto3"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            logger.info("Successfully installed boto3")
            return True
        else:
            logger.error(f"Failed to install boto3: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error installing boto3: {e}")
        return False

def is_minio_running():
    """Check if MinIO server is running."""
    try:
        response = requests.get(f"http://localhost:{MINIO_PORT}/minio/health/live", timeout=5)
        if response.status_code == 200:
            logger.info("MinIO server is running")
            return True
        else:
            logger.warning(f"MinIO health check failed: HTTP {response.status_code}")
            return False
    except requests.RequestException:
        logger.warning("MinIO server is not running")
        return False

def start_minio_server(minio_path):
    """Start the MinIO server."""
    if is_minio_running():
        logger.info("MinIO server is already running")
        return True
    
    # Create data and config directories
    os.makedirs(MINIO_DATA_DIR, exist_ok=True)
    os.makedirs(MINIO_CONFIG_DIR, exist_ok=True)
    
    # Environment variables for MinIO
    env = os.environ.copy()
    env["MINIO_ROOT_USER"] = MINIO_ROOT_USER
    env["MINIO_ROOT_PASSWORD"] = MINIO_ROOT_PASSWORD
    
    try:
        # Start MinIO server in the background
        logger.info(f"Starting MinIO server on port {MINIO_PORT}")
        process = subprocess.Popen(
            [
                minio_path, "server",
                "--address", f":{MINIO_PORT}",
                "--console-address", f":{MINIO_CONSOLE_PORT}",
                MINIO_DATA_DIR
            ],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True
        )
        
        # Wait for server to start
        max_retries = 10
        for i in range(max_retries):
            if is_minio_running():
                logger.info(f"MinIO server started successfully (PID: {process.pid})")
                
                # Save PID to file
                with open("minio_server.pid", "w") as f:
                    f.write(str(process.pid))
                
                return True
            logger.info(f"Waiting for MinIO server to start ({i+1}/{max_retries})...")
            time.sleep(1)
        
        logger.error("MinIO server failed to start within timeout")
        return False
    except Exception as e:
        logger.error(f"Error starting MinIO server: {e}")
        return False

def create_s3_bucket():
    """Create an S3 bucket in the MinIO server."""
    try:
        # Check if boto3 is installed
        try:
            import boto3
        except ImportError:
            if not install_boto3():
                logger.error("Failed to install boto3, cannot create bucket")
                return False
            import boto3
        
        # Create S3 client
        s3 = boto3.client(
            's3',
            endpoint_url=f"http://localhost:{MINIO_PORT}",
            aws_access_key_id=MINIO_ROOT_USER,
            aws_secret_access_key=MINIO_ROOT_PASSWORD,
            region_name="us-east-1"
        )
        
        bucket_name = "ipfs-storage-demo"
        
        # Check if bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket '{bucket_name}' already exists")
            return True
        except Exception:
            # Create bucket
            try:
                s3.create_bucket(Bucket=bucket_name)
                logger.info(f"Created bucket '{bucket_name}'")
                return True
            except Exception as e:
                logger.error(f"Failed to create bucket: {e}")
                return False
    except Exception as e:
        logger.error(f"Error creating S3 bucket: {e}")
        return False

def update_mcp_credentials():
    """Update MCP credentials to use local MinIO server."""
    creds_file = "real_mcp_credentials.sh"
    if not os.path.exists(creds_file):
        creds_file = "mcp_credentials.sh"
    
    if not os.path.exists(creds_file):
        logger.warning("No credentials file found, creating new one")
        creds_file = "local_mcp_credentials.sh"
    
    try:
        # Create or update credentials file
        with open(creds_file, "w") as f:
            f.write(f"""#!/bin/bash
# MCP Server Credentials for Local Services

# AWS S3 credentials (MinIO)
export AWS_ENDPOINT_URL="http://localhost:{MINIO_PORT}"
export AWS_ACCESS_KEY_ID="{MINIO_ROOT_USER}"
export AWS_SECRET_ACCESS_KEY="{MINIO_ROOT_PASSWORD}"
export AWS_S3_BUCKET_NAME="ipfs-storage-demo"
export AWS_REGION="us-east-1"

# Set this to true to use local implementations
export USE_LOCAL_IMPLEMENTATIONS="true"
""")
        
        os.chmod(creds_file, 0o755)
        logger.info(f"Updated credentials in {creds_file}")
        
        # Load the credentials into the environment
        os.environ["AWS_ENDPOINT_URL"] = f"http://localhost:{MINIO_PORT}"
        os.environ["AWS_ACCESS_KEY_ID"] = MINIO_ROOT_USER
        os.environ["AWS_SECRET_ACCESS_KEY"] = MINIO_ROOT_PASSWORD
        os.environ["AWS_S3_BUCKET_NAME"] = "ipfs-storage-demo"
        os.environ["AWS_REGION"] = "us-east-1"
        
        return True
    except Exception as e:
        logger.error(f"Error updating credentials file: {e}")
        return False

def test_s3_connection():
    """Test the S3 connection to the MinIO server."""
    try:
        import boto3
        
        # Create S3 client
        s3 = boto3.client(
            's3',
            endpoint_url=f"http://localhost:{MINIO_PORT}",
            aws_access_key_id=MINIO_ROOT_USER,
            aws_secret_access_key=MINIO_ROOT_PASSWORD,
            region_name="us-east-1"
        )
        
        # List buckets
        response = s3.list_buckets()
        
        # Print the bucket names
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        logger.info(f"S3 connection successful. Buckets: {buckets}")
        
        # Test uploading a file
        test_data = b"Test data for S3"
        s3.put_object(
            Bucket="ipfs-storage-demo",
            Key="test.txt",
            Body=test_data
        )
        
        # Test downloading the file
        response = s3.get_object(
            Bucket="ipfs-storage-demo",
            Key="test.txt"
        )
        content = response['Body'].read()
        
        if content == test_data:
            logger.info("S3 upload/download test successful")
            return True
        else:
            logger.warning("S3 upload/download test failed: content mismatch")
            return False
    except Exception as e:
        logger.error(f"Error testing S3 connection: {e}")
        return False

def update_s3_extension():
    """Update the S3 extension to use the local MinIO server."""
    s3_extension_path = "mcp_extensions/s3_extension.py"
    
    if not os.path.exists(s3_extension_path):
        logger.warning(f"S3 extension file not found: {s3_extension_path}")
        return False
    
    try:
        with open(s3_extension_path, "r") as f:
            content = f.read()
        
        # Check if we need to modify the file
        if "endpoint_url=os.environ.get(\"AWS_ENDPOINT_URL\")" not in content:
            # Add endpoint_url parameter to boto3.client
            content = content.replace(
                "s3_client = boto3.client(\n            's3',",
                "s3_client = boto3.client(\n            's3',\n            endpoint_url=os.environ.get(\"AWS_ENDPOINT_URL\"),"
            )
            
            with open(s3_extension_path, "w") as f:
                f.write(content)
            
            logger.info("Updated S3 extension to use local MinIO server")
        else:
            logger.info("S3 extension already configured for local MinIO server")
        
        return True
    except Exception as e:
        logger.error(f"Error updating S3 extension: {e}")
        return False

def main():
    """Main function to setup local S3 server."""
    logger.info("Setting up local S3 server using MinIO...")

    if platform.system().lower() == "windows":
        logger.warning("Local MinIO setup is not supported on Windows in this script. Skipping.")
        return True
    
    # Check if MinIO is installed
    minio_path = find_minio_binary()
    
    if not minio_path:
        logger.info("MinIO not found, downloading...")
        minio_path = download_minio()
        
        if not minio_path:
            logger.error("Failed to download MinIO")
            return False
    
    # Start MinIO server
    if not start_minio_server(minio_path):
        logger.error("Failed to start MinIO server")
        return False
    
    # Create S3 bucket
    if not create_s3_bucket():
        logger.warning("Failed to create S3 bucket")
    
    # Update MCP credentials
    if not update_mcp_credentials():
        logger.warning("Failed to update MCP credentials")
    
    # Update S3 extension
    if not update_s3_extension():
        logger.warning("Failed to update S3 extension")
    
    # Test S3 connection
    if not test_s3_connection():
        logger.warning("S3 connection test failed")
    
    logger.info("Local S3 server setup complete!")
    logger.info(f"MinIO server running on port {MINIO_PORT}")
    logger.info(f"MinIO console available at http://localhost:{MINIO_CONSOLE_PORT}")
    logger.info(f"S3 endpoint: http://localhost:{MINIO_PORT}")
    logger.info(f"Access key: {MINIO_ROOT_USER}")
    logger.info(f"Secret key: {MINIO_ROOT_PASSWORD}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)