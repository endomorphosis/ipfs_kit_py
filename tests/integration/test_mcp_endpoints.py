import requests
import json
import time
import sys
import tempfile
import os

# Test endpoints on different ports
BASE_URLS = [
    "http://localhost:8000/api/v0/mcp"
]

# Test content
TEST_CONTENT = "test content for MCP server"
TEST_FILE_CONTENT = b"Hello, MCP Server! This is a test file."

def test_endpoint(url, method="GET", data=None, params=None, files=None):
    """Test an API endpoint with error handling."""
    try:
        print(f"Testing {method} {url}")
        
        if method == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method == "POST":
            if files:
                response = requests.post(url, files=files, timeout=10)
            else:
                response = requests.post(url, json=data, timeout=10)
        
        print(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            if response.content:
                try:
                    json_data = response.json()
                    return {
                        "status": "success",
                        "status_code": response.status_code,
                        "data": json_data
                    }
                except json.JSONDecodeError:
                    return {
                        "status": "success",
                        "status_code": response.status_code,
                        "data": response.content[:100]  # First 100 bytes for binary data
                    }
            else:
                return {
                    "status": "success",
                    "status_code": response.status_code,
                    "data": None
                }
        else:
            return {
                "status": "error",
                "status_code": response.status_code,
                "data": response.text
            }
    except requests.RequestException as e:
        return {
            "status": "error",
            "error": str(e)
        }

def test_core_endpoints(base_url):
    """Test the core IPFS endpoints."""
    print("\n===== Testing Core IPFS Endpoints =====")
    
    # Test health endpoint (baseline test)
    health_url = f"{base_url}/health"
    print(f"\nTesting health endpoint: {health_url}")
    health_result = test_endpoint(health_url)
    print(json.dumps(health_result, indent=2))
    
    # Test core IPFS functionality - add string content
    add_url = f"{base_url}/ipfs/add"
    print(f"\nTesting add endpoint (string content): {add_url}")
    test_content = {"content": TEST_CONTENT}
    add_result = test_endpoint(add_url, method="POST", data=test_content)
    print(json.dumps(add_result, indent=2))
    
    # Get CID for further tests
    if add_result["status"] == "success" and "cid" in add_result.get("data", {}):
        test_cid = add_result["data"]["cid"]
        print(f"Generated test CID: {test_cid}")
        
        # Test cat endpoint with the CID
        cat_url = f"{base_url}/ipfs/cat/{test_cid}"
        print(f"\nTesting cat endpoint: {cat_url}")
        cat_result = test_endpoint(cat_url)
        print(json.dumps(cat_result, indent=2))
        
        # Test pinning endpoints
        pin_url = f"{base_url}/ipfs/pin"
        print(f"\nTesting pin endpoint: {pin_url}")
        pin_data = {"cid": test_cid}
        pin_result = test_endpoint(pin_url, method="POST", data=pin_data)
        print(json.dumps(pin_result, indent=2))
        
        pins_url = f"{base_url}/ipfs/pins"
        print(f"\nTesting pins list endpoint: {pins_url}")
        pins_result = test_endpoint(pins_url)
        print(json.dumps(pins_result, indent=2))
        
        unpin_url = f"{base_url}/ipfs/unpin"
        print(f"\nTesting unpin endpoint: {unpin_url}")
        unpin_data = {"cid": test_cid}
        unpin_result = test_endpoint(unpin_url, method="POST", data=unpin_data)
        print(json.dumps(unpin_result, indent=2))
        
        return test_cid
    else:
        print("Failed to get CID from add operation")
        return None

def test_new_endpoints(base_url, test_cid):
    """Test the newly implemented API endpoints."""
    if not test_cid:
        print("No CID available. Skipping new endpoint tests.")
        return
        
    print("\n===== Testing Newly Implemented Endpoints =====")
    
    # Test Files API (MFS) endpoints
    print("\n----- Files API (MFS) Endpoints -----")
    
    # Test mkdir
    mkdir_url = f"{base_url}/ipfs/files/mkdir"
    print(f"\nTesting files mkdir endpoint: {mkdir_url}")
    mkdir_data = {"path": "/test-dir", "parents": True}
    mkdir_result = test_endpoint(mkdir_url, method="POST", data=mkdir_data)
    print(json.dumps(mkdir_result, indent=2))
    
    # Test ls
    ls_url = f"{base_url}/ipfs/files/ls"
    print(f"\nTesting files ls endpoint: {ls_url}")
    ls_params = {"path": "/", "long": "true"}
    ls_result = test_endpoint(ls_url, params=ls_params)
    print(json.dumps(ls_result, indent=2))
    
    # Test stat
    stat_url = f"{base_url}/ipfs/files/stat"
    print(f"\nTesting files stat endpoint: {stat_url}")
    stat_params = {"path": "/test-dir"}
    stat_result = test_endpoint(stat_url, params=stat_params)
    print(json.dumps(stat_result, indent=2))
    
    # Test IPNS endpoints
    print("\n----- IPNS Endpoints -----")
    
    # Test name publish
    publish_url = f"{base_url}/ipfs/name/publish"
    print(f"\nTesting name publish endpoint: {publish_url}")
    publish_data = {"path": f"/ipfs/{test_cid}", "key": "self"}
    publish_result = test_endpoint(publish_url, method="POST", data=publish_data)
    print(json.dumps(publish_result, indent=2))
    
    # If we got a name, try to resolve it
    if publish_result["status"] == "success" and "Name" in publish_result.get("data", {}):
        ipns_name = publish_result["data"]["Name"]
        
        # Test name resolve
        resolve_url = f"{base_url}/ipfs/name/resolve"
        print(f"\nTesting name resolve endpoint: {resolve_url}")
        resolve_params = {"name": ipns_name}
        resolve_result = test_endpoint(resolve_url, params=resolve_params)
        print(json.dumps(resolve_result, indent=2))
    
    # Test DAG endpoints
    print("\n----- DAG Endpoints -----")
    
    # Test dag put
    dag_put_url = f"{base_url}/ipfs/dag/put"
    print(f"\nTesting dag put endpoint: {dag_put_url}")
    dag_node = {"data": "test data", "links": []}
    dag_put_data = {"node": dag_node, "store_codec": "dag-cbor", "pin": True}
    dag_put_result = test_endpoint(dag_put_url, method="POST", data=dag_put_data)
    print(json.dumps(dag_put_result, indent=2))
    
    # If we got a CID, try to get it
    if dag_put_result["status"] == "success" and "cid" in dag_put_result.get("data", {}):
        dag_cid = dag_put_result["data"]["cid"]
        
        # Test dag get
        dag_get_url = f"{base_url}/ipfs/dag/get"
        print(f"\nTesting dag get endpoint: {dag_get_url}")
        dag_get_params = {"cid": dag_cid}
        dag_get_result = test_endpoint(dag_get_url, params=dag_get_params)
        print(json.dumps(dag_get_result, indent=2))
    
    # Test Block endpoints
    print("\n----- Block Endpoints -----")
    
    # Test block stat
    block_stat_url = f"{base_url}/ipfs/block/stat"
    print(f"\nTesting block stat endpoint: {block_stat_url}")
    block_stat_params = {"cid": test_cid}
    block_stat_result = test_endpoint(block_stat_url, params=block_stat_params)
    print(json.dumps(block_stat_result, indent=2))
    
    # Test block get
    block_get_url = f"{base_url}/ipfs/block/get/{test_cid}"
    print(f"\nTesting block get endpoint: {block_get_url}")
    block_get_result = test_endpoint(block_get_url)
    print(json.dumps(block_get_result, indent=2))
    
    # Test DHT endpoints
    print("\n----- DHT Endpoints -----")
    
    # Test dht findpeer
    findpeer_url = f"{base_url}/ipfs/dht/findpeer"
    print(f"\nTesting dht findpeer endpoint: {findpeer_url}")
    findpeer_params = {"peer_id": "QmSoLV4Bbm51jM9C4gDYZQ9Cy3U6aXMJDAbzgu2fzaDs64"}
    findpeer_result = test_endpoint(findpeer_url, params=findpeer_params)
    print(json.dumps(findpeer_result, indent=2))
    
    # Test dht findprovs
    findprovs_url = f"{base_url}/ipfs/dht/findprovs"
    print(f"\nTesting dht findprovs endpoint: {findprovs_url}")
    findprovs_params = {"cid": test_cid}
    findprovs_result = test_endpoint(findprovs_url, params=findprovs_params)
    print(json.dumps(findprovs_result, indent=2))

def test_file_upload(base_url):
    """Test file upload endpoint."""
    print("\n===== Testing File Upload =====")
    
    # Create temp file for upload
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(TEST_FILE_CONTENT)
        temp_file_path = temp_file.name
    
    try:
        # Test file upload
        upload_url = f"{base_url}/ipfs/add"
        print(f"\nTesting file upload endpoint: {upload_url}")
        
        with open(temp_file_path, 'rb') as f:
            files = {'file': ('test.txt', f, 'text/plain')}
            upload_result = test_endpoint(upload_url, method="POST", files=files)
            
        print(json.dumps(upload_result, indent=2))
        
        if upload_result["status"] == "success" and "cid" in upload_result.get("data", {}):
            file_cid = upload_result["data"]["cid"]
            print(f"File CID: {file_cid}")
            return file_cid
        else:
            print("Failed to upload file")
            return None
            
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file_path)
        except OSError:
            pass

