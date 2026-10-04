"""
S3 backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Amazon S3 and S3-compatible
storage services with enhanced performance, caching, and migration capabilities.
"""

import logging
import time
import os
import threading
import json
import hashlib
import tempfile
import shutil
import uuid
from typing import Dict, Any, Optional, Union, BinaryIO, Tuple

from concurrent.futures import ThreadPoolExecutor

# Import from backend_base
from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)

# Define constants
DEFAULT_MAX_THREADS = 10
DEFAULT_CACHE_SIZE = 100
DEFAULT_CONNECTION_TIMEOUT = 5  # seconds
DEFAULT_READ_TIMEOUT = 60  # seconds
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024  # 8MB


class S3ConnectionPool:
    """Manages a pool of S3 clients for improved performance."""
    def __init__(self, config: Dict[str, Any], max_clients: int = 5):
        """
        Initialize the connection pool.

        Args:
            config: S3 client configuration
            max_clients: Maximum number of clients in the pool
        """
        self.config = config
        self.max_clients = max_clients
        self.clients = []
        self.lock = threading.RLock()
        self.in_use = set()

        # Import boto3 here to keep dependency optional
        import boto3

        self.boto3 = boto3

    def get_client(self):
        """Get an S3 client from the pool or create a new one."""
        with self.lock:
            # Check if there's an available client
            available = [c for c in self.clients if c not in self.in_use]
            if available:
                client = available[0]
                self.in_use.add(client)
                return client

            # Create a new client if under max limit
            if len(self.clients) < self.max_clients:
                client = self.boto3.client("s3", **self.config)
                self.clients.append(client)
                self.in_use.add(client)
                return client

            # Wait for a client to become available
            while not available:
                self.lock.release()
                time.sleep(0.1)
                self.lock.acquire()
                available = [c for c in self.clients if c not in self.in_use]

            client = available[0]
            self.in_use.add(client)
            return client

    def release_client(self, client):
        """Release a client back to the pool."""
        with self.lock:
            if client in self.in_use:
                self.in_use.remove(client)

    def __enter__(self):
        self.client = self.get_client()
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release_client(self.client)


