"""
S3 storage backend implementation for MCP server.

This module provides real (non-simulated) integration with AWS S3
for storing and retrieving IPFS content.
"""

import os
import json
import logging
import tempfile
import time
import subprocess
from typing import Dict, Any, Optional, Union, List

# Configure logging
logger = logging.getLogger(__name__)

# Check if boto3 is available
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
    logger.info("AWS S3 SDK (boto3) is available")
except ImportError:
    S3_AVAILABLE = False
    logger.warning("AWS S3 SDK (boto3) is not available. Install with: pip install boto3")

# Mock S3 client for when credentials are not available
class MockS3Client:
    """A mock implementation of the S3 client for use when real credentials are not available."""

    def __init__(self, bucket_name="mock-bucket", region_name="us-east-1"):
        self.bucket_name = bucket_name
        self.region_name = region_name
        self.mock_data_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", bucket_name)
        # Ensure mock directory exists
        os.makedirs(self.mock_data_dir, exist_ok=True)
        logger.info(f"Initialized mock S3 client with bucket: {bucket_name}")

    def list_objects_v2(self, Bucket=None, Prefix=None, MaxKeys=1000):
        """Mock implementation of list_objects_v2."""
        bucket_dir = self.mock_data_dir
        if Bucket:
            bucket_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", Bucket)
            os.makedirs(bucket_dir, exist_ok=True)

        contents = []
        count = 0

        # Walk the directory and find files
        for root, dirs, files in os.walk(bucket_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, bucket_dir)

                # Apply prefix filter if specified
                if Prefix and not rel_path.startswith(Prefix):
                    continue

                # Get file stats
                stat = os.stat(full_path)

                contents.append({
                    'Key': rel_path,
                    'Size': stat.st_size,
                    'LastModified': time.ctime(stat.st_mtime),
                    'ETag': f"mock-etag-{hash(rel_path)}",
                    'StorageClass': 'STANDARD'
                })

                count += 1
                if count >= MaxKeys:
                    break

            if count >= MaxKeys:
                break

        return {
            'Contents': contents,
            'IsTruncated': False,
            'KeyCount': len(contents),
            'MaxKeys': MaxKeys,
            'Name': Bucket,
            'Prefix': Prefix or ''
        }

    def head_bucket(self, Bucket=None):
        """Mock implementation of head_bucket."""
        bucket_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", Bucket or self.bucket_name)
        if not os.path.exists(bucket_dir):
            raise Exception("Mock bucket does not exist")
        return {}

    def create_bucket(self, Bucket=None, CreateBucketConfiguration=None, **kwargs):
        """Mock implementation of create_bucket."""
        bucket_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", Bucket or self.bucket_name)
        os.makedirs(bucket_dir, exist_ok=True)
        return {'Location': f"/{Bucket or self.bucket_name}"}

    def download_file(self, Bucket=None, Key=None, Filename=None):
        """Mock implementation of download_file."""
        bucket_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", Bucket or self.bucket_name)
        source_path = os.path.join(bucket_dir, Key)

        if not os.path.exists(source_path):
            raise ClientError({
                'Error': {
                    'Code': 'NoSuchKey',
                    'Message': 'The specified key does not exist.'
                }
            }, 'GetObject')

        # Copy the file
        import shutil
        shutil.copy2(source_path, Filename)
        return True

    def upload_file(self, Filename=None, Bucket=None, Key=None, **kwargs):
        """Mock implementation of upload_file."""
        bucket_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", Bucket or self.bucket_name)
        target_path = os.path.join(bucket_dir, Key)

        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # Copy the file
        import shutil
        shutil.copy2(Filename, target_path)
        return True

