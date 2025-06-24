#!/usr/bin/env python3
"""
API comparison tool for the MCP server and main API.
Identifies missing features in the MCP server compared to the main API.
"""

import sys
import requests
import json
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# URLs
MCP_BASE_URL = "http://localhost:9999"
MAIN_API_URL = "http://localhost:8000"

def get_openapi_schema(base_url):
    """Get OpenAPI schema from a server."""
    try:
        response = requests.get(f"{base_url}/openapi.json", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get OpenAPI schema from {base_url}: {e}")
        return None

def extract_endpoints(schema):
    """Extract endpoints from OpenAPI schema."""
    if not schema or "paths" not in schema:
        return []

    endpoints = []
    for path, methods in schema["paths"].items():
        for method, details in methods.items():
            if method.lower() in ["get", "post", "put", "delete", "patch"]:
                endpoints.append({
                    "path": path,
                    "method": method.upper(),
                    "summary": details.get("summary", ""),
                    "description": details.get("description", ""),
                    "tags": details.get("tags", [])
                })

    return endpoints

def test_endpoint(url, method="GET", json_data=None):
    """Test if an endpoint is working."""
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        else:
            response = requests.request(
                method,
                url,
                json=json_data,
                timeout=5
            )

        return {
            "status_code": response.status_code,
            "working": response.status_code < 500  # Consider 4xx as "working but unauthorized/invalid"
        }
    except Exception as e:
        logger.debug(f"Error testing {method} {url}: {e}")
        return {"status_code": 0, "working": False, "error": str(e)}

def compare_apis():
    """Compare MCP API with main API and identify missing features."""
    # Get schemas
    mcp_schema = get_openapi_schema(MCP_BASE_URL)
    main_schema = get_openapi_schema(MAIN_API_URL)

    if not mcp_schema:
        logger.error("Failed to get MCP schema")
        return None

    if not main_schema:
        logger.error("Failed to get main API schema")
        return None

    # Extract endpoints
    mcp_endpoints = extract_endpoints(mcp_schema)
    main_endpoints = extract_endpoints(main_schema)

    logger.info(f"Found {len(mcp_endpoints)} endpoints in MCP API")
    logger.info(f"Found {len(main_endpoints)} endpoints in main API")

    # Group endpoints by tag for cleaner reporting
    mcp_endpoints_by_tag = {}
    for endpoint in mcp_endpoints:
        for tag in endpoint["tags"] or ["untagged"]:
            if tag not in mcp_endpoints_by_tag:
                mcp_endpoints_by_tag[tag] = []
            mcp_endpoints_by_tag[tag].append(endpoint)

    main_endpoints_by_tag = {}
    for endpoint in main_endpoints:
        for tag in endpoint["tags"] or ["untagged"]:
            if tag not in main_endpoints_by_tag:
                main_endpoints_by_tag[tag] = []
            main_endpoints_by_tag[tag].append(endpoint)

    # Find tags only in main API
    main_only_tags = set(main_endpoints_by_tag.keys()) - set(mcp_endpoints_by_tag.keys())
    logger.info(f"Found {len(main_only_tags)} tags only in main API: {main_only_tags}")

    # Test sample endpoints from each API to verify
    logger.info("Testing sample endpoints from each API...")

    # Test MCP health endpoint
    mcp_health = test_endpoint(f"{MCP_BASE_URL}/api/v0/mcp/health")
    logger.info(f"MCP health endpoint: {mcp_health}")

    # Test main API health endpoint
    main_health = test_endpoint(f"{MAIN_API_URL}/api/v0/health")
    logger.info(f"Main API health endpoint: {main_health}")

    # Identify major feature areas in main API missing from MCP
    missing_features = []

    # Check IPNS functionality
    if "ipns" in main_only_tags:
        missing_features.append({
            "feature": "IPNS Functionality",
            "endpoints": [e for e in main_endpoints if "ipns" in e["path"].lower()],
            "description": "IPNS publishing and resolving endpoints"
        })

    # Check for AI/ML integration
    ai_ml_endpoints = [e for e in main_endpoints if any(kw in e["path"].lower()
                                              for kw in ["ai", "ml", "vector", "embedding", "model"])]
    mcp_ai_ml_endpoints = [e for e in mcp_endpoints if any(kw in e["path"].lower()
                                               for kw in ["ai", "ml", "vector", "embedding", "model"])]

    if ai_ml_endpoints and not mcp_ai_ml_endpoints:
        missing_features.append({
            "feature": "AI/ML Integration",
            "endpoints": ai_ml_endpoints,
            "description": "AI and ML functionality including vectors, embeddings, and models"
        })

    # Check for GraphQL
    graphql_endpoints = [e for e in main_endpoints if "graphql" in e["path"].lower()]
    if graphql_endpoints and not any("graphql" in e["path"].lower() for e in mcp_endpoints):
        missing_features.append({
            "feature": "GraphQL Support",
            "endpoints": graphql_endpoints,
            "description": "GraphQL API for flexible queries"
        })

    # Check for WAL (Write-Ahead Log)
    wal_endpoints = [e for e in main_endpoints if "wal" in e["path"].lower()]
    if wal_endpoints and not any("wal" in e["path"].lower() for e in mcp_endpoints):
        missing_features.append({
            "feature": "Write-Ahead Log (WAL)",
            "endpoints": wal_endpoints,
            "description": "Write-Ahead Log for durable operations"
        })

    # Check for cluster management
    cluster_endpoints = [e for e in main_endpoints if "cluster" in e["path"].lower()]
    mcp_cluster_endpoints = [e for e in mcp_endpoints if "cluster" in e["path"].lower()]

    if cluster_endpoints and not mcp_cluster_endpoints:
        missing_features.append({
            "feature": "Cluster Management",
            "endpoints": cluster_endpoints,
            "description": "Cluster management capabilities"
        })

    # Check for filesystem journal
    fs_endpoints = [e for e in main_endpoints if "fs" in e["path"].lower() or "filesystem" in e["path"].lower()]
    mcp_fs_endpoints = [e for e in mcp_endpoints if "fs" in e["path"].lower() or "filesystem" in e["path"].lower()]

    # Test if the MCP filesystem journal endpoint is working or just defined
    if mcp_fs_endpoints:
        fs_endpoint = mcp_fs_endpoints[0]["path"]
        fs_method = mcp_fs_endpoints[0]["method"]
        fs_test = test_endpoint(f"{MCP_BASE_URL}{fs_endpoint}", method=fs_method)

        if not fs_test["working"]:
            missing_features.append({
                "feature": "Filesystem Journal",
                "endpoints": mcp_fs_endpoints,
                "description": "Filesystem journal is defined but not working",
                "status": fs_test
            })
    elif fs_endpoints:
        missing_features.append({
            "feature": "Filesystem Journal",
            "endpoints": fs_endpoints,
            "description": "Filesystem journal functionality"
        })

    # Now test MCP IPNS endpoints
    ipns_endpoints = [e for e in mcp_endpoints if "publish" in e["path"].lower() or "resolve" in e["path"].lower()]

    if ipns_endpoints:
        # Test publish endpoint
        publish_endpoint = next((e for e in ipns_endpoints if "publish" in e["path"].lower()), None)
        if publish_endpoint:
            test_cid = "QmPChd2hVbrJ6bfo3WBcTW4iZnpHm8TEzWkLHmLpXhF68A"  # Test CID
            publish_test = test_endpoint(
                f"{MCP_BASE_URL}{publish_endpoint['path'].replace('{cid}', test_cid)}",
                method=publish_endpoint["method"],
                json_data={"key": "self", "lifetime": "24h"}
            )

            if publish_test["status_code"] == 200:
                # Test if the response indicates a real implementation
                try:
                    response = requests.request(
                        publish_endpoint["method"],
                        f"{MCP_BASE_URL}{publish_endpoint['path'].replace('{cid}', test_cid)}",
                        json={"key": "self", "lifetime": "24h"}
                    )

                    response_data = response.json()

                    # Check if there's an error indicating missing implementation
                    if (not response_data.get("success", True) or
                        "has no attribute" in str(response_data) or
                        "not implemented" in str(response_data).lower()):
                        missing_features.append({
                            "feature": "IPNS Functionality",
                            "endpoints": ipns_endpoints,
                            "description": "IPNS functionality is defined but not working",
                            "error": response_data
                        })
                except Exception as e:
                    logger.error(f"Error testing IPNS publish: {e}")

    # Test AI/ML endpoints in MCP
    ai_endpoints = [e for e in mcp_endpoints if "ai" in e["path"].lower() or "vector" in e["path"].lower()]

    if ai_endpoints:
        # Test AI model list endpoint
        ai_endpoint = next((e for e in ai_endpoints if "model" in e["path"].lower() and "list" in e["path"].lower()), None)
        if ai_endpoint:
            ai_test = test_endpoint(f"{MCP_BASE_URL}{ai_endpoint['path']}", method=ai_endpoint["method"])

            if ai_test["status_code"] == 200:
                # Test if the response is simulated
                try:
                    response = requests.request(ai_endpoint["method"], f"{MCP_BASE_URL}{ai_endpoint['path']}")
                    response_data = response.json()

                    # Check for simulation note
                    if isinstance(response_data, dict) and "result" in response_data:
                        result = response_data["result"]
                        if isinstance(result, dict) and "simulation_note" in result:
                            missing_features.append({
                                "feature": "AI/ML Integration",
                                "endpoints": ai_endpoints,
                                "description": "AI/ML integration is simulated, not fully implemented",
                                "simulation_note": result["simulation_note"]
                            })
                except Exception as e:
                    logger.error(f"Error testing AI model list: {e}")

    return {
        "mcp_schema": mcp_schema,
        "main_schema": main_schema,
        "mcp_endpoints": mcp_endpoints,
        "main_endpoints": main_endpoints,
        "mcp_endpoints_by_tag": mcp_endpoints_by_tag,
        "main_endpoints_by_tag": main_endpoints_by_tag,
        "main_only_tags": list(main_only_tags),
        "missing_features": missing_features
    }

def main():
    """Main entry point."""
    logger.info("Comparing MCP API with main API...")
    comparison = compare_apis()

    if not comparison:
        logger.error("Comparison failed")
        return 1

    # Print missing features
    logger.info(f"\n=== Missing Features ===")
    for feature in comparison["missing_features"]:
        logger.info(f"Feature: {feature['feature']}")
        logger.info(f"Description: {feature['description']}")
        if "endpoints" in feature:
            logger.info(f"Related Endpoints: {len(feature['endpoints'])}")
            for i, endpoint in enumerate(feature["endpoints"][:3]):  # Show just a few examples
                logger.info(f"  - {endpoint['method']} {endpoint['path']}")
            if len(feature["endpoints"]) > 3:
                logger.info(f"  - ... and {len(feature['endpoints'])-3} more")
        if "simulation_note" in feature:
            logger.info(f"Simulation Note: {feature['simulation_note']}")
        if "error" in feature:
            logger.info(f"Error: {feature['error']}")
        logger.info("")

    # Count by feature area
    logger.info("\n=== Summary ===")
    logger.info(f"Total Missing Features: {len(comparison['missing_features'])}")

    logger.info("\n== By Feature Area ==")
    feature_areas = [f["feature"] for f in comparison["missing_features"]]
    for area in sorted(set(feature_areas)):
        count = feature_areas.count(area)
        logger.info(f"{area}: {count}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
