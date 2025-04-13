#!/usr/bin/env python3
"""
Interactive credential management tool for ipfs_kit_py.
Run this script to securely add, update, or view credentials for storage backends.
"""

import os
import json
import getpass
import argparse
from pathlib import Path

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
    print(f"Configuration saved to {CONFIG_FILE}")

def add_huggingface_credentials(config):
    """Add HuggingFace credentials to the configuration."""
    config.setdefault("credentials", {}).setdefault("huggingface", {})
    
    print("\n=== HuggingFace Credentials ===")
    token = getpass.getpass("Enter your HuggingFace token: ")
    repo = input("Enter your HuggingFace test repository (username/repo): ")
    
    config["credentials"]["huggingface"]["token"] = token
    config["credentials"]["huggingface"]["test_repo"] = repo
    
    print("HuggingFace credentials added successfully.")
    return config

def add_aws_credentials(config):
    """Add AWS credentials to the configuration."""
    config.setdefault("credentials", {}).setdefault("aws", {})
    config.setdefault("credentials", {}).setdefault("s3", {})
    
    print("\n=== AWS Credentials ===")
    access_key = input("Enter your AWS Access Key ID: ")
    secret_key = getpass.getpass("Enter your AWS Secret Access Key: ")
    region = input("Enter your AWS Region (default: us-east-1): ") or "us-east-1"
    bucket = input("Enter your S3 test bucket name: ")
    
    config["credentials"]["aws"]["access_key_id"] = access_key
    config["credentials"]["aws"]["secret_access_key"] = secret_key
    config["credentials"]["aws"]["region"] = region
    config["credentials"]["s3"]["test_bucket"] = bucket
    
    print("AWS credentials added successfully.")
    return config

def add_storacha_credentials(config):
    """Add Storacha/W3 credentials to the configuration."""
    config.setdefault("credentials", {}).setdefault("storacha", {})
    
    print("\n=== Storacha/Web3.Storage Credentials ===")
    token = getpass.getpass("Enter your Web3.Storage token: ")
    
    config["credentials"]["storacha"]["token"] = token
    
    print("Web3.Storage credentials added successfully.")
    return config

def display_credentials(config):
    """Display a redacted view of stored credentials."""
    creds = config.get("credentials", {})
    
    print("\n=== Current Credentials ===")
    
    if "huggingface" in creds:
        hf = creds["huggingface"]
        token = hf.get("token", "")
        repo = hf.get("test_repo", "")
        print(f"HuggingFace: Token {'✓ Set' if token else '✗ Not set'}, " 
              f"Test Repo: {repo if repo else '✗ Not set'}")
    else:
        print("HuggingFace: Not configured")
        
    if "aws" in creds:
        aws = creds["aws"]
        access_key = aws.get("access_key_id", "")
        secret_key = aws.get("secret_access_key", "")
        region = aws.get("region", "")
        print(f"AWS: Access Key {'✓ Set' if access_key else '✗ Not set'}, " 
              f"Secret Key {'✓ Set' if secret_key else '✗ Not set'}, "
              f"Region: {region if region else 'Default'}")
        
        if "s3" in creds:
            s3 = creds["s3"]
            bucket = s3.get("test_bucket", "")
            print(f"S3: Test Bucket: {bucket if bucket else '✗ Not set'}")
    else:
        print("AWS: Not configured")
        
    if "storacha" in creds:
        storacha = creds["storacha"]
        token = storacha.get("token", "")
        print(f"Storacha/Web3.Storage: Token {'✓ Set' if token else '✗ Not set'}")
    else:
        print("Storacha/Web3.Storage: Not configured")

def export_env_script(config):
    """Export credentials as environment variables to a script file."""
    creds = config.get("credentials", {})
    script_path = os.path.join(os.getcwd(), ".env")
    
    with open(script_path, 'w') as f:
        f.write("# Environment variables for ipfs_kit_py storage backends\n\n")
        
        if "huggingface" in creds:
            hf = creds["huggingface"]
            if "token" in hf:
                f.write(f'export HUGGINGFACE_TOKEN="{hf["token"]}"\n')
            if "test_repo" in hf:
                f.write(f'export HF_TEST_REPO="{hf["test_repo"]}"\n')
                
        if "aws" in creds:
            aws = creds["aws"]
            if "access_key_id" in aws:
                f.write(f'export AWS_ACCESS_KEY_ID="{aws["access_key_id"]}"\n')
            if "secret_access_key" in aws:
                f.write(f'export AWS_SECRET_ACCESS_KEY="{aws["secret_access_key"]}"\n')
            if "region" in aws:
                f.write(f'export AWS_REGION="{aws["region"]}"\n')
                
        if "s3" in creds and "test_bucket" in creds["s3"]:
            f.write(f'export S3_TEST_BUCKET="{creds["s3"]["test_bucket"]}"\n')
            
        if "storacha" in creds and "token" in creds["storacha"]:
            f.write(f'export W3_TOKEN="{creds["storacha"]["token"]}"\n')
    
    # Set permissions to be readable only by the user
    os.chmod(script_path, 0o600)
    print(f"Environment variables exported to {script_path}")
    print(f"Run 'source {script_path}' to load them into your environment")

def main():
    parser = argparse.ArgumentParser(description="Manage credentials for ipfs_kit_py storage backends")
    parser.add_argument('--export', action='store_true', help='Export credentials as environment variables')
    parser.add_argument('--show', action='store_true', help='Show configured credentials (redacted)')
    args = parser.parse_args()
    
    config = load_config()
    
    if args.show:
        display_credentials(config)
        return
        
    if args.export:
        export_env_script(config)
        return
    
    # Interactive mode
    while True:
        print("\n=== IPFS Kit Credential Manager ===")
        print("1. Add/Update HuggingFace credentials")
        print("2. Add/Update AWS/S3 credentials")
        print("3. Add/Update Storacha/Web3.Storage credentials")
        print("4. View current credentials")
        print("5. Export credentials as environment variables")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            config = add_huggingface_credentials(config)
            save_config(config)
        elif choice == '2':
            config = add_aws_credentials(config)
            save_config(config)
        elif choice == '3':
            config = add_storacha_credentials(config)
            save_config(config)
        elif choice == '4':
            display_credentials(config)
        elif choice == '5':
            export_env_script(config)
        elif choice == '6':
            print("Exiting. Your credentials are saved.")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()