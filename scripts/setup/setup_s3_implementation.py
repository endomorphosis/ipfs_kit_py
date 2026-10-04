#!/usr/bin/env python3
"""
AWS S3 Implementation Setup for MCP Server

This script sets up a working AWS S3 implementation for the MCP server using
either existing credentials or creating temporary credentials with proper permissions.
"""

import os
import sys
import json
import uuid
import logging
import subprocess
import importlib
from pathlib import Path
import configparser
try:
    import boto3
except ModuleNotFoundError:
    boto3 = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def ensure_boto3():
    """Ensure boto3 is available."""
    global boto3
    if boto3 is not None:
        return True
    try:
        logger.info("Installing boto3...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "boto3"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            boto3 = importlib.import_module("boto3")
            return True
        logger.warning(f"Failed to install boto3: {result.stderr}")
    except Exception as e:
        logger.warning(f"Error installing boto3: {e}")
    return False

AWS_CONFIG_DIR = os.path.expanduser("~/.aws")
AWS_CREDS_FILE = os.path.join(AWS_CONFIG_DIR, "credentials")
AWS_CONFIG_FILE = os.path.join(AWS_CONFIG_DIR, "config")

def setup_aws_configuration():
    """Set up AWS configuration directory if it doesn't exist"""
    os.makedirs(AWS_CONFIG_DIR, exist_ok=True)
    
    if not os.path.exists(AWS_CONFIG_FILE):
        config = configparser.ConfigParser()
        config['default'] = {
            'region': 'us-east-1',
            'output': 'json'
        }
        
        with open(AWS_CONFIG_FILE, 'w') as f:
            config.write(f)
        
        logger.info(f"Created AWS config file at {AWS_CONFIG_FILE}")
    
    return True

def check_existing_aws_credentials():
    """Check if AWS credentials already exist"""
    # Check environment variables
    if os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('AWS_SECRET_ACCESS_KEY'):
        logger.info("Found AWS credentials in environment variables")
        return True
    
    # Check credentials file
    if os.path.exists(AWS_CREDS_FILE):
        config = configparser.ConfigParser()
        config.read(AWS_CREDS_FILE)
        
        if 'default' in config and 'aws_access_key_id' in config['default'] and 'aws_secret_access_key' in config['default']:
            logger.info("Found AWS credentials in credentials file")
            return True
    
    return False

def create_local_aws_credentials():
    """Create a local AWS credential file with temporary credentials using boto3 session"""
    try:
        # Create a session with 'fake' credentials for localstack/minio
        config = configparser.ConfigParser()
        config['default'] = {
            'aws_access_key_id': f'mcp-test-key-{uuid.uuid4().hex[:8]}',
            'aws_secret_access_key': f'mcp-test-secret-{uuid.uuid4().hex}',
            'region': 'us-east-1'
        }
        
        # Create the credentials file
        with open(AWS_CREDS_FILE, 'w') as f:
            config.write(f)
        
        # Set permissions
        os.chmod(AWS_CREDS_FILE, 0o600)
        
        logger.info(f"Created temporary AWS credentials in {AWS_CREDS_FILE}")
        
        # Also set environment variables
        os.environ['AWS_ACCESS_KEY_ID'] = config['default']['aws_access_key_id']
        os.environ['AWS_SECRET_ACCESS_KEY'] = config['default']['aws_secret_access_key']
        os.environ['AWS_DEFAULT_REGION'] = config['default']['region']
        
        return True
    except Exception as e:
        logger.error(f"Error creating AWS credentials: {e}")
        return False

def setup_local_s3_server():
    """Set up a local S3-compatible server like MinIO or configure endpoint for localstack"""
    from subprocess import Popen, PIPE, STDOUT
    
    # Check if Docker is installed
    try:
        import subprocess
        result = subprocess.run(['docker', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            logger.warning("Docker not available. Cannot start local S3 server.")
            return False
    except:
        logger.warning("Docker not available. Cannot start local S3 server.")
        return False
    
    # Check if MinIO is running
    try:
        result = subprocess.run(['docker', 'ps', '--filter', 'name=minio-server'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if 'minio-server' in result.stdout:
            logger.info("MinIO server is already running")
            return True
    except:
        pass
    
    # Start MinIO in Docker
    logger.info("Starting MinIO server in Docker...")
    
    try:
        # Create directories for MinIO data
        minio_data_dir = os.path.expanduser("~/.minio/data")
        os.makedirs(minio_data_dir, exist_ok=True)
        
        # Pull MinIO image
        subprocess.run(['docker', 'pull', 'minio/minio'], check=True)
        
        # Start MinIO server
        cmd = [
            'docker', 'run', '-d',
            '--name', 'minio-server',
            '-p', '9000:9000',
            '-p', '9001:9001',
            '-e', f'MINIO_ROOT_USER={os.environ["AWS_ACCESS_KEY_ID"]}',
            '-e', f'MINIO_ROOT_PASSWORD={os.environ["AWS_SECRET_ACCESS_KEY"]}',
            '-v', f'{minio_data_dir}:/data',
            'minio/minio', 'server', '/data', '--console-address', ':9001'
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode == 0:
            logger.info(f"Started MinIO server: {result.stdout.strip()}")
            
            # Set environment variable to point to local MinIO
            os.environ['S3_ENDPOINT_URL'] = 'http://localhost:9000'
            
            # Wait for MinIO to start
            import time
            time.sleep(3)
            
            # Create the bucket
            create_s3_bucket()
            
            return True
        else:
            logger.error(f"Failed to start MinIO: {result.stderr}")
            return False
    
    except Exception as e:
        logger.error(f"Error starting MinIO: {e}")
        return False

def create_s3_bucket():
    """Create S3 bucket for testing"""
    if not ensure_boto3():
        logger.warning("boto3 is unavailable; skipping S3 bucket creation")
        return False
    bucket_name = 'ipfs-storage-demo'
    
    try:
        # Create S3 client
        endpoint_url = os.environ.get('S3_ENDPOINT_URL')
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')
        )
        
        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} already exists")
        except:
            # Create bucket
            logger.info(f"Creating bucket {bucket_name}")
            
            if endpoint_url:  # For local S3 servers
                s3_client.create_bucket(Bucket=bucket_name)
            else:  # For AWS S3
                if os.environ.get('AWS_DEFAULT_REGION') == 'us-east-1':
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={
                            'LocationConstraint': os.environ.get('AWS_DEFAULT_REGION')
                        }
                    )
            
            logger.info(f"Successfully created bucket {bucket_name}")
        
        # Upload a test file
        test_file = os.path.join(os.getcwd(), "s3_test_file.txt")
        with open(test_file, 'w') as f:
            f.write(f"S3 Test file for MCP Server - {uuid.uuid4()}")
        
        s3_client.upload_file(test_file, bucket_name, 'test/s3_test_file.txt')
        logger.info(f"Uploaded test file to s3://{bucket_name}/test/s3_test_file.txt")
        
        return True
    except Exception as e:
        logger.error(f"Error creating S3 bucket: {e}")
        return False

def update_mcp_config():
    """Update MCP configuration with the S3 settings"""
    repo_root = Path(__file__).resolve().parents[2]
    config_candidates = [
        Path(os.getcwd()) / "mcp_config.sh",
        Path(__file__).resolve().parent / "config" / "mcp_config.sh",
        repo_root / "scripts" / "setup" / "config" / "mcp_config.sh",
    ]
    config_file = next((str(path) for path in config_candidates if path.exists()), None)
    if not config_file:
        logger.warning("MCP config file not found. Skipping config update.")
        return True
    
    try:
        # Read existing file
        with open(config_file, 'r') as f:
            lines = f.readlines()
        
        # Find S3 section and update it
        s3_section_start = -1
        s3_section_end = -1
        
        for i, line in enumerate(lines):
            if "# AWS S3 configuration" in line:
                s3_section_start = i
            elif s3_section_start > -1 and "fi" in line and s3_section_end == -1:
                s3_section_end = i
        
        if s3_section_start > -1 and s3_section_end > -1:
            # Create new S3 configuration
            new_s3_config = [
                "# AWS S3 configuration\n",
                "# Using real S3 credentials configured by setup script\n",
                "export AWS_ACCESS_KEY_ID=\"{}\"\n".format(os.environ.get('AWS_ACCESS_KEY_ID')),
                "export AWS_SECRET_ACCESS_KEY=\"{}\"\n".format(os.environ.get('AWS_SECRET_ACCESS_KEY')),
                "export AWS_DEFAULT_REGION=\"{}\"\n".format(os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')),
                "export S3_BUCKET_NAME=\"ipfs-storage-demo\"\n"
            ]
            
            # Add endpoint URL if using local S3
            if os.environ.get('S3_ENDPOINT_URL'):
                new_s3_config.append("export S3_ENDPOINT_URL=\"{}\"\n".format(os.environ.get('S3_ENDPOINT_URL')))
            
            # Replace the section
            lines[s3_section_start:s3_section_end+1] = new_s3_config
            
            # Write updated file
            with open(config_file, 'w') as f:
                f.writelines(lines)
            
            logger.info(f"Updated MCP configuration file with S3 settings")
            return True
        else:
            logger.error("Could not find S3 section in MCP configuration file")
            return False
    
    except Exception as e:
        logger.error(f"Error updating MCP configuration: {e}")
        return False

def main():
    """Main function"""
    logger.info("Setting up AWS S3 implementation for MCP Server")
    
    # Set up AWS configuration directory
    setup_aws_configuration()
    
    # Check for existing credentials
    if not check_existing_aws_credentials():
        logger.info("No existing AWS credentials found. Creating temporary credentials...")
        create_local_aws_credentials()
    
    # Set up local S3 server (MinIO)
    if not setup_local_s3_server():
        logger.warning("Failed to set up local S3 server. S3 backend may not be fully functional.")
    
    # Update MCP configuration
    update_mcp_config()
    
    logger.info("AWS S3 implementation setup complete.")
    logger.info("Restart the MCP server to apply changes.")

if __name__ == "__main__":
    main()