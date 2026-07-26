#!/usr/bin/env python3
import sys
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def main():
    server_url = "http://localhost:8000"
    
    try:
        # Check health endpoint
        health = requests.get(f"{server_url}/health", timeout=5).json()
        print(f"Server health: {json.dumps(health, indent=2)}")
        
        # Try to list methods
        methods_resp = requests.post(
            f"{server_url}/jsonrpc",
            json={"jsonrpc": "2.0", "method": "rpc.discover", "id": 1},
            timeout=5
        ).json()
        
        if "result" in methods_resp and "methods" in methods_resp["result"]:
            methods = methods_resp["result"]["methods"]
            ipfs_methods = {name: desc for name, desc in methods.items() if name.startswith("ipfs_")}
            
            print(f"\nFound {len(ipfs_methods)} IPFS methods:")
            for name, desc in ipfs_methods.items():
                print(f"  - {name}")
                
            # Try calling ipfs_add
            test_resp = requests.post(
                f"{server_url}/jsonrpc",
                json={
                    "jsonrpc": "2.0", 
                    "method": "ipfs_add", 
                    "params": {"content": "Hello IPFS!"}, 
                    "id": 2
                },
                timeout=10
            ).json()
            
            print(f"\nTesting ipfs_add:")
            print(json.dumps(test_resp, indent=2))
        else:
            print(f"Error listing methods: {methods_resp}")
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
