#!/usr/bin/env python3
"""
Test bucket creation functionality
"""

import requests
import json

def test_bucket_creation():
    """Test creating a bucket via the MCP dashboard API."""
    url = "http://127.0.0.1:8004/api/buckets"
    
    data = {
        "bucket_name": "test-demo-bucket",
        "bucket_type": "general",
        "vfs_structure": "hybrid",
        "metadata": {
            "description": "Test bucket created from Python script",
            "created_by": "test_script"
        }
    }
    
    try:
        print("🧪 Testing bucket creation...")
        response = requests.post(url, json=data, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                print("✅ Bucket created successfully!")
                print(f"Bucket details: {json.dumps(result, indent=2)}")
            else:
                print(f"❌ Bucket creation failed: {result.get('error')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_bucket_listing():
    """Test listing buckets via the MCP dashboard API."""
    url = "http://127.0.0.1:8004/api/buckets"
    
    try:
        print("\n🧪 Testing bucket listing...")
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Bucket listing successful!")
            print(f"Buckets: {json.dumps(result, indent=2)}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_bucket_listing()
    test_bucket_creation()
    test_bucket_listing()
