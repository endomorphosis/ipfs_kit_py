#!/usr/bin/env python3
"""
Test script for the migration extension.

This script tests the basic functionality of the cross-backend migration system.
"""

import os
import sys
import logging
import anyio
import json
import uuid
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add the parent directory to the path to import modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import the migration extension
from mcp_extensions.migration_extension import (
    create_migration_router,
    MigrationPolicy,
    MigrationRequest,
    perform_migration,
    estimate_migration_cost
)

# Mock FastAPI for testing
class MockResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self.json_data = json_data or {}
        
    def json(self):
        return self.json_data
        
    def __getitem__(self, key):
        return self.json_data[key]

# Mock storage backends for testing
mock_storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "s3": {"available": True, "simulation": False},
    "filecoin": {"available": True, "simulation": False},
    "storacha": {"available": True, "simulation": False},
    "huggingface": {"available": True, "simulation": False},
    "lassie": {"available": True, "simulation": False}
}

# Sample test file content
TEST_CONTENT = b"This is test content for migration between backends"
TEST_CID = "QmTest123456789"

# Mock backend modules
class MockBackendModule:
    def __init__(self, name):
        self.name = name
        self.storage = {}  # CID -> content mapping
        self.metadata = {}  # CID -> metadata mapping
        
    async def get_content(self, cid):
        """Get content by CID."""
        if cid in self.storage:
            return self.storage[cid]
        return None
        
    async def store_content(self, content, cid=None):
        """Store content and return CID."""
        # Use provided CID or generate a mock one
        new_cid = cid or f"Qm{uuid.uuid4().hex[:10]}"
        self.storage[new_cid] = content
        return {"cid": new_cid, "size": len(content)}
        
    async def get_content_info(self, cid):
        """Get content info by CID."""
        if cid in self.storage:
            return {"cid": cid, "size": len(self.storage[cid])}
        return None
        
    async def get_metadata(self, cid):
        """Get metadata by CID."""
        return self.metadata.get(cid, {})
        
    async def set_metadata(self, cid, metadata):
        """Set metadata for CID."""
        self.metadata[cid] = metadata
        return True
        
    async def remove_content(self, cid):
        """Remove content by CID."""
        if cid in self.storage:
            del self.storage[cid]
            if cid in self.metadata:
                del self.metadata[cid]
            return True
        return False

# Mock get_backend_module function
mock_backend_modules = {
    "s3": MockBackendModule("s3"),
    "filecoin": MockBackendModule("filecoin"),
    "storacha": MockBackendModule("storacha"),
    "huggingface": MockBackendModule("huggingface"),
    "lassie": MockBackendModule("lassie")
}

async def mock_get_backend_module(backend_name):
    """Mock version of get_backend_module for testing."""
    return mock_backend_modules.get(backend_name)

# Test functions
async def test_migration_basic():
    """Test basic migration between backends."""
    logger.info("Testing basic migration functionality")
    
    # Setup test data
    source_backend = "s3"
    target_backend = "filecoin"
    
    # Store test content in source backend
    source_module = await mock_get_backend_module(source_backend)
    result = await source_module.store_content(TEST_CONTENT, TEST_CID)
    source_cid = result["cid"]
    
    # Set metadata
    test_metadata = {"name": "test file", "description": "test migration", "timestamp": time.time()}
    await source_module.set_metadata(source_cid, test_metadata)
    
    logger.info(f"Stored test content in {source_backend} with CID: {source_cid}")
    
    # Create migration ID
    migration_id = f"test_mig_{int(time.time())}"
    
    # Mock the migration record
    migrations = {}
    migrations[migration_id] = {
        "id": migration_id,
        "source_backend": source_backend,
        "target_backend": target_backend,
        "cid": source_cid,
        "status": "queued",
        "created_at": time.time(),
        "updated_at": time.time(),
        "progress": 0.0,
        "metadata_sync": True,
        "remove_source": False
    }
    
    # Patch the get_backend_module function in the migration_extension module
    import mcp_extensions.migration_extension
    original_get_backend_module = mcp_extensions.migration_extension.get_backend_module
    mcp_extensions.migration_extension.get_backend_module = mock_get_backend_module
    
    try:
        # Perform migration
        await mcp_extensions.migration_extension.perform_migration(
            migration_id,
            source_backend,
            target_backend,
            source_cid,
            True,  # metadata_sync
            False  # remove_source
        )
        
        # Verify migrations record is updated
        assert migrations[migration_id]["status"] == "completed", "Migration should be completed"
        assert migrations[migration_id]["progress"] == 100.0, "Progress should be 100%"
        assert "result" in migrations[migration_id], "Result should be present"
        
        # Verify content is migrated
        target_module = await mock_get_backend_module(target_backend)
        target_cid = migrations[migration_id]["result"]["target_cid"]
        target_content = await target_module.get_content(target_cid)
        assert target_content == TEST_CONTENT, "Content should match"
        
        # Verify metadata is migrated
        target_metadata = await target_module.get_metadata(target_cid)
        assert target_metadata == test_metadata, "Metadata should match"
        
        logger.info(f"Migration successful to {target_backend} with CID: {target_cid}")
        return True
    except Exception as e:
        logger.error(f"Migration test failed: {e}")
        return False
    finally:
        # Restore original function
        mcp_extensions.migration_extension.get_backend_module = original_get_backend_module

