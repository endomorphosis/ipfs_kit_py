#!/usr/bin/env python3
"""
Enhanced MCP server verification.
Tests MCP server endpoints and tools functionality.
"""
import requests
import json
import time
import uuid

print("Starting MCP server verification at", time.strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 50)

# Check if server is running
try:
    response = requests.get("http://localhost:9994/", timeout=5)
    print(f"Server response status: {response.status_code}")
    if response.status_code == 200:
        print("Server is running! 🎉")
        data = response.json()
        print(f"Controllers available: {data.get('controllers', [])}")
        print(f"IPFS extensions: {data.get('ipfs_extensions', {})}")
        print(f"Storage backends: {data.get('storage_backends', {})}")
    else:
        print(f"Server responded with error: {response.text}")
except Exception as e:
    print(f"Error connecting to server: {e}")

print("\nChecking SSE endpoint...")
try:
    response = requests.get("http://localhost:9994/api/v0/sse", stream=True, timeout=5)
    print(f"SSE endpoint status: {response.status_code}")
    if response.status_code == 200:
        print("SSE endpoint is available!")
        # Read a few lines to confirm it's working
        line_count = 0
        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"SSE data: {line}")
                line_count += 1
            if line_count >= 3:
                break
        response.close()
    else:
        print(f"SSE endpoint error: {response.text}")
except Exception as e:
    print(f"Error connecting to SSE endpoint: {e}")

print("\nVerification completed")

# Test JSON-RPC endpoint
print("\nTesting JSON-RPC endpoints...")

# Test the main MCP server's JSON-RPC endpoint
try:
    jsonrpc_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "capabilities": {},
            "processId": 12345
        }
    }
    
    # Try the endpoint at the API prefix
    response = requests.post(
        "http://localhost:9994/api/v0/jsonrpc",
        json=jsonrpc_payload,
        headers={"Content-Type": "application/json"},
        timeout=5
    )
    
    print(f"MCP JSON-RPC endpoint status: {response.status_code}")
    if response.status_code == 200:
        print("✅ MCP JSON-RPC endpoint is available!")
        try:
            data = response.json()
            print(f"Response data: {json.dumps(data)[:200]}...")
        except:
            print(f"Response (not JSON): {response.text[:200]}...")
    else:
        print(f"❌ MCP JSON-RPC endpoint error: {response.text[:200]}...")
except Exception as e:
    print(f"❌ Error connecting to MCP JSON-RPC endpoint: {e}")

# Test the JSON-RPC proxy
try:
    # Try the dedicated JSON-RPC proxy
    response = requests.post(
        "http://localhost:9995/jsonrpc",
        json=jsonrpc_payload,
        headers={"Content-Type": "application/json"},
        timeout=5
    )
    
    print(f"\nJSON-RPC proxy endpoint status: {response.status_code}")
    if response.status_code == 200:
        print("✅ JSON-RPC proxy endpoint is available!")
        try:
            data = response.json()
            print(f"Response data: {json.dumps(data)[:200]}...")
        except:
            print(f"Response (not JSON): {response.text[:200]}...")
    else:
        print(f"❌ JSON-RPC proxy endpoint error: {response.text[:200]}...")
except Exception as e:
    print(f"❌ Error connecting to JSON-RPC proxy endpoint: {e}")

# Test the actual MCP tools
print("\nTesting MCP tools functionality:")

# Test IPFS add functionality
try:
    print("\nTesting IPFS add...")
    test_content = f"Test content {uuid.uuid4()}"
    files = {'file': ('test.txt', test_content)}
    
    response = requests.post(
        "http://localhost:9994/api/v0/ipfs/add",
        files=files,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        cid = data.get('cid')
        print(f"✅ IPFS add successful! CID: {cid}")
        
        # Now test IPFS cat using the CID
        if cid:
            print("\nTesting IPFS cat...")
            cat_response = requests.get(
                f"http://localhost:9994/api/v0/ipfs/cat/{cid}",
                timeout=10
            )
            
            if cat_response.status_code == 200:
                # Verify content matches
                if cat_response.text == test_content:
                    print(f"✅ IPFS cat successful! Content matches.")
                else:
                    print(f"❌ IPFS cat returned different content. Expected: '{test_content}', Got: '{cat_response.text}'")
            else:
                print(f"❌ IPFS cat failed: {cat_response.status_code} - {cat_response.text[:100]}")
            
            # Test IPFS pin
            print("\nTesting IPFS pin add...")
            pin_response = requests.post(
                f"http://localhost:9994/api/v0/ipfs/pin/add/{cid}",
                timeout=10
            )
            
            if pin_response.status_code == 200:
                print(f"✅ IPFS pin add successful!")
                
                # Test pin list
                print("\nTesting IPFS pin list...")
                pin_ls_response = requests.get(
                    f"http://localhost:9994/api/v0/ipfs/pin/ls",
                    timeout=10
                )
                
                if pin_ls_response.status_code == 200:
                    pin_data = pin_ls_response.json()
                    pins = pin_data.get('pins', [])
                    if cid in pins:
                        print(f"✅ IPFS pin list successful! Found our CID.")
                    else:
                        print(f"❌ IPFS pin list doesn't contain our CID. Pins: {pins[:5]}...")
                else:
                    print(f"❌ IPFS pin list failed: {pin_ls_response.status_code} - {pin_ls_response.text[:100]}")
            else:
                print(f"❌ IPFS pin add failed: {pin_response.status_code} - {pin_response.text[:100]}")
    else:
        print(f"❌ IPFS add failed: {response.status_code} - {response.text[:100]}")
except Exception as e:
    print(f"❌ Error testing IPFS tools: {e}")

print("\nAll tests completed")
