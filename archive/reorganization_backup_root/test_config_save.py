#!/usr/bin/env python3
"""
Test script to verify configuration saving functionality.
"""
import asyncio
import json
from pathlib import Path
import sys

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from mcp.ipfs_kit.backends import BackendHealthMonitor

async def test_s3_config_save():
    """Test S3 configuration saving."""
    print("Testing S3 configuration saving...")
    
    monitor = BackendHealthMonitor()
    
    # Test configuration data
    test_config = {
        "access_key_id": "test_access_key",
        "secret_access_key": "test_secret_key",
        "bucket": "test-bucket",
        "region": "us-west-2",
        "endpoint_url": "https://s3.test.com",
        "enabled": True
    }
    
    print(f"Saving test config: {test_config}")
    
    # Save configuration
    result = await monitor.set_backend_config("s3", test_config)
    print(f"Save result: {result}")
    
    # Verify configuration was saved
    config_file = Path("/tmp/ipfs_kit_config/backends/s3_config.json")
    if config_file.exists():
        with open(config_file, 'r') as f:
            saved_config = json.load(f)
        print(f"Saved configuration: {saved_config}")
        
        # Verify all fields were saved
        for key, value in test_config.items():
            if key in saved_config and saved_config[key] == value:
                print(f"✓ {key}: {value}")
            else:
                print(f"✗ {key}: expected {value}, got {saved_config.get(key)}")
    else:
        print("✗ Configuration file was not created!")
    
    # Test retrieving configuration
    print("\nTesting configuration retrieval...")
    retrieved_config = await monitor.get_backend_config("s3")
    print(f"Retrieved config: {retrieved_config}")

if __name__ == "__main__":
    asyncio.run(test_s3_config_save())
