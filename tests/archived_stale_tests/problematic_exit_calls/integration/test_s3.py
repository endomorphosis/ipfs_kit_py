#!/usr/bin/env python3
"""
Run S3 backend test using securely stored credentials.
"""

import os
import sys
import json
from test_all_backends import test_s3, create_test_file

CONFIG_DIR = os.path.expanduser("~/.ipfs_kit")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def get_stored_credentials():
    """Get credentials from secure storage."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("credentials", {})
        except json.JSONDecodeError:
            print(f"Error: {CONFIG_FILE} contains invalid JSON.")
            return {}
    else:
        print(f"No configuration file found at {CONFIG_FILE}")
        return {}

# Load credentials from secure storage
creds = get_stored_credentials()
s3_creds = creds.get("s3", {})

# Set environment variables for test
if "access_key" in s3_creds:
    os.environ["AWS_ACCESS_KEY_ID"] = s3_creds["access_key"]
if "secret_key" in s3_creds:
    os.environ["AWS_SECRET_ACCESS_KEY"] = s3_creds["secret_key"]
if "test_bucket" in s3_creds:
    os.environ["S3_TEST_BUCKET"] = s3_creds.get("test_bucket", "ipfs-kit-test")
if "server" in s3_creds:
    os.environ["S3_ENDPOINT_URL"] = f"https://{s3_creds['server']}"

# Check if we have the required credentials
if not os.environ.get("AWS_ACCESS_KEY_ID") or not os.environ.get("AWS_SECRET_ACCESS_KEY"):
    print("❌ Error: Missing S3 credentials in secure storage")
    print("Please run setup_s3_credentials.py to securely store your credentials")
    sys.exit(1)

if not os.environ.get("S3_TEST_BUCKET"):
    print("⚠️ Warning: No test bucket specified. Using default: ipfs-kit-test")
    os.environ["S3_TEST_BUCKET"] = "ipfs-kit-test"

# Create test file if it doesn't exist
create_test_file()

print("\nTesting S3 Backend with secure credentials...")
print(f"S3 Endpoint: {os.environ.get('S3_ENDPOINT_URL', 'Default AWS')}")
print(f"Test Bucket: {os.environ.get('S3_TEST_BUCKET')}")

# Run the test
result = test_s3()

if result:
    print("\n✅ S3 test passed successfully!")
    print(f"Resource location: {result}")
else:
    print("\n❌ S3 test failed")
    print("Check your credentials and bucket permissions.")