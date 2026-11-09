"""
Basic test module to verify pytest infrastructure is working.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock

def test_basic_assertion():
    """A simple test that will always pass."""
    assert True, "This test should always pass"
    
def test_math_operations():
    """Test basic math operations."""
    assert 2 + 2 == 4, "Basic addition should work"
    assert 5 * 5 == 25, "Basic multiplication should work"
    
def test_mock_objects():
    """Test that mock objects can be created and used."""
    mock = MagicMock()
    mock.test_attribute = "test value"
    mock.test_method.return_value = 42
    
    assert mock.test_attribute == "test value"
    assert mock.test_method() == 42
    
@pytest.mark.parametrize("input_value,expected", [
    (1, 1),
    (2, 4),
    (3, 9),
    (4, 16),
])
def test_square_function(input_value, expected):
    """Test a simple square function with parametrized inputs."""
    def square(x):
        return x * x
        
    assert square(input_value) == expected