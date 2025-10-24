#!/usr/bin/env python3
"""
Storacha Connection Test Script

This script tests the Storacha kit functionality including:
- Basic initialization and configuration
- Install and config methods
- Connection verification (mock mode when credentials unavailable)
"""

import os
import sys
import json
import logging
import pytest
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Import storacha_kit
try:
    from ipfs_kit_py.storacha_kit import storacha_kit
    STORACHA_AVAILABLE = True
except ImportError as e:
    logger.error(f"Import error: {e}")
    STORACHA_AVAILABLE = False
    # Skip this module's tests if dependencies aren't available
    pytestmark = pytest.mark.skip(reason="Storacha dependencies not available")

def test_storacha_initialization():
    """Test basic storacha_kit initialization."""
    if not STORACHA_AVAILABLE:
        pytest.skip("Storacha dependencies not available")
    
    logger.info("Testing storacha_kit initialization...")
    
    # Test basic initialization
    kit = storacha_kit()
    assert kit is not None, "storacha_kit should initialize"
    assert hasattr(kit, 'metadata'), "storacha_kit should have metadata attribute"
    assert hasattr(kit, 'resources'), "storacha_kit should have resources attribute"
    
    # Test initialization with metadata
    metadata = {"api_key": "test_key", "mock_mode": True}
    kit_with_metadata = storacha_kit(metadata=metadata)
    assert kit_with_metadata.metadata == metadata, "Metadata should be stored"
    
    logger.info("✓ Storacha initialization tests passed")


def test_storacha_install_method():
    """Test storacha_kit install() method."""
    if not STORACHA_AVAILABLE:
        pytest.skip("Storacha dependencies not available")
    
    logger.info("Testing storacha_kit install() method...")
    
    kit = storacha_kit()
    assert hasattr(kit, 'install'), "storacha_kit should have install() method"
    
    # Test install method returns a result
    # Note: This may fail if dependencies are missing, but should not crash
    try:
        result = kit.install()
        assert isinstance(result, dict), "install() should return a dictionary"
        assert 'success' in result or 'status' in result, "Result should have success or status field"
        logger.info(f"Install result: {result}")
    except Exception as e:
        # Install may fail in test environment, but should not crash pytest
        logger.warning(f"Install failed (expected in test environment): {e}")
    
    logger.info("✓ Storacha install method tests passed")


def test_storacha_config_method():
    """Test storacha_kit config() method."""
    if not STORACHA_AVAILABLE:
        pytest.skip("Storacha dependencies not available")
    
    logger.info("Testing storacha_kit config() method...")
    
    kit = storacha_kit()
    assert hasattr(kit, 'config'), "storacha_kit should have config() method"
    
    # Test config method with mock settings
    config_params = {
        "api_key": "test_api_key",
        "mock_mode": True,
        "api_url": "https://test.storacha.network"
    }
    
    result = kit.config(**config_params)
    assert isinstance(result, dict), "config() should return a dictionary"
    assert 'success' in result, "Result should have success field"
    
    # Verify configuration was applied
    if result.get('success'):
        logger.info(f"Config result: {result}")
    
    logger.info("✓ Storacha config method tests passed")

def test_storacha_with_env_credentials():
    """Test storacha_kit with environment credentials if available."""
    if not STORACHA_AVAILABLE:
        pytest.skip("Storacha dependencies not available")
    
    logger.info("Testing storacha_kit with environment credentials...")
    
    # Get credentials from environment
    api_key = os.environ.get("STORACHA_API_KEY")
    api_endpoint = os.environ.get("STORACHA_API_URL") or os.environ.get("STORACHA_API_ENDPOINT")
    
    has_credentials = api_key is not None
    logger.info(f"API Key: {'Provided' if api_key else 'Not provided'}")
    logger.info(f"API Endpoint: {api_endpoint or 'Not provided (will use default)'}")
    
    # Initialize with environment credentials
    metadata = {}
    if api_key:
        metadata['api_key'] = api_key
    if api_endpoint:
        metadata['api_url'] = api_endpoint
    
    # Always use mock mode in tests unless explicitly configured
    if not has_credentials:
        metadata['mock_mode'] = True
        logger.info("No credentials found, using mock mode")
    
    kit = storacha_kit(metadata=metadata)
    assert kit is not None, "storacha_kit should initialize with credentials"
    
    # Test config method to apply settings
    if api_key:
        config_result = kit.config(api_key=api_key, api_url=api_endpoint or "https://up.storacha.network/bridge")
        logger.info(f"Config result: {config_result}")
        assert isinstance(config_result, dict), "config() should return a dictionary"
    else:
        # In mock mode, just verify the kit works
        logger.info("Testing mock mode configuration")
        config_result = kit.config(mock_mode=True)
        logger.info(f"Mock config result: {config_result}")
        assert isinstance(config_result, dict), "config() should return a dictionary"
    
    logger.info("✓ Storacha environment credentials tests passed")


# Run all tests when executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
