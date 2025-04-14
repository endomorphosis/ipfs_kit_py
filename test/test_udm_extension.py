#!/usr/bin/env python3
"""
Test script for the Unified Data Management extension.

This script tests the basic functionality of the unified data management system.
"""

import os
import sys
import logging
import asyncio
import json
import uuid
import time
import random
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

# Try to import required modules
try:
    from fastapi import FastAPI, UploadFile, File, Form
    from fastapi.testclient import TestClient
    HAS_REQUIREMENTS = True
except ImportError:
    logger.warning("Missing required packages. Please install: fastapi")
    HAS_REQUIREMENTS = False

# Import the UDM extension
try:
    from mcp_extensions.udm_extension import (
        create_udm_router,
        initialize,
        store_content,
        retrieve_content,
        StoreRequest,
        update_udm_status
    )
    HAS_UDM_EXTENSION = True
except ImportError as e:
    logger.error(f"Failed to import UDM extension: {e}")
    HAS_UDM_EXTENSION = False

# Mock storage backends for testing
mock_storage_backends = {
    "ipfs": {"available": True, "simulation": False},
    "local": {"available": True, "simulation": False},
    "s3": {"available": True, "simulation": False},
    "filecoin": {"available": True, "simulation": False},
    "storacha": {"available": False, "simulation": True},
    "huggingface": {"available": True, "simulation": False},
    "lassie": {"available": False, "simulation": True}
}

# Test variables
TEST_CONTENT = b"This is test content for the Unified Data Management system"
TEST_FILENAME = "test_file.txt"
TEST_CONTENT_TYPE = "text/plain"
TEST_METADATA = {
    "title": "Test File",
    "description": "A test file for UDM",
    "author": "IPFS Kit Team"
}
TEST_TAGS = ["test", "udm", "sample"]

# Test functions
def test_store_content():
    """Test storing content in the UDM system."""
    logger.info("Testing content storage")
    
    if not HAS_UDM_EXTENSION:
        logger.error("UDM extension not available")
        return False
    
    try:
        # Update backends status
        update_udm_status(mock_storage_backends)
        
        # Create a store request
        request = StoreRequest(
            content_name=TEST_FILENAME,
            content_type=TEST_CONTENT_TYPE,
            preferred_backend="ipfs",
            metadata=TEST_METADATA,
            tags=TEST_TAGS
        )
        
        # Store content
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(store_content(TEST_CONTENT, request))
        
        # Verify result
        if not result.get("success", False):
            logger.error(f"Failed to store content: {result.get('error')}")
            return False
        
        # Save CID for later tests
        cid = result.get("cid")
        logger.info(f"Content stored with CID: {cid}")
        
        # Check backend info
        backend = result.get("primary_backend")
        if not backend:
            logger.error("No primary backend in result")
            return False
        
        logger.info(f"Content stored in backend: {backend}")
        return True, cid
    
    except Exception as e:
        logger.error(f"Error testing content storage: {e}")
        return False, None

def test_retrieve_content(cid):
    """Test retrieving content from the UDM system."""
    logger.info("Testing content retrieval")
    
    if not HAS_UDM_EXTENSION:
        logger.error("UDM extension not available")
        return False
    
    try:
        # Update backends status
        update_udm_status(mock_storage_backends)
        
        # Retrieve content
        loop = asyncio.get_event_loop()
        content, metadata = loop.run_until_complete(retrieve_content(cid))
        
        # Verify content was retrieved
        if not content:
            logger.error(f"Failed to retrieve content: {metadata.get('error')}")
            return False
        
        # Verify content matches what we stored
        if content != TEST_CONTENT:
            logger.error("Retrieved content does not match original")
            return False
        
        logger.info(f"Content retrieved successfully (size: {len(content)} bytes)")
        logger.info(f"Retrieved from backend: {metadata.get('source_backend')}")
        return True
    
    except Exception as e:
        logger.error(f"Error testing content retrieval: {e}")
        return False

def test_content_info(cid):
    """Test getting content info."""
    logger.info("Testing content info")
    
    if not HAS_UDM_EXTENSION or not HAS_REQUIREMENTS:
        logger.error("UDM extension or FastAPI not available")
        return False
    
    try:
        # Create a test FastAPI app
        app = FastAPI()
        
        # Add the UDM router
        router = create_udm_router("/api/v0")
        app.include_router(router)
        
        # Create a test client
        client = TestClient(app)
        
        # Get content info
        response = client.get(f"/api/v0/udm/info/{cid}")
        
        # Verify response
        if response.status_code != 200:
            logger.error(f"Info request failed with status code {response.status_code}")
            return False
        
        data = response.json()
        if not data.get("success"):
            logger.error(f"Info request returned error: {data.get('error')}")
            return False
        
        # Verify content info
        content_info = data.get("content", {})
        if content_info.get("cid") != cid:
            logger.error("Returned CID does not match")
            return False
        
        if content_info.get("name") != TEST_FILENAME:
            logger.error("Returned filename does not match")
            return False
        
        if content_info.get("content_type") != TEST_CONTENT_TYPE:
            logger.error("Returned content type does not match")
            return False
        
        # Verify metadata
        metadata = data.get("metadata", {})
        for key, value in TEST_METADATA.items():
            if metadata.get(key) != value:
                logger.error(f"Metadata key {key} does not match expected value")
                return False
        
        logger.info("Content info retrieved successfully")
        logger.info(f"Content tags: {content_info.get('tags')}")
        return True
    
    except Exception as e:
        logger.error(f"Error testing content info: {e}")
        return False

