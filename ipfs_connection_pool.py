"""
IPFS Connection Pool Module.

This module provides a connection pooling mechanism for IPFS clients to improve
performance by reusing connections rather than creating new ones for each request.
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

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
        return self.session.get(url, timeout=self.config.connection_timeout, **kwargs)
    
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
        return self.session.post(url, timeout=self.config.connection_timeout, **kwargs)
    
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
        self._shutdown = False
        self._cleanup_thread.start()
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
    
    def _get_connection(self) -> IPFSConnection:
        """
        Get an available connection from the pool or create a new one.
        
        Returns:
            An IPFS connection.
        """
        with self._lock:
            # Try to find an available connection
            for conn in self._connections:
                if not conn.in_use:
                    conn.in_use = True
                    return conn
            
            # If we don't have max connections yet, create a new one
            if len(self._connections) < self.config.max_connections:
                conn = IPFSConnection(self.config)
                conn.in_use = True
                self._connections.append(conn)
                logger.debug(f"Created new connection {conn.id}, total: {len(self._connections)}")
                return conn
            
            # Otherwise, wait for an existing connection to become available
            while True:
                for conn in self._connections:
                    if not conn.in_use:
                        conn.in_use = True
                        return conn
                
                # If we're here, all connections are in use
                # Release the lock temporarily to allow other threads to release connections
                self._lock.release()
                time.sleep(0.1)
                self._lock.acquire()
    
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
        try:
            if method.upper() == 'GET':
                return conn.get(path, **kwargs)
            elif method.upper() == 'POST':
                return conn.post(path, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        finally:
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
    
    def async_execute(self, method: str, path: str, callback: Callable[[requests.Response], Any] = None, **kwargs) -> None:
        """
        Execute a request asynchronously.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            callback: Function to call with the response
            **kwargs: Additional arguments for the request
        """
        def _execute_and_callback():
            response = self.execute(method, path, **kwargs)
            if callback:
                callback(response)
            return response
        
        return self._executor.submit(_execute_and_callback)
    
    def shutdown(self):
        """Shut down the connection pool."""
        logger.info("Shutting down IPFS connection pool")
        self._shutdown = True
        
        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=1.0)
        
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