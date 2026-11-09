#!/usr/bin/env python3
"""
Distributed Controller Test Script

This script specifically tests the distributed controller endpoints of the MCP server
"""

import requests
import json
import time
import sys
import os

def run_test(endpoint, method="GET", data=None, files=None, 
           headers=None, test_name=None, expected_status=200, base_url="http://localhost:9999"):
    """Run a test on a specific endpoint."""
    if test_name is None:
        test_name = f"{method} {endpoint}"
        
    url = f"{base_url}{endpoint}"
    print(f"\n[TEST] {test_name}")
    print(f"Request: {method} {url}")
    
    if data:
        if isinstance(data, dict) and not any(isinstance(v, (bytes, bytearray)) for v in data.values()):
            try:
                print(f"Data: {json.dumps(data)}")
            except:
                print(f"Data: [Complex data structure]")
        else:
            print(f"Data: [Binary or complex data]")
            
    start_time = time.time()
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            if files:
                response = requests.post(url, files=files, headers=headers)
            elif headers and headers.get("Content-Type") == "application/json":
                response = requests.post(url, json=data, headers=headers)
            else:
                response = requests.post(url, data=data, headers=headers)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        elapsed = time.time() - start_time
        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.3f}s")
        
        try:
            response_data = response.json()
            print(f"Response: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response: {response.text[:500]}")
            
        # Check status
        success = response.status_code == expected_status
        if success:
            print(f"✅ Test passed: {test_name}")
        else:
            print(f"❌ Test failed: {test_name}")
            print(f"Expected status: {expected_status}, got: {response.status_code}")
        
        return response
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print(f"❌ Test failed: {test_name}")
        return None

def test_discover_peers():
    """Test peer discovery."""
    print("\n=== Testing Peer Discovery ===")
    
    discovery_data = {
        "discovery_methods": ["mdns", "dht", "bootstrap"],
        "max_peers": 10,
        "timeout_seconds": 10,
        "discovery_namespace": "ipfs-kit-test"
    }
    
    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/distributed/peers/discover", "POST", 
                       data=discovery_data, headers=headers, 
                       test_name="Discover Peers")
    
    return response and response.status_code == 200

def test_list_peers():
    """Test listing known peers."""
    print("\n=== Testing List Known Peers ===")
    
    response = run_test("/api/v0/mcp/distributed/peers/list", "GET", 
                       test_name="List Known Peers")
    
    return response and response.status_code == 200

def test_register_node():
    """Test node registration."""
    print("\n=== Testing Node Registration ===")
    
    node_data = {
        "role": "worker",
        "capabilities": ["storage", "compute"],
        "resources": {
            "cpu_count": 4,
            "memory_gb": 8,
            "disk_gb": 100
        },
        "address": "127.0.0.1:4001"
    }
    
    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/distributed/nodes/register", "POST", 
                       data=node_data, headers=headers, 
                       test_name="Register Node")
    
    return response and response.status_code == 200

def test_list_nodes():
    """Test listing nodes."""
    print("\n=== Testing List Nodes ===")
    
    response = run_test("/api/v0/mcp/distributed/nodes/list", "GET", 
                       test_name="List Nodes")
    
    return response and response.status_code == 200

def test_cache_operation():
    """Test cluster cache operations."""
    print("\n=== Testing Cluster Cache Operations ===")
    
    # Test put operation
    cache_put_data = {
        "operation": "put",
        "key": "test_key",
        "value": "test_value",
        "metadata": {"type": "string", "test": True},
        "propagate": True,
        "ttl_seconds": 3600
    }
    
    headers = {"Content-Type": "application/json"}
    put_response = run_test("/api/v0/mcp/distributed/cache", "POST", 
                          data=cache_put_data, headers=headers, 
                          test_name="Cache Put Operation")
    
    if not (put_response and put_response.status_code == 200):
        return False
    
    # Test get operation
    cache_get_data = {
        "operation": "get",
        "key": "test_key"
    }
    
    get_response = run_test("/api/v0/mcp/distributed/cache", "POST", 
                          data=cache_get_data, headers=headers, 
                          test_name="Cache Get Operation")
    
    # Test cache status
    status_response = run_test("/api/v0/mcp/distributed/cache/status", "GET", 
                             test_name="Cache Status")
    
    return (get_response and get_response.status_code == 200 and 
            status_response and status_response.status_code == 200)

