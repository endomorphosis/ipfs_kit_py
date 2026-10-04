#!/usr/bin/env python3
# examples/wal_api_example.py

"""
Example showing how to use the Write-Ahead Log (WAL) API via HTTP endpoints.

This example demonstrates:
1. Viewing the list of WAL operations
2. Getting details of a specific operation
3. Retrying a failed operation
4. Getting WAL metrics and status
5. Managing WAL configuration
6. Deleting operations from the WAL

The WAL API provides REST endpoints for monitoring and managing the fault-tolerance
system provided by the Write-Ahead Log.
"""

import os
import json
import time
import requests
import argparse
from pprint import pprint

# Define API endpoint
DEFAULT_API_URL = "http://localhost:8000"

def setup_api_server():
    """Setup API server for demonstration."""
    try:
        # Try to import and run the server
        from ipfs_kit_py import api
        
        # TODO: Implement server setup if needed
        print("Please start the API server manually with:")
        print("  uvicorn ipfs_kit_py.api:app --reload --port 8000")
        print("Press Enter when the server is running...")
        input()
    except ImportError:
        print("Failed to import ipfs_kit_py.api")
        print("Please start the API server manually.")
        return False
    
    return True

def list_operations(api_url, status=None, operation_type=None, backend=None, limit=10):
    """List WAL operations with optional filtering."""
    params = {}
    if status:
        params["status"] = status
    if operation_type:
        params["operation_type"] = operation_type
    if backend:
        params["backend"] = backend
    if limit:
        params["limit"] = limit
    
    response = requests.get(f"{api_url}/api/v0/wal/operations", params=params)
    if response.status_code == 200:
        result = response.json()
        print("\n=== WAL Operations ===")
        print(f"Total operations: {result.get('count', 0)}")
        for op in result.get("operations", []):
            print(f"- Operation {op['operation_id']}: {op['type']} - {op['status']}")
        return result.get("operations", [])
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return []

def get_operation_details(api_url, operation_id):
    """Get details of a specific WAL operation."""
    response = requests.get(f"{api_url}/api/v0/wal/operations/{operation_id}")
    if response.status_code == 200:
        result = response.json()
        print("\n=== Operation Details ===")
        op = result.get("operation_data", {})
        print(f"ID: {op.get('operation_id')}")
        print(f"Type: {op.get('type')}")
        print(f"Backend: {op.get('backend')}")
        print(f"Status: {op.get('status')}")
        print(f"Created: {op.get('created_at')}")
        print(f"Updated: {op.get('updated_at')}")
        print(f"Retry Count: {op.get('retry_count')}")
        print(f"Parameters: {json.dumps(op.get('parameters', {}), indent=2)}")
        if op.get("result"):
            print(f"Result: {json.dumps(op.get('result'), indent=2)}")
        if op.get("error"):
            print(f"Error: {op.get('error')}")
        return op
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def retry_operation(api_url, operation_id):
    """Retry a failed WAL operation."""
    response = requests.post(f"{api_url}/api/v0/wal/operations/{operation_id}/retry")
    if response.status_code == 200:
        result = response.json()
        print("\n=== Operation Retry ===")
        print(f"Operation {result.get('operation_id')} status changed to {result.get('new_status')}")
        return True
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return False

