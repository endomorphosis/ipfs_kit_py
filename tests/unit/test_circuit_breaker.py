#!/usr/bin/env python3
"""
Unit tests for circuit breaker functionality.
"""

import time
import unittest
from unittest.mock import Mock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ipfs_kit_py.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    circuit_breaker,
    CircuitBreakerManager,
    get_global_circuit_breaker_manager,
)


class TestCircuitBreaker(unittest.TestCase):
    """Test circuit breaker functionality."""
    
    def test_circuit_initialization(self):
        """Test circuit breaker initialization."""
        config = CircuitBreakerConfig(
            failure_threshold=5,
            timeout=30.0,
        )
        
        breaker = CircuitBreaker("test_backend", config)
        
        self.assertEqual(breaker.name, "test_backend")
        self.assertEqual(breaker.state, CircuitState.CLOSED)
        self.assertEqual(breaker.failure_count, 0)
    
    def test_successful_operations(self):
        """Test successful operations through circuit."""
        breaker = CircuitBreaker("test")
        
        def successful_op():
            return "success"
        
        result = breaker.call(successful_op)
        
        self.assertEqual(result, "success")
        
        state = breaker.get_state()
        self.assertEqual(state['total_successes'], 1)
        self.assertEqual(state['total_failures'], 0)
    
    def test_circuit_opens_on_failures(self):
        """Test circuit opens after failure threshold."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
        )
        breaker = CircuitBreaker("test", config)
        
        def failing_op():
            raise Exception("Operation failed")
        
        # Trigger failures
        for i in range(3):
            with self.assertRaises(Exception):
                breaker.call(failing_op)
        
        # Circuit should be open now
        self.assertEqual(breaker.state, CircuitState.OPEN)
        
        # Further calls should fail fast
        with self.assertRaises(CircuitBreakerOpenError):
            breaker.call(failing_op)
    
    def test_circuit_half_open_recovery(self):
        """Test circuit recovery through half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.5,  # Short timeout for testing
        )
        breaker = CircuitBreaker("test", config)
        
        def failing_op():
            raise Exception("Failed")
        
        def successful_op():
            return "success"
        
        # Open the circuit
        for _ in range(2):
            with self.assertRaises(Exception):
                breaker.call(failing_op)
        
        self.assertEqual(breaker.state, CircuitState.OPEN)
        
        # Wait for timeout
        time.sleep(0.6)
        
        # Next call should transition to half-open
        result = breaker.call(successful_op)
        self.assertEqual(result, "success")
        self.assertEqual(breaker.state, CircuitState.HALF_OPEN)
        
        # Another success should close the circuit
        result = breaker.call(successful_op)
        self.assertEqual(breaker.state, CircuitState.CLOSED)
    
    def test_half_open_reopens_on_failure(self):
        """Test circuit reopens if failure occurs in half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            timeout=0.5,
        )
        breaker = CircuitBreaker("test", config)
        
        def failing_op():
            raise Exception("Failed")
        
        # Open circuit
        for _ in range(2):
            with self.assertRaises(Exception):
                breaker.call(failing_op)
        
        self.assertEqual(breaker.state, CircuitState.OPEN)
        
        # Wait for timeout to enter half-open
        time.sleep(0.6)
        
        # Failure in half-open should reopen
        with self.assertRaises(Exception):
            breaker.call(failing_op)
        
        self.assertEqual(breaker.state, CircuitState.OPEN)
    
    def test_failure_rate_threshold(self):
        """Test circuit opens based on failure rate."""
        config = CircuitBreakerConfig(
            failure_threshold=100,  # High threshold
            failure_rate_threshold=0.5,  # 50% failure rate
            min_requests_for_rate=10,
        )
        breaker = CircuitBreaker("test", config)
        
        def op(should_fail):
            if should_fail:
                raise Exception("Failed")
            return "success"
        
        # Execute operations with 60% failure rate
        for i in range(15):
            should_fail = i % 10 < 6  # 60% failures
            try:
                breaker.call(op, should_fail)
            except Exception:
                pass
        
        # Circuit should be open due to failure rate
        self.assertEqual(breaker.state, CircuitState.OPEN)
    
    def test_circuit_decorator(self):
        """Test circuit breaker decorator."""
        @circuit_breaker("decorated_test", CircuitBreakerConfig(failure_threshold=2))
        def my_function(should_fail):
            if should_fail:
                raise Exception("Failed")
            return "success"
        
        # Successful call
        result = my_function(False)
        self.assertEqual(result, "success")
        
        # Trigger failures to open circuit
        for _ in range(2):
            with self.assertRaises(Exception):
                my_function(True)
        
        # Should fail fast now
        with self.assertRaises(CircuitBreakerOpenError):
            my_function(False)
        
        # Check breaker is attached
        self.assertTrue(hasattr(my_function, 'circuit_breaker'))
    
    def test_force_open_and_close(self):
        """Test manually forcing circuit state."""
        breaker = CircuitBreaker("test")
        
        # Force open
        breaker.force_open()
        self.assertEqual(breaker.state, CircuitState.OPEN)
        
        # Force close
        breaker.force_closed()
        self.assertEqual(breaker.state, CircuitState.CLOSED)
    
    def test_circuit_reset(self):
        """Test resetting circuit breaker."""
        breaker = CircuitBreaker("test")
        
        def failing_op():
            raise Exception("Failed")
        
        # Accumulate some failures
        for _ in range(3):
            with self.assertRaises(Exception):
                breaker.call(failing_op)
        
        self.assertGreater(breaker.failure_count, 0)
        
        # Reset
        breaker.reset()
        
        self.assertEqual(breaker.failure_count, 0)
        self.assertEqual(breaker.state, CircuitState.CLOSED)
    
    def test_circuit_statistics(self):
        """Test circuit breaker statistics."""
        breaker = CircuitBreaker("test")
        
        def op(should_fail):
            if should_fail:
                raise Exception("Failed")
            return "success"
        
        # Execute operations
        for i in range(10):
            try:
                breaker.call(op, i % 3 == 0)  # 1/3 failure rate
            except Exception:
                pass
        
        state = breaker.get_state()
        
        self.assertEqual(state['total_requests'], 10)
        self.assertGreater(state['total_successes'], 0)
        self.assertGreater(state['total_failures'], 0)
        self.assertGreater(state['success_rate'], 0)


class TestCircuitBreakerManager(unittest.TestCase):
    """Test circuit breaker manager."""
    
    def test_get_or_create(self):
        """Test getting or creating circuit breakers."""
        manager = CircuitBreakerManager()
        
        # Create breaker
        breaker1 = manager.get_or_create("backend1")
        self.assertIsNotNone(breaker1)
        
        # Get same breaker
        breaker2 = manager.get_or_create("backend1")
        self.assertIs(breaker1, breaker2)
        
        # Create different breaker
        breaker3 = manager.get_or_create("backend2")
        self.assertIsNot(breaker1, breaker3)
    
    def test_get_all_states(self):
        """Test getting all circuit breaker states."""
        manager = CircuitBreakerManager()
        
        manager.get_or_create("backend1")
        manager.get_or_create("backend2")
        
        states = manager.get_all_states()
        
        self.assertEqual(len(states), 2)
        self.assertIn('backend1', states)
        self.assertIn('backend2', states)
    
    def test_reset_all(self):
        """Test resetting all circuit breakers."""
        manager = CircuitBreakerManager()
        
        breaker1 = manager.get_or_create("backend1")
        breaker2 = manager.get_or_create("backend2")
        
        # Force open both
        breaker1.force_open()
        breaker2.force_open()
        
        # Reset all
        manager.reset_all()
        
        # Both should be closed
        self.assertEqual(breaker1.state, CircuitState.CLOSED)
        self.assertEqual(breaker2.state, CircuitState.CLOSED)
    
    def test_global_manager(self):
        """Test global circuit breaker manager."""
        manager1 = get_global_circuit_breaker_manager()
        manager2 = get_global_circuit_breaker_manager()
        
        # Should be same instance
        self.assertIs(manager1, manager2)


if __name__ == '__main__':
    unittest.main()
