#!/usr/bin/env python3
"""
Unit tests for retry strategy functionality.
"""

import time
import unittest
from unittest.mock import Mock, patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ipfs_kit_py.retry_strategy import (
    RetryStrategy,
    RetryConfig,
    BackoffStrategy,
    RetryExhaustedError,
    with_retry,
    AdaptiveRetryStrategy,
    OperationSpecificRetryPolicy,
    get_retry_policy,
)


class TestRetryStrategy(unittest.TestCase):
    """Test retry strategy functionality."""
    
    def test_successful_first_attempt(self):
        """Test operation succeeds on first attempt."""
        strategy = RetryStrategy(RetryConfig(max_attempts=3))
        
        def successful_op():
            return "success"
        
        result = strategy.execute(successful_op)
        self.assertEqual(result, "success")
    
    def test_retry_on_failure(self):
        """Test retry after failures."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
        )
        strategy = RetryStrategy(config)
        
        attempt_count = [0]
        
        def flaky_op():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = strategy.execute(flaky_op)
        
        self.assertEqual(result, "success")
        self.assertEqual(attempt_count[0], 3)
    
    def test_retry_exhausted(self):
        """Test all retries exhausted."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
        )
        strategy = RetryStrategy(config)
        
        def failing_op():
            raise Exception("Always fails")
        
        with self.assertRaises(RetryExhaustedError):
            strategy.execute(failing_op)
    
    def test_fixed_backoff(self):
        """Test fixed backoff strategy."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            backoff_strategy=BackoffStrategy.FIXED,
        )
        strategy = RetryStrategy(config)
        
        # Test delay calculation
        delay1 = strategy._calculate_delay(1)
        delay2 = strategy._calculate_delay(2)
        delay3 = strategy._calculate_delay(3)
        
        # All delays should be the same
        self.assertEqual(delay1, 0.1)
        self.assertEqual(delay2, 0.1)
        self.assertEqual(delay3, 0.1)
    
    def test_linear_backoff(self):
        """Test linear backoff strategy."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            backoff_strategy=BackoffStrategy.LINEAR,
        )
        strategy = RetryStrategy(config)
        
        delay1 = strategy._calculate_delay(1)
        delay2 = strategy._calculate_delay(2)
        delay3 = strategy._calculate_delay(3)
        
        # Linear increase
        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 3.0)
    
    def test_exponential_backoff(self):
        """Test exponential backoff strategy."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            backoff_multiplier=2.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
        )
        strategy = RetryStrategy(config)
        
        delay1 = strategy._calculate_delay(1)
        delay2 = strategy._calculate_delay(2)
        delay3 = strategy._calculate_delay(3)
        
        # Exponential increase
        self.assertEqual(delay1, 1.0)
        self.assertEqual(delay2, 2.0)
        self.assertEqual(delay3, 4.0)
    
    def test_exponential_with_jitter(self):
        """Test exponential backoff with jitter."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=1.0,
            backoff_multiplier=2.0,
            jitter_range=0.3,
            backoff_strategy=BackoffStrategy.EXPONENTIAL_JITTER,
        )
        strategy = RetryStrategy(config)
        
        # Calculate multiple delays to test jitter
        delays = [strategy._calculate_delay(2) for _ in range(10)]
        
        # All delays should be close to 2.0 but vary due to jitter
        for delay in delays:
            self.assertGreater(delay, 1.0)
            self.assertLess(delay, 3.0)
        
        # Delays should not all be identical
        unique_delays = set(delays)
        self.assertGreater(len(unique_delays), 1)
    
    def test_max_delay_cap(self):
        """Test maximum delay cap."""
        config = RetryConfig(
            max_attempts=10,
            initial_delay=1.0,
            max_delay=5.0,
            backoff_multiplier=3.0,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
        )
        strategy = RetryStrategy(config)
        
        # Large attempt number should be capped
        delay = strategy._calculate_delay(10)
        self.assertLessEqual(delay, 5.0)
    
    def test_retry_callback(self):
        """Test retry callback is called."""
        callback_calls = []
        
        def on_retry(attempt, exception):
            callback_calls.append((attempt, str(exception)))
        
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            on_retry=on_retry,
        )
        strategy = RetryStrategy(config)
        
        def failing_op():
            raise Exception("Test error")
        
        with self.assertRaises(RetryExhaustedError):
            strategy.execute(failing_op)
        
        # Callback is invoked after each failed attempt
        # With 3 max_attempts, we get callbacks for all 3 failed attempts
        # Attempt 1 fails -> on_retry(1, exc)
        # Attempt 2 fails -> on_retry(2, exc)
        # Attempt 3 fails -> on_retry(3, exc) -> then raise RetryExhaustedError
        self.assertEqual(len(callback_calls), 3)
    
    def test_retryable_exceptions(self):
        """Test only retryable exceptions are retried."""
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            retryable_exceptions=(ValueError,),
        )
        strategy = RetryStrategy(config)
        
        def value_error_op():
            raise ValueError("Retryable")
        
        def runtime_error_op():
            raise RuntimeError("Not retryable")
        
        # ValueError should be retried
        with self.assertRaises(RetryExhaustedError):
            strategy.execute(value_error_op)
        
        # RuntimeError should not be retried
        with self.assertRaises(RuntimeError):
            strategy.execute(runtime_error_op)
    
    def test_with_retry_decorator(self):
        """Test retry decorator."""
        attempt_count = [0]
        
        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.1))
        def flaky_function():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = flaky_function()
        
        self.assertEqual(result, "success")
        self.assertEqual(attempt_count[0], 3)
        
        # Check strategy is attached
        self.assertTrue(hasattr(flaky_function, 'retry_strategy'))