def get_wal_metrics(api_url):
    """Get WAL metrics and backend status."""
    response = requests.get(f"{api_url}/api/v0/wal/metrics")
    if response.status_code == 200:
        result = response.json()
        print("\n=== WAL Metrics ===")
        print(f"Total operations: {result.get('total_operations')}")
        print(f"Pending operations: {result.get('pending_operations')}")
        print(f"Completed operations: {result.get('completed_operations')}")
        print(f"Failed operations: {result.get('failed_operations')}")
        
        print("\nBackend Status:")
        for backend, status in result.get('backend_status', {}).items():
            status_text = "Available" if status else "Unavailable"
            print(f"- {backend}: {status_text}")
        return result
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def get_wal_config(api_url):
    """Get current WAL configuration."""
    response = requests.get(f"{api_url}/api/v0/wal/config")
    if response.status_code == 200:
        result = response.json()
        config = result.get("config", {})
        print("\n=== WAL Configuration ===")
        print(f"Base Path: {config.get('base_path')}")
        print(f"Partition Size: {config.get('partition_size')}")
        print(f"Max Retries: {config.get('max_retries')}")
        print(f"Retry Delay: {config.get('retry_delay')} seconds")
        print(f"Archive Completed: {config.get('archive_completed')}")
        print(f"Process Interval: {config.get('process_interval')} seconds")
        print(f"Health Monitoring: {config.get('enable_health_monitoring')}")
        if config.get('enable_health_monitoring'):
            print(f"Health Check Interval: {config.get('health_check_interval')} seconds")
        return config
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def update_wal_config(api_url, config_updates):
    """Update WAL configuration."""
    response = requests.post(f"{api_url}/api/v0/wal/config", json=config_updates)
    if response.status_code == 200:
        result = response.json()
        print("\n=== Updated WAL Configuration ===")
        config = result.get("config", {})
        print(f"Max Retries: {config.get('max_retries')}")
        print(f"Retry Delay: {config.get('retry_delay')} seconds")
        print(f"Archive Completed: {config.get('archive_completed')}")
        print(f"Process Interval: {config.get('process_interval')} seconds")
        
        # Check for warning about settings that couldn't be updated
        if "warning" in result:
            print(f"\nWarning: {result['warning']}")
        return config
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def delete_operation(api_url, operation_id):
    """Delete a WAL operation."""
    response = requests.delete(f"{api_url}/api/v0/wal/operations/{operation_id}")
    if response.status_code == 200:
        result = response.json()
        print("\n=== Operation Deleted ===")
        print(f"Operation {result.get('operation_id')} deleted successfully")
        return True
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return False

def main():
    """Main function demonstrating WAL API usage."""
    parser = argparse.ArgumentParser(description="WAL API Example")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="API endpoint URL")
    args = parser.parse_args()
    
    api_url = args.api_url.rstrip("/")
    
    # Check if server is running
    try:
        response = requests.get(f"{api_url}/health")
        if response.status_code != 200:
            print(f"API server not available. Status code: {response.status_code}")
            return
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to API server at {api_url}")
        setup_api_server()
    
    # Simulate some operations to create WAL entries
    print("\nCreating sample operations through the WAL...")
    
    # Content addition - should succeed
    add_response = requests.post(
        f"{api_url}/api/v0/add",
        files={"file": ("test.txt", b"Hello WAL API Example!")},
        data={"pin": "true"}
    )
    if add_response.status_code == 200:
        print("Added content to IPFS successfully")
        add_result = add_response.json()
        content_cid = add_result.get("cid")
        print(f"Content CID: {content_cid}")
    else:
        print(f"Error adding content: {add_response.status_code} - {add_response.text}")
        content_cid = "QmTestCID"  # Fallback CID for demo
    
    # List all operations
    operations = list_operations(api_url)
    
    # Get metrics
    get_wal_metrics(api_url)
    
    # Get configuration
    config = get_wal_config(api_url)
    
    # If we have operations, show details of the first one
    if operations:
        operation_id = operations[0]["operation_id"]
        operation = get_operation_details(api_url, operation_id)
        
        # For demonstration, let's retry an operation
        if operation and operation.get("status") == "failed":
            retry_operation(api_url, operation_id)
            # Check the updated status
            time.sleep(1)  # Give it a second to update
            get_operation_details(api_url, operation_id)
    
    # Update configuration
    if config:
        print("\nUpdating WAL configuration...")
        new_config = {
            "max_retries": 10,  # Increase max retries
            "retry_delay": 30   # Reduce retry delay
        }
        update_wal_config(api_url, new_config)
    
    # Filter operations by status
    print("\nListing pending operations...")
    pending_ops = list_operations(api_url, status="pending")
    
    print("\nListing completed operations...")
    completed_ops = list_operations(api_url, status="completed")
    
    # Delete an operation if available
    if operations:
        operation_id = operations[-1]["operation_id"]
        print(f"\nDeleting operation {operation_id}...")
        delete_operation(api_url, operation_id)
        
        # Verify deletion
        print("\nListing operations after deletion...")
        list_operations(api_url)
    
    print("\nWAL API example complete.")

if __name__ == "__main__":
    main()