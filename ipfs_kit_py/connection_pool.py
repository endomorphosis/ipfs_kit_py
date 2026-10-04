#!/usr/bin/env python3
"""
Connection Pool Manager for Backend Adapters

Provides connection pooling to improve performance and reduce overhead
for backend operations by reusing connections.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class PooledConnection(Generic[T]):
    """Represents a pooled connection with metadata."""
    connection: T
    created_at: float
    last_used: float
    use_count: int = 0
    is_healthy: bool = True


class ConnectionPool(Generic[T]):
    """
    Generic connection pool for backend adapters.
    
    Features:
    - Configurable min/max pool size
    - Connection health checking
    - Automatic connection recycling
    - Thread-safe operations
    - Connection timeout handling
    """
    
    def __init__(
        self,
        connection_factory: Callable[[], T],
        health_check: Optional[Callable[[T], bool]] = None,
        min_size: int = 2,
        max_size: int = 10,
        max_idle_time: int = 300,  # 5 minutes
        max_connection_lifetime: int = 3600,  # 1 hour
        health_check_interval: int = 60,  # 1 minute
    ):
        """
        Initialize connection pool.
        
        Args:
            connection_factory: Callable that creates a new connection
            health_check: Optional callable to check connection health
            min_size: Minimum number of connections to maintain
            max_size: Maximum number of connections allowed
            max_idle_time: Maximum idle time before connection is closed (seconds)
            max_connection_lifetime: Maximum lifetime for a connection (seconds)
            health_check_interval: How often to check connection health (seconds)
        """
        self.connection_factory = connection_factory
        self.health_check = health_check
        self.min_size = min_size
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.max_connection_lifetime = max_connection_lifetime
        self.health_check_interval = health_check_interval
        
        # Connection storage
        self._available: deque[PooledConnection[T]] = deque()
        self._in_use: Dict[int, PooledConnection[T]] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        
        # Statistics
        self._stats = {
            'total_created': 0,
            'total_recycled': 0,
            'total_health_check_failures': 0,
            'total_timeouts': 0,
            'peak_size': 0,
        }
        
        # Initialize minimum connections
        self._initialize_pool()
        
        # Start maintenance thread
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True
        )
        self._maintenance_thread.start()
        
        logger.info(
            f"Initialized connection pool: min={min_size}, max={max_size}"
        )
    
    def _initialize_pool(self):
        """Create initial connections up to min_size."""
        with self._lock:
            for _ in range(self.min_size):
                try:
                    conn = self._create_connection()
                    self._available.append(conn)
                except Exception as e:
                    logger.error(f"Failed to create initial connection: {e}")
    
    def _create_connection(self) -> PooledConnection[T]:
        """Create a new pooled connection."""
        now = time.time()
        connection = self.connection_factory()
        
        self._stats['total_created'] += 1
        
        return PooledConnection(
            connection=connection,
            created_at=now,
            last_used=now,
        )
    
    def acquire(self, timeout: float = 30.0) -> Optional[T]:
        """
        Acquire a connection from the pool.
        
        Args:
            timeout: Maximum time to wait for a connection (seconds)
            
        Returns:
            Connection object or None if timeout
        """
        deadline = time.time() + timeout
        
        with self._condition:
            while True:
                # Try to get an available connection
                if self._available:
                    pooled = self._available.popleft()
                    
                    # Check if connection is still healthy
                    if self._is_connection_valid(pooled):
                        pooled.last_used = time.time()
                        pooled.use_count += 1
                        self._in_use[id(pooled.connection)] = pooled
                        
                        logger.debug(
                            f"Acquired connection from pool "
                            f"(use_count={pooled.use_count})"
                        )
                        return pooled.connection
                    else:
                        # Connection is invalid, discard it
                        logger.debug("Discarding invalid connection")
                        continue
                
                # No available connections, try to create new one
                current_size = len(self._available) + len(self._in_use)
                if current_size < self.max_size:
                    try:
                        pooled = self._create_connection()
                        pooled.use_count = 1
                        self._in_use[id(pooled.connection)] = pooled
                        
                        # Update peak size
                        if current_size + 1 > self._stats['peak_size']:
                            self._stats['peak_size'] = current_size + 1
                        
                        logger.debug("Created new connection for pool")
                        return pooled.connection
                    except Exception as e:
                        logger.error(f"Failed to create connection: {e}")
                
                # Wait for a connection to become available
                remaining = deadline - time.time()
                if remaining <= 0:
                    self._stats['total_timeouts'] += 1
                    logger.warning("Connection pool timeout")
                    return None
                
                self._condition.wait(timeout=min(remaining, 1.0))
    
    def release(self, connection: T):
        """
        Release a connection back to the pool.
        
        Args:
            connection: Connection to release
        """
        with self._condition:
            conn_id = id(connection)
            
            if conn_id not in self._in_use:
                logger.warning("Attempted to release unknown connection")
                return
            
            pooled = self._in_use.pop(conn_id)
            pooled.last_used = time.time()
            
            # Check if connection should be recycled
            if self._should_recycle(pooled):
                logger.debug("Recycling connection due to age/lifetime")
                self._stats['total_recycled'] += 1
                
                # Create new connection if below min_size
                current_size = len(self._available) + len(self._in_use)
                if current_size < self.min_size:
                    try:
                        new_pooled = self._create_connection()
                        self._available.append(new_pooled)
                    except Exception as e:
                        logger.error(f"Failed to create replacement connection: {e}")
            else:
                # Return to available pool
                self._available.append(pooled)
                logger.debug("Released connection back to pool")
            
            # Notify waiting threads
            self._condition.notify()
    
    def _is_connection_valid(self, pooled: PooledConnection[T]) -> bool:
        """Check if a connection is still valid."""
        now = time.time()
        
        # Check lifetime
        if now - pooled.created_at > self.max_connection_lifetime:
            return False
        
        # Check idle time
        if now - pooled.last_used > self.max_idle_time:
            return False
        
        # Run health check if provided
        if self.health_check:
            try:
                if not self.health_check(pooled.connection):
                    self._stats['total_health_check_failures'] += 1
                    return False
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                self._stats['total_health_check_failures'] += 1
                return False
        
        return True
    
    def _should_recycle(self, pooled: PooledConnection[T]) -> bool:
        """Determine if a connection should be recycled."""
        now = time.time()
        
        # Recycle if near end of lifetime
        if now - pooled.created_at > self.max_connection_lifetime * 0.9:
            return True
        
        # Recycle if heavily used
        if pooled.use_count > 1000:
            return True
        
        return False
    
    def _maintenance_loop(self):
        """Background thread for pool maintenance."""
        while True:
            try:
                time.sleep(self.health_check_interval)
                self._perform_maintenance()
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
    
    def _perform_maintenance(self):
        """Perform periodic maintenance on the pool."""
        with self._lock:
            # Remove stale connections from available pool
            valid_connections = deque()
            
            for pooled in self._available:
                if self._is_connection_valid(pooled):
                    valid_connections.append(pooled)
                else:
                    logger.debug("Removing stale connection during maintenance")
            
            self._available = valid_connections
            
            # Ensure minimum pool size
            current_size = len(self._available) + len(self._in_use)
            while current_size < self.min_size:
                try:
                    pooled = self._create_connection()
                    self._available.append(pooled)
                    current_size += 1
                except Exception as e:
                    logger.error(f"Failed to create connection during maintenance: {e}")
                    break
            
            logger.debug(
                f"Pool maintenance: available={len(self._available)}, "
                f"in_use={len(self._in_use)}"
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                'available': len(self._available),
                'in_use': len(self._in_use),
                'total_size': len(self._available) + len(self._in_use),
                'min_size': self.min_size,
                'max_size': self.max_size,
                **self._stats
            }
    
    def close(self):
        """Close all connections and shutdown the pool."""
        with self._lock:
            # Move all connections to available
            self._available.extend(self._in_use.values())
            self._in_use.clear()
            
            # Clear available connections
            self._available.clear()
            
            logger.info("Connection pool closed")


class ConnectionPoolManager:
    """
    Manages multiple connection pools for different backends.
    """
    
    def __init__(self):
        """Initialize the connection pool manager."""
        self._pools: Dict[str, ConnectionPool] = {}
        self._lock = threading.RLock()
        
    def get_or_create_pool(
        self,
        backend_name: str,
        connection_factory: Callable[[], T],
        **pool_kwargs
    ) -> ConnectionPool[T]:
        """
        Get or create a connection pool for a backend.
        
        Args:
            backend_name: Name of the backend
            connection_factory: Callable to create connections
            **pool_kwargs: Additional arguments for ConnectionPool
            
        Returns:
            Connection pool for the backend
        """
        with self._lock:
            if backend_name not in self._pools:
                self._pools[backend_name] = ConnectionPool(
                    connection_factory=connection_factory,
                    **pool_kwargs
                )
                logger.info(f"Created connection pool for backend: {backend_name}")
            
            return self._pools[backend_name]
    
    def get_pool(self, backend_name: str) -> Optional[ConnectionPool]:
        """Get existing pool for a backend."""
        with self._lock:
            return self._pools.get(backend_name)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all pools."""
        with self._lock:
            return {
                name: pool.get_stats()
                for name, pool in self._pools.items()
            }
    
    def close_all(self):
        """Close all connection pools."""
        with self._lock:
            for pool in self._pools.values():
                pool.close()
            self._pools.clear()
            logger.info("All connection pools closed")


# Global connection pool manager instance
_global_pool_manager: Optional[ConnectionPoolManager] = None
_global_pool_lock = threading.Lock()


def get_global_pool_manager() -> ConnectionPoolManager:
    """Get the global connection pool manager instance."""
    global _global_pool_manager
    
    with _global_pool_lock:
        if _global_pool_manager is None:
            _global_pool_manager = ConnectionPoolManager()
        return _global_pool_manager
