#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_test_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
Run HuggingFace backend test using securely stored credentials.
"""

import os
import sys
import json
from test_all_backends import test_huggingface

CONFIG_DIR = os.path.expanduser("~/.ipfs_kit")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def create_config_dir():
    """Create the config directory if it doesn't exist."""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        print(f"Created configuration directory: {CONFIG_DIR}")

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

# Get repository from command line if provided
repo = None
if len(sys.argv) > 1:
    repo = sys.argv[1]

# Load credentials from secure storage
creds = get_stored_credentials()
hf_creds = creds.get("huggingface", {})

# Use token from secure storage
token = hf_creds.get("token")
if not token:
    print("No HuggingFace token found in secure credential store.")
    print("Please run manage_credentials.py to securely store your token.")
    sys.exit(1)

# Set the token in environment
os.environ["HUGGINGFACE_TOKEN"] = token

# Set repository (command line, stored config, or default)
if repo:
    os.environ["HF_TEST_REPO"] = repo
elif "test_repo" in hf_creds:
    os.environ["HF_TEST_REPO"] = hf_creds["test_repo"]
else:
    os.environ["HF_TEST_REPO"] = "endomorphosis/test-repo"

print(f"Using test repository: {os.environ['HF_TEST_REPO']}")
print("You can specify a different repository by running:")
print(f"  python {sys.argv[0]} your-username/your-repo-name")

print("\nTesting HuggingFace Hub Backend with token from secure storage...\n")
result = test_huggingface()

if result:
    print("\n✅ HuggingFace test passed successfully!")
    print(f"Resource location: {result}")
else:
    print("\n❌ HuggingFace test failed")
    print("Check that your token is valid and has write access to the repository.")
