"""
Simple test to verify our LOTUS_KIT_AVAILABLE fix works.
"""
import pytest

def test_lotus_kit_available():
    """Test that we can import LOTUS_KIT_AVAILABLE from lotus_kit."""
    from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
    assert LOTUS_KIT_AVAILABLE is True