class S3Storage:
    """
    Real implementation of S3 storage backend for IPFS content.

    This class provides methods to store and retrieve IPFS content using AWS S3,
    implementing a real (non-simulated) storage backend.
    """

    def __init__(
        self,
        bucket_name=None,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        region_name=None
    ):
        """
        Initialize the S3 storage backend.

        Args:
            bucket_name (str): S3 bucket name. If None, will try to get from environment.
            aws_access_key_id (str): AWS access key ID. If None, will try to get from environment.
            aws_secret_access_key (str): AWS secret access key. If None, will try to get from environment.
            region_name (str): AWS region name. If None, will try to get from environment.
        """
        # Try to get MCP_USE_MOCK_MODE from environment
        use_mock = os.environ.get("MCP_USE_MOCK_MODE", "").lower() in ["true", "1", "yes"]

        self.bucket_name = bucket_name or os.environ.get("AWS_S3_BUCKET_NAME") or os.environ.get("S3_BUCKET_NAME", "ipfs-storage-demo")
        self.aws_access_key_id = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.region_name = region_name or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        self.s3_client = None
        self.mock_mode = use_mock
        self.simulation_mode = not S3_AVAILABLE

        # If mock mode is forced, use it regardless of other conditions
        if self.mock_mode:
            logger.info("Using S3 mock mode (as specified by environment)")
            self.simulation_mode = False
            self.s3_client = MockS3Client(bucket_name=self.bucket_name, region_name=self.region_name)
            return

        # Initialize the S3 client if available
        if S3_AVAILABLE and self.aws_access_key_id and self.aws_secret_access_key and self.bucket_name:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.region_name
                )
                logger.info("Initialized S3 client")
                self.simulation_mode = False
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                self.simulation_mode = True

        # If credentials are missing but libraries are available, use mock mode
        if (self.simulation_mode or self.s3_client is None) and S3_AVAILABLE:
            logger.info("Using S3 mock mode (functional without real credentials)")
            self.simulation_mode = False
            self.mock_mode = True
            self.s3_client = MockS3Client(bucket_name=self.bucket_name, region_name=self.region_name)

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the S3 storage backend.

        Returns:
            Dict containing status information
        """
        status_info = {
            "success": True,
            "available": S3_AVAILABLE and self.s3_client is not None,
            "simulation": self.simulation_mode,
            "mock": self.mock_mode,
            "timestamp": time.time(),
            "region": self.region_name,
            "bucket": self.bucket_name
        }

        if self.simulation_mode:
            status_info["message"] = "Running in simulation mode"
            if not S3_AVAILABLE:
                status_info["error"] = "AWS S3 SDK (boto3) not installed"
            elif not self.aws_access_key_id or not self.aws_secret_access_key:
                status_info["error"] = "AWS credentials not provided"
            elif not self.bucket_name:
                status_info["error"] = "S3 bucket name not provided"
        elif self.mock_mode:
            status_info["message"] = "Running in mock mode"
            status_info["warning"] = "Using local mock implementation (functional but not connected to AWS S3)"

            # Create mock bucket directory if it doesn't exist
            mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", self.bucket_name)
            try:
                os.makedirs(mock_dir, exist_ok=True)
                status_info["mock_bucket_path"] = mock_dir
            except Exception as e:
                status_info["mock_setup_error"] = str(e)
        else:
            # Test S3 bucket access
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    MaxKeys=1
                )
                status_info["bucket_exists"] = True
                status_info["message"] = "Connected to S3 bucket"
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                if error_code == 'NoSuchBucket':
                    status_info["bucket_exists"] = False
                    status_info["error"] = f"Bucket {self.bucket_name} does not exist"
                    status_info["success"] = False
                else:
                    status_info["error"] = str(e)
                    status_info["success"] = False
            except Exception as e:
                status_info["error"] = str(e)
                status_info["success"] = False

        return status_info

    def _ensure_bucket_exists(self) -> bool:
        """
        Ensure the S3 bucket exists, creating it if necessary.

        Returns:
            bool: True if bucket exists or was created, False otherwise
        """
        if self.simulation_mode:
            return False

        try:
            # Check if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                logger.debug(f"Bucket {self.bucket_name} already exists")
                return True
            except Exception as e:
                # If we're in mock mode, just create the bucket
                if self.mock_mode:
                    self.s3_client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created mock bucket {self.bucket_name}")
                    return True

                # For real S3, check error code
                if hasattr(e, 'response') and isinstance(e.response, dict):
                    error_code = e.response.get('Error', {}).get('Code', '')
                    if error_code == '404' or error_code == 'NoSuchBucket':
                        # Bucket doesn't exist, create it
                        logger.info(f"Creating bucket {self.bucket_name}")
                        if self.region_name == 'us-east-1':
                            self.s3_client.create_bucket(Bucket=self.bucket_name)
                        else:
                            self.s3_client.create_bucket(
                                Bucket=self.bucket_name,
                                CreateBucketConfiguration={'LocationConstraint': self.region_name}
                            )
                        logger.info(f"Created bucket {self.bucket_name}")
                        return True

                # Other error
                logger.error(f"Error accessing bucket: {e}")
                return False
        except Exception as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            return False

    def to_ipfs(self, s3_key: str, cid: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload content from S3 to IPFS.

        Args:
            s3_key: Object key in S3
            cid: Optional CID to assign (for verification)

        Returns:
            Dict with upload status and CID
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "S3 backend is in simulation mode"
            }

        try:
            # Create a temporary file to download the S3 object
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            # Download from S3
            try:
                self.s3_client.download_file(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Filename=temp_path
                )
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to download from S3: {str(e)}",
                    "mock": self.mock_mode
                }

            # Upload to IPFS
            result = subprocess.run(
                ["ipfs", "add", "-q", temp_path],
                capture_output=True,
                text=True
            )

            # Clean up temporary file
            os.unlink(temp_path)

            if result.returncode == 0:
                new_cid = result.stdout.strip()

                # Verify CID if provided
                if cid and cid != new_cid:
                    return {
                        "success": False,
                        "error": f"CID mismatch: expected {cid}, got {new_cid}",
                        "mock": self.mock_mode
                    }

                return {
                    "success": True,
                    "cid": new_cid,
                    "source": f"s3://{self.bucket_name}/{s3_key}",
                    "mock": self.mock_mode
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to add to IPFS: {result.stderr}",
                    "mock": self.mock_mode
                }

        except Exception as e:
            logger.error(f"Error transferring from S3 to IPFS: {e}")
            return {
                "success": False,
                "error": str(e),
                "mock": self.mock_mode
            }

    def from_ipfs(self, cid: str, s3_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload content from IPFS to S3.

        Args:
            cid: Content ID to upload
            s3_key: Optional S3 object key

        Returns:
            Dict with upload status and URL
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "S3 backend is in simulation mode"
            }

        # Ensure bucket exists
        if not self._ensure_bucket_exists():
            return {
                "success": False,
                "error": "Failed to ensure bucket exists",
                "mock": self.mock_mode
            }

        try:
            # Create a temporary file to store the IPFS content
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            # Get content from IPFS
            result = subprocess.run(
                ["ipfs", "cat", cid],
                capture_output=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}",
                    "mock": self.mock_mode
                }

            # Write content to temporary file
            with open(temp_path, "wb") as f:
                f.write(result.stdout)

            # Determine S3 key
            s3_key = s3_key or f"ipfs/{cid}"

            # Upload to S3
            try:
                self.s3_client.upload_file(
                    Filename=temp_path,
                    Bucket=self.bucket_name,
                    Key=s3_key
                )
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to upload to S3: {str(e)}",
                    "mock": self.mock_mode
                }

            # Clean up temporary file
            os.unlink(temp_path)

            # Get public URL (if bucket is public)
            if self.mock_mode:
                mock_dir = os.path.join(os.path.expanduser("~"), ".ipfs_kit", "mock_s3", self.bucket_name)
                s3_url = f"file://{os.path.join(mock_dir, s3_key)}"
            else:
                s3_url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{s3_key}"

            return {
                "success": True,
                "url": s3_url,
                "cid": cid,
                "key": s3_key,
                "bucket": self.bucket_name,
                "mock": self.mock_mode
            }

        except Exception as e:
            logger.error(f"Error transferring from IPFS to S3: {e}")
            return {
                "success": False,
                "error": str(e),
                "mock": self.mock_mode
            }

    def list_objects(self, prefix: Optional[str] = None, max_keys: int = 1000) -> Dict[str, Any]:
        """
        List objects in the S3 bucket.

        Args:
            prefix: Optional prefix to filter objects
            max_keys: Maximum number of keys to return

        Returns:
            Dict with list of objects
        """
        if self.simulation_mode:
            return {
                "success": False,
                "simulation": True,
                "error": "S3 backend is in simulation mode"
            }

        try:
            # Ensure bucket exists
            if not self._ensure_bucket_exists():
                return {
                    "success": False,
                    "error": "Failed to ensure bucket exists",
                    "mock": self.mock_mode
                }

            # List objects in the bucket
            params = {
                "Bucket": self.bucket_name,
                "MaxKeys": max_keys
            }

            if prefix:
                params["Prefix"] = prefix

            response = self.s3_client.list_objects_v2(**params)

            # Extract object information
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    "key": obj.get('Key'),
                    "size": obj.get('Size'),
                    "last_modified": str(obj.get('LastModified')) if obj.get('LastModified') else None,
                    "etag": obj.get('ETag')
                })

            return {
                "success": True,
                "objects": objects,
                "count": len(objects),
                "is_truncated": response.get('IsTruncated', False),
                "bucket": self.bucket_name,
                "prefix": prefix,
                "mock": self.mock_mode
            }

        except Exception as e:
            logger.error(f"Error listing objects from S3: {e}")
            return {
                "success": False,
                "error": str(e),
                "mock": self.mock_mode
            }
