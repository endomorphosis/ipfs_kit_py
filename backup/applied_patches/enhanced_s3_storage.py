"""
Enhanced S3 storage backend with local persistence.

This module provides a robust S3 storage implementation that works as a real
backend by storing files locally when AWS credentials aren't available.
"""

import os
import json
import logging
import tempfile
import time
import subprocess
import hashlib
import shutil
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

class EnhancedS3Storage:
    """
    Enhanced S3 storage backend for IPFS content.

    This class provides a robust implementation that works with real S3 when credentials
    are available, but falls back to a local storage implementation when they aren't.
    """

    def __init__(
        self,
        bucket_name=None,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        region_name=None,
        local_storage_path=None
    ):
        """
        Initialize the S3 storage backend.

        Args:
            bucket_name: S3 bucket name. If None, will try to get from environment.
            aws_access_key_id: AWS access key ID. If None, will try to get from environment.
            aws_secret_access_key: AWS secret access key. If None, will try to get from environment.
            region_name: AWS region name. If None, will try to get from environment.
            local_storage_path: Path for local storage when AWS is unavailable.
        """
        self.bucket_name = bucket_name or os.environ.get("AWS_S3_BUCKET_NAME", "ipfs-storage-demo")
        self.aws_access_key_id = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self.region_name = region_name or os.environ.get("AWS_REGION", "us-east-1")
        self.local_storage_path = local_storage_path or os.path.join(
            os.path.expanduser("~"), ".ipfs_kit", "enhanced_s3", self.bucket_name
        )

        self.s3_client = None
        self.local_mode = False

        # Initialize the S3 client if boto3 is available and credentials are provided
        if S3_AVAILABLE and self.aws_access_key_id and self.aws_secret_access_key:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.region_name
                )
                # Test the connection
                self.s3_client.list_buckets()
                logger.info("Successfully connected to AWS S3")
            except Exception as e:
                logger.warning(f"Failed to initialize S3 client: {e}")
                self.s3_client = None

        # If S3 client initialization failed, use local storage
        if not self.s3_client:
            logger.info(f"Using enhanced local S3 implementation at: {self.local_storage_path}")
            self.local_mode = True
            # Ensure local storage directory exists
            os.makedirs(self.local_storage_path, exist_ok=True)

    def status(self) -> Dict[str, Any]:
        """
        Get the status of the S3 storage backend.

        Returns:
            Dict containing status information
        """
        status_info = {
            "success": True,
            "available": True,  # Always available because we have a local fallback
            "simulation": False,
            "timestamp": time.time(),
            "region": self.region_name,
            "bucket": self.bucket_name
        }

        if self.local_mode:
            status_info["local_mode"] = True
            status_info["message"] = "Using enhanced local S3 storage"
            status_info["storage_path"] = self.local_storage_path

            # Count objects in local storage
            object_count = 0
            for root, dirs, files in os.walk(self.local_storage_path):
                object_count += len(files)
            status_info["object_count"] = object_count
        else:
            # Test S3 bucket access
            try:
                response = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name,
                    MaxKeys=1
                )
                status_info["message"] = "Connected to AWS S3"
                status_info["bucket_exists"] = True
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                status_info["error"] = str(e)

                if error_code == 'NoSuchBucket':
                    status_info["bucket_exists"] = False
                    # Try to create the bucket
                    try:
                        if self.region_name == 'us-east-1':
                            self.s3_client.create_bucket(Bucket=self.bucket_name)
                        else:
                            self.s3_client.create_bucket(
                                Bucket=self.bucket_name,
                                CreateBucketConfiguration={'LocationConstraint': self.region_name}
                            )
                        status_info["message"] = f"Created bucket {self.bucket_name}"
                        status_info["bucket_exists"] = True
                        del status_info["error"]
                    except Exception as create_err:
                        status_info["creation_error"] = str(create_err)
            except Exception as e:
                status_info["error"] = str(e)

        return status_info

    def to_ipfs(self, s3_key: str, cid: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload content from S3 to IPFS.

        Args:
            s3_key: Object key in S3
            cid: Optional CID to assign (for verification)

        Returns:
            Dict with upload status and CID
        """
        if self.local_mode:
            # Enhanced local implementation
            try:
                # Check if the file exists in local storage
                local_file_path = os.path.join(self.local_storage_path, s3_key)
                if not os.path.exists(local_file_path):
                    return {
                        "success": False,
                        "local_mode": True,
                        "error": f"File not found in local S3 storage: {s3_key}"
                    }

                # Add the file to IPFS
                result = subprocess.run(
                    ["ipfs", "add", "-q", local_file_path],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    return {
                        "success": False,
                        "local_mode": True,
                        "error": f"Failed to add to IPFS: {result.stderr}"
                    }

                new_cid = result.stdout.strip()

                # Verify CID if provided
                if cid and cid != new_cid:
                    return {
                        "success": False,
                        "local_mode": True,
                        "error": f"CID mismatch: expected {cid}, got {new_cid}"
                    }

                # Get file stats
                file_stats = os.stat(local_file_path)

                return {
                    "success": True,
                    "local_mode": True,
                    "message": "Added content from local S3 storage to IPFS",
                    "cid": new_cid,
                    "source": f"local_s3:{self.bucket_name}/{s3_key}",
                    "size": file_stats.st_size,
                    "last_modified": time.ctime(file_stats.st_mtime)
                }

            except Exception as e:
                logger.error(f"Error in local to_ipfs: {e}")
                return {
                    "success": False,
                    "local_mode": True,
                    "error": str(e)
                }
        else:
            # Real AWS S3 implementation
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
                except ClientError as e:
                    return {
                        "success": False,
                        "error": f"Failed to download from S3: {str(e)}"
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
                            "error": f"CID mismatch: expected {cid}, got {new_cid}"
                        }

                    return {
                        "success": True,
                        "cid": new_cid,
                        "source": f"s3://{self.bucket_name}/{s3_key}"
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to add to IPFS: {result.stderr}"
                    }

            except Exception as e:
                logger.error(f"Error transferring from S3 to IPFS: {e}")
                return {
                    "success": False,
                    "error": str(e)
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
        # Determine S3 key if not provided
        s3_key = s3_key or f"ipfs/{cid}"

        if self.local_mode:
            # Enhanced local implementation
            try:
                # Get content from IPFS
                result = subprocess.run(
                    ["ipfs", "cat", cid],
                    capture_output=True
                )

                if result.returncode != 0:
                    return {
                        "success": False,
                        "local_mode": True,
                        "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                    }

                # Ensure directory exists for the key
                full_path = os.path.join(self.local_storage_path, s3_key)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)

                # Write content to file
                with open(full_path, "wb") as f:
                    f.write(result.stdout)

                # Calculate file hash for ETag simulation
                sha1 = hashlib.sha1()
                sha1.update(result.stdout)
                etag = sha1.hexdigest()

                # Generate metadata
                file_stats = os.stat(full_path)

                return {
                    "success": True,
                    "local_mode": True,
                    "message": "Content stored in local S3 storage",
                    "url": f"file://{full_path}",
                    "cid": cid,
                    "key": s3_key,
                    "bucket": self.bucket_name,
                    "etag": etag,
                    "size": file_stats.st_size,
                    "last_modified": time.ctime(file_stats.st_mtime)
                }

            except Exception as e:
                logger.error(f"Error in local from_ipfs: {e}")
                return {
                    "success": False,
                    "local_mode": True,
                    "error": str(e)
                }
        else:
            # Real AWS S3 implementation
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
                        "error": f"Failed to get content from IPFS: {result.stderr.decode('utf-8')}"
                    }

                # Write content to temporary file
                with open(temp_path, "wb") as f:
                    f.write(result.stdout)

                # Upload to S3
                try:
                    self.s3_client.upload_file(
                        Filename=temp_path,
                        Bucket=self.bucket_name,
                        Key=s3_key,
                        ExtraArgs={'Metadata': {'source': 'ipfs', 'cid': cid}}
                    )
                except ClientError as e:
                    return {
                        "success": False,
                        "error": f"Failed to upload to S3: {str(e)}"
                    }

                # Clean up temporary file
                os.unlink(temp_path)

                # Get S3 URL and object info
                s3_url = f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{s3_key}"

                # Get object info
                try:
                    obj_info = self.s3_client.get_object(
                        Bucket=self.bucket_name,
                        Key=s3_key
                    )

                    return {
                        "success": True,
                        "url": s3_url,
                        "cid": cid,
                        "key": s3_key,
                        "bucket": self.bucket_name,
                        "etag": obj_info.get('ETag', '').strip('"'),
                        "last_modified": obj_info.get('LastModified', '').isoformat() if obj_info.get('LastModified') else None,
                        "size": obj_info.get('ContentLength', 0)
                    }
                except Exception as info_err:
                    # Return basic info if we can't get detailed object info
                    return {
                        "success": True,
                        "url": s3_url,
                        "cid": cid,
                        "key": s3_key,
                        "bucket": self.bucket_name,
                        "info_error": str(info_err)
                    }

            except Exception as e:
                logger.error(f"Error transferring from IPFS to S3: {e}")
                return {
                    "success": False,
                    "error": str(e)
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
        if self.local_mode:
            # Enhanced local implementation
            try:
                objects = []
                start_path = self.local_storage_path

                # If prefix is specified, adjust the start path
                if prefix:
                    start_path = os.path.join(self.local_storage_path, prefix)
                    if not os.path.exists(start_path):
                        return {
                            "success": True,
                            "local_mode": True,
                            "message": "No objects found with prefix",
                            "objects": [],
                            "count": 0,
                            "bucket": self.bucket_name,
                            "prefix": prefix
                        }

                # Walk the directory structure
                for root, dirs, files in os.walk(start_path):
                    for file in files:
                        # Calculate the relative path from the storage root
                        full_path = os.path.join(root, file)
                        if os.path.isdir(full_path):
                            continue

                        rel_path = os.path.relpath(full_path, self.local_storage_path)

                        # Apply prefix filter if specified
                        if prefix and not rel_path.startswith(prefix):
                            continue

                        # Get file stats
                        file_stats = os.stat(full_path)

                        # Calculate ETag-like hash
                        with open(full_path, 'rb') as f:
                            sha1 = hashlib.sha1()
                            # Read in chunks to handle large files
                            for chunk in iter(lambda: f.read(4096), b''):
                                sha1.update(chunk)
                            etag = sha1.hexdigest()

                        objects.append({
                            "key": rel_path,
                            "size": file_stats.st_size,
                            "last_modified": time.ctime(file_stats.st_mtime),
                            "etag": etag
                        })

                        # Limit to max_keys
                        if len(objects) >= max_keys:
                            break

                    # Check if we've reached the limit
                    if len(objects) >= max_keys:
                        break

                return {
                    "success": True,
                    "local_mode": True,
                    "message": "Listed objects from local S3 storage",
                    "objects": objects,
                    "count": len(objects),
                    "is_truncated": False,  # Local implementation doesn't truncate
                    "bucket": self.bucket_name,
                    "prefix": prefix
                }

            except Exception as e:
                logger.error(f"Error in local list_objects: {e}")
                return {
                    "success": False,
                    "local_mode": True,
                    "error": str(e)
                }
        else:
            # Real AWS S3 implementation
            try:
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
                        "last_modified": obj.get('LastModified').isoformat() if obj.get('LastModified') else None,
                        "etag": obj.get('ETag', '').strip('"')
                    })

                return {
                    "success": True,
                    "objects": objects,
                    "count": len(objects),
                    "is_truncated": response.get('IsTruncated', False),
                    "bucket": self.bucket_name,
                    "prefix": prefix
                }

            except Exception as e:
                logger.error(f"Error listing objects from S3: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

    def delete_object(self, s3_key: str) -> Dict[str, Any]:
        """
        Delete an object from S3.

        Args:
            s3_key: Object key in S3

        Returns:
            Dict with deletion status
        """
        if self.local_mode:
            # Enhanced local implementation
            try:
                local_file_path = os.path.join(self.local_storage_path, s3_key)
                if not os.path.exists(local_file_path):
                    return {
                        "success": False,
                        "local_mode": True,
                        "error": f"File not found in local S3 storage: {s3_key}"
                    }

                # Delete the file
                os.remove(local_file_path)

                # Clean up empty directories
                dir_path = os.path.dirname(local_file_path)
                try:
                    # Try to remove parent directories if they're empty
                    os.removedirs(dir_path)
                except OSError:
                    # This is expected if directories aren't empty
                    pass

                return {
                    "success": True,
                    "local_mode": True,
                    "message": f"Deleted object from local S3 storage: {s3_key}",
                    "key": s3_key,
                    "bucket": self.bucket_name
                }

            except Exception as e:
                logger.error(f"Error in local delete_object: {e}")
                return {
                    "success": False,
                    "local_mode": True,
                    "error": str(e)
                }
        else:
            # Real AWS S3 implementation
            try:
                # Delete the object from S3
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=s3_key
                )

                return {
                    "success": True,
                    "message": f"Deleted object from S3: {s3_key}",
                    "key": s3_key,
                    "bucket": self.bucket_name
                }

            except Exception as e:
                logger.error(f"Error deleting object from S3: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
