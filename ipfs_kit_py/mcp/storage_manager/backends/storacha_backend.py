"""
Storacha backend implementation for the Unified Storage Manager.

This module implements the BackendStorage interface for Storacha (Web3.Storage),
providing high-performance access to decentralized storage via the W3 Blob Protocol
with enhanced reliability, caching, and migration capabilities.
"""

import logging
import time
import os
import json
import base64
import hashlib
import tempfile
import shutil
import threading
import io
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Union, BinaryIO, Tuple
from urllib.parse import urljoin
from ..backend_base import BackendStorage
from ..storage_types import StorageBackendType

# Configure logger
logger = logging.getLogger(__name__)

# Define constants
DEFAULT_MAX_THREADS = 5
DEFAULT_CACHE_SIZE = 100 * 1024 * 1024  # 100MB
DEFAULT_CONNECTION_TIMEOUT = 10  # seconds
DEFAULT_READ_TIMEOUT = 60  # seconds
DEFAULT_MAX_RETRIES = 3


class StorachaConnectionManager:
    """
    Manages connections to Storacha API endpoints with failover capabilities.

    This class provides reliable connectivity to Storacha services by:
    1. Managing multiple endpoints and rotating through them on failure
    2. Implementing exponential backoff for retries
    3. Monitoring connection health and status
    4. Providing detailed error information
    5. Supporting connection pooling for performance
    """
    DEFAULT_ENDPOINTS = ["https://api.web3.storage/", "https://w3s.link/"]

    def __init__(
        self,
        api_endpoints = None,
        api_key = None,
        max_retries=DEFAULT_MAX_RETRIES,
        mock_mode=False,
        connection_timeout=DEFAULT_CONNECTION_TIMEOUT,
        read_timeout=DEFAULT_READ_TIMEOUT,
    ):
        """Initialize connection manager with endpoints and authentication."""
        self.api_endpoints = api_endpoints or self.DEFAULT_ENDPOINTS.copy()
        self.api_key = api_key
        self.max_retries = max_retries
        self.mock_mode = mock_mode
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout

        # Track endpoint health and performance
        self.endpoint_health = {endpoint: True for endpoint in self.api_endpoints}
        self.endpoint_performance = {
            endpoint: {"success": 0, "error": 0, "latency": []} for endpoint in self.api_endpoints
        }
        self.current_endpoint_index = 0

        # Lock for thread safety
        self.lock = threading.RLock()

        # Create session for connection pooling
        self.session = requests.Session()

        # Create adapter with connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=20, max_retries=max_retries
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Configure default headers
        self.session.headers.update(
            {"User-Agent": "IPFS-Kit-Python/1.0", "Accept": "application/json"}
        )

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

        # Verify connection on startup
        self._verify_connection()

    def _verify_connection(self):
        """Verify connectivity to endpoints and mark unhealthy ones."""
        logger.info("Verifying connection to Storacha endpoints...")

        for endpoint in self.api_endpoints:
            try:
                start_time = time.time()
                self.session.get(
                    urljoin(endpoint, ""),
                    timeout=(self.connection_timeout, self.read_timeout),
                )
                latency = time.time() - start_time

                # Consider successful if we get any response (even error)
                self.endpoint_health[endpoint] = True

                # Record performance data
                with self.lock:
                    self.endpoint_performance[endpoint]["success"] += 1
                    self.endpoint_performance[endpoint]["latency"].append(latency)
                    # Keep only last 10 latency measurements
                    if len(self.endpoint_performance[endpoint]["latency"]) > 10:
                        self.endpoint_performance[endpoint]["latency"] = self.endpoint_performance[
                            endpoint
                        ]["latency"][-10:]

                logger.info(f"Storacha endpoint {endpoint} is reachable (latency: {latency:.2f}s)")
            except Exception as e:
                logger.warning(f"Storacha endpoint {endpoint} is unreachable: {str(e)}")
                self.endpoint_health[endpoint] = False

                # Record error
                with self.lock:
                    self.endpoint_performance[endpoint]["error"] += 1

        # Check if we have any healthy endpoints
        if not any(self.endpoint_health.values()):
            logger.warning("No healthy Storacha endpoints found. Falling back to mock mode.")
            self.mock_mode = True

    def _get_current_endpoint(self):
        """Get current active endpoint, rotating to a healthy one if needed."""
        with self.lock:
            # Start with current index
            start_index = self.current_endpoint_index
            endpoint = self.api_endpoints[start_index]

            # If current endpoint is healthy, use it
            if self.endpoint_health[endpoint]:
                return endpoint

            # Otherwise, find a healthy endpoint
            for _ in range(len(self.api_endpoints)):
                # Rotate to next endpoint
                self.current_endpoint_index = (self.current_endpoint_index + 1) % len(
                    self.api_endpoints
                )
                endpoint = self.api_endpoints[self.current_endpoint_index]

                # If healthy, use it
                if self.endpoint_health[endpoint]:
                    logger.info(f"Switched to healthy Storacha endpoint: {endpoint}")
                    return endpoint

                # If we've tried all endpoints and come back to start, all are unhealthy
                if self.current_endpoint_index == start_index:
                    break

            # All endpoints are unhealthy
            logger.error("All Storacha endpoints are unhealthy")
            return self.api_endpoints[start_index]  # Return original one for consistent errors

    def _handle_request_with_retry(self, method, path, **kwargs):
        """Make request with automatic retries and endpoint failover."""
        if self.mock_mode:
            logger.info(f"Running in mock mode, simulating {method} request to {path}")
            return self._mock_response(method, path, **kwargs)

        endpoint = self._get_current_endpoint()
        url = urljoin(endpoint, path)

        # Set default timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = (self.connection_timeout, self.read_timeout)

        retries = 0
        while retries <= self.max_retries:
            try:
                start_time = time.time()
                response = self.session.request(method=method, url=url, **kwargs)
                latency = time.time() - start_time

                # Record performance data
                with self.lock:
                    self.endpoint_performance[endpoint]["success"] += 1
                    self.endpoint_performance[endpoint]["latency"].append(latency)
                    # Keep only last 10 latency measurements
                    if len(self.endpoint_performance[endpoint]["latency"]) > 10:
                        self.endpoint_performance[endpoint]["latency"] = self.endpoint_performance[
                            endpoint
                        ]["latency"][-10:]

                # Mark endpoint as healthy
                self.endpoint_health[endpoint] = True

                # Check for API errors
                if response.status_code >= 400:
                    error_info = {}
                    try:
                        error_info = response.json()
                    except Exception:
                        error_info = {"message": response.text}

                    logger.error(f"Storacha API error ({response.status_code}): {error_info}")

                    # Record error
                    with self.lock:
                        self.endpoint_performance[endpoint]["error"] += 1

                    if response.status_code >= 500:
                        # Server error, try another endpoint
                        self.endpoint_health[endpoint] = False
                        if retries < self.max_retries:
                            retries += 1
                            endpoint = self._get_current_endpoint()
                            url = urljoin(endpoint, path)
                            backoff_time = 2**retries
                            logger.info(
                                f"Retrying with endpoint {endpoint} after {backoff_time}s backoff"
                            )
                            time.sleep(backoff_time)
                            continue

                return response

            except requests.RequestException as e:
                logger.error(f"Request to {url} failed: {str(e)}")

                # Mark endpoint as unhealthy
                self.endpoint_health[endpoint] = False

                # Record error
                with self.lock:
                    self.endpoint_performance[endpoint]["error"] += 1

                if retries < self.max_retries:
                    retries += 1
                    endpoint = self._get_current_endpoint()
                    url = urljoin(endpoint, path)
                    backoff_time = 2**retries
                    logger.info(f"Retrying with endpoint {endpoint} after {backoff_time}s backoff")
                    time.sleep(backoff_time)
                else:
                    logger.error(f"Max retries reached for {url}")
                    raise

        raise requests.RequestException(
            f"Failed to connect to any Storacha endpoints after {self.max_retries} retries"
        )

    def get_status(self):
        """Get the status and health of all endpoints."""
        status = {
            "endpoints": {},
            "mock_mode": self.mock_mode,
            "has_api_key": bool(self.api_key),
            "healthy_endpoints": sum(1 for v in self.endpoint_health.values() if v),
            "total_endpoints": len(self.api_endpoints),
        }

        # Gather endpoint stats
        for endpoint in self.api_endpoints:
            # Calculate average latency
            latencies = self.endpoint_performance[endpoint]["latency"]
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            status["endpoints"][endpoint] = {
                "healthy": self.endpoint_health[endpoint],
                "success_count": self.endpoint_performance[endpoint]["success"],
                "error_count": self.endpoint_performance[endpoint]["error"],
                "average_latency": avg_latency,
                "recent_latencies": latencies[-5:] if latencies else [],
            }

        return status

    def _mock_response(self, method, path, **kwargs):
        """Generate mock responses for testing without a real API connection."""
        mock_response = requests.Response()
        mock_response.status_code = 200

        if method.lower() == "get" and path.startswith("status"):
            mock_content = {
                "ok": True,
                "message": "Mock mode active",
                "version": "mock-1.0.0",
            }
        elif method.lower() == "post" and path.startswith("upload"):
            # Generate a mock CID based on request content
            content = kwargs.get("data", b"")
            if isinstance(content, (str, bytes)):
                mock_cid = (
                    base64.b32encode(hashlib.sha256(str(content).encode()).digest()[:10])
                    .decode()
                    .lower()
                )
                mock_cid = f"bafy{mock_cid}"
            else:
                mock_cid = f"bafymock{int(time.time())}"

            mock_content = {"cid": mock_cid, "created": time.time()}
        elif method.lower() == "get" and "/cid/" in path:
            mock_content = {"ok": True, "value": b"Mock content"}
            mock_response._content = b"Mock content"
            return mock_response
        else:
            mock_content = {"ok": True, "message": "Mock operation successful"}

        mock_response._content = json.dumps(mock_content).encode("utf-8")
        mock_response.headers["Content-Type"] = "application/json"
        return mock_response

    def get(self, path, **kwargs):
        """Make GET request to Storacha API."""
        return self._handle_request_with_retry("get", path, **kwargs)

    def post(self, path, **kwargs):
        """Make POST request to Storacha API."""
        return self._handle_request_with_retry("post", path, **kwargs)

    def delete(self, path, **kwargs):
        """Make DELETE request to Storacha API."""
        return self._handle_request_with_retry("delete", path, **kwargs)

    def put(self, path, **kwargs):
        """Make PUT request to Storacha API."""
        return self._handle_request_with_retry("put", path, **kwargs)


