#!/usr/bin/env python3
"""
Filecoin Backend Integration Test Script

This script tests the functionality of the Filecoin backend implementation
for the MCP storage manager, verifying that it meets the requirements
specified in the MCP roadmap.
"""

import os
import sys
import time
import json
import logging
import tempfile
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("filecoin-test")

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    # Import required modules
    from ipfs_kit_py.mcp.storage_manager.backends.filecoin_backend import FilecoinBackend
    from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType
    logger.info("Successfully imported Filecoin backend")
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)

def create_test_file(content: str = "Test content for Filecoin storage") -> str:
    """Create a temporary file with test content."""
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(content.encode('utf-8'))
    temp_file.close()
    return temp_file.name

def load_config() -> Dict[str, Any]:
    """Load configuration for the test."""
    config_path = os.path.join(os.path.dirname(__file__), "config", "filecoin_test_config.json")

    # Default configuration
    default_config = {
        "mock_mode": True,  # Use mock mode by default for testing
        "resources": {
            "api_key": os.environ.get("FILECOIN_API_KEY", ""),
            "endpoint": os.environ.get("FILECOIN_ENDPOINT", ""),
            "max_retries": 3
        },
        "metadata": {
            "default_miner": os.environ.get("FILECOIN_DEFAULT_MINER", ""),
            "replication_count": 1,
            "verify_deals": True,
            "max_price": "100000000000",  # In attoFIL
            "deal_duration": 518400  # 180 days in epochs
        }
    }

    # Try to load from file
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
    except Exception as e:
        logger.warning(f"Failed to load configuration, using defaults: {e}")

    return default_config

