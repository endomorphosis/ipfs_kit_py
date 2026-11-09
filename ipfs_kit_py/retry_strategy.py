#!/usr/bin/env python3
"""
Advanced Retry Strategies for Backend Operations

Implements sophisticated retry mechanisms with:
- Exponential backoff with jitter
- Configurable retry policies
- Operation-specific retry logic
- Circuit breaker integration
"""

import time
import random
import logging
from typing import Callable, Optional, Any, Type, Tuple
from functools import wraps
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Types of backoff strategies."""
    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL_JITTER
    backoff_multiplier: float = 2.0
    jitter_range: float = 0.3  # 30% jitter
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable[[int, Exception], None]] = None


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""
    pass


class RetryStrategy:
    """
    Advanced retry strategy with multiple backoff algorithms.
    
    Features:
    - Multiple backoff strategies
    - Jitter to prevent thundering herd
    - Configurable retry policies
    - Retry callbacks for monitoring
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry strategy.
        
        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()
        
        logger.info(
            f"Initialized retry strategy: "
            f"{self.config.backoff_strategy.value}, "
            f"max_attempts={self.config.max_attempts}"
        )
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from successful execution
            
        Raises:
            RetryExhaustedError: If all retry attempts fail
        """
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(
                        f"Operation succeeded on attempt {attempt}"
                    )
                
                return result
                
            except self.config.retryable_exceptions as e:
                last_exception = e
                
                logger.warning(
                    f"Attempt {attempt}/{self.config.max_attempts} failed: {e}"
                )
                
                # Call retry callback if provided
                if self.config.on_retry:
                    try:
                        self.config.on_retry(attempt, e)
                    except Exception as callback_error:
                        logger.error(f"Error in retry callback: {callback_error}")
                
                # Don't sleep after last attempt
                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.debug(f"Waiting {delay:.2f}s before retry")
                    time.sleep(delay)
            
            except Exception as e:
                # Non-retryable exception
                logger.error(f"Non-retryable exception: {e}")
                raise
        
        # All attempts exhausted
        raise RetryExhaustedError(
            f"Failed after {self.config.max_attempts} attempts. "
            f"Last error: {last_exception}"
        )
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry attempt.
        
        Args:
            attempt: Current attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        if self.config.backoff_strategy == BackoffStrategy.FIXED:
            delay = self.config.initial_delay
            
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.initial_delay * attempt
            
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL:
            delay = self.config.initial_delay * (
                self.config.backoff_multiplier ** (attempt - 1)
            )
            
        elif self.config.backoff_strategy == BackoffStrategy.EXPONENTIAL_JITTER:
            # Exponential backoff with jitter
            base_delay = self.config.initial_delay * (
                self.config.backoff_multiplier ** (attempt - 1)
            )
            
            # Add random jitter
            jitter = base_delay * self.config.jitter_range
            delay = base_delay + random.uniform(-jitter, jitter)
        
        else:
            delay = self.config.initial_delay
        
        # Cap at max delay
        return min(delay, self.config.max_delay)


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic to functions.
    
    Args:
        config: Retry configuration
        
    Example:
        @with_retry(RetryConfig(max_attempts=5))
        def fetch_data():
            # ... implementation
            pass
    """
    strategy = RetryStrategy(config)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return strategy.execute(func, *args, **kwargs)
        
        # Attach strategy instance for inspection
        wrapper.retry_strategy = strategy
        
        return wrapper
    
    return decorator


