#!/usr/bin/env python3
"""
Securely store S3 credentials in credential manager.
"""

import os
import json
import sys

CONFIG_DIR = os.path.expanduser("~/.ipfs_kit")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def create_config_dir():
    """Create the config directory if it doesn't exist."""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
        print(f"Created configuration directory: {CONFIG_DIR}")

def load_config():
    """Load the existing configuration file or create a new one."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {CONFIG_FILE} contains invalid JSON. Creating a new configuration.")
            return {"credentials": {}}
    else:
        return {"credentials": {}}

def save_config(config):
    """Save the configuration to the config file."""
    create_config_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Set secure permissions on the file
    os.chmod(CONFIG_FILE, 0o600)
    print(f"Configuration saved to {CONFIG_FILE} with secure permissions")

def add_s3_credentials(access_key, secret_key, server=None, bucket=None):
    """Add S3 credentials to the configuration."""
    config = load_config()
    config.setdefault("credentials", {}).setdefault("s3", {})
    
    # Add credentials
    config["credentials"]["s3"]["access_key"] = access_key
    config["credentials"]["s3"]["secret_key"] = secret_key
    
    # Add server if provided
    if server:
        config["credentials"]["s3"]["server"] = server
        
    # Add test bucket if provided  
    if bucket:
        config["credentials"]["s3"]["test_bucket"] = bucket
        
    save_config(config)
    print("S3 credentials securely stored.")

def main():
    # SECURITY: Credentials have been removed from this file
    # Use the secure credential management system instead:
    # 1. Run: python setup_credentials.py
    # 2. Or use environment variables: IPFS_KIT_S3_ACCESS_KEY, IPFS_KIT_S3_SECRET_KEY
    
    print("❌ This script has been deprecated for security reasons.")
    print("🔐 Please use the secure credential management system:")
    print("   1. Run: python setup_credentials.py")
    print("   2. Or set environment variables:")
    print("      export IPFS_KIT_S3_ACCESS_KEY='your_access_key'")
    print("      export IPFS_KIT_S3_SECRET_KEY='your_secret_key'")
    print("   3. See SECURE_CREDENTIALS_GUIDE.md for more information")
    print("To use these credentials, run: python test_s3.py")

if __name__ == "__main__":
    main()