class S3Backend(BackendStorage):
    """S3 backend implementation for Amazon S3 and compatible services with enhanced features."""
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize S3 backend with advanced features."""
        super().__init__(StorageBackendType.S3, resources, metadata)

        try:
            import boto3
            from botocore.exceptions import ClientError
            from botocore.config import Config
        except ImportError:
            logger.error("boto3 is required for S3 backend. Install with 'pip install boto3'")
            raise ImportError("boto3 is required for S3 backend")

        self.boto3 = boto3
        self.ClientError = ClientError
        self.boto_config = Config

        # Extract configuration from resources/metadata
        self.aws_access_key = resources.get("aws_access_key") or os.environ.get("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = resources.get("aws_secret_key") or os.environ.get(
            "AWS_SECRET_ACCESS_KEY")
        self.region = resources.get("region") or os.environ.get("AWS_REGION", "us-east-1")
        self.endpoint_url = resources.get("endpoint_url") or os.environ.get("S3_ENDPOINT_URL")
        self.default_bucket = resources.get("bucket") or os.environ.get("S3_DEFAULT_BUCKET")

        # Performance and reliability configuration
        self.max_threads = int(resources.get("max_threads", DEFAULT_MAX_THREADS))
        self.connection_timeout = int(
            resources.get("connection_timeout", DEFAULT_CONNECTION_TIMEOUT))
        self.read_timeout = int(resources.get("read_timeout", DEFAULT_READ_TIMEOUT))
        self.max_retries = int(resources.get("max_retries", 3))
        self.chunk_size = int(resources.get("chunk_size", DEFAULT_CHUNK_SIZE))

        # Initialize metadata dictionary for storing object metadata
        self._metadata_cache = {}

        # Create thread pool for parallel operations
        self.executor = ThreadPoolExecutor(max_workers=self.max_threads)

        # Set up S3 client and connection pool
        self._setup_client()

        # Initialize local cache for frequently accessed data
        self._init_local_cache()

    def _init_local_cache(self):
        """Initialize the local cache for frequently accessed data."""
        cache_dir = os.environ.get("MCP_S3_CACHE_DIR")
        if not cache_dir:
            temp_dir = tempfile.gettempdir()
            cache_dir = os.path.join(temp_dir, f"mcp_s3_cache_{uuid.uuid4().hex[:8]}")

        os.makedirs(cache_dir, exist_ok=True)
        self.cache_dir = cache_dir
        logger.info(f"S3 backend using local cache directory: {cache_dir}")

        # Cache expiration time in seconds
        self.cache_ttl = int(self.resources.get("cache_ttl", 3600))  # Default: 1 hour

        # Cache size limit in bytes
        self.cache_size_limit = int(
            self.resources.get("cache_size_limit", 1024 * 1024 * 100))  # Default: 100MB

        # Track cache usage
        self.cache_usage = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def _cache_path(self, bucket: str, key: str) -> str:
        """Get the cache path for an S3 object."""
        # Create a unique but reproducible path from bucket and key
        hash_val = hashlib.md5(f"{bucket}:{key}".encode("utf-8")).hexdigest()
        return os.path.join(self.cache_dir, hash_val)

    def _is_in_cache(self, bucket: str, key: str) -> Tuple[bool, Optional[str]]:
        """Check if an object is in the cache and not expired."""
        cache_path = self._cache_path(bucket, key)
        meta_path = f"{cache_path}.meta"

        if not os.path.exists(cache_path) or not os.path.exists(meta_path):
            return False, None

        try:
            with open(meta_path, "r") as f:
                metadata = json.load(f)

            # Check if cache has expired
            if time.time() - metadata.get("cached_at", 0) > self.cache_ttl:
                # Cache expired
                return False, None

            return True, cache_path
        except Exception as e:
            logger.warning(f"Error checking cache: {str(e)}")
            return False, None

    def _add_to_cache(self, bucket: str, key: str, data: bytes, metadata: Dict[str, Any]) -> str:
        """Add object to cache."""
        cache_path = self._cache_path(bucket, key)
        meta_path = f"{cache_path}.meta"

        # Check if we need to enforce cache size limits
        if self.cache_usage + len(data) > self.cache_size_limit:
            self._clean_cache()

        # Check if we still have space
        if self.cache_usage + len(data) > self.cache_size_limit:
            return None # Cannot cache if still over limit

        try:
            with open(cache_path, "wb") as f:
                f.write(data)

            cache_metadata = {
                "cached_at": time.time(),
                "size": len(data),
                "bucket": bucket,
                "key": key,
                "object_metadata": metadata,
            }

            with open(meta_path, "w") as f:
                json.dump(cache_metadata, f)

            # Update cache usage
            self.cache_usage += len(data)

            return cache_path
        except Exception as e:
            logger.warning(f"Error caching object: {str(e)}")
            return None

    def _clean_cache(self):
        """Clean up old cache entries to free up space."""
        try:
            # Get all cache files and their metadata
            cache_files = []
            for filename in os.listdir(self.cache_dir):
                if filename.endswith(".meta"):
                    continue

                meta_path = os.path.join(self.cache_dir, f"{filename}.meta")
                file_path = os.path.join(self.cache_dir, filename)

                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r") as f:
                            metadata = json.load(f)
                            cached_at = metadata.get("cached_at", 0)
                            size = metadata.get("size", 0)

                        cache_files.append((file_path, meta_path, cached_at, size))
                    except Exception:
                        # If we can't read metadata, just use file stats
                        size = os.path.getsize(file_path)
                        cached_at = os.path.getmtime(file_path)
                        cache_files.append((file_path, meta_path, cached_at, size))

            # Sort by access time (oldest first)
            cache_files.sort(key=lambda x: x[2])

            # Remove oldest files until we're under the limit
            freed_space = 0
            target_free = max(self.cache_size_limit // 2, self.chunk_size * 2) # Target freeing up 50% or at least 2 chunks

            for file_path, meta_path, _, size in cache_files:
                # Stop if we've freed enough space
                if self.cache_usage - freed_space <= self.cache_size_limit - target_free:
                    break

                # Delete the file and its metadata
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if os.path.exists(meta_path):
                        os.remove(meta_path)

                    freed_space += size
                    self.cache_usage -= size

                except Exception as e:
                    logger.warning(f"Error cleaning cache file {file_path}: {str(e)}")

            logger.info(f"Cleaned S3 cache, freed {freed_space} bytes")
        except Exception as e:
            logger.error(f"Cache cleaning failed: {str(e)}")

    def _setup_client(self):
        """Set up S3 client with appropriate configuration."""
        # Configure boto3 for better performance
        boto_config = self.boto_config(
            connect_timeout=self.connection_timeout,
            read_timeout=self.read_timeout,
            retries={"max_attempts": self.max_retries},
            max_pool_connections=self.max_threads,)

        # Configure client parameters
        client_kwargs = {"region_name": self.region, "config": boto_config}

        # Add credentials if provided
        if self.aws_access_key and self.aws_secret_key:
            client_kwargs["aws_access_key_id"] = self.aws_access_key
            client_kwargs["aws_secret_access_key"] = self.aws_secret_key

        # Add custom endpoint if provided (for S3-compatible services)
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        # Create S3 client
        try:
            self.s3_client = self.boto3.client("s3", **client_kwargs)
            self.s3_resource = self.boto3.resource("s3", **client_kwargs)
            logger.info(f"S3 backend initialized successfully with region {self.region}")

            # Initialize connection pool
            self.connection_pool = S3ConnectionPool(client_kwargs, max_clients=self.max_threads)

        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}")
            raise

    def _resolve_bucket(self, container: Optional[str] = None) -> str:
        """Resolve bucket name, using default if none provided."""
        bucket = container or self.default_bucket
        if not bucket:
            raise ValueError("No bucket specified and no default bucket configured")
        return bucket

    def _generate_object_id(self, path: Optional[str] = None) -> str:
        """Generate a unique object ID if path not provided."""
        if path:
            return path
        return f"mcp-s3-{uuid.uuid4()}"

    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
        """Store data in S3 with enhanced performance."""
        options = options or {}
        bucket = self._resolve_bucket(container)
        object_key = path or self._generate_object_id()

        # Set up metadata
        metadata = {"mcp_added": str(int(time.time())), "mcp_backend": self.get_name()}

        # Add custom metadata from options
        if "metadata" in options:
            for k, v in options["metadata"].items():
                if isinstance(v, (str, int, float, bool)):
                    metadata[f"mcp_{k}"] = str(v)

        try:
            # Handle different data types
            if isinstance(data, str):
                data = data.encode("utf-8")

            # Handle large uploads with multipart if needed
            if isinstance(data, bytes):
                data_size = len(data)

                # If data is large, use multipart upload for better performance and reliability
                if data_size > self.chunk_size and options.get("use_multipart", True):
                    return self._multipart_upload(data, bucket, object_key, metadata, options)

                # For smaller data, upload directly
                with self.connection_pool as client:
                    client.put_object(Bucket=bucket, Key=object_key, Body=data, Metadata=metadata)

                # If caching is enabled and size is reasonable, cache the data
                if options.get("cache", True) and data_size < self.chunk_size:
                    self._add_to_cache(bucket, object_key, data, metadata)
            else:
                # Upload file-like object
                with self.connection_pool as client:
                    client.upload_fileobj(
                        data, bucket, object_key, ExtraArgs={"Metadata": metadata})

            # Store object details in cache
            self._metadata_cache[f"{bucket}:{object_key}"] = {
                "metadata": metadata,
                "size": len(data) if isinstance(data, bytes) else None,
            }

            return {
                "success": True,
                "identifier": object_key,
                "backend": self.get_name(),
                "container": bucket,
                "details": {"bucket": bucket, "key": object_key, "metadata": metadata},
            }

        except self.ClientError as e:
            logger.error(f"S3 store error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "details": {
                    "code": getattr(e, "response", {}).get("Error", {}).get("Code", "Unknown"),
                    "message": getattr(e, "response", {}).get("Error", {}).get("Message", str(e)),
                },
            }
        except Exception as e:
            logger.error(f"Unexpected error in S3 store: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def _multipart_upload(
        self,
        data: bytes,
        bucket: str,
        key: str,
        metadata: Dict[str, Any],
        options: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a multipart upload for large data."""
        try:
            # Start multipart upload
            with self.connection_pool as client:
                mpu = client.create_multipart_upload(Bucket=bucket, Key=key, Metadata=metadata)

            upload_id = mpu["UploadId"]

            # Split data into chunks
            parts = []
            part_number = 1
            chunks = [data[i : i + self.chunk_size] for i in range(0, len(data), self.chunk_size)]

            # Upload each part
            for chunk in chunks:
                with self.connection_pool as client:
                    response = client.upload_part(
                        Bucket=bucket,
                        Key=key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=chunk,)

                # Add part information
                parts.append({"PartNumber": part_number, "ETag": response["ETag"]})

                part_number += 1

            # Complete multipart upload
            with self.connection_pool as client:
                client.complete_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},)

            return {
                "success": True,
                "identifier": key,
                "backend": self.get_name(),
                "container": bucket,
                "details": {
                    "bucket": bucket,
                    "key": key,
                    "metadata": metadata,
                    "multipart": True,
                    "parts": len(parts),
                },
            }
        except Exception as e:
            # Attempt to abort the multipart upload on failure
            try:
                if "upload_id" in locals():
                    with self.connection_pool as client:
                        client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
            except Exception as abort_error:
                logger.error(f"Failed to abort multipart upload: {str(abort_error)}")

            logger.error(f"Multipart upload failed: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
        """Retrieve data from S3 with caching capabilities."""
        options = options or {}
        bucket = self._resolve_bucket(container)

        # Check if the object is in cache
        use_cache = options.get("use_cache", True)
        if use_cache:
            in_cache, cache_path = self._is_in_cache(bucket, identifier)
            if in_cache:
                try:
                    with open(cache_path, "rb") as f:
                        data = f.read()

                    # Read metadata
                    with open(f"{cache_path}.meta", "r") as f:
                        metadata = json.load(f)

                    self.cache_hits += 1

                    return {
                        "success": True,
                        "data": data,
                        "backend": self.get_name(),
                        "identifier": identifier,
                        "container": bucket,
                        "cached": True,
                        "details": {
                            "bucket": bucket,
                            "key": identifier,
                            "metadata": metadata.get("object_metadata", {}),
                            "cache_info": {
                                "cached_at": metadata.get("cached_at"),
                                "size": metadata.get("size"),
                            },
                        },
                    }
                except Exception as cache_error:
                    logger.warning(f"Error reading from cache: {str(cache_error)}")

        self.cache_misses += 1

        try:
            # Get S3 object
            with self.connection_pool as client:
                response = client.get_object(Bucket=bucket, Key=identifier)

                # Read data
                data = response["Body"].read()

                # Extract metadata
                metadata = response.get("Metadata", {})
                content_type = response.get("ContentType")
                content_length = response.get("ContentLength")

                # Add to cache if enabled
                if use_cache and len(data) < self.chunk_size:
                    self._add_to_cache(bucket, identifier, data, metadata)

                return {
                    "success": True,
                    "data": data,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "container": bucket,
                    "details": {
                        "bucket": bucket,
                        "key": identifier,
                        "metadata": metadata,
                        "content_type": content_type,
                        "content_length": content_length,
                    },
                }

        except self.ClientError as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                logger.warning(f"Object {identifier} not found in bucket {bucket}")
                return {
                    "success": False,
                    "error": f"Object {identifier} not found",
                    "backend": self.get_name(),
                    "details": {"code": "NoSuchKey"},
                }

            logger.error(f"S3 retrieve error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "details": {
                    "code": error_code,
                    "message": getattr(e, "response", {}).get("Error", {}).get("Message", str(e)),
                },
            }
        except Exception as e:
            logger.error(f"Unexpected error in S3 retrieve: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
        """Delete object from S3."""
        options = options or {}
        bucket = self._resolve_bucket(container)

        try:
            # Delete object
            with self.connection_pool as client:
                client.delete_object(Bucket=bucket, Key=identifier)

            # Remove from cache if present
            cache_key = f"{bucket}:{identifier}"
            if cache_key in self._metadata_cache:
                del self._metadata_cache[cache_key]

            # Remove from local cache if present
            cache_path = self._cache_path(bucket, identifier)
            meta_path = f"{cache_path}.meta"

            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                except Exception as cache_error:
                    logger.warning(f"Error removing cached file: {str(cache_error)}")

            if os.path.exists(meta_path):
                try:
                    os.remove(meta_path)
                except Exception as cache_error:
                    logger.warning(f"Error removing cache metadata: {str(cache_error)}")

            return {
                "success": True,
                "backend": self.get_name(),
                "identifier": identifier,
                "container": bucket,
                "details": {"bucket": bucket, "key": identifier},
            }

        except self.ClientError as e:
            logger.error(f"S3 delete error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "details": {
                    "code": getattr(e, "response", {}).get("Error", {}).get("Code", "Unknown"),
                    "message": getattr(e, "response", {}).get("Error", {}).get("Message", str(e)),
                },
            }
        except Exception as e:
            logger.error(f"Unexpected error in S3 delete: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def list(
        self,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
        """List objects in S3 bucket with enhanced performance."""
        options = options or {}
        bucket = self._resolve_bucket(container)

        try:
            # Set up list parameters
            list_params = {"Bucket": bucket}

            if prefix:
                list_params["Prefix"] = prefix

            if "max_keys" in options:
                list_params["MaxKeys"] = options["max_keys"]

            if "delimiter" in options:
                list_params["Delimiter"] = options["delimiter"]

            if "continuation_token" in options:
                list_params["ContinuationToken"] = options["continuation_token"]

            # Get objects
            with self.connection_pool as client:
                response = client.list_objects_v2(**list_params)

            # Process results
            items = []
            for obj in response.get("Contents", []):
                items.append(
                    {
                        "identifier": obj.get("Key"),
                        "size": obj.get("Size"),
                        "last_modified": 
                            obj.get("LastModified").isoformat() if obj.get("LastModified") else None,
                        "etag": obj.get("ETag"),
                        "backend": self.get_name(),
                        "container": bucket,
                    })

            result = {
                "success": True,
                "items": items,
                "backend": self.get_name(),
                "container": bucket,
                "details": {
                    "key_count": response.get("KeyCount", 0),
                    "is_truncated": response.get("IsTruncated", False),
                },
            }

            # Add continuation token if response was truncated
            if response.get("IsTruncated", False) and "NextContinuationToken" in response:
                result["details"]["continuation_token"] = response["NextContinuationToken"]

            # Add common prefixes if delimiter was used
            if "CommonPrefixes" in response:
                result["details"]["common_prefixes"] = [
                    p.get("Prefix") for p in response["CommonPrefixes"]
                ]

            return result

        except self.ClientError as e:
            logger.error(f"S3 list error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "details": {
                    "code": getattr(e, "response", {}).get("Error", {}).get("Code", "Unknown"),
                    "message": getattr(e, "response", {}).get("Error", {}).get("Message", str(e)),
                },
            }
        except Exception as e:
            logger.error(f"Unexpected error in S3 list: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def exists(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> bool:
        """Check if object exists in S3 with cache support."""
        options = options or {}
        bucket = self._resolve_bucket(container)

        # Check local cache first
        use_cache = options.get("use_cache", True)
        if use_cache:
            in_cache, _ = self._is_in_cache(bucket, identifier)
            if in_cache:
                return True

        try:
            # Use head_object to check existence without fetching data
            with self.connection_pool as client:
                client.head_object(Bucket=bucket, Key=identifier)
            return True
        except self.ClientError as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code == "404" or error_code == "NoSuchKey" or error_code == "NotFound":
                return False
            # Log other errors but return False
            logger.error(f"S3 exists check error: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in S3 exists check: {str(e)}")
            return False

    def get_metadata(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
        """Get metadata for S3 object with cache support."""
        options = options or {}
        bucket = self._resolve_bucket(container)

        # Check if metadata is in cache
        use_cache = options.get("use_cache", True)
        if use_cache:
            in_cache, cache_path = self._is_in_cache(bucket, identifier)
            if in_cache:
                try:
                    with open(f"{cache_path}.meta", "r") as f:
                        cached_metadata = json.load(f)

                    if "object_metadata" in cached_metadata:
                        return {
                            "success": True,
                            "metadata": {
                                "size": cached_metadata.get("size", 0),
                                "last_modified": time.ctime(cached_metadata.get("cached_at", 0)),
                                "backend": self.get_name(),
                                "user_metadata": cached_metadata.get("object_metadata", {}),
                            },
                            "backend": self.get_name(),
                            "identifier": identifier,
                            "container": bucket,
                            "cached": True,
                            "details": {"bucket": bucket, "key": identifier},
                        }
                except Exception:
                    # If anything goes wrong with cache, fall back to S3
                    pass

        try:
            # Use head_object to get metadata
            with self.connection_pool as client:
                response = client.head_object(Bucket=bucket, Key=identifier)

            metadata = response.get("Metadata", {})

            return {
                "success": True,
                "metadata": {
                    "size": response.get("ContentLength", 0),
                    "content_type": response.get("ContentType"),
                    "last_modified": 
                        response.get("LastModified").isoformat()
                        if response.get("LastModified")
                        else None,
                    "etag": response.get("ETag"),
                    "storage_class": response.get("StorageClass"),
                    "backend": self.get_name(),
                    "user_metadata": metadata,
                },
                "backend": self.get_name(),
                "identifier": identifier,
                "container": bucket,
                "details": {
                    "bucket": bucket,
                    "key": identifier,
                    "full_response": {
                        k: str(v) for k, v in response.items() if k != "ResponseMetadata"
                    },
                },
            }

        except self.ClientError as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code == "404" or error_code == "NoSuchKey" or error_code == "NotFound":
                return {
                    "success": False,
                    "error": f"Object {identifier} not found",
                    "backend": self.get_name(),
                    "details": {"code": error_code},
                }

            logger.error(f"S3 get_metadata error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "details": {
                    "code": error_code,
                    "message": getattr(e, "response", {}).get("Error", {}).get("Message", str(e)),
                },
            }
        except Exception as e:
            logger.error(f"Unexpected error in S3 get_metadata: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def update_metadata(
        self,
        identifier: str,
        metadata: Dict[str, Any],
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
        """
        Update metadata for S3 object.

        Note: S3 does not allow direct metadata updates.
        This method copies the object to itself with new metadata.
        """
        options = options or {}
        bucket = self._resolve_bucket(container)

        try:
            # S3 doesn't allow updating metadata directly
            # We need to copy the object to itself with new metadata

            # First, get the current object to preserve its content
            current_metadata = {}
            try:
                with self.connection_pool as client:
                    head_response = client.head_object(Bucket=bucket, Key=identifier)
                current_metadata = head_response.get("Metadata", {})
            except Exception as e:
                logger.warning(f"Could not retrieve current metadata for {identifier}: {str(e)}")

            # Merge current metadata with new metadata
            new_metadata = {**current_metadata}
            for k, v in metadata.items():
                if v is None:
                    # Remove metadata if value is None
                    if k in new_metadata:
                        del new_metadata[k]
                else:
                    # Add or update metadata
                    new_metadata[k] = str(v)

            # Copy object to itself with new metadata
            copy_source = {"Bucket": bucket, "Key": identifier}
            with self.connection_pool as client:
                copy_response = client.copy_object(
                    CopySource=copy_source,
                    Bucket=bucket,
                    Key=identifier,
                    Metadata=new_metadata,
                    MetadataDirective="REPLACE",)

            # Update cache
            cache_key = f"{bucket}:{identifier}"
            if cache_key in self._metadata_cache:
                self._metadata_cache[cache_key]["metadata"] = new_metadata

            # Update local cache metadata if present
            cache_path = self._cache_path(bucket, identifier)
            meta_path = f"{cache_path}.meta"

            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        cached_metadata = json.load(f)

                    cached_metadata["object_metadata"] = new_metadata

                    with open(meta_path, "w") as f:
                        json.dump(cached_metadata, f)
                except Exception as cache_error:
                    logger.warning(f"Error updating cache metadata: {str(cache_error)}")

            return {
                "success": True,
                "backend": self.get_name(),
                "identifier": identifier,
                "container": bucket,
                "details": {
                    "bucket": bucket,
                    "key": identifier,
                    "metadata": new_metadata,
                    "copy_result": copy_response.get("CopyObjectResult", {}),
                },
            }

        except self.ClientError as e:
            logger.error(f"S3 update_metadata error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "backend": self.get_name(),
                "details": {
                    "code": getattr(e, "response", {}).get("Error", {}).get("Code", "Unknown"),
                    "message": getattr(e, "response", {}).get("Error", {}).get("Message", str(e)),
                },
            }
        except Exception as e:
            logger.error(f"Unexpected error in S3 update_metadata: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def migrate_to(
        self,
        source_identifier: str,
        target_backend: BackendStorage,
        target_container: Optional[str] = None,
        target_path: Optional[str] = None,
        source_container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,) -> Dict[str, Any]:
        """
        Migrate content from S3 to another storage backend.

        Args:
            source_identifier: Identifier of content in S3
            target_backend: Target backend to migrate to
            target_container: Optional container in target backend
            target_path: Optional path in target backend
            source_container: Optional S3 bucket (uses default if not provided)
            options: Additional options for migration process

        Returns:
            Dict with migration status and details
        """
        options = options or {}
        source_bucket = self._resolve_bucket(source_container)

        start_time = time.time()

        # Retrieve the content from S3
        retrieve_result = self.retrieve(source_identifier, source_bucket, options)

        if not retrieve_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to retrieve source content: {retrieve_result.get('error', 'Unknown error')}",
                "source_backend": self.get_name(),
                "target_backend": target_backend.get_name(),
                "source_identifier": source_identifier,
                "source_container": source_bucket,
            }

        # Get data and metadata
        data = retrieve_result.get("data")
        metadata = retrieve_result.get("details", {}).get("metadata", {})

        # Add migration metadata
        migration_metadata = options.get("migration_metadata", {})
        migration_metadata.update(
            {
                "migrated_from": self.get_name(),
                "migrated_at": str(int(time.time())),
                "source_identifier": source_identifier,
                "source_container": source_bucket,
            })

        # Store in target backend
        storage_options = {"metadata": {**metadata, **migration_metadata}}

        # Add additional options
        if "storage_options" in options:
            storage_options.update(options["storage_options"])

        # Store in target backend
        store_result = target_backend.store(
            data, container=target_container, path=target_path, options=storage_options)

        if not store_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to store content in target backend: {store_result.get('error', 'Unknown error')}",
                "source_backend": self.get_name(),
                "target_backend": target_backend.get_name(),
                "source_identifier": source_identifier,
                "source_container": source_bucket,
            }

        end_time = time.time()
        duration = end_time - start_time

        # Handle verification if requested
        verify = options.get("verify", False)
        verification_result = None

        if verify:
            # Get the target identifier
            target_identifier = store_result.get("identifier")

            # Retrieve content from target backend to verify
            target_retrieve = target_backend.retrieve(
                target_identifier,
                container=target_container,
                options=options.get("verification_options", {}),)

            if not target_retrieve.get("success", False):
                verification_result = {
                    "success": False,
                    "error": f"Failed to retrieve content from target for verification: {target_retrieve.get('error', 'Unknown error')}",
                }
            else:
                # Compare content
                source_data = data
                target_data = target_retrieve.get("data")

                if source_data == target_data:
                    verification_result = {
                        "success": True,
                        "message": "Verification successful: content matches",
                    }
                else:
                    # Content doesn't match
                    verification_result = {
                        "success": False,
                        "error": "Verification failed: content doesn't match",
                        "source_size": len(source_data),
                        "target_size": len(target_data) if target_data else 0,
                    }

        # Build the final result
        result = {
            "success": True,
            "source_backend": self.get_name(),
            "target_backend": target_backend.get_name(),
            "source_identifier": source_identifier,
            "source_container": source_bucket,
            "target_identifier": store_result.get("identifier"),
            "target_container": store_result.get("container"),
            "operation_time": duration,
            "content_size": (
                len(data)
                if isinstance(data, bytes)
                else retrieve_result.get("details", {}).get("content_length", 0)
            ),
            "timestamp": int(time.time()),
            "details": {
                "source_details": retrieve_result.get("details", {}),
                "target_details": store_result.get("details", {}),
            }
        }

        # Add verification results if performed
        if verification_result:
            result["verification"] = verification_result
            # If verification failed, mark the overall migration as failed
            if not verification_result.get("success", False):
                result["success"] = False
                result["error"] = (
                    f"Migration verification failed: {verification_result.get('error', 'Unknown error')}")

        return result

    def migrate_from(
        self,
        source_backend: BackendStorage,
        source_identifier: str,
        target_path: Optional[str] = None,
        source_container: Optional[str] = None,
        target_container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Migrate content from another storage backend to S3.

        Args:
            source_backend: Source backend to migrate from
            source_identifier: Identifier of content in source backend
            target_path: Optional path in S3
            source_container: Optional container in source backend
            target_container: Optional S3 bucket (uses default if not provided)
            options: Additional options for migration process

        Returns:
            Dict with migration status and details
        """
        options = options or {}
        target_bucket = self._resolve_bucket(target_container)

        start_time = time.time()

        # Retrieve the content from source backend
        retrieve_result = source_backend.retrieve(
            source_identifier,
            container=source_container,
            options=options.get("source_options", {}),)

        if not retrieve_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to retrieve source content: {retrieve_result.get('error', 'Unknown error')}",
                "source_backend": source_backend.get_name(),
                "target_backend": self.get_name(),
                "source_identifier": source_identifier,
                "target_container": target_bucket,
            }

        # Get data and metadata
        data = retrieve_result.get("data")
        metadata = retrieve_result.get("details", {}).get("metadata", {})

        # Add migration metadata
        migration_metadata = options.get("migration_metadata", {})
        migration_metadata.update(
            {
                "migrated_from": source_backend.get_name(),
                "migrated_at": str(int(time.time())),
                "source_identifier": source_identifier,
                "source_container": source_container,
            })

        # Store in S3
        storage_options = {"metadata": {**metadata, **migration_metadata}}

        # Add additional options
        if "storage_options" in options:
            storage_options.update(options["storage_options"])

        # Store in S3
        store_result = self.store(
            data, container=target_bucket, path=target_path, options=storage_options)

        if not store_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to store content in S3: {store_result.get('error', 'Unknown error')}",
                "source_backend": source_backend.get_name(),
                "target_backend": self.get_name(),
                "source_identifier": source_identifier,
                "target_container": target_bucket,
            }

        end_time = time.time()
        duration = end_time - start_time

        # Handle verification if requested
        verify = options.get("verify", False)
        verification_result = None

        if verify:
            # Get the target identifier
            target_identifier = store_result.get("identifier")

            # Retrieve content from S3 to verify
            target_retrieve = self.retrieve(
                target_identifier,
                container=target_bucket,
                options=options.get("verification_options", {}),)

            if not target_retrieve.get("success", False):
                verification_result = {
                    "success": False,
                    "error": f"Failed to retrieve content from S3 for verification: {target_retrieve.get('error', 'Unknown error')}",
                }
            else:
                # Compare content
                source_data = data
                target_data = target_retrieve.get("data")

                if source_data == target_data:
                    verification_result = {
                        "success": True,
                        "message": "Verification successful: content matches",
                    }
                else:
                    # Content doesn't match
                    verification_result = {
                        "success": False,
                        "error": "Verification failed: content doesn't match",
                        "source_size": len(source_data),
                        "target_size": len(target_data) if target_data else 0,
                    }

        # Build the final result
        result = {
            "success": True,
            "source_backend": source_backend.get_name(),
            "target_backend": self.get_name(),
            "source_identifier": source_identifier,
            "source_container": source_container,
            "target_identifier": store_result.get("identifier"),
            "target_container": target_bucket,
            "operation_time": duration,
            "content_size": (
                len(data)
                if isinstance(data, bytes)
                else retrieve_result.get("details", {}).get("content_length", 0)
            ),
            "timestamp": int(time.time()),
            "details": {
                "source_details": retrieve_result.get("details", {}),
                "target_details": store_result.get("details", {}),
            }
        }

        # Add verification results if performed
        if verification_result:
            result["verification"] = verification_result
            # If verification failed, mark the overall migration as failed
            if not verification_result.get("success", False):
                result["success"] = False
                result["error"] = (
                    f"Migration verification failed: {verification_result.get('error', 'Unknown error')}")

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get status information about the S3 backend."""
        try:
            # Check S3 connectivity
            try:
                with self.connection_pool as client:
                    client.list_buckets()
                connection_status = "connected"
            except Exception as e:
                connection_status = f"error: {str(e)}"

            # Check if default bucket exists
            bucket_status = "not_checked"
            if self.default_bucket:
                try:
                    with self.connection_pool as client:
                        client.head_bucket(Bucket=self.default_bucket)
                    bucket_status = "exists"
                except self.ClientError as e:
                    error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
                    if error_code == "404":
                        bucket_status = "not_found"
                    else:
                        bucket_status = f"error: {error_code}"
                except Exception as e:
                    bucket_status = f"error: {str(e)}"

            return {
                "success": True,
                "backend": self.get_name(),
                "available": connection_status == "connected",
                "status": {
                    "connection": connection_status,
                    "default_bucket": self.default_bucket,
                    "bucket_status": bucket_status,
                    "region": self.region,
                    "endpoint": self.endpoint_url or "default",
                    "cache_info": {
                        "enabled": True,
                        "directory": self.cache_dir,
                        "ttl": self.cache_ttl,
                        "size_limit": self.cache_size_limit,
                        "current_usage": self.cache_usage,
                        "hits": self.cache_hits,
                        "misses": self.cache_misses,
                    },
                    "performance": {
                        "max_threads": self.max_threads,
                        "connection_timeout": self.connection_timeout,
                        "read_timeout": self.read_timeout,
                        "max_retries": self.max_retries,
                        "chunk_size": self.chunk_size,
                    },
                },
            }
        except Exception as e:
            logger.error(f"Error getting S3 backend status: {str(e)}")
            return {
                "success": False,
                "backend": self.get_name(),
                "available": False,
                "error": str(e),
            }

    def cleanup(self):
        """Clean up resources used by the S3 backend."""
        try:
            # Shutdown thread pool
            if hasattr(self, "executor"):
                self.executor.shutdown(wait=False)

            # Delete cache if it was created by this instance
            if hasattr(self, "cache_dir") and os.path.exists(self.cache_dir):
                if "mcp_s3_cache_" in self.cache_dir:  # Safety check
                    try:
                        shutil.rmtree(self.cache_dir)
                        logger.info(f"Removed S3 backend cache directory: {self.cache_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to remove cache directory: {str(e)}")
        except Exception as e:
            logger.error(f"Error during S3 backend cleanup: {str(e)}")