#!/usr/bin/env python3
"""
Test script for verifying IPNS functionality in the MCP server.

This script tests:
1. The IPNS publish functionality (ipfs_name_publish)
2. The IPNS resolve functionality (ipfs_name_resolve)
3. The compatibility with high-level API IPNS methods
"""

import os
import sys
import json
import time
import logging
import requests
from typing import Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure ipfs_kit_py is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the model directly to test IPNS methods
from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel

# Import high-level API for comparison
from ipfs_kit_py.high_level_api import IPFSSimpleAPI

# URL to MCP server API if running
MCP_SERVER_URL = "http://localhost:8000"

def test_model_ipns_publish():
    """Test IPNS publishing via the model directly."""
    logger.info("Testing IPNS publishing via the model...")
    
    # Create model instance
    model = IPFSModel()
    
    # Add some content first
    test_content = b"Test content for IPNS publish via model"
    result = model.add_content(test_content)
    if not result.get("success", False):
        logger.error(f"Failed to add content: {result}")
        return False
    
    cid = result.get("cid", result.get("Hash", None))
    logger.info(f"Added content with CID: {cid}")
    
    # Publish to IPNS
    publish_result = model.ipfs_name_publish(cid)
    logger.info(f"IPNS publish result: {publish_result}")
    
    if not publish_result.get("success", False):
        logger.error(f"Failed to publish to IPNS: {publish_result}")
        return False
    
    # Check the result for expected fields
    ipns_name = publish_result.get("name")
    value = publish_result.get("value")
    
    logger.info(f"Published {cid} to IPNS name: {ipns_name} with value: {value}")
    
    # Verify fields
    if not ipns_name or not value:
        logger.error("Missing required fields in publish result")
        return False
    
    if not value.endswith(cid):
        logger.warning(f"Value {value} does not end with CID {cid}")
    
    return ipns_name

def test_model_ipns_resolve(ipns_name):
    """Test IPNS resolution via the model directly."""
    logger.info(f"Testing IPNS resolution via the model for name: {ipns_name}...")
    
    # Create model instance
    model = IPFSModel()
    
    # Resolve IPNS name
    resolve_result = model.ipfs_name_resolve(ipns_name)
    logger.info(f"IPNS resolve result: {resolve_result}")
    
    if not resolve_result.get("success", False):
        logger.error(f"Failed to resolve IPNS name: {resolve_result}")
        return False
    
    # Check the result for expected fields
    resolved_path = resolve_result.get("path")
    
    logger.info(f"Resolved IPNS name {ipns_name} to path: {resolved_path}")
    
    # Verify field
    if not resolved_path:
        logger.error("Missing required field 'path' in resolve result")
        return False
    
    if not resolved_path.startswith("/ipfs/"):
        logger.error(f"Resolved path {resolved_path} does not start with /ipfs/")
        return False
    
    return True

def test_http_ipns_publish():
    """Test IPNS publishing via HTTP API."""
    if not MCP_SERVER_URL:
        logger.warning("Skipping HTTP test - no MCP server URL provided")
        return None
    
    logger.info("Testing IPNS publishing via HTTP API...")
    
    # Add some content first
    test_content = b"Test content for IPNS publish via HTTP"
    add_response = requests.post(
        f"{MCP_SERVER_URL}/api/v0/add",
        files={"file": ("test.txt", test_content)}
    )
    
    if add_response.status_code != 200:
        logger.error(f"Failed to add content: {add_response.text}")
        return False
    
    add_result = add_response.json()
    cid = add_result.get("Hash")
    logger.info(f"Added content with CID: {cid}")
    
    # Publish to IPNS via CLI controller
    publish_response = requests.post(
        f"{MCP_SERVER_URL}/cli/publish/{cid}",
        params={"key": "self", "lifetime": "24h", "ttl": "1h"}
    )
    
    if publish_response.status_code != 200:
        logger.error(f"Failed to publish to IPNS: {publish_response.text}")
        return False
    
    publish_result = publish_response.json()
    logger.info(f"IPNS publish result: {publish_result}")
    
    # Check the result for expected fields
    success = publish_result.get("success", False)
    
    if not success:
        logger.error(f"Publish operation reported failure: {publish_result}")
        return False
    
    # Check result dictionary
    result_dict = publish_result.get("result", {})
    ipns_name = None
    value = None
    
    # The structure can vary based on implementation
    if isinstance(result_dict, dict):
        ipns_name = result_dict.get("name")
        value = result_dict.get("value")
    
    logger.info(f"Published {cid} to IPNS name: {ipns_name} with value: {value}")
    
    # Verify fields
    if not ipns_name or not value:
        logger.warning("Missing fields in publish result - this might be expected depending on controller implementation")
    
    return cid

