"""
IPFS Connection Pool Module.

This module provides a connection pooling mechanism for IPFS clients to improve
performance by reusing connections rather than creating new ones for each request.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable, Counter as CounterType
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from collections import Counter

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging
logger = logging.getLogger(__name__)

class IPFSConnectionConfig:
    """Configuration class for IPFS connection pool."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5001/api/v0",
        max_connections: int = 10,
        connection_timeout: int = 10,
        idle_timeout: int = 60,
        max_retries: int = 3,
        retry_backoff_factor: float = 0.5,
        retry_status_codes: List[int] = None,
        headers: Dict[str, str] = None,
        verify_ssl: bool = True,
        connection_check_interval: int = 10,
        health_check_endpoint: str = "id",
    ):
        """
        Initialize the IPFS connection pool configuration.

        Args:
            base_url: Base URL for the IPFS API.
            max_connections: Maximum number of connections in the pool.
            connection_timeout: Timeout for new connections in seconds.
            idle_timeout: Maximum time a connection can remain idle before being closed.
            max_retries: Maximum number of retries for failed requests.
            retry_backoff_factor: Backoff factor for retries.
            retry_status_codes: HTTP status codes to retry.
            headers: Default headers to include in all requests.
            verify_ssl: Whether to verify SSL certificates.
            connection_check_interval: Interval in seconds to check connection health.
            health_check_endpoint: Endpoint to use for health checks.
        """
        self.base_url = base_url
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor
        self.retry_status_codes = retry_status_codes or [500, 502, 503, 504]
        self.headers = headers or {}
        self.verify_ssl = verify_ssl
        self.connection_check_interval = connection_check_interval
        self.health_check_endpoint = health_check_endpoint

        # Parse the URL to extract host information
        parsed_url = urlparse(base_url)
        self.host = parsed_url.netloc
        self.scheme = parsed_url.scheme
        self.api_path = parsed_url.path

