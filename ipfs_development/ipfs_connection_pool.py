"""IPFS Connection Pool

This module provides connection pooling for IPFS API calls.
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable, Union
import threading

logger = logging.getLogger(__name__)


@dataclass
class IPFSConnectionConfig:
    """Configuration for an IPFS connection."""
    
    host: str = "127.0.0.1"
    port: int = 5001
    base_url: str = ""
    timeout: int = 120
    headers: Optional[Dict[str, str]] = None
    username: Optional[str] = None
    password: Optional[str] = None


class IPFSConnection:
    """Represents a single connection to an IPFS node."""
    
    def __init__(self, config: IPFSConnectionConfig):
        """Initialize with a connection configuration."""
        self.config = config
        self.ipfs = None
        self.last_used = 0
        self.in_use = False
        self.error_count = 0
        self.initialize()
    
    def initialize(self) -> None:
        """Initialize the connection to the IPFS node."""
        try:
            import ipfshttpclient
            
            # Construct the API URL
            if self.config.base_url:
                base_url = self.config.base_url
            else:
                protocol = "http"
                base_url = f"{protocol}://{self.config.host}:{self.config.port}"
            
            # Set up authentication if provided
            auth = None
            if self.config.username and self.config.password:
                auth = (self.config.username, self.config.password)
            
            # Create the IPFS client
            self.ipfs = ipfshttpclient.connect(
                base_url,
                timeout=self.config.timeout,
                headers=self.config.headers,
                auth=auth
            )
            
            logger.info(f"Initialized IPFS connection to {base_url}")
            
        except ImportError:
            logger.warning("ipfshttpclient not available. Using mock implementation.")
            self.ipfs = self._create_mock_ipfs()
        
        except Exception as e:
            logger.error(f"Error initializing IPFS connection: {str(e)}")
            self.ipfs = self._create_mock_ipfs()
            self.error_count += 1
    
    def _create_mock_ipfs(self) -> Any:
        """Create a mock IPFS client for testing or fallback."""
        class MockIPFS:
            def __getattr__(self, name):
                def mock_method(*args, **kwargs):
                    logger.warning(f"Mock IPFS method called: {name}({args}, {kwargs})")
                    if name == "add":
                        return {"Hash": "QmMockHash", "Name": "mock_file"}
                    elif name == "cat":
                        return b"Mock content"
                    elif name == "get":
                        return b"Mock content"
                    elif name == "ls":
                        return {"Objects": [{"Hash": "QmMockHash", "Links": []}]}
                    elif name == "pin":
                        return {"Pins": ["QmMockHash"]}
                    return {}
                return mock_method
        
        return MockIPFS()
    
    def check_health(self) -> bool:
        """Check if the connection is healthy."""
        try:
            # Try to get node ID as a basic health check
            self.ipfs.id()
            return True
        except Exception as e:
            logger.warning(f"Connection health check failed: {str(e)}")
            self.error_count += 1
            return False
    
    def reset(self) -> None:
        """Reset the connection status."""
        self.in_use = False
        self.last_used = time.time()


class IPFSConnectionPool:
    """Pool of connections to IPFS nodes."""
    
    def __init__(
        self,
        config: IPFSConnectionConfig,
        max_connections: int = 5,
        ttl: int = 300,
        health_check_interval: int = 60
    ):
        """Initialize the connection pool."""
        self.config = config
        self.max_connections = max_connections
        self.ttl = ttl  # Time-to-live for idle connections in seconds
        self.health_check_interval = health_check_interval
        
        self.connections: List[IPFSConnection] = []
        self.lock = threading.RLock()
        self.last_health_check = 0
        
        # Initialize with a single connection
        self._add_connection()
        
        logger.info(f"Initialized IPFS connection pool with max={max_connections}, ttl={ttl}s")
    
    def _add_connection(self) -> IPFSConnection:
        """Add a new connection to the pool."""
        with self.lock:
            connection = IPFSConnection(self.config)
            self.connections.append(connection)
            return connection
    
    def get_connection(self) -> IPFSConnection:
        """Get an available connection from the pool."""
        with self.lock:
            # Run health check if needed
            self._run_health_check()
            
            # Look for an available connection
            for conn in self.connections:
                if not conn.in_use:
                    conn.in_use = True
                    conn.last_used = time.time()
                    return conn
            
            # No available connections, create a new one if possible
            if len(self.connections) < self.max_connections:
                conn = self._add_connection()
                conn.in_use = True
                conn.last_used = time.time()
                return conn
            
            # All connections are in use and at max capacity
            # Find the least recently used connection and reset it
            least_recent = min(self.connections, key=lambda c: c.last_used)
            least_recent.in_use = True
            least_recent.last_used = time.time()
            return least_recent
    
    def release_connection(self, connection: IPFSConnection) -> None:
        """Release a connection back to the pool."""
        with self.lock:
            if connection in self.connections:
                connection.reset()
    
    def _run_health_check(self) -> None:
        """Run a health check on all connections."""
        current_time = time.time()
        
        # Only run health check at specified intervals
        if current_time - self.last_health_check < self.health_check_interval:
            return
        
        self.last_health_check = current_time
        
        # Check each connection
        for i, conn in enumerate(self.connections):
            # Skip connections in use
            if conn.in_use:
                continue
            
            # Remove stale connections
            if current_time - conn.last_used > self.ttl:
                self.connections.pop(i)
                logger.info(f"Removed stale connection {i} from pool")
                continue
            
            # Check health of idle connections
            if not conn.check_health():
                # If health check fails, reinitialize
                conn.initialize()
    
    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self.lock:
            for conn in self.connections:
                conn.ipfs = None
            self.connections = []
            logger.info("Closed all connections in the pool")


# Global connection pool instance
_connection_pool = None
_pool_lock = threading.RLock()


def get_connection_pool(
    config: Optional[IPFSConnectionConfig] = None,
    max_connections: int = 5,
    ttl: int = 300,
    health_check_interval: int = 60
) -> IPFSConnectionPool:
    """Get or create the global connection pool."""
    global _connection_pool
    
    with _pool_lock:
        if _connection_pool is None:
            if config is None:
                config = IPFSConnectionConfig()
            _connection_pool = IPFSConnectionPool(
                config=config,
                max_connections=max_connections,
                ttl=ttl,
                health_check_interval=health_check_interval
            )
        
        return _connection_pool