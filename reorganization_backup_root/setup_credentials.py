#!/usr/bin/env python3
"""
Setup script for IPFS Kit credentials and configuration.

This script helps users configure their credentials securely.
"""

import os
import json
import sys
from pathlib import Path
from getpass import getpass

def setup_credentials():
    """Interactive setup for credentials."""
    
    print("🔐 IPFS Kit Credential Setup")
    print("=" * 40)
    
    # Create config directory
    config_dir = Path("/tmp/ipfs_kit_config")
    config_dir.mkdir(exist_ok=True)
    
    credentials_file = config_dir / "credentials.json"
    
    # Load existing credentials if they exist
    credentials = {}
    if credentials_file.exists():
        try:
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)
            print(f"✓ Found existing credentials at {credentials_file}")
        except Exception as e:
            print(f"⚠️  Error loading existing credentials: {e}")
    
    # Setup Hugging Face credentials
    print("\n🤗 Hugging Face Configuration")
    print("-" * 30)
    
    current_hf_token = credentials.get("huggingface", {}).get("token", "")
    if current_hf_token:
        print(f"Current token: {current_hf_token[:8]}...")
        update_hf = input("Update Hugging Face token? (y/n): ").strip().lower() == 'y'
    else:
        update_hf = True
    
    if update_hf:
        print("Enter your Hugging Face token:")
        print("(You can get one at https://huggingface.co/settings/tokens)")
        hf_token = getpass("HF Token: ").strip()
        
        if hf_token:
            if "huggingface" not in credentials:
                credentials["huggingface"] = {}
            credentials["huggingface"]["token"] = hf_token
            print("✓ Hugging Face token saved")
    
    # Setup S3 credentials
    print("\n🪣 S3 Configuration")
    print("-" * 20)
    
    current_s3_key = credentials.get("s3", {}).get("access_key", "")
    if current_s3_key:
        print(f"Current access key: {current_s3_key[:8]}...")
        update_s3 = input("Update S3 credentials? (y/n): ").strip().lower() == 'y'
    else:
        update_s3 = True
    
    if update_s3:
        print("Enter your S3 credentials:")
        s3_access_key = getpass("S3 Access Key: ").strip()
        s3_secret_key = getpass("S3 Secret Key: ").strip()
        
        if s3_access_key and s3_secret_key:
            if "s3" not in credentials:
                credentials["s3"] = {}
            credentials["s3"]["access_key"] = s3_access_key
            credentials["s3"]["secret_key"] = s3_secret_key
            print("✓ S3 credentials saved")
    
    # Setup Storacha credentials
    print("\n📦 Storacha Configuration")
    print("-" * 25)
    
    current_storacha_token = credentials.get("storacha", {}).get("token", "")
    if current_storacha_token:
        print(f"Current token: {current_storacha_token[:8]}...")
        update_storacha = input("Update Storacha token? (y/n): ").strip().lower() == 'y'
    else:
        update_storacha = input("Setup Storacha token? (y/n): ").strip().lower() == 'y'
    
    if update_storacha:
        print("Enter your Storacha token:")
        storacha_token = getpass("Storacha Token: ").strip()
        
        if storacha_token:
            if "storacha" not in credentials:
                credentials["storacha"] = {}
            credentials["storacha"]["token"] = storacha_token
            print("✓ Storacha token saved")
    
    # Save credentials
    try:
        with open(credentials_file, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        # Set secure permissions
        os.chmod(credentials_file, 0o600)
        
        print(f"\n✅ Credentials saved to {credentials_file}")
        print("🔒 File permissions set to 600 (owner read/write only)")
        
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        sys.exit(1)
    
    # Create environment variables example
    env_file = config_dir / ".env.example"
    
    env_content = """# IPFS Kit Environment Variables
# Copy this file to .env and fill in your credentials
# These take precedence over the credentials.json file

# Hugging Face
IPFS_KIT_HUGGINGFACE_TOKEN=your_hf_token_here

# S3
IPFS_KIT_S3_ACCESS_KEY=your_s3_access_key_here
IPFS_KIT_S3_SECRET_KEY=your_s3_secret_key_here

# Storacha
IPFS_KIT_STORACHA_TOKEN=your_storacha_token_here
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print(f"📝 Created environment variables example at {env_file}")
        
    except Exception as e:
        print(f"⚠️  Error creating .env.example: {e}")
    
    # Create .gitignore
    gitignore_file = config_dir / ".gitignore"
    
    gitignore_content = """# Credential files - DO NOT COMMIT
credentials.json
.env
*.key
*.pem
*.p12
*.pfx

# Backup files
*.backup
*.bak

# OS files
.DS_Store
Thumbs.db
"""
    
    try:
        with open(gitignore_file, 'w') as f:
            f.write(gitignore_content)
        
        print(f"🚫 Created .gitignore at {gitignore_file}")
        
    except Exception as e:
        print(f"⚠️  Error creating .gitignore: {e}")
    
    print("\n✅ Setup complete!")
    print("\n📋 Summary:")
    print(f"   • Credentials stored in: {credentials_file}")
    print(f"   • Environment example: {env_file}")
    print(f"   • Gitignore created: {gitignore_file}")
    
    print("\n🔐 Security Notes:")
    print("   • Credentials are stored with 600 permissions (owner only)")
    print("   • .gitignore prevents accidental commits")
    print("   • Environment variables take precedence over config files")
    print("   • Never commit credentials.json or .env files!")

def main():
    """Main entry point."""
    
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("IPFS Kit Credential Setup")
        print("Usage: python setup_credentials.py")
        print("Interactive setup for secure credential management")
        return
    
    setup_credentials()

if __name__ == "__main__":
    main()