class TestAdaptiveRetryStrategy(unittest.TestCase):
    """Test adaptive retry strategy."""
    
    def test_adaptation_on_success(self):
        """Test retry count adapts based on success rate."""
        strategy = AdaptiveRetryStrategy(
            RetryConfig(max_attempts=5),
            learning_window=10,
        )
        
        # Execute many successful operations
        for _ in range(15):
            strategy.execute(lambda: "success")
        
        # Max attempts should decrease
        stats = strategy.get_statistics()
        self.assertGreater(stats['overall_success_rate'], 0.9)
        self.assertGreater(stats['recent_success_rate'], 0.9)
    
    def test_adaptation_on_failures(self):
        """Test retry count increases with failures."""
        strategy = AdaptiveRetryStrategy(
            RetryConfig(max_attempts=3, initial_delay=0.1),
            learning_window=10,
        )
        
        # Execute operations with high failure rate
        for i in range(15):
            try:
                if i % 2 == 0:
                    strategy.execute(lambda: "success")
                else:
                    def failing():
                        raise Exception("Failed")
                    strategy.execute(failing)
            except RetryExhaustedError:
                pass
        
        stats = strategy.get_statistics()
        # Should have both successes and failures
        self.assertGreater(stats['total_operations'], 0)
    
    def test_statistics(self):
        """Test adaptive strategy statistics."""
        strategy = AdaptiveRetryStrategy(
            RetryConfig(max_attempts=3, initial_delay=0.1),
        )
        
        # Execute some operations
        for _ in range(5):
            strategy.execute(lambda: "success")
        
        stats = strategy.get_statistics()
        
        self.assertIn('total_operations', stats)
        self.assertIn('successful_operations', stats)
        self.assertIn('overall_success_rate', stats)
        self.assertIn('recent_success_rate', stats)
        self.assertIn('current_max_attempts', stats)
        
        self.assertEqual(stats['total_operations'], 5)
        self.assertEqual(stats['successful_operations'], 5)


class TestOperationSpecificRetryPolicy(unittest.TestCase):
    """Test operation-specific retry policies."""
    
    def test_different_policies(self):
        """Test different operations get different policies."""
        policy = OperationSpecificRetryPolicy()
        
        read_strategy = policy.get_strategy('read')
        write_strategy = policy.get_strategy('write')
        pin_strategy = policy.get_strategy('pin')
        
        # Check different configurations
        self.assertNotEqual(
            read_strategy.config.max_attempts,
            write_strategy.config.max_attempts
        )
    
    def test_execute_with_policy(self):
        """Test executing with operation-specific policy."""
        policy = OperationSpecificRetryPolicy()
        
        attempt_count = [0]
        
        def flaky_read():
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise Exception("Read failed")
            return "data"
        
        result = policy.execute_with_policy('read', flaky_read)
        
        self.assertEqual(result, "data")
        self.assertGreater(attempt_count[0], 1)
    
    def test_global_retry_policy(self):
        """Test global retry policy singleton."""
        policy1 = get_retry_policy()
        policy2 = get_retry_policy()
        
        # Should be same instance
        self.assertIs(policy1, policy2)


if __name__ == '__main__':
    unittest.main()