class StorachaBackend(BackendStorage):
    """
    Storacha backend implementation for Web3.Storage with enhanced capabilities.

    This backend provides:
    1. Reliable connectivity with automatic failover
    2. Local content caching for improved performance
    3. Background operations with ThreadPoolExecutor
    4. Cross-backend migration capabilities
    5. Enhanced error handling and monitoring
    """
    def __init__(self, resources: Dict[str, Any], metadata: Dict[str, Any]):
        """Initialize Storacha backend with advanced features."""
        super().__init__(StorageBackendType.STORACHA, resources, metadata)

        # Extract configuration
        self.api_key = resources.get("api_key") or os.environ.get("W3S_API_KEY")
        endpoints = resources.get("endpoints") or os.environ.get("W3S_ENDPOINTS")
        mock_mode = resources.get("mock_mode", False)

        if endpoints:
            if isinstance(endpoints, str):
                endpoints = [e.strip() for e in endpoints.split(",")]
            elif not isinstance(endpoints, list):
                endpoints = None

        # Performance configuration
        self.max_threads = int(resources.get("max_threads", DEFAULT_MAX_THREADS))
        self.connection_timeout = int(
            resources.get("connection_timeout", DEFAULT_CONNECTION_TIMEOUT)
        )
        self.read_timeout = int(resources.get("read_timeout", DEFAULT_READ_TIMEOUT))
        self.max_retries = int(resources.get("max_retries", DEFAULT_MAX_RETRIES))

        # Initialize connection manager
        self.connection = StorachaConnectionManager(
            api_endpoints=endpoints,
            api_key=self.api_key,
            max_retries=self.max_retries,
            mock_mode=mock_mode or not self.api_key,
            connection_timeout=self.connection_timeout,
            read_timeout=self.read_timeout,
        )

        # Initialize metadata cache
        self._metadata_cache = {}

        # Initialize thread pool for background operations
        self.executor = ThreadPoolExecutor(max_workers=self.max_threads)

        # Initialize local cache for frequently accessed data
        self._init_local_cache()

    def _init_local_cache(self):
        """Initialize the local cache for frequently accessed data."""
        cache_dir = os.environ.get("MCP_STORACHA_CACHE_DIR")
        if not cache_dir:
            temp_dir = tempfile.gettempdir()
            cache_dir = os.path.join(
                temp_dir,
                f"mcp_storacha_cache_{base64.b32encode(os.urandom(5)).decode().lower()}",
            )

        os.makedirs(cache_dir, exist_ok=True)
        self.cache_dir = cache_dir
        logger.info(f"Storacha backend using local cache directory: {cache_dir}")

        # Cache expiration time in seconds
        self.cache_ttl = int(self.resources.get("cache_ttl", 3600))  # Default: 1 hour

        # Cache size limit in bytes
        self.cache_size_limit = int(self.resources.get("cache_size_limit", DEFAULT_CACHE_SIZE))

        # Track cache usage
        self.cache_usage = 0
        self.cache_hits = 0
        self.cache_misses = 0

    def _cache_path(self, cid: str) -> str:
        """Get the cache path for a CID."""
        # Create a safe path from the CID
        return os.path.join(self.cache_dir, cid)

    def _is_in_cache(self, cid: str) -> Tuple[bool, Optional[str]]:
        """Check if a CID is in the cache and not expired."""
        cache_path = self._cache_path(cid)
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
            logger.warning(f"Error checking cache for {cid}: {str(e)}")
            return False, None

    def _add_to_cache(self, cid: str, data: bytes, metadata: Dict[str, Any]) -> str:
        """Add object to cache."""
        cache_path = self._cache_path(cid)
        meta_path = f"{cache_path}.meta"

        # Check if we need to enforce cache size limits
        if self.cache_usage + len(data) > self.cache_size_limit:
            self._clean_cache()

        try:
            with open(cache_path, "wb") as f:
                f.write(data)

            cache_metadata = {
                "cached_at": time.time(),
                "size": len(data),
                "cid": cid,
                "object_metadata": metadata,
            }

            with open(meta_path, "w") as f:
                json.dump(cache_metadata, f)

            # Update cache usage
            self.cache_usage += len(data)

            return cache_path
        except Exception as e:
            logger.warning(f"Error caching object {cid}: {str(e)}")
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
            target_free = self.cache_size_limit // 2

            for file_path, meta_path, _, size in cache_files:
                # Delete the file and its metadata
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if os.path.exists(meta_path):
                        os.remove(meta_path)

                    freed_space += size
                    self.cache_usage -= size

                    if freed_space >= target_free:
                        break
                except Exception as e:
                    logger.warning(f"Error cleaning cache: {str(e)}")

            logger.info(f"Cleaned Storacha cache, freed {freed_space} bytes")
        except Exception as e:
            logger.error(f"Cache cleaning failed: {str(e)}")

    def _is_file_like(self, obj):
        """Check if object is file-like (has read method)."""
        return hasattr(obj, "read") and callable(obj.read)

    def store(
        self,
        data: Union[bytes, BinaryIO, str],
        container: Optional[str] = None,
        path: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store data in Storacha (Web3.Storage) with enhanced reliability."""
        options = options or {}

        try:
            # Prepare data for upload
            files = {}
            metadata = {
                "mcp_added": str(int(time.time())),
                "mcp_backend": self.get_name(),
            }

            # Add custom metadata from options
            if "metadata" in options:
                for k, v in options["metadata"].items():
                    if isinstance(v, (str, int, float, bool)):
                        metadata[f"mcp_{k}"] = str(v)

            # Create upload payload
            if isinstance(data, str):
                # If it's a string, convert to bytes
                data = data.encode("utf-8")
                filename = path or "file.txt"
                files = {"file": (filename, io.BytesIO(data))}
            elif isinstance(data, bytes):
                # If it's bytes, create BytesIO
                filename = path or "file.bin"
                files = {"file": (filename, io.BytesIO(data))}
            elif self._is_file_like(data):
                # If it's a file-like object
                filename = path or getattr(data, "name", "uploaded_file")
                files = {"file": (filename, data)}

            # Add metadata as form field
            form_data = {"meta": json.dumps(metadata)}

            # Make upload request
            response = self.connection.post("upload", files=files, data=form_data)

            if response.status_code == 200:
                result = response.json()
                cid = result.get("cid")

                # Store in metadata cache
                if cid:
                    self._metadata_cache[cid] = {
                        "metadata": metadata,
                        "created": time.time(),
                    }

                    # Cache the data if it's a reasonable size and caching is enabled
                    if (
                        options.get("cache", True)
                        and isinstance(data, bytes)
                        and len(data) < self.cache_size_limit // 10
                    ):
                        self._add_to_cache(cid, data, metadata)

                return {
                    "success": True,
                    "identifier": cid,
                    "backend": self.get_name(),
                    "details": result,
                }
            else:
                error_msg = "Failed to upload to Storacha"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except Exception:
                    error_msg = f"{error_msg}: HTTP {response.status_code}"

                return {
                    "success": False,
                    "error": error_msg,
                    "backend": self.get_name(),
                    "details": {
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                }

        except Exception as e:
            logger.error(f"Storacha store error: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def retrieve(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve data from Storacha with caching support."""
        options = options or {}

        # Check if the object is in cache
        use_cache = options.get("use_cache", True)
        if use_cache:
            in_cache, cache_path = self._is_in_cache(identifier)
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
                        "cached": True,
                        "details": {
                            "cid": identifier,
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
            # Request content by CID
            response = self.connection.get(f"content/cid/{identifier}")

            if response.status_code == 200:
                # Get content
                data = response.content

                # Get metadata if available
                metadata = {}
                try:
                    meta_response = self.connection.get(f"metadata/cid/{identifier}")
                    if meta_response.status_code == 200:
                        metadata = meta_response.json().get("metadata", {})
                except Exception as e:
                    logger.warning(f"Failed to get metadata for {identifier}: {str(e)}")

                # Add to cache if enabled and size is reasonable
                if use_cache and len(data) < self.cache_size_limit // 10:
                    self._add_to_cache(identifier, data, metadata)

                return {
                    "success": True,
                    "data": data,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "details": {
                        "metadata": metadata,
                        "content_type": response.headers.get("Content-Type"),
                        "content_length": len(data),
                    },
                }
            else:
                error_msg = f"Failed to retrieve {identifier} from Storacha"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except Exception:
                    error_msg = f"{error_msg}: HTTP {response.status_code}"

                return {
                    "success": False,
                    "error": error_msg,
                    "backend": self.get_name(),
                    "details": {
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                }

        except Exception as e:
            logger.error(f"Storacha retrieve error: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def delete(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Delete content from Storacha.

        Note: In decentralized storage like Web3.Storage, content is immutable and
        content-addressed. This operation marks the content as deleted in the user's
        account but the data may still persist on the network.
        """
        options = options or {}

        try:
            # Web3.Storage may not support explicit deletion
            # This is a placeholder and may need implementation when supported
            deletion_attempt = False
            deletion_result = None

            # Try deletion API if instructed
            if options.get("try_deletion_api", False):
                try:
                    # Attempt to call deletion API if it exists
                    response = self.connection.delete(f"unpin/cid/{identifier}")
                    deletion_attempt = True

                    if response.status_code in (200, 202, 204):
                        deletion_result = {
                            "success": True,
                            "message": "Content unpinned successfully",
                        }
                    else:
                        deletion_result = {
                            "success": False,
                            "message": f"Unpin operation failed: HTTP {response.status_code}",
                            "details": response.text,
                        }
                except Exception as del_error:
                    deletion_result = {
                        "success": False,
                        "message": f"Deletion API error: {str(del_error)}",
                    }

            # Remove from cache
            cache_path = self._cache_path(identifier)
            meta_path = f"{cache_path}.meta"

            if os.path.exists(cache_path):
                try:
                    # Get size before deleting for accurate cache usage tracking
                    size = os.path.getsize(cache_path)
                    os.remove(cache_path)
                    self.cache_usage -= size
                except Exception as cache_error:
                    logger.warning(f"Error removing cached file: {str(cache_error)}")

            if os.path.exists(meta_path):
                try:
                    os.remove(meta_path)
                except Exception as cache_error:
                    logger.warning(f"Error removing cache metadata: {str(cache_error)}")

            # For now, we'll also remove it from our metadata cache
            if identifier in self._metadata_cache:
                del self._metadata_cache[identifier]

            result = {
                "success": True,
                "warning": "Content may still be available on IPFS network",
                "backend": self.get_name(),
                "identifier": identifier,
                "details": {
                    "note": "Deletion in decentralized storage is limited to unpinning",
                    "cache_cleaned": True,
                },
            }

            # Add deletion attempt information if applicable
            if deletion_attempt:
                result["deletion_attempt"] = deletion_result

            return result

        except Exception as e:
            logger.error(f"Storacha delete error: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def list(
        self,
        container: Optional[str] = None,
        prefix: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """List content stored in Storacha account with enhanced performance."""
        options = options or {}

        try:
            # Set pagination parameters
            query_params = {}
            if "limit" in options:
                query_params["size"] = options["limit"]
            if "before" in options:
                query_params["before"] = options["before"]

            # Make API request to list uploads
            response = self.connection.get("user/uploads", params=query_params)

            if response.status_code == 200:
                result = response.json()
                items = []

                for upload in result.get("uploads", []):
                    cid = upload.get("cid")

                    # Apply prefix filter if provided
                    if prefix and not cid.startswith(prefix):
                        continue

                    # Add metadata from cache if available
                    cached_metadata = {}
                    if cid in self._metadata_cache:
                        cached_metadata = self._metadata_cache[cid].get("metadata", {})

                    item = {
                        "identifier": cid,
                        "name": upload.get("name", cid),
                        "created": upload.get("created"),
                        "size": upload.get("dagSize"),
                        "pins": upload.get("pins", []),
                        "backend": self.get_name(),
                        "cached_metadata": cached_metadata if cached_metadata else None,
                        "cached": cid in self._metadata_cache,
                    }
                    items.append(item)

                return {
                    "success": True,
                    "items": items,
                    "backend": self.get_name(),
                    "details": {
                        "count": len(items),
                        "has_more": result.get("next") is not None,
                        "next_token": result.get("next"),
                    },
                }
            else:
                error_msg = "Failed to list content from Storacha"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except Exception:
                    error_msg = f"{error_msg}: HTTP {response.status_code}"

                return {
                    "success": False,
                    "error": error_msg,
                    "backend": self.get_name(),
                    "details": {
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                }

        except Exception as e:
            logger.error(f"Storacha list error: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def exists(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if content exists in Storacha with cache support."""
        options = options or {}

        # Check local cache first
        use_cache = options.get("use_cache", True)
        if use_cache:
            in_cache, _ = self._is_in_cache(identifier)
            if in_cache:
                return True

        try:
            # Check if content exists by making a HEAD request
            response = self.connection.get(f"status/cid/{identifier}", allow_redirects=False)

            # 200 means found, 404 means not found
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Storacha exists check error: {str(e)}")
            return False

    def get_metadata(
        self,
        identifier: str,
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get metadata for content in Storacha with cache support."""
        options = options or {}

        # Check if metadata is in cache
        use_cache = options.get("use_cache", True)
        if use_cache:
            # Check in-memory cache first
            if identifier in self._metadata_cache:
                cached = self._metadata_cache[identifier]
                return {
                    "success": True,
                    "metadata": cached.get("metadata", {}),
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "details": {
                        "source": "memory_cache",
                        "cached_at": cached.get("created"),
                    },
                }

            # Then check disk cache
            in_cache, cache_path = self._is_in_cache(identifier)
            if in_cache:
                try:
                    with open(f"{cache_path}.meta", "r") as f:
                        cached_metadata = json.load(f)

                    if "object_metadata" in cached_metadata:
                        # Update in-memory cache as well
                        self._metadata_cache[identifier] = {
                            "metadata": cached_metadata.get("object_metadata", {}),
                            "created": cached_metadata.get("cached_at", time.time()),
                        }

                        return {
                            "success": True,
                            "metadata": cached_metadata.get("object_metadata", {}),
                            "backend": self.get_name(),
                            "identifier": identifier,
                            "cached": True,
                            "details": {
                                "source": "disk_cache",
                                "cached_at": cached_metadata.get("cached_at"),
                            },
                        }
                except Exception:
                    # If anything goes wrong with cache, fall back to API
                    pass

        try:
            # Not in cache, try to get from API
            response = self.connection.get(f"status/cid/{identifier}")

            if response.status_code == 200:
                status_data = response.json()

                # Now try to get metadata
                metadata = {}
                try:
                    meta_response = self.connection.get(f"metadata/cid/{identifier}")
                    if meta_response.status_code == 200:
                        metadata = meta_response.json().get("metadata", {})
                except Exception as e:
                    logger.warning(f"Failed to get metadata for {identifier}: {str(e)}")

                # Build response
                result = {
                    "success": True,
                    "metadata": metadata,
                    "backend": self.get_name(),
                    "identifier": identifier,
                    "details": status_data,
                }

                # Update cache
                self._metadata_cache[identifier] = {
                    "metadata": metadata,
                    "created": time.time(),
                    "status": status_data,
                }

                return result
            else:
                error_msg = f"Failed to get metadata for {identifier}"
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_msg)
                except Exception:
                    error_msg = f"{error_msg}: HTTP {response.status_code}"

                return {
                    "success": False,
                    "error": error_msg,
                    "backend": self.get_name(),
                    "details": {
                        "status_code": response.status_code,
                        "response": response.text,
                    },
                }

        except Exception as e:
            logger.error(f"Storacha get_metadata error: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def update_metadata(
        self,
        identifier: str,
        metadata: Dict[str, Any],
        container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for content in Storacha.

        Note: Web3.Storage's metadata update capabilities may be limited.
        This implementation tries to use the API if available, but may fall back
        to only updating the local cache.
        """
        options = options or {}

        try:
            # Get current metadata
            current_metadata = {}
            if identifier in self._metadata_cache:
                current_metadata = self._metadata_cache[identifier].get("metadata", {})
            else:
                # Try to get from API
                meta_result = self.get_metadata(identifier)
                if meta_result.get("success"):
                    current_metadata = meta_result.get("metadata", {})

            # Merge with new metadata
            updated_metadata = {**current_metadata}
            for k, v in metadata.items():
                if v is None:
                    # Remove if value is None
                    if k in updated_metadata:
                        del updated_metadata[k]
                else:
                    # Add or update
                    updated_metadata[k] = v

            # Try to update via API if available
            # This is a placeholder as the exact API may vary
            api_update_success = False
            api_update_details = {}

            try:
                # Attempt API update - implementation depends on Web3.Storage API
                # This might not be supported, so we catch exceptions separately
                meta_payload = {"cid": identifier, "metadata": updated_metadata}
                update_response = self.connection.put(
                    f"metadata/cid/{identifier}", json=meta_payload
                )

                if update_response.status_code in (200, 201, 204):
                    api_update_success = True
                    try:
                        api_update_details = update_response.json()
                    except Exception:
                        api_update_details = {
                            "status_code": update_response.status_code,
                            "response": update_response.text,
                        }
            except Exception as update_error:
                logger.warning(f"API metadata update not supported: {str(update_error)}")
                # Continue with local update only

            # Update cache regardless of API success
            if identifier in self._metadata_cache:
                self._metadata_cache[identifier]["metadata"] = updated_metadata
                self._metadata_cache[identifier]["updated"] = time.time()
            else:
                self._metadata_cache[identifier] = {
                    "metadata": updated_metadata,
                    "created": time.time(),
                    "updated": time.time(),
                }

            # Update disk cache if present
            cache_path = self._cache_path(identifier)
            meta_path = f"{cache_path}.meta"

            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        cached_metadata = json.load(f)

                    cached_metadata["object_metadata"] = updated_metadata
                    cached_metadata["updated_at"] = time.time()

                    with open(meta_path, "w") as f:
                        json.dump(cached_metadata, f)
                except Exception as cache_error:
                    logger.warning(f"Error updating cache metadata: {str(cache_error)}")

            return {
                "success": True,
                "api_update": api_update_success,
                "backend": self.get_name(),
                "identifier": identifier,
                "details": {
                    "api_details": api_update_details,
                    "cache_updated": True,
                    "metadata": updated_metadata,
                },
            }

        except Exception as e:
            logger.error(f"Storacha update_metadata error: {str(e)}")
            return {"success": False, "error": str(e), "backend": self.get_name()}

    def migrate_to(
        self,
        source_identifier: str,
        target_backend: BackendStorage,
        target_container: Optional[str] = None,
        target_path: Optional[str] = None,
        source_container: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Migrate content from Storacha to another storage backend.

        Args:
            source_identifier: Identifier of content in Storacha
            target_backend: Target backend to migrate to
            target_container: Optional container in target backend
            target_path: Optional path in target backend
            source_container: Unused parameter (kept for interface consistency)
            options: Additional options for migration process

        Returns:
            Dict with migration status and details
        """
        options = options or {}

        start_time = time.time()

        # Retrieve the content from Storacha
        retrieve_result = self.retrieve(source_identifier, None, options)

        if not retrieve_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to retrieve source content: {retrieve_result.get('error', 'Unknown error')}",
                "source_backend": self.get_name(),
                "target_backend": target_backend.get_name(),
                "source_identifier": source_identifier,
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
            }
        )

        # Store in target backend
        storage_options = {"metadata": {**metadata, **migration_metadata}}

        # Add additional options
        if "storage_options" in options:
            storage_options.update(options["storage_options"])

        # Store in target backend
        store_result = target_backend.store(
            data, container=target_container, path=target_path, options=storage_options
        )

        if not store_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to store content in target backend: {store_result.get('error', 'Unknown error')}",
                "source_backend": self.get_name(),
                "target_backend": target_backend.get_name(),
                "source_identifier": source_identifier,
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
                options=options.get("verification_options", {}),
            )

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
            },
        }

        # Add verification results if performed
        if verification_result:
            result["verification"] = verification_result
            # If verification failed, mark the overall migration as failed
            if not verification_result.get("success", False):
                result["success"] = False
                result["error"] = (
                    f"Migration verification failed: {verification_result.get('error', 'Unknown error')}"
                )

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
        Migrate content from another storage backend to Storacha.

        Args:
            source_backend: Source backend to migrate from
            source_identifier: Identifier of content in source backend
            target_path: Optional path in Storacha
            source_container: Optional container in source backend
            target_container: Unused parameter (kept for interface consistency)
            options: Additional options for migration process

        Returns:
            Dict with migration status and details
        """
        options = options or {}

        start_time = time.time()

        # Retrieve the content from source backend
        retrieve_result = source_backend.retrieve(
            source_identifier,
            container=source_container,
            options=options.get("source_options", {}),
        )

        if not retrieve_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to retrieve source content: {retrieve_result.get('error', 'Unknown error')}",
                "source_backend": source_backend.get_name(),
                "target_backend": self.get_name(),
                "source_identifier": source_identifier,
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
            }
        )

        # Store in Storacha
        storage_options = {"metadata": {**metadata, **migration_metadata}}

        # Add additional options
        if "storage_options" in options:
            storage_options.update(options["storage_options"])

        # Store in Storacha
        store_result = self.store(
            data,
            container = None,  # Not used in Storacha
            path=target_path,
            options=storage_options,
        )

        if not store_result.get("success", False):
            return {
                "success": False,
                "error": f"Failed to store content in Storacha: {store_result.get('error', 'Unknown error')}",
                "source_backend": source_backend.get_name(),
                "target_backend": self.get_name(),
                "source_identifier": source_identifier,
            }

        end_time = time.time()
        duration = end_time - start_time

        # Handle verification if requested
        verify = options.get("verify", False)
        verification_result = None

        if verify:
            # Get the target identifier
            target_identifier = store_result.get("identifier")

            # Retrieve content from Storacha to verify
            target_retrieve = self.retrieve(
                target_identifier,
                container = None,
                options=options.get("verification_options", {}),
            )

            if not target_retrieve.get("success", False):
                verification_result = {
                    "success": False,
                    "error": f"Failed to retrieve content from Storacha for verification: {target_retrieve.get('error', 'Unknown error')}",
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
            },
        }

        # Add verification results if performed
        if verification_result:
            result["verification"] = verification_result
            # If verification failed, mark the overall migration as failed
            if not verification_result.get("success", False):
                result["success"] = False
                result["error"] = (
                    f"Migration verification failed: {verification_result.get('error', 'Unknown error')}"
                )

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get status information about the Storacha backend."""
        try:
            # Get connection status
            connection_status = self.connection.get_status()

            # Check API connectivity
            try:
                response = self.connection.get("status")
                api_status = (
                    "connected"
                    if response.status_code == 200
                    else f"error ({response.status_code})"
                )

                # Try to parse version information
                api_version = None
                try:
                    data = response.json()
                    api_version = data.get("version")
                except Exception:
                    pass
            except Exception as e:
                api_status = f"error: {str(e)}"
                api_version = None

            return {
                "success": True,
                "backend": self.get_name(),
                "available": any(
                    endpoint["healthy"] for endpoint in connection_status["endpoints"].values()
                ),
                "status": {
                    "connection": connection_status,
                    "api_status": api_status,
                    "api_version": api_version,
                    "mock_mode": connection_status["mock_mode"],
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
                    },
                },
            }
        except Exception as e:
            logger.error(f"Error getting Storacha backend status: {str(e)}")
            return {
                "success": False,
                "backend": self.get_name(),
                "available": False,
                "error": str(e),
            }

    def cleanup(self):
        """Clean up resources used by the Storacha backend."""
        try:
            # Shutdown thread pool
            if hasattr(self, "executor"):
                self.executor.shutdown(wait=False)

            # Close connection session
            if hasattr(self, "connection") and hasattr(self.connection, "session"):
                self.connection.session.close()

            # Delete cache if it was created by this instance
            if hasattr(self, "cache_dir") and os.path.exists(self.cache_dir):
                if "mcp_storacha_cache_" in self.cache_dir:  # Safety check
                    try:
                        shutil.rmtree(self.cache_dir)
                        logger.info(f"Removed Storacha backend cache directory: {self.cache_dir}")
                    except Exception as e:
                        logger.warning(f"Failed to remove cache directory: {str(e)}")
        except Exception as e:
            logger.error(f"Error during Storacha backend cleanup: {str(e)}")
            
    def get_name(self) -> str:
        """Get the name of this backend implementation.
        
        Returns:
            String representation of the backend name
        """
        return "storacha"
            
    # BackendStorage interface implementations
    def add_content(self, content: Union[str, bytes, BinaryIO], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add content to the storage backend.
        
        Args:
            content: Content to store (can be a path, bytes, or file-like object)
            metadata: Optional metadata for the content
            
        Returns:
            Dict with operation result including content ID
        """
        # Convert metadata format if needed
        options = {}
        if metadata:
            options["metadata"] = metadata
            
        # Delegate to the underlying store method
        return self.store(content, options=options)
        
    def get_content(self, content_id: str) -> Dict[str, Any]:
        """Retrieve content from the storage backend.
        
        Args:
            content_id: ID of the content to retrieve
            
        Returns:
            Dict with operation result including content data
        """
        # Delegate to the underlying retrieve method
        return self.retrieve(content_id)
        
    def remove_content(self, content_id: str) -> Dict[str, Any]:
        """Remove content from the storage backend.
        
        Args:
            content_id: ID of the content to remove
            
        Returns:
            Dict with operation result
        """
        # Delegate to the underlying delete method
        return self.delete(content_id)