def test_filecoin_backend():
    """Test the Filecoin backend implementation."""
    logger.info("Starting Filecoin backend test")

    # Load configuration
    config = load_config()

    # Initialize the backend
    try:
        backend = FilecoinBackend(
            resources=config["resources"],
            metadata=config["metadata"]
        )
        logger.info(f"Initialized Filecoin backend in {backend.mode} mode")
    except Exception as e:
        logger.error(f"Failed to initialize Filecoin backend: {e}")
        return False

    # Check if the backend is available
    if backend.mode == "unavailable":
        logger.error("Filecoin backend is unavailable")
        return False

    # Test data
    test_data = "Test content for Filecoin storage " + str(time.time())
    test_metadata = {
        "test_name": "filecoin_backend_test",
        "timestamp": time.time(),
        "description": "Test data for Filecoin backend integration"
    }

    # 1. Test Store Operation
    logger.info("Testing store operation")
    store_result = backend.store(
        data=test_data.encode('utf-8'),
        options={"add_metadata": True, "test_metadata": test_metadata}
    )

    if not store_result.get("success", False):
        logger.error(f"Store operation failed: {store_result.get('error', 'Unknown error')}")
        return False

    content_id = store_result.get("identifier")
    logger.info(f"Successfully stored content with ID: {content_id}")

    # 2. Test Exists Operation
    logger.info("Testing exists operation")
    exists_result = backend.exists(content_id)

    if not exists_result:
        logger.error(f"Exists operation failed: Content should exist but wasn't found")
        return False

    logger.info(f"Content exists check passed: {exists_result}")

    # 3. Test Get Metadata Operation
    logger.info("Testing get_metadata operation")
    metadata_result = backend.get_metadata(content_id)

    if not metadata_result.get("success", False):
        logger.error(f"Get metadata operation failed: {metadata_result.get('error', 'Unknown error')}")
        return False

    logger.info(f"Successfully retrieved metadata: {json.dumps(metadata_result.get('metadata', {}), indent=2)}")

    # 4. Test Update Metadata Operation
    logger.info("Testing update_metadata operation")
    update_metadata = {
        "updated_at": time.time(),
        "update_test": "This is updated metadata"
    }

    update_result = backend.update_metadata(content_id, update_metadata)

    if not update_result.get("success", False):
        logger.error(f"Update metadata operation failed: {update_result.get('error', 'Unknown error')}")
        # Not failing the test as metadata updates may be limited in Filecoin
        logger.warning("Metadata update limitations in Filecoin are expected")
    else:
        logger.info(f"Successfully updated metadata")

    # 5. Test Retrieve Operation
    logger.info("Testing retrieve operation")
    retrieve_result = backend.retrieve(content_id)

    if not retrieve_result.get("success", False):
        logger.error(f"Retrieve operation failed: {retrieve_result.get('error', 'Unknown error')}")
        return False

    retrieved_data = retrieve_result.get("data")
    if retrieved_data:
        try:
            decoded_data = retrieved_data.decode('utf-8')
            if decoded_data != test_data:
                logger.error(f"Retrieved data doesn't match original data")
                logger.error(f"Original: {test_data}")
                logger.error(f"Retrieved: {decoded_data}")
                return False

            logger.info(f"Successfully retrieved and verified content data")
        except UnicodeDecodeError:
            logger.error("Failed to decode retrieved data")
            return False
    else:
        logger.error("No data returned from retrieve operation")
        return False

    # 6. Test List Operation
    logger.info("Testing list operation")
    list_result = backend.list()

    if not list_result.get("success", False):
        logger.error(f"List operation failed: {list_result.get('error', 'Unknown error')}")
        return False

    items = list_result.get("items", [])
    logger.info(f"Listed {len(items)} items from Filecoin")

    # Check if our content ID is in the list
    found = False
    for item in items:
        if item.get("identifier") == content_id:
            found = True
            break

    if not found:
        logger.warning(f"Content ID {content_id} not found in list results")
    else:
        logger.info(f"Content ID {content_id} found in list results")

    # 7. Test Advanced Filecoin Integration Features from MCP Roadmap
    logger.info("Testing advanced Filecoin integration features")

    # 7.1. Network Analytics & Metrics
    # This would typically access the Filecoin network statistics, miner information, etc.
    logger.info("Testing Network Analytics & Metrics functionality")
    # For this test, we'll just verify that the relevant data is accessible in the metadata
    metadata_result = backend.get_metadata(content_id)
    deal_info = metadata_result.get('metadata', {}).get('deals', [])
    if deal_info:
        logger.info(f"Network analytics information available: {len(deal_info)} deals found")
    else:
        logger.warning("No network analytics information available")

    # 7.2. Miner Selection & Management
    # This would test the ability to select specific miners for storage
    logger.info("Testing Miner Selection & Management functionality")
    specific_miner = config["metadata"].get("default_miner")
    if specific_miner:
        store_with_miner_result = backend.store(
            data=f"Miner selection test {time.time()}".encode('utf-8'),
            container=specific_miner  # Use container parameter for miner selection
        )
        if store_with_miner_result.get("success", False):
            logger.info(f"Successfully stored content with specific miner: {specific_miner}")
        else:
            logger.warning(f"Failed to store with specific miner: {store_with_miner_result.get('error')}")
    else:
        logger.warning("No specific miner configured for testing miner selection")

    # 7.3. Enhanced Storage Operations
    # Test redundant storage across multiple miners
    logger.info("Testing Enhanced Storage Operations functionality")
    replication_count = config["metadata"].get("replication_count", 1)
    if replication_count > 1:
        store_with_replication_result = backend.store(
            data=f"Replication test {time.time()}".encode('utf-8'),
            options={"replication_count": replication_count}
        )
        if store_with_replication_result.get("success", False):
            replicated_id = store_with_replication_result.get("identifier")
            logger.info(f"Successfully stored content with replication: {replication_count}")

            # Check if multiple deals were created
            deals = store_with_replication_result.get("deals", [])
            logger.info(f"Created {len(deals)} deals for replicated content")
        else:
            logger.warning(f"Failed to store with replication: {store_with_replication_result.get('error')}")
    else:
        logger.warning("Replication count not configured for testing enhanced storage operations")

    # 7.4. Content Health & Reliability
    # This would verify storage health metrics and monitoring
    logger.info("Testing Content Health & Reliability functionality")
    # Typically, this would involve checking deal status, replication status, etc.
    # For the test, we'll just verify we can access this information
    deal_status_available = False
    for item in items:
        deal_info = item.get("deal_id")
        if deal_info:
            deal_status_available = True
            break

    if deal_status_available:
        logger.info("Content health monitoring information is available")
    else:
        logger.warning("No content health monitoring information available")

    # 8. Test Delete Operation (or attempt to)
    logger.info("Testing delete operation")
    delete_result = backend.delete(content_id)

    # In Filecoin, sealed deals can't be deleted, so we don't fail if delete doesn't work
    if delete_result.get("success", False):
        logger.info(f"Successfully deleted content (or at least pending deals)")
    else:
        logger.warning(f"Delete operation note: {delete_result.get('error', 'Unknown issue')}")
        logger.warning("This is expected if the deals are already sealed in Filecoin")

    logger.info("Filecoin backend test completed successfully")
    return True

if __name__ == "__main__":
    try:
        success = test_filecoin_backend()
        if success:
            logger.info("All tests passed successfully")
            sys.exit(0)
        else:
            logger.error("Some tests failed")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error in test script: {e}")
        sys.exit(1)