def test_state_operations():
    """Test cluster state operations."""
    print("\n=== Testing Cluster State Operations ===")
    
    # Test state update
    state_update_data = {
        "operation": "update",
        "path": "test.path",
        "value": {"status": "active", "timestamp": time.time()}
    }
    
    headers = {"Content-Type": "application/json"}
    update_response = run_test("/api/v0/mcp/distributed/state", "POST", 
                             data=state_update_data, headers=headers, 
                             test_name="State Update Operation")
    
    if not (update_response and update_response.status_code == 200):
        return False
    
    # Test state query
    state_query_data = {
        "operation": "query",
        "path": "test.path"
    }
    
    query_response = run_test("/api/v0/mcp/distributed/state", "POST", 
                            data=state_query_data, headers=headers, 
                            test_name="State Query Operation")
    
    # Test state synchronization using the simple_sync2 endpoint
    sync_response = run_test("/api/v0/mcp/distributed/state/sync2", "POST",
                         headers=headers,
                         test_name="State Synchronization via simple_sync2")
    
    # Return true if all tests passed
    return (query_response and query_response.status_code == 200 and
            sync_response and sync_response.status_code == 200)

def test_task_operations():
    """Test distributed task operations."""
    print("\n=== Testing Distributed Task Operations ===")
    
    # Submit a task
    task_data = {
        "task_type": "test_task",
        "parameters": {
            "data": "test data",
            "operation": "process"
        },
        "priority": 5,
        "target_role": "worker"
    }
    
    headers = {"Content-Type": "application/json"}
    submit_response = run_test("/api/v0/mcp/distributed/tasks/submit", "POST", 
                             data=task_data, headers=headers, 
                             test_name="Submit Task")
    
    if not (submit_response and submit_response.status_code == 200):
        return False
    
    # Get the task ID from the response
    task_id = submit_response.json().get("task_id")
    if not task_id:
        print("No task ID in response, can't check status")
        return False
    
    # Get task status
    status_response = run_test(f"/api/v0/mcp/distributed/tasks/{task_id}/status", "GET", 
                             test_name="Get Task Status")
    
    # List all tasks
    list_response = run_test("/api/v0/mcp/distributed/tasks/list", "GET", 
                           test_name="List Tasks")
    
    # Cancel the task
    cancel_response = run_test(f"/api/v0/mcp/distributed/tasks/{task_id}/cancel", "POST", 
                             headers=headers, test_name="Cancel Task")
    
    return (status_response and status_response.status_code == 200 and 
            list_response and list_response.status_code == 200 and 
            cancel_response and cancel_response.status_code == 200)

def run_all_tests():
    """Run all distributed controller tests."""
    print("\n=== Running All Distributed Controller Tests ===")
    
    success_count = 0
    total_tests = 6
    
    # Test 1: Discover Peers
    if test_discover_peers():
        success_count += 1
    
    # Test 2: List Peers
    if test_list_peers():
        success_count += 1
    
    # Test 3: Register Node
    if test_register_node():
        success_count += 1
    
    # Test 4: List Nodes
    if test_list_nodes():
        success_count += 1
    
    # Test 5: Cache Operations
    if test_cache_operation():
        success_count += 1
    
    # Test 6: State Operations
    if test_state_operations():
        success_count += 1
    
    # Test 7: Task Operations
    if test_task_operations():
        success_count += 1
        total_tests += 1  # Add this test to total if it runs
    
    # Print summary
    print("\n=== Test Summary ===")
    print(f"Total tests: {total_tests}")
    print(f"Successful: {success_count}")
    print(f"Failed: {total_tests - success_count}")
    print(f"Success rate: {success_count/total_tests:.1%}")

if __name__ == "__main__":
    # Allow specifying base URL as command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9999"
    
    # Run all tests
    run_all_tests()