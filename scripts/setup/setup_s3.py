#!/usr/bin/env python3
"""
AWS S3 Integration Setup

This script verifies and sets up proper AWS S3 integration for the MCP server.
It checks for required libraries, validates credentials, and ensures the bucket exists.
"""

import os
import sys
import logging
import json
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def install_boto3():
    """Install the boto3 library."""
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

def verify_s3_credentials():
    """Verify AWS S3 credentials."""
    access_key = os.environ.get("AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
    region = os.environ.get("AWS_REGION", "us-east-1")
    
    if not access_key or not secret_key:
        logger.warning("AWS credentials not found in environment")
        logger.info("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        return None
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        # Create S3 client
        try:
            s3 = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            
            # Try listing buckets to verify credentials
            response = s3.list_buckets()
            
            logger.info(f"Successfully authenticated with AWS S3 - found {len(response['Buckets'])} buckets")
            return True
        except NoCredentialsError:
            logger.error("AWS credentials not found or invalid")
            return False
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            error_message = e.response.get('Error', {}).get('Message', '')
            logger.error(f"AWS S3 error: {error_code} - {error_message}")
            return False
    except ImportError:
        logger.error("boto3 library is not installed")
        if install_boto3():
            # Try again after installation
            return verify_s3_credentials()
        return False
    except Exception as e:
        logger.error(f"Error verifying AWS S3 credentials: {e}")
        return False

def ensure_bucket_exists():
    """Ensure the S3 bucket exists, creating it if necessary."""
    bucket_name = os.environ.get("AWS_S3_BUCKET_NAME")
    region = os.environ.get("AWS_REGION", "us-east-1")
    
    if not bucket_name:
        logger.warning("No S3 bucket name found in environment")
        logger.info("Set AWS_S3_BUCKET_NAME environment variable")
        return False
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Create S3 client
        s3 = boto3.client('s3')
        
        # Check if bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
            logger.info(f"S3 bucket '{bucket_name}' already exists")
            return True
        except ClientError as e:
            error_code = int(e.response.get('Error', {}).get('Code', 0))
            
            # If bucket doesn't exist (404) or we don't have access (403), create it
            if error_code == 404 or error_code == 403:
                logger.info(f"Creating S3 bucket '{bucket_name}'...")
                try:
                    # Create bucket with location constraint if not in us-east-1
                    if region == 'us-east-1':
                        s3.create_bucket(Bucket=bucket_name)
                    else:
                        s3.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                    logger.info(f"Successfully created S3 bucket '{bucket_name}'")
                    return True
                except ClientError as e:
                    logger.error(f"Failed to create S3 bucket: {e}")
                    return False
            else:
                logger.error(f"Error checking S3 bucket: {e}")
                return False
    except ImportError:
        logger.error("boto3 library is not installed")
        return False
    except Exception as e:
        logger.error(f"Error ensuring S3 bucket exists: {e}")
        return False

def test_s3_upload():
    """Test uploading a small file to S3."""
    bucket_name = os.environ.get("AWS_S3_BUCKET_NAME")
    
    if not bucket_name:
        logger.warning("No S3 bucket name found in environment")
        return False
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        # Create a test file
        test_file = "test_s3_upload.txt"
        with open(test_file, "w") as f:
            f.write("This is a test file for S3 integration.")
        
        # Create S3 client
        s3 = boto3.client('s3')
        
        # Upload test file
        try:
            s3.upload_file(
                Filename=test_file,
                Bucket=bucket_name,
                Key="test/test_s3_upload.txt"
            )
            logger.info(f"Successfully uploaded test file to S3 bucket '{bucket_name}'")
            
            # Clean up test file
            os.remove(test_file)
            
            return True
        except ClientError as e:
            logger.error(f"Failed to upload test file to S3: {e}")
            
            # Clean up test file
            if os.path.exists(test_file):
                os.remove(test_file)
                
            return False
    except ImportError:
        logger.error("boto3 library is not installed")
        return False
    except Exception as e:
        logger.error(f"Error testing S3 upload: {e}")
        
        # Clean up test file if it exists
        if os.path.exists("test_s3_upload.txt"):
            os.remove("test_s3_upload.txt")
            
        return False

def main():
    """Main function to setup AWS S3 integration."""
    logger.info("Setting up AWS S3 integration...")
    
    # Verify credentials
    credentials_status = verify_s3_credentials()
    if credentials_status is None:
        logger.warning("Skipping S3 verification due to missing credentials")
        logger.info("S3 integration will run in mock/simulation mode")
        return True
    if credentials_status is False:
        logger.error("Failed to verify AWS S3 credentials")
        return False
    
    # Ensure bucket exists
    if not ensure_bucket_exists():
        logger.error("Failed to ensure S3 bucket exists")
        return False
    
    # Test upload
    if not test_s3_upload():
        logger.warning("Failed to test S3 upload, but continuing setup")
    
    logger.info("AWS S3 integration setup complete!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)