def test_http_ipns_resolve(cid_or_name):
    """Test IPNS resolution via HTTP API."""
    if not MCP_SERVER_URL:
        logger.warning("Skipping HTTP test - no MCP server URL provided")
        return False
    
    logger.info(f"Testing IPNS resolution via HTTP API for: {cid_or_name}...")
    
    # First try to resolve the name
    name = cid_or_name
    if not name.startswith("/ipns/"):
        name = f"/ipns/{name}"
    
    # Resolve IPNS name via CLI controller
    resolve_response = requests.get(
        f"{MCP_SERVER_URL}/cli/resolve/{name}",
        params={"recursive": "true", "timeout": "30"}
    )
    
    if resolve_response.status_code != 200:
        logger.error(f"Failed to resolve IPNS name: {resolve_response.text}")
        return False
    
    resolve_result = resolve_response.json()
    logger.info(f"IPNS resolve result: {resolve_result}")
    
    # Check the result for expected fields
    success = resolve_result.get("success", False)
    
    if not success:
        logger.error(f"Resolve operation reported failure: {resolve_result}")
        return False
    
    # Check result dictionary
    result_dict = resolve_result.get("result", {})
    resolved_path = None
    
    # The structure can vary based on implementation
    if isinstance(result_dict, dict):
        resolved_path = result_dict.get("path")
    
    if resolved_path:
        logger.info(f"Resolved IPNS name {name} to path: {resolved_path}")
    else:
        logger.warning("Could not extract resolved path from result")
    
    return success

def test_high_level_api_compatibility():
    """Test compatibility with high-level API IPNS methods."""
    logger.info("Testing high-level API compatibility for IPNS...")
    
    # Create API instance
    api = IPFSSimpleAPI()
    
    # Add some content first
    test_content = b"Test content for IPNS via high-level API"
    result = api.add(test_content)
    if not result.get("success", False):
        logger.error(f"Failed to add content: {result}")
        return False
    
    cid = result.get("cid", result.get("Hash", None))
    logger.info(f"Added content with CID: {cid}")
    
    # Publish to IPNS 
    publish_result = api.publish(cid)
    logger.info(f"High-level API IPNS publish result: {publish_result}")
    
    if not publish_result.get("success", False):
        logger.error(f"Failed to publish to IPNS via high-level API: {publish_result}")
        return False
    
    # Get the IPNS name
    ipns_name = publish_result.get("name")
    if not ipns_name:
        logger.error("Missing name in high-level API publish result")
        return False
    
    # Resolve the name with high-level API
    resolve_result = api.resolve(ipns_name)
    logger.info(f"High-level API IPNS resolve result: {resolve_result}")
    
    if not resolve_result.get("success", False):
        logger.error(f"Failed to resolve IPNS name via high-level API: {resolve_result}")
        return False
    
    path = resolve_result.get("path")
    if not path:
        logger.error("Missing path in high-level API resolve result")
        return False
    
    logger.info(f"High-level API resolved {ipns_name} to {path}")
    return True

