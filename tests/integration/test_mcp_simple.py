#!/usr/bin/env python3
"""
Simple MCP Server feature tester
Identifies missing features by testing endpoints directly
"""

import sys
import json
import requests
import time

# MCP Server base URL
MCP_BASE_URL = "http://localhost:9999/api/v0/mcp"

def test_endpoint(url, method="GET", data=None, params=None, json_response=True):
    """Test an API endpoint and return the result."""
    try:
        print(f"\n--- Testing {method} {url} ---")
        if method == "GET":
            response = requests.get(url, params=params, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, params=params, timeout=5)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            if json_response:
                try:
                    result_data = response.json()
                    return {"success": True, "data": result_data, "status_code": response.status_code}
                except json.JSONDecodeError:
                    # Handle non-JSON responses
                    return {"success": True, "data": response.text, "status_code": response.status_code, "raw": True}
            else:
                return {"success": True, "data": response.text, "status_code": response.status_code, "raw": True}
        else:
            print(f"Error response: {response.text}")
            return {"success": False, "error": response.text, "status_code": response.status_code}
    except Exception as e:
        print(f"Request failed: {str(e)}")
        return {"success": False, "error": str(e)}

def main():
    results = {}
    
    # Test core server endpoints
    print("\n=== Testing Core Server Endpoints ===")
    
    # Health endpoint
    health_result = test_endpoint(f"{MCP_BASE_URL}/health")
    results["health"] = health_result
    print(json.dumps(health_result["data"] if health_result["success"] else health_result, indent=2))
    
    # Add content
    print("\n=== Testing IPFS Add ===")
    add_data = {"content": "Test content for MCP server testing"}
    add_result = test_endpoint(f"{MCP_BASE_URL}/ipfs/add", method="POST", data=add_data)
    results["ipfs_add"] = add_result
    print(json.dumps(add_result["data"] if add_result["success"] else add_result, indent=2))
    
    test_cid = None
    if add_result["success"] and "cid" in add_result.get("data", {}):
        test_cid = add_result["data"]["cid"]
        print(f"Added content with CID: {test_cid}")
    
    # Test CLI version
    print("\n=== Testing CLI Version ===")
    cli_version_result = test_endpoint(f"{MCP_BASE_URL}/cli/version")
    results["cli_version"] = cli_version_result
    print(json.dumps(cli_version_result["data"] if cli_version_result["success"] else cli_version_result, indent=2))
    
    # Test IPNS publish (should fail with meaningful error)
    if test_cid:
        print("\n=== Testing IPNS Publish ===")
        publish_data = {"key": "self", "lifetime": "24h", "ttl": "1h"}
        publish_result = test_endpoint(f"{MCP_BASE_URL}/cli/publish/{test_cid}", method="POST", data=publish_data)
        results["ipns_publish"] = publish_result
        print(json.dumps(publish_result["data"] if publish_result["success"] else publish_result, indent=2))
    
    # Test AI/ML model list (should return simulated data)
    print("\n=== Testing AI/ML Model List ===")
    ai_model_list_result = test_endpoint(f"{MCP_BASE_URL}/cli/ai/model/list")
    results["ai_model_list"] = ai_model_list_result
    print(json.dumps(ai_model_list_result["data"] if ai_model_list_result["success"] else ai_model_list_result, indent=2))
    
    # Test filesystem journal status
    print("\n=== Testing Filesystem Journal Status ===")
    fs_status_result = test_endpoint(f"{MCP_BASE_URL}/fs-journal/status")
    results["fs_journal_status"] = fs_status_result
    print(json.dumps(fs_status_result["data"] if fs_status_result["success"] else fs_status_result, indent=2))
    
    # Test WebRTC check
    print("\n=== Testing WebRTC Check ===")
    webrtc_check_result = test_endpoint(f"{MCP_BASE_URL}/webrtc/check")
    results["webrtc_check"] = webrtc_check_result
    print(json.dumps(webrtc_check_result["data"] if webrtc_check_result["success"] else webrtc_check_result, indent=2))
    
    # Identify missing features
    missing_features = []
    
    # Check IPNS functionality
    if "ipns_publish" in results and results["ipns_publish"]["success"]:
        data = results["ipns_publish"]["data"]
        if "result" in data and "error" in data["result"] and "has no attribute" in data["result"]["error"]:
            missing_features.append({
                "feature": "IPNS Functionality",
                "details": "IPNS publishing and resolving are not fully implemented",
                "error": data["result"]["error"]
            })
    
    # Check AI/ML functionality
    if "ai_model_list" in results and results["ai_model_list"]["success"]:
        data = results["ai_model_list"]["data"]
        if "result" in data and "simulation_note" in data["result"]:
            missing_features.append({
                "feature": "AI/ML Integration",
                "details": "AI/ML functionality is simulated, not fully implemented",
                "note": data["result"]["simulation_note"]
            })
    
    # Check filesystem journal
    if "fs_journal_status" in results and not results["fs_journal_status"]["success"]:
        error_text = results["fs_journal_status"].get("error", "")
        if "not enabled" in error_text or "Filesystem journaling is not enabled" in error_text:
            missing_features.append({
                "feature": "Filesystem Journal",
                "details": "Filesystem journaling is not enabled or fully implemented",
                "error": error_text
            })
    
    # Additional known missing features
    missing_features.extend([
        {
            "feature": "GraphQL Support",
            "details": "GraphQL API for flexible queries is not implemented in MCP server"
        },
        {
            "feature": "Write-Ahead Log (WAL)",
            "details": "Write-Ahead Log for durable operations is not implemented in MCP server"
        },
        {
            "feature": "Cluster Management",
            "details": "Comprehensive cluster management is not implemented in MCP server"
        }
    ])
    
    print("\n=== Missing Features ===")
    for feature in missing_features:
        print(f"Feature: {feature['feature']}")
        print(f"Details: {feature['details']}")
        if "error" in feature:
            print(f"Error: {feature['error']}")
        if "note" in feature:
            print(f"Note: {feature['note']}")
        print()

if __name__ == "__main__":
    main()