def test_other_controllers(base_url):
    """Test other controller endpoints."""
    print("\n===== Testing Other Controllers =====")
    
    # Test CLI controller
    print("\n----- CLI Controller -----")
    cli_version_url = f"{base_url}/cli/version"
    print(f"\nTesting CLI version endpoint: {cli_version_url}")
    cli_version_result = test_endpoint(cli_version_url)
    print(json.dumps(cli_version_result, indent=2))
    
    # Test filesystem journal controller
    print("\n----- FS Journal Controller -----")
    fs_status_url = f"{base_url}/fs_journal/status"
    print(f"\nTesting filesystem journal status endpoint: {fs_status_url}")
    fs_status_result = test_endpoint(fs_status_url)
    print(json.dumps(fs_status_result, indent=2))
    
    # Test WebRTC controller
    print("\n----- WebRTC Controller -----")
    webrtc_url = f"{base_url}/webrtc/capabilities"
    print(f"\nTesting WebRTC capabilities endpoint: {webrtc_url}")
    webrtc_result = test_endpoint(webrtc_url)
    print(json.dumps(webrtc_result, indent=2))

# Main function
def main():
    """Run tests for all MCP API endpoints."""
    for base_url in BASE_URLS:
        print(f"\n===== Testing MCP API at {base_url} =====")
        
        # Test core endpoints and get CID
        test_cid = test_core_endpoints(base_url)
        
        # Test file upload
        file_cid = test_file_upload(base_url)
        
        # Use any available CID for further tests
        cid_to_use = test_cid or file_cid
        
        # Test newly implemented endpoints
        test_new_endpoints(base_url, cid_to_use)
        
        # Test other controllers
        test_other_controllers(base_url)

if __name__ == "__main__":
    main()
