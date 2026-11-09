#!/usr/bin/env python3
"""
Peer WebSocket Controller Test Script

This script specifically tests the peer WebSocket controller endpoints of the MCP server
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

def test_check_websocket_support():
    """Test checking WebSocket support."""
    print("\n=== Testing Check WebSocket Support ===")
    
    response = run_test("/api/v0/mcp/peer/websocket/check", "GET", 
                       test_name="Check WebSocket Support")
    
    return response and response.status_code == 200

def test_start_server():
    """Test starting a peer WebSocket server."""
    print("\n=== Testing Start WebSocket Server ===")
    
    server_data = {
        "host": "127.0.0.1",
        "port": 8765,
        "max_peers": 100,
        "heartbeat_interval": 30,
        "peer_ttl": 300
    }
    
    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/peer/websocket/server/start", "POST", 
                       data=server_data, headers=headers, 
                       test_name="Start WebSocket Server")
    
    if response and response.status_code == 200:
        result = response.json()
        if result.get("success"):
            # Test server status
            time.sleep(1)  # Give server time to fully start
            return test_server_status()
    
    return False

def test_server_status():
    """Test getting WebSocket server status."""
    print("\n=== Testing WebSocket Server Status ===")
    
    response = run_test("/api/v0/mcp/peer/websocket/server/status", "GET", 
                       test_name="Get WebSocket Server Status")
    
    return response and response.status_code == 200

def test_stop_server():
    """Test stopping the WebSocket server."""
    print("\n=== Testing Stop WebSocket Server ===")
    
    response = run_test("/api/v0/mcp/peer/websocket/server/stop", "POST", 
                       test_name="Stop WebSocket Server")
    
    # Check if it was successful by getting status again
    if response and response.status_code == 200:
        result = response.json()
        if result.get("success"):
            # Verify server is stopped
            status_response = run_test("/api/v0/mcp/peer/websocket/server/status", "GET", 
                                     test_name="Verify Server Stopped")
            if status_response and status_response.status_code == 200:
                status_result = status_response.json()
                return status_result.get("success") and not status_result.get("running", False)
    
    return False

def test_connect_to_server():
    """Test connecting to a WebSocket server."""
    print("\n=== Testing Connect to WebSocket Server ===")
    
    # First make sure we have a server running
    server_started = False
    server_status_response = run_test("/api/v0/mcp/peer/websocket/server/status", "GET")
    if server_status_response and server_status_response.status_code == 200:
        status_result = server_status_response.json()
        if status_result.get("success") and status_result.get("running", False):
            server_started = True
        
    if not server_started:
        print("Server not running, starting one first...")
        server_data = {
            "host": "127.0.0.1",
            "port": 8765,
            "max_peers": 100,
            "heartbeat_interval": 30,
            "peer_ttl": 300
        }
        
        headers = {"Content-Type": "application/json"}
        start_response = run_test("/api/v0/mcp/peer/websocket/server/start", "POST", 
                                data=server_data, headers=headers, 
                                test_name="Start WebSocket Server")
        if not (start_response and start_response.status_code == 200):
            print("Failed to start server, can't test connection")
            return False
    
    # Now try to connect
    connect_data = {
        "server_url": "ws://127.0.0.1:8765",
        "auto_connect": True,
        "reconnect_interval": 30,
        "max_reconnect_attempts": 5
    }
    
    headers = {"Content-Type": "application/json"}
    response = run_test("/api/v0/mcp/peer/websocket/client/connect", "POST", 
                       data=connect_data, headers=headers, 
                       test_name="Connect to WebSocket Server")
    
    return response and response.status_code == 200

def test_get_discovered_peers():
    """Test getting discovered peers."""
    print("\n=== Testing Get Discovered Peers ===")
    
    response = run_test("/api/v0/mcp/peer/websocket/peers", "GET", 
                       test_name="Get Discovered Peers")
    
    return response and response.status_code == 200

def test_disconnect_from_server():
    """Test disconnecting from a WebSocket server."""
    print("\n=== Testing Disconnect from WebSocket Server ===")
    
    response = run_test("/api/v0/mcp/peer/websocket/client/disconnect", "POST", 
                       test_name="Disconnect from WebSocket Server")
    
    return response and response.status_code == 200

def run_all_tests():
    """Run all peer WebSocket controller tests."""
    print("\n=== Running All Peer WebSocket Controller Tests ===")
    
    success_count = 0
    total_tests = 6
    
    # Test 1: Check WebSocket Support
    if test_check_websocket_support():
        success_count += 1
    
    # Test 2: Start Server
    if test_start_server():
        success_count += 1
    
    # Test 3: Server Status
    if test_server_status():
        success_count += 1
    
    # Test 4: Connect to Server
    if test_connect_to_server():
        success_count += 1
    
    # Test 5: Get Discovered Peers
    if test_get_discovered_peers():
        success_count += 1
    
    # Test 6: Stop Server
    if test_stop_server():
        success_count += 1
    
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