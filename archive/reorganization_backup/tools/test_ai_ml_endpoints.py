#!/usr/bin/env python3
"""
Test Client for MCP Server AI/ML Integration

This script tests the AI/ML endpoints of the MCP server to verify
that the integration is working correctly.
"""

import argparse
import json
import sys
import time
import requests
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

def test_ai_ml_endpoints(base_url: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Test the AI/ML endpoints of the MCP server.
    
    Args:
        base_url: The base URL of the MCP server
        verbose: Whether to print verbose output
        
    Returns:
        A dictionary with test results
    """
    # Ensure the base URL has the correct format
    if not base_url.endswith('/'):
        base_url += '/'
    
    # The AI/ML endpoints base URL
    ai_base_url = f"{base_url}api/v0/ai"
    
    # Results dictionary
    results = {
        "success": True,
        "timestamp": time.time(),
        "base_url": base_url,
        "ai_base_url": ai_base_url,
        "endpoints_tested": 0,
        "endpoints_succeeded": 0,
        "endpoints_failed": 0,
        "endpoint_results": {}
    }
    
    # Helper function for making requests and handling errors
    def make_request(endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{ai_base_url}/{endpoint}"
        result = {
            "url": url,
            "method": method,
            "success": False,
            "status_code": None,
            "response": None,
            "error": None
        }
        
        try:
            if verbose:
                print(f"Testing {method} {url}...")
            
            if method == "GET":
                response = requests.get(url, timeout=10)
            elif method == "POST":
                response = requests.post(url, json=data, timeout=10)
            elif method == "PUT":
                response = requests.put(url, json=data, timeout=10)
            elif method == "DELETE":
                response = requests.delete(url, timeout=10)
            else:
                result["error"] = f"Unsupported method: {method}"
                return result
            
            result["status_code"] = response.status_code
            
            # Try to parse response as JSON
            try:
                result["response"] = response.json()
            except json.JSONDecodeError:
                result["response"] = response.text
            
            # Check if the request was successful
            if 200 <= response.status_code < 300:
                result["success"] = True
            else:
                result["error"] = f"HTTP Error {response.status_code}: {response.reason}"
            
            return result
        except requests.exceptions.RequestException as e:
            result["error"] = str(e)
            return result
    
    # Define the endpoints to test
    endpoints_to_test = [
        # Model Registry endpoints
        {"name": "list_models", "endpoint": "models", "method": "GET"},
        # Model Deployment endpoints
        {"name": "list_deployments", "endpoint": "deployments", "method": "GET"},
        # Test creating a model (will likely fail but we want to see the correct error)
        {"name": "create_model", "endpoint": "models", "method": "POST", "data": {
            "name": "TestModel",
            "version": "1.0.0",
            "framework": "pytorch",
            "description": "Test model for AI/ML integration"
        }}
    ]
    
    # Test each endpoint
    for endpoint_test in endpoints_to_test:
        endpoint_name = endpoint_test["name"]
        result = make_request(
            endpoint_test["endpoint"], 
            endpoint_test["method"], 
            endpoint_test.get("data")
        )
        
        results["endpoints_tested"] += 1
        if result["success"]:
            results["endpoints_succeeded"] += 1
        else:
            results["endpoints_failed"] += 1
        
        results["endpoint_results"][endpoint_name] = result
        
        if verbose:
            print(f"Endpoint {endpoint_name}: {'SUCCESS' if result['success'] else 'FAILURE'}")
            if not result["success"]:
                print(f"  Error: {result['error']}")
    
    # Update overall success status
    results["success"] = results["endpoints_failed"] == 0
    
    return results

def main():
    """Main entry point for the test client."""
    parser = argparse.ArgumentParser(description="Test Client for MCP Server AI/ML Integration")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Base URL of the MCP server")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--output", "-o", type=str, help="Output file for test results (JSON format)")
    args = parser.parse_args()
    
    # Run the tests
    print(f"Testing AI/ML endpoints at {args.url}...")
    results = test_ai_ml_endpoints(args.url, args.verbose)
    
    # Print summary
    print("\nTest Summary:")
    print(f"Base URL: {results['base_url']}")
    print(f"AI/ML API URL: {results['ai_base_url']}")
    print(f"Endpoints Tested: {results['endpoints_tested']}")
    print(f"Endpoints Succeeded: {results['endpoints_succeeded']}")
    print(f"Endpoints Failed: {results['endpoints_failed']}")
    print(f"Overall Status: {'SUCCESS' if results['success'] else 'FAILURE'}")
    
    # Save results to file if requested
    if args.output:
        try:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nTest results saved to {args.output}")
        except Exception as e:
            print(f"Error saving results to {args.output}: {e}")
    
    # Exit with appropriate status code
    sys.exit(0 if results["success"] else 1)

if __name__ == "__main__":
    main()