class IPFSConnection:
    """Represents a single connection to an IPFS node."""

    def __init__(self, config: IPFSConnectionConfig):
        """
        Initialize a connection with the given configuration.

        Args:
            config: Connection configuration.
        """
        self.config = config
        self.session = self._create_session()
        self.last_used = time.time()
        self.in_use = False
        self.id = id(self)  # Unique identifier for the connection
        self.is_healthy = True
        self.error_count = 0
        self.request_count = 0
        self.total_response_time = 0.0

    def _create_session(self) -> requests.Session:
        """
        Create a new session with retry logic.

        Returns:
            A configured requests.Session object.
        """
        session = requests.Session()

        # Configure retry logic
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff_factor,
            status_forcelist=self.config.retry_status_codes,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount(f"{self.config.scheme}://", adapter)

        # Apply default headers
        session.headers.update(self.config.headers)
        session.verify = self.config.verify_ssl

        return session

    def get(self, path: str, **kwargs) -> requests.Response:
        """
        Perform a GET request.

        Args:
            path: The API path to call.
            **kwargs: Additional arguments to pass to the request.

        Returns:
            The response from the IPFS node.
        """
        self.last_used = time.time()
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        start_time = time.time()
        try:
            response = self.session.get(url, timeout=self.config.connection_timeout, **kwargs)
            self.request_count += 1
            self.total_response_time += time.time() - start_time

            if response.status_code >= 400:
                self.error_count += 1
                if self.error_count > 5:  # Mark unhealthy after 5 consecutive errors
                    self.is_healthy = False
            else:
                self.error_count = 0  # Reset error count on successful request
                self.is_healthy = True

            return response
        except Exception as e:
            self.error_count += 1
            if self.error_count > 5:
                self.is_healthy = False
            duration = time.time() - start_time
            self.total_response_time += duration
            logger.error(f"Error in GET request to {url}: {str(e)}")
            raise

    def post(self, path: str, **kwargs) -> requests.Response:
        """
        Perform a POST request.

        Args:
            path: The API path to call.
            **kwargs: Additional arguments to pass to the request.

        Returns:
            The response from the IPFS node.
        """
        self.last_used = time.time()
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        start_time = time.time()
        try:
            response = self.session.post(url, timeout=self.config.connection_timeout, **kwargs)
            self.request_count += 1
            self.total_response_time += time.time() - start_time

            if response.status_code >= 400:
                self.error_count += 1
                if self.error_count > 5:
                    self.is_healthy = False
            else:
                self.error_count = 0
                self.is_healthy = True

            return response
        except Exception as e:
            self.error_count += 1
            if self.error_count > 5:
                self.is_healthy = False
            duration = time.time() - start_time
            self.total_response_time += duration
            logger.error(f"Error in POST request to {url}: {str(e)}")
            raise

    def check_health(self) -> bool:
        """
        Check if the connection is healthy by making a request to the health check endpoint.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = self.get(self.config.health_check_endpoint)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for connection {self.id}: {str(e)}")
            return False

    def close(self):
        """Close the session."""
        self.session.close()

    def is_expired(self, current_time: float = None) -> bool:
        """
        Check if the connection has expired based on idle timeout.

        Args:
            current_time: Current time as a timestamp.

        Returns:
            True if the connection has expired, False otherwise.
        """
        if current_time is None:
            current_time = time.time()
        return not self.in_use and (current_time - self.last_used) > self.config.idle_timeout

    def get_average_response_time(self) -> float:
        """
        Get the average response time for this connection.

        Returns:
            Average response time in seconds, or 0 if no requests have been made.
        """
        if self.request_count == 0:
            return 0.0
        return self.total_response_time / self.request_count

class IPFSConnectionPool:
    """
    Pool of IPFS connections for reuse.

    This class manages a pool of IPFS connections to improve performance
    by reusing existing connections rather than creating new ones for each request.
    """

    def __init__(self, config: IPFSConnectionConfig = None):
        """
        Initialize the connection pool.

        Args:
            config: Connection pool configuration.
        """
        self.config = config or IPFSConnectionConfig()
        self._lock = threading.RLock()
        self._connections: List[IPFSConnection] = []
        self._executor = ThreadPoolExecutor(max_workers=self.config.max_connections)
        self._cleanup_thread = threading.Thread(target=self._cleanup_expired_connections, daemon=True)
        self._health_check_thread = threading.Thread(target=self._check_connection_health, daemon=True)
        self._shutdown = False

        # Metrics
        self.request_count = 0
        self.error_count = 0
        self.total_response_time = 0.0
        self.endpoint_stats: Dict[str, Dict[str, Any]] = {}

        # Start maintenance threads
        self._cleanup_thread.start()
        self._health_check_thread.start()

        logger.info(f"Initialized IPFS connection pool with max {self.config.max_connections} connections")

    def _cleanup_expired_connections(self):
        """Background thread to clean up expired connections."""
        while not self._shutdown:
            try:
                with self._lock:
                    current_time = time.time()
                    expired_connections = [conn for conn in self._connections if conn.is_expired(current_time)]

                    for conn in expired_connections:
                        logger.debug(f"Removing expired connection {conn.id}")
                        self._connections.remove(conn)
                        conn.close()

                    if expired_connections:
                        logger.info(f"Cleaned up {len(expired_connections)} expired connections")
            except Exception as e:
                logger.error(f"Error during connection cleanup: {str(e)}")

            # Sleep for a while before checking again
            time.sleep(10)

    def _check_connection_health(self):
        """Background thread to check the health of connections."""
        while not self._shutdown:
            try:
                with self._lock:
                    unhealthy_connections = []
                    for conn in self._connections:
                        if not conn.in_use and not conn.is_healthy:
                            # Try to recover the connection
                            if not conn.check_health():
                                unhealthy_connections.append(conn)

                    # Remove unhealthy connections
                    for conn in unhealthy_connections:
                        logger.warning(f"Removing unhealthy connection {conn.id}")
                        self._connections.remove(conn)
                        conn.close()

                    if unhealthy_connections:
                        logger.info(f"Removed {len(unhealthy_connections)} unhealthy connections")
            except Exception as e:
                logger.error(f"Error during connection health check: {str(e)}")

            # Sleep for the configured interval
            time.sleep(self.config.connection_check_interval)

    def _get_connection(self) -> IPFSConnection:
        """
        Get an available connection from the pool or create a new one.

        Returns:
            An IPFS connection.
        """
        with self._lock:
            # First try to find a healthy available connection
            for conn in self._connections:
                if not conn.in_use and conn.is_healthy:
                    conn.in_use = True
                    return conn

            # If we don't have max connections yet, create a new one
            if len(self._connections) < self.config.max_connections:
                conn = IPFSConnection(self.config)
                conn.in_use = True
                self._connections.append(conn)
                logger.debug(f"Created new connection {conn.id}, total: {len(self._connections)}")
                return conn

            # If all connections are in use or unhealthy, try to wait for one to become available
            attempts = 0
            while attempts < 5:  # Limit wait attempts
                for conn in self._connections:
                    if not conn.in_use and conn.is_healthy:
                        conn.in_use = True
                        return conn

                # Release the lock temporarily to allow other threads to release connections
                self._lock.release()
                time.sleep(0.1)
                self._lock.acquire()
                attempts += 1

            # If we still don't have a connection, use any available connection even if unhealthy
            for conn in self._connections:
                if not conn.in_use:
                    conn.in_use = True
                    logger.warning(f"Using potentially unhealthy connection {conn.id} as all connections are busy")
                    return conn

            # As a last resort, create a new connection even if we exceed the max
            logger.warning(f"Creating connection beyond max ({len(self._connections)} >= {self.config.max_connections})")
            conn = IPFSConnection(self.config)
            conn.in_use = True
            self._connections.append(conn)
            return conn

    def _release_connection(self, conn: IPFSConnection):
        """
        Release a connection back to the pool.

        Args:
            conn: The connection to release.
        """
        with self._lock:
            if conn in self._connections:
                conn.in_use = False
                conn.last_used = time.time()

    def _update_metrics(self, path: str, response_time: float, success: bool):
        """
        Update metrics for the pool and endpoint.

        Args:
            path: API path
            response_time: Response time in seconds
            success: Whether the request was successful
        """
        with self._lock:
            self.request_count += 1
            self.total_response_time += response_time
            if not success:
                self.error_count += 1

            # Update endpoint stats
            if path not in self.endpoint_stats:
                self.endpoint_stats[path] = {
                    "count": 0,
                    "total_time": 0.0,
                    "errors": 0
                }

            endpoint_stat = self.endpoint_stats[path]
            endpoint_stat["count"] += 1
            endpoint_stat["total_time"] += response_time
            if not success:
                endpoint_stat["errors"] += 1

    def execute(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Execute a request using a connection from the pool.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            **kwargs: Additional arguments for the request

        Returns:
            The HTTP response

        Raises:
            ValueError: If an invalid method is specified
        """
        conn = self._get_connection()
        start_time = time.time()
        success = False

        try:
            if method.upper() == 'GET':
                response = conn.get(path, **kwargs)
            elif method.upper() == 'POST':
                response = conn.post(path, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            success = response.status_code < 400
            return response
        except Exception:
            success = False
            raise
        finally:
            response_time = time.time() - start_time
            self._update_metrics(path, response_time, success)
            self._release_connection(conn)

    def get(self, path: str, **kwargs) -> requests.Response:
        """
        Execute a GET request.

        Args:
            path: API path
            **kwargs: Additional arguments for the request

        Returns:
            The HTTP response
        """
        return self.execute('GET', path, **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        """
        Execute a POST request.

        Args:
            path: API path
            **kwargs: Additional arguments for the request

        Returns:
            The HTTP response
        """
        return self.execute('POST', path, **kwargs)

    def async_execute(self, method: str, path: str, callback: Callable[[requests.Response], Any] = None, **kwargs):
        """
        Execute a request asynchronously.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            callback: Function to call with the response
            **kwargs: Additional arguments for the request

        Returns:
            Future object with the response
        """
        def _execute_and_callback():
            try:
                response = self.execute(method, path, **kwargs)
                if callback:
                    callback(response)
                return response
            except Exception as e:
                logger.error(f"Error in async_execute for {method} {path}: {str(e)}")
                raise

        return self._executor.submit(_execute_and_callback)

    def batch_execute(self, requests_list: List[Dict[str, Any]]) -> List[Optional[requests.Response]]:
        """
        Execute multiple requests in parallel.

        Args:
            requests_list: List of request specifications, each a dict with 'method', 'path', and optionally 'kwargs'

        Returns:
            List of responses in the same order as the requests
        """
        futures = []
        for request in requests_list:
            method = request.get('method', 'GET')
            path = request.get('path')
            kwargs = request.get('kwargs', {})

            if not path:
                logger.warning("Skipping request with no path")
                continue

            futures.append(self.async_execute(method, path, **kwargs))

        # Wait for all futures to complete
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"Error in batch request: {str(e)}")
                results.append(None)

        return results

    def optimized_batch_execute(
        self,
        requests_list: List[Dict[str, Any]],
        max_concurrency: int = None,
        timeout: float = None,
        error_strategy: str = "continue"
    ) -> Dict[str, Any]:
        """
        Execute multiple requests with optimized concurrency control and improved error handling.

        This method enhances the basic batch_execute with better concurrency control,
        detailed metrics, and configurable error handling strategies.

        Args:
            requests_list: List of request specifications, each a dict with:
                - 'method': HTTP method (GET, POST, etc.)
                - 'path': API path
                - 'kwargs': Optional arguments for the request
                - 'id': Optional identifier for the request
            max_concurrency: Maximum number of concurrent requests (default: use pool max_connections)
            timeout: Timeout for the entire batch in seconds (default: None = no timeout)
            error_strategy: How to handle errors: 'continue', 'fail_fast', or 'collect'

        Returns:
            Dictionary with:
            - 'success': Overall success status
            - 'results': List of responses (or errors) in the same order as the requests
            - 'metrics': Performance metrics for the batch
            - 'errors': List of errors if error_strategy is 'collect'
        """
        # Set defaults
        if max_concurrency is None:
            max_concurrency = self.config.max_connections

        # Validate error strategy
        if error_strategy not in ["continue", "fail_fast", "collect"]:
            error_strategy = "continue"
            logger.warning(f"Invalid error_strategy '{error_strategy}', defaulting to 'continue'")

        # Track metrics
        start_time = time.time()
        results = []
        errors = []
        request_times = []

        # Create a smaller thread pool if requested concurrency is less than max connections
        executor = self._executor
        if max_concurrency < self.config.max_connections:
            executor = ThreadPoolExecutor(max_workers=max_concurrency)

        try:
            # Prepare futures with request metadata
            futures_with_meta = []
            for i, request in enumerate(requests_list):
                method = request.get('method', 'GET')
                path = request.get('path')
                kwargs = request.get('kwargs', {})
                request_id = request.get('id', i)

                if not path:
                    logger.warning(f"Skipping request with no path at index {i}")
                    results.append({
                        "success": False,
                        "error": "No path specified",
                        "id": request_id,
                        "index": i
                    })
                    continue

                # Create a future with metadata
                future = executor.submit(self.execute, method, path, **kwargs)
                futures_with_meta.append((future, i, request_id, path, method))

            # Wait for futures with timeout if specified
            remaining_futures = [f[0] for f in futures_with_meta]
            if timeout:
                done_futures, _ = concurrent.futures.wait(
                    remaining_futures,
                    timeout=timeout,
                    return_when=concurrent.futures.ALL_COMPLETED
                )
                # Handle timeout for remaining futures
                for future, idx, req_id, path, method in futures_with_meta:
                    if future not in done_futures:
                        future.cancel()
                        error_info = {
                            "success": False,
                            "error": "Request timed out",
                            "id": req_id,
                            "index": idx,
                            "path": path,
                            "method": method
                        }
                        results.append(error_info)
                        errors.append(error_info)

            # Process all completed futures
            for future, idx, req_id, path, method in futures_with_meta:
                # Skip futures that were already processed due to timeout
                if timeout and future not in remaining_futures:
                    continue

                req_start_time = time.time()
                try:
                    response = future.result()
                    req_time = time.time() - req_start_time
                    request_times.append(req_time)

                    # Format response data
                    result = {
                        "success": response.status_code < 400,
                        "status_code": response.status_code,
                        "id": req_id,
                        "index": idx,
                        "path": path,
                        "method": method,
                        "duration": req_time
                    }

                    # Include response data if successful
                    if result["success"]:
                        try:
                            result["data"] = response.json()
                        except ValueError:
                            result["data"] = response.text
                    else:
                        result["error"] = f"HTTP {response.status_code}: {response.text}"
                        errors.append(result)

                        # Handle fail fast strategy
                        if error_strategy == "fail_fast":
                            # Cancel remaining futures
                            for f, _, _, _, _ in futures_with_meta:
                                if not f.done():
                                    f.cancel()
                            # Break out of the loop
                            break

                    results.append(result)
                except Exception as e:
                    req_time = time.time() - req_start_time
                    request_times.append(req_time)

                    error_info = {
                        "success": False,
                        "error": str(e),
                        "id": req_id,
                        "index": idx,
                        "path": path,
                        "method": method,
                        "duration": req_time
                    }
                    results.append(error_info)
                    errors.append(error_info)

                    # Handle fail fast strategy
                    if error_strategy == "fail_fast":
                        # Cancel remaining futures
                        for f, _, _, _, _ in futures_with_meta:
                            if not f.done():
                                f.cancel()
                        # Break out of the loop
                        break

        finally:
            # Clean up the executor if we created a temporary one
            if executor != self._executor:
                executor.shutdown(wait=False)

        # Calculate metrics
        total_time = time.time() - start_time
        success_count = sum(1 for r in results if r.get("success", False))
        error_count = len(errors)

        metrics = {
            "total_time": total_time,
            "request_count": len(results),
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / len(results) if results else 0,
            "avg_request_time": sum(request_times) / len(request_times) if request_times else 0,
            "min_request_time": min(request_times) if request_times else 0,
            "max_request_time": max(request_times) if request_times else 0,
        }

        # Create the final response
        response = {
            "success": error_count == 0,
            "results": results,
            "metrics": metrics
        }

        # Include errors if using collect strategy
        if error_strategy == "collect" and errors:
            response["errors"] = errors

        return response

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the connection pool.

        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            active_connections = sum(1 for conn in self._connections if conn.in_use)
            healthy_connections = sum(1 for conn in self._connections if conn.is_healthy)

            avg_response_time = 0.0
            if self.request_count > 0:
                avg_response_time = self.total_response_time / self.request_count

            error_rate = 0.0
            if self.request_count > 0:
                error_rate = self.error_count / self.request_count

            # Calculate endpoint statistics
            endpoint_stats = {}
            for path, stats in self.endpoint_stats.items():
                count = stats["count"]
                if count > 0:
                    endpoint_stats[path] = {
                        "count": count,
                        "avg_time": stats["total_time"] / count,
                        "error_rate": stats["errors"] / count if count > 0 else 0.0
                    }

            # Sort endpoints by request count
            sorted_endpoints = sorted(
                endpoint_stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )

            return {
                "total_connections": len(self._connections),
                "active_connections": active_connections,
                "healthy_connections": healthy_connections,
                "request_count": self.request_count,
                "error_count": self.error_count,
                "error_rate": error_rate,
                "avg_response_time": avg_response_time,
                "top_endpoints": dict(sorted_endpoints[:10]) if sorted_endpoints else {},
                "connection_pool_size": self.config.max_connections
            }

    def shutdown(self):
        """Shut down the connection pool."""
        logger.info("Shutting down IPFS connection pool")
        self._shutdown = True

        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1.0)

        if self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=1.0)

        self._executor.shutdown(wait=True)

        with self._lock:
            for conn in self._connections:
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"Error closing connection {conn.id}: {str(e)}")

            self._connections.clear()

        logger.info("IPFS connection pool shutdown complete")


# Global connection pool instance
_default_pool = None

def get_connection_pool(config: IPFSConnectionConfig = None) -> IPFSConnectionPool:
    """
    Get or create the global connection pool.

    Args:
        config: Optional configuration to use if creating a new pool

    Returns:
        The global connection pool
    """
    global _default_pool

    if _default_pool is None:
        _default_pool = IPFSConnectionPool(config)

    return _default_pool

def shutdown_connection_pool():
    """Shut down the global connection pool."""
    global _default_pool

    if _default_pool is not None:
        _default_pool.shutdown()
        _default_pool = None