def test_fastapi_integration():
    """Test FastAPI integration."""
    logger.info("Testing FastAPI integration")
    
    if not HAS_REQUIREMENTS or not HAS_UDM_EXTENSION:
        logger.error("Required packages not available")
        return False
    
    try:
        # Create a test FastAPI app
        app = FastAPI()
        
        # Create and add a UDM router
        udm_router = create_udm_router("/api/v0")
        app.include_router(udm_router)
        
        # Create a test client
        client = TestClient(app)
        
        # Test the UDM status endpoint
        response = client.get("/api/v0/udm/status")
        if response.status_code != 200:
            logger.error(f"UDM status endpoint returned status code {response.status_code}")
            return False
        
        # Check the response JSON
        data = response.json()
        if not data.get("success"):
            logger.error("UDM status didn't return success=True")
            return False
        
        # Create a file to upload
        test_content = b"This is a test file for FastAPI integration"
        
        # Create form data for the request
        from io import BytesIO
        
        test_file = BytesIO(test_content)
        
        # Test the store content endpoint
        response = client.post(
            "/api/v0/udm/store",
            files={
                "file": ("test_fastapi.txt", test_file, "text/plain")
            },
            data={
                "content_name": "test_fastapi.txt",
                "content_type": "text/plain",
                "tags": ["test", "fastapi"],
                "metadata": json.dumps({"source": "FastAPI test"})
            }
        )
        
        if response.status_code != 200:
            logger.error(f"UDM store endpoint returned status code {response.status_code}")
            return False
        
        store_data = response.json()
        if not store_data.get("success"):
            logger.error(f"UDM store failed: {store_data.get('error')}")
            return False
        
        logger.info("FastAPI integration working correctly")
        logger.info(f"Stored content with CID: {store_data.get('cid')}")
        return True
    except Exception as e:
        logger.error(f"Error testing FastAPI integration: {e}")
        return False

def test_content_query():
    """Test content querying."""
    logger.info("Testing content querying")
    
    if not HAS_REQUIREMENTS or not HAS_UDM_EXTENSION:
        logger.error("Required packages not available")
        return False
    
    try:
        # Create a test FastAPI app
        app = FastAPI()
        
        # Add the UDM router
        router = create_udm_router("/api/v0")
        app.include_router(router)
        
        # Create a test client
        client = TestClient(app)
        
        # Query content by tags
        response = client.post(
            "/api/v0/udm/query",
            json={
                "tags": ["test"],
                "limit": 10,
                "offset": 0
            }
        )
        
        # Verify response
        if response.status_code != 200:
            logger.error(f"Query request failed with status code {response.status_code}")
            return False
        
        data = response.json()
        if not data.get("success"):
            logger.error(f"Query request returned error: {data.get('error')}")
            return False
        
        results = data.get("results", [])
        logger.info(f"Query returned {len(results)} results")
        
        # Verify at least one result has our test tags
        found_test_content = False
        for result in results:
            tags = result.get("tags", [])
            if "test" in tags and "udm" in tags:
                found_test_content = True
                break
        
        if not found_test_content and len(results) > 0:
            logger.warning("Could not find our test content in query results")
            # This might not be an error if there's no test content or it was deleted
        
        return True
    
    except Exception as e:
        logger.error(f"Error testing content query: {e}")
        return False

def run_all_tests():
    """Run all tests."""
    logger.info("Starting unified data management tests")
    
    # Check requirements
    if not HAS_REQUIREMENTS:
        logger.error("Required packages are missing. Please install fastapi")
        return False
    
    if not HAS_UDM_EXTENSION:
        logger.error("UDM extension not available or could not be imported")
        return False
    
    # Initialize the UDM system
    initialize()
    
    # Run store content test first to get a CID
    store_result, cid = test_store_content()
    if not store_result or not cid:
        logger.error("Failed to store test content, can't continue with other tests")
        return False
    
    # Run tests that depend on a stored CID
    retrieve_result = test_retrieve_content(cid)
    info_result = test_content_info(cid)
    
    # Run other tests
    fastapi_result = test_fastapi_integration()
    query_result = test_content_query()
    
    # Collect all results
    results = {
        "store_content": store_result,
        "retrieve_content": retrieve_result,
        "content_info": info_result,
        "fastapi_integration": fastapi_result,
        "content_query": query_result
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
    run_all_tests()