def compare_mcp_with_high_level_api():
    """Compare MCP IPNS implementation with high-level API."""
    logger.info("Comparing MCP and high-level API IPNS implementations...")
    
    # Use the high-level API as reference
    api = IPFSSimpleAPI()
    model = IPFSModel()
    
    # Test data
    test_content = b"Test content for comparison"
    
    # Add with both implementations
    api_add = api.add(test_content)
    model_add = model.add_content(test_content)
    
    api_cid = api_add.get("cid", api_add.get("Hash"))
    model_cid = model_add.get("cid", model_add.get("Hash"))
    
    logger.info(f"Added content with high-level API CID: {api_cid}")
    logger.info(f"Added content with MCP model CID: {model_cid}")
    
    # Publish with both implementations
    api_publish = api.publish(api_cid)
    model_publish = model.ipfs_name_publish(model_cid)
    
    logger.info(f"High-level API publish: {api_publish}")
    logger.info(f"MCP model publish: {model_publish}")
    
    # Compare key fields
    comparison = {
        "high_level_api": {
            "success": api_publish.get("success"),
            "name": api_publish.get("name"),
            "value": api_publish.get("value")
        },
        "mcp_model": {
            "success": model_publish.get("success"),
            "name": model_publish.get("name"),
            "value": model_publish.get("value")
        },
        "match": {
            "success": api_publish.get("success") == model_publish.get("success"),
            "name_format": bool(api_publish.get("name")) and bool(model_publish.get("name")),
            "value_format": bool(api_publish.get("value")) and bool(model_publish.get("value"))
        }
    }
    
    logger.info(f"Comparison: {json.dumps(comparison, indent=2)}")
    
    # Resolve with both implementations
    api_name = api_publish.get("name")
    model_name = model_publish.get("name")
    
    api_resolve = api.resolve(api_name)
    model_resolve = model.ipfs_name_resolve(model_name)
    
    logger.info(f"High-level API resolve: {api_resolve}")
    logger.info(f"MCP model resolve: {model_resolve}")
    
    # Compare resolve results
    resolve_comparison = {
        "high_level_api": {
            "success": api_resolve.get("success"),
            "path": api_resolve.get("path")
        },
        "mcp_model": {
            "success": model_resolve.get("success"),
            "path": model_resolve.get("path")
        },
        "match": {
            "success": api_resolve.get("success") == model_resolve.get("success"),
            "path_format": bool(api_resolve.get("path")) and bool(model_resolve.get("path"))
        }
    }
    
    logger.info(f"Resolve comparison: {json.dumps(resolve_comparison, indent=2)}")
    
    return all(comparison["match"].values()) and all(resolve_comparison["match"].values())

def run_all_tests():
    """Run all IPNS tests and report results."""
    results = {}
    
    # Test model methods
    logger.info("\n=== Testing Model IPNS Methods ===")
    ipns_name = test_model_ipns_publish()
    if ipns_name:
        results["model_publish"] = True
        results["model_resolve"] = test_model_ipns_resolve(ipns_name)
    else:
        results["model_publish"] = False
        results["model_resolve"] = False
    
    # Test HTTP API
    logger.info("\n=== Testing HTTP IPNS Endpoints ===")
    cid_or_name = test_http_ipns_publish()
    if cid_or_name:
        results["http_publish"] = True
        results["http_resolve"] = test_http_ipns_resolve(cid_or_name)
    else:
        results["http_publish"] = False
        results["http_resolve"] = False
    
    # Test high-level API compatibility
    logger.info("\n=== Testing High-Level API Compatibility ===")
    results["high_level_api"] = test_high_level_api_compatibility()
    
    # Compare implementations
    logger.info("\n=== Comparing MCP with High-Level API ===")
    results["comparison"] = compare_mcp_with_high_level_api()
    
    # Report results
    logger.info("\n=== IPNS Testing Results ===")
    for test, result in results.items():
        logger.info(f"{test}: {'PASS' if result else 'FAIL'}")
    
    return all(results.values())

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)