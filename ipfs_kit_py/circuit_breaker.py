#!/usr/bin/env python3
"""
Circuit Breaker Pattern for Backend Adapters

Implements circuit breaker pattern to prevent cascading failures
and improve system resilience when backends are unhealthy.
"""

import time
import logging
import threading
from enum import Enum
from typing import Any, Callable, Optional, Dict
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """States of the circuit breaker."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests due to failures
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes to close from half-open
    timeout: float = 60.0  # Seconds to wait before half-open
    expected_exception: type = Exception
    failure_rate_threshold: float = 0.5  # 50% failure rate
    min_requests_for_rate: int = 10  # Minimum requests to calculate rate


class CircuitBreaker:
    """
    Circuit breaker for protecting backend operations.
    
    The circuit breaker monitors operation failures and opens the circuit
    when failure thresholds are exceeded, preventing further requests
    and allowing the backend to recover.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit broken, requests fail fast
    - HALF_OPEN: Testing recovery, limited requests pass through
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.
        
        Args:
            name: Name of the circuit (e.g., backend name)
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # State tracking
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None
        
        # Statistics
        self.total_requests = 0
        self.total_successes = 0
        self.total_failures = 0
        self.total_timeouts = 0
        self.total_circuit_opens = 0
        
        # Thread safety
        self._lock = threading.RLock()
        
        logger.info(
            f"Initialized circuit breaker '{name}' "
            f"(threshold={self.config.failure_threshold}, "
            f"timeout={self.config.timeout}s)"
        )
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by func
        """
        with self._lock:
            self.total_requests += 1
            
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    self.total_timeouts += 1
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN"
                    )
        
        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.config.expected_exception as e:
            self._on_failure()
            raise
            
        except Exception as e:
            # Unexpected exceptions don't count as failures
            logger.warning(
                f"Unexpected exception in circuit breaker '{self.name}': {e}"
            )
            raise
    
    def _on_success(self):
        """Handle successful operation."""
        with self._lock:
            self.total_successes += 1
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                
                if self.success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = max(0, self.failure_count - 1)
    
    def _on_failure(self):
        """Handle failed operation."""
        with self._lock:
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Single failure in half-open state reopens circuit
                self._transition_to_open()
                
            elif self.state == CircuitState.CLOSED:
                # Check if we should open the circuit
                if self._should_open_circuit():
                    self._transition_to_open()
    
    def _should_open_circuit(self) -> bool:
        """Determine if circuit should be opened."""
        # Check absolute failure count
        if self.failure_count >= self.config.failure_threshold:
            return True
        
        # Check failure rate if we have enough requests
        if self.total_requests >= self.config.min_requests_for_rate:
            failure_rate = self.total_failures / self.total_requests
            if failure_rate >= self.config.failure_rate_threshold:
                return True
        
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Determine if we should attempt to reset the circuit."""
        if self.opened_at is None:
            return False
        
        return (time.time() - self.opened_at) >= self.config.timeout
    
    def _transition_to_open(self):
        """Transition circuit to OPEN state."""
        if self.state != CircuitState.OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = time.time()
            self.total_circuit_opens += 1
            
            logger.warning(
                f"Circuit breaker '{self.name}' opened "
                f"(failures={self.failure_count})"
            )
    
    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.failure_count = 0
        
        logger.info(f"Circuit breaker '{self.name}' half-opened (testing recovery)")
    
    def _transition_to_closed(self):
        """Transition circuit to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.success_count = 0
        self.failure_count = 0
        self.opened_at = None
        
        logger.info(f"Circuit breaker '{self.name}' closed (recovered)")
    
    def force_open(self):
        """Manually force circuit to OPEN state."""
        with self._lock:
            self._transition_to_open()
            logger.warning(f"Circuit breaker '{self.name}' manually opened")
    
    def force_closed(self):
        """Manually force circuit to CLOSED state."""
        with self._lock:
            self._transition_to_closed()
            logger.info(f"Circuit breaker '{self.name}' manually closed")
    
    def reset(self):
        """Reset circuit breaker statistics."""
        with self._lock:
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.opened_at = None
            
            if self.state == CircuitState.OPEN:
                self._transition_to_closed()
            
            logger.info(f"Circuit breaker '{self.name}' reset")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'total_requests': self.total_requests,
                'total_successes': self.total_successes,
                'total_failures': self.total_failures,
                'total_timeouts': self.total_timeouts,
                'total_circuit_opens': self.total_circuit_opens,
                'success_rate': (
                    self.total_successes / self.total_requests 
                    if self.total_requests > 0 else 0
                ),
                'failure_rate': (
                    self.total_failures / self.total_requests 
                    if self.total_requests > 0 else 0
                ),
                'last_failure_time': self.last_failure_time,
                'opened_at': self.opened_at,
            }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass


def circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None):
    """
    Decorator for applying circuit breaker to functions.
    
    Args:
        name: Name of the circuit breaker
        config: Circuit breaker configuration
        
    Example:
        @circuit_breaker("ipfs_backend")
        async def fetch_from_ipfs(cid):
            # ... implementation
            pass
    """
    breaker = CircuitBreaker(name, config)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        
        # Attach breaker instance to wrapper for inspection
        wrapper.circuit_breaker = breaker
        
        return wrapper
    
    return decorator


class CircuitBreakerManager:
    """
    Manages multiple circuit breakers for different backends.
    """
    
    def __init__(self):
        """Initialize circuit breaker manager."""
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def get_or_create(
        self, 
        name: str, 
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.
        
        Args:
            name: Circuit breaker name
            config: Configuration for new circuit breakers
            
        Returns:
            Circuit breaker instance
        """
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config)
                logger.info(f"Created circuit breaker: {name}")
            
            return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get existing circuit breaker."""
        with self._lock:
            return self._breakers.get(name)
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get states of all circuit breakers."""
        with self._lock:
            return {
                name: breaker.get_state()
                for name, breaker in self._breakers.items()
            }
    
    def reset_all(self):
        """Reset all circuit breakers."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
            logger.info("Reset all circuit breakers")


# Global circuit breaker manager
_global_cb_manager: Optional[CircuitBreakerManager] = None
_global_cb_lock = threading.Lock()


def get_global_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager instance."""
    global _global_cb_manager
    
    with _global_cb_lock:
        if _global_cb_manager is None:
            _global_cb_manager = CircuitBreakerManager()
        return _global_cb_manager