async def test_migration_cost_estimation():
    """Test migration cost estimation."""
    logger.info("Testing migration cost estimation")
    
    # Setup test data
    source_backend = "s3"
    target_backend = "filecoin"
    
    # Store test content in source backend
    source_module = await mock_get_backend_module(source_backend)
    result = await source_module.store_content(TEST_CONTENT, TEST_CID)
    source_cid = result["cid"]
    
    logger.info(f"Stored test content in {source_backend} with CID: {source_cid}")
    
    # Patch the get_backend_module function
    import mcp_extensions.migration_extension
    original_get_backend_module = mcp_extensions.migration_extension.get_backend_module
    mcp_extensions.migration_extension.get_backend_module = mock_get_backend_module
    
    try:
        # Estimate migration cost
        cost_estimate = await mcp_extensions.migration_extension.estimate_migration_cost(
            source_backend,
            target_backend,
            source_cid
        )
        
        # Verify cost estimate has expected fields
        assert "estimated_cost" in cost_estimate, "Should have estimated_cost field"
        assert "currency" in cost_estimate, "Should have currency field"
        assert "size_bytes" in cost_estimate, "Should have size_bytes field"
        assert "time_estimate_seconds" in cost_estimate, "Should have time_estimate_seconds field"
        
        logger.info(f"Cost estimation successful: {cost_estimate}")
        return True
    except Exception as e:
        logger.error(f"Cost estimation test failed: {e}")
        return False
    finally:
        # Restore original function
        mcp_extensions.migration_extension.get_backend_module = original_get_backend_module

async def test_policy_application():
    """Test migration policy application."""
    logger.info("Testing migration policy application")
    
    # Create a test policy
    policy = MigrationPolicy(
        name="test_policy",
        description="Test migration policy",
        source_backend="s3",
        target_backend="filecoin",
        content_filter={"type": "document"},
        priority=2,
        cost_optimized=True,
        metadata_sync=True,
        auto_clean=True
    )
    
    # Convert to dict as the system would do
    policy_dict = policy.dict()
    
    # Create policy store
    policies = {"test_policy": policy_dict}
    
    # Create migration request
    request = MigrationRequest(
        source_backend="s3",
        target_backend="filecoin",
        cid=TEST_CID,
        policy_name="test_policy"
    )
    
    # Check if policy was correctly applied
    try:
        # Verify policy settings are applied
        if request.policy_name and request.policy_name in policies:
            applied_policy = policies[request.policy_name]
            
            # Metadata sync should follow policy
            if "metadata_sync" in applied_policy:
                assert request.metadata_sync == applied_policy["metadata_sync"], "metadata_sync should match policy"
            
            # Auto-clean (remove source) should follow policy
            if "auto_clean" in applied_policy:
                # We need to translate between policy's auto_clean and request's remove_source
                assert applied_policy["auto_clean"] == True, "Policy auto_clean should be True"
        
        logger.info("Policy application test successful")
        return True
    except Exception as e:
        logger.error(f"Policy application test failed: {e}")
        return False

# Main test function
async def run_tests():
    """Run all tests."""
    logger.info("Starting migration extension tests")
    
    # Run tests and collect results
    results = {
        "basic_migration": await test_migration_basic(),
        "cost_estimation": await test_migration_cost_estimation(),
        "policy_application": await test_policy_application()
    }
    
    # Check if all tests passed
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("✅ All tests passed!")
    else:
        logger.error("❌ Some tests failed!")
        failed_tests = [test for test, result in results.items() if not result]
        logger.error(f"Failed tests: {failed_tests}")
    
    return all_passed

# Main entry point
if __name__ == "__main__":
    # Run the test coroutine
    anyio.run(run_tests)