class AdaptiveRetryStrategy(RetryStrategy):
    """
    Adaptive retry strategy that adjusts based on success/failure patterns.
    
    Features:
    - Learns from success/failure patterns
    - Adjusts retry count based on recent performance
    - Reduces retries when backend is stable
    - Increases retries during instability
    """
    
    def __init__(
        self, 
        config: Optional[RetryConfig] = None,
        learning_window: int = 100
    ):
        """
        Initialize adaptive retry strategy.
        
        Args:
            config: Base retry configuration
            learning_window: Number of recent operations to consider
        """
        super().__init__(config)
        
        self.learning_window = learning_window
        self.recent_results = []  # True for success, False for failure
        self.total_operations = 0
        self.successful_operations = 0
        
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with adaptive retry logic."""
        # Adjust max attempts based on recent performance
        original_max_attempts = self.config.max_attempts
        self._adjust_retry_count()
        
        try:
            result = super().execute(func, *args, **kwargs)
            self._record_result(success=True)
            return result
            
        except RetryExhaustedError:
            self._record_result(success=False)
            raise
            
        finally:
            # Restore original config
            self.config.max_attempts = original_max_attempts
    
    def _adjust_retry_count(self):
        """Adjust retry count based on recent performance."""
        if len(self.recent_results) < 10:
            # Not enough data, use default
            return
        
        # Calculate recent success rate
        recent_window = self.recent_results[-self.learning_window:]
        success_rate = sum(recent_window) / len(recent_window)
        
        # Adjust retry count
        if success_rate > 0.9:
            # High success rate, reduce retries
            self.config.max_attempts = max(2, self.config.max_attempts - 1)
            logger.debug(f"Reduced retry attempts to {self.config.max_attempts}")
            
        elif success_rate < 0.5:
            # Low success rate, increase retries
            self.config.max_attempts = min(10, self.config.max_attempts + 2)
            logger.debug(f"Increased retry attempts to {self.config.max_attempts}")
    
    def _record_result(self, success: bool):
        """Record operation result."""
        self.total_operations += 1
        if success:
            self.successful_operations += 1
        
        self.recent_results.append(success)
        
        # Keep only learning window size
        if len(self.recent_results) > self.learning_window:
            self.recent_results = self.recent_results[-self.learning_window:]
    
    def get_statistics(self) -> dict:
        """Get adaptive strategy statistics."""
        if self.total_operations == 0:
            success_rate = 0.0
        else:
            success_rate = self.successful_operations / self.total_operations
        
        recent_window = self.recent_results[-self.learning_window:]
        recent_success_rate = (
            sum(recent_window) / len(recent_window) 
            if recent_window else 0.0
        )
        
        return {
            'total_operations': self.total_operations,
            'successful_operations': self.successful_operations,
            'overall_success_rate': success_rate,
            'recent_success_rate': recent_success_rate,
            'current_max_attempts': self.config.max_attempts,
        }


class OperationSpecificRetryPolicy:
    """
    Retry policy that varies based on operation type.
    
    Different operations may require different retry strategies.
    For example:
    - Read operations: Aggressive retry with short delays
    - Write operations: Conservative retry with longer delays
    - Pin operations: Very aggressive retry with long timeout
    """
    
    def __init__(self):
        """Initialize operation-specific policies."""
        self.policies = {
            'read': RetryConfig(
                max_attempts=5,
                initial_delay=0.5,
                max_delay=10.0,
                backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
            ),
            'write': RetryConfig(
                max_attempts=3,
                initial_delay=2.0,
                max_delay=30.0,
                backoff_strategy=BackoffStrategy.EXPONENTIAL,
            ),
            'pin': RetryConfig(
                max_attempts=10,
                initial_delay=5.0,
                max_delay=120.0,
                backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
            ),
            'delete': RetryConfig(
                max_attempts=3,
                initial_delay=1.0,
                max_delay=15.0,
                backoff_strategy=BackoffStrategy.LINEAR,
            ),
            'list': RetryConfig(
                max_attempts=3,
                initial_delay=1.0,
                max_delay=20.0,
                backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
            ),
        }
    
    def get_strategy(self, operation_type: str) -> RetryStrategy:
        """
        Get retry strategy for operation type.
        
        Args:
            operation_type: Type of operation (read, write, pin, etc.)
            
        Returns:
            Retry strategy for the operation
        """
        config = self.policies.get(
            operation_type, 
            RetryConfig()  # Default config
        )
        
        return RetryStrategy(config)
    
    def execute_with_policy(
        self, 
        operation_type: str, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute operation with appropriate retry policy.
        
        Args:
            operation_type: Type of operation
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Result from function
        """
        strategy = self.get_strategy(operation_type)
        return strategy.execute(func, *args, **kwargs)


# Global operation-specific policy instance
_global_retry_policy: Optional[OperationSpecificRetryPolicy] = None


def get_retry_policy() -> OperationSpecificRetryPolicy:
    """Get global operation-specific retry policy."""
    global _global_retry_policy
    
    if _global_retry_policy is None:
        _global_retry_policy = OperationSpecificRetryPolicy()
    
    return _global_retry_policy
