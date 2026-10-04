#!/usr/bin/env python3
"""
Example: Using Encrypted Configuration Storage

This example demonstrates how to use the encrypted configuration storage
feature to securely store backend credentials.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ipfs_kit_py.secure_config import SecureConfigManager


def main():
    """Demonstrate encrypted configuration usage."""
    
    print("=" * 60)
    print("Encrypted Configuration Storage Example")
    print("=" * 60)
    
    # Create manager with encryption enabled
    print("\n1. Initializing SecureConfigManager...")
    manager = SecureConfigManager(
        data_dir="/tmp/encrypted_config_demo",
        enable_encryption=True
    )
    
    # Check encryption status
    print("\n2. Checking encryption status...")
    status = manager.get_encryption_status()
    print(f"   Encryption enabled: {status['encryption_enabled']}")
    print(f"   Cryptography available: {status['cryptography_available']}")
    print(f"   Key exists: {status['key_exists']}")
    
    # Create sample configuration with sensitive credentials
    print("\n3. Creating sample backend configuration...")
    config = {
        "backends": {
            "s3_production": {
                "type": "s3",
                "description": "Production S3 storage",
                "status": "enabled",
                "config": {
                    "endpoint": "https://s3.amazonaws.com",
                    "access_key": "AKIAIOSFODNN7EXAMPLE",
                    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                    "bucket": "my-production-bucket",
                    "region": "us-east-1"
                }
            },
            "hf_models": {
                "type": "huggingface",
                "description": "HuggingFace model storage",
                "status": "enabled",
                "config": {
                    "token": "hf_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890",
                    "endpoint": "https://huggingface.co"
                }
            },
            "ipfs_local": {
                "type": "ipfs",
                "description": "Local IPFS node",
                "status": "enabled",
                "config": {
                    "api_url": "http://localhost:5001",
                    "gateway_url": "http://localhost:8080"
                }
            }
        }
    }
    
    # Save with encryption
    print("\n4. Saving configuration with automatic encryption...")
    success = manager.save_config("backends.json", config, encrypt=True)
    if success:
        print("   ✅ Configuration saved and encrypted")
    else:
        print("   ❌ Failed to save configuration")
        return 1
    
    # Load and decrypt
    print("\n5. Loading and decrypting configuration...")
    loaded_config = manager.load_config("backends.json", decrypt=True)
    
    if loaded_config:
        print("   ✅ Configuration loaded and decrypted")
        print(f"   Found {len(loaded_config['backends'])} backends")
        
        # Display decrypted credentials (demonstrating they were decrypted)
        print("\n6. Verifying decrypted credentials...")
        for backend_name, backend_data in loaded_config['backends'].items():
            print(f"\n   Backend: {backend_name}")
            print(f"   Type: {backend_data['type']}")
            
            config_data = backend_data.get('config', {})
            
            # Show sensitive fields (decrypted)
            if 'access_key' in config_data:
                print(f"   Access Key: {config_data['access_key'][:10]}... (decrypted)")
            if 'secret_key' in config_data:
                print(f"   Secret Key: {config_data['secret_key'][:10]}... (decrypted)")
            if 'token' in config_data:
                print(f"   Token: {config_data['token'][:10]}... (decrypted)")
            
            # Show non-sensitive fields
            if 'endpoint' in config_data:
                print(f"   Endpoint: {config_data['endpoint']}")
            if 'bucket' in config_data:
                print(f"   Bucket: {config_data['bucket']}")
    else:
        print("   ❌ Failed to load configuration")
        return 1
    
    # Show what's in the file (encrypted)
    print("\n7. Showing encrypted file structure...")
    import json
    file_path = Path("/tmp/encrypted_config_demo/backends.json")
    with open(file_path, 'r') as f:
        raw_data = json.load(f)
    
    s3_config = raw_data['backends']['s3_production']['config']
    print("   Raw access_key field in file:")
    print(f"   {json.dumps(s3_config['access_key'], indent=4)}")
    print("\n   Note: The actual credential is encrypted!")
    
    # Demonstrate encryption markers
    print("\n8. Encryption markers...")
    if isinstance(s3_config['access_key'], dict):
        if s3_config['access_key'].get('__encrypted__'):
            print("   ✅ Sensitive field is marked as encrypted")
            print(f"   Version: {s3_config['access_key'].get('version')}")
    
    # Show file permissions
    print("\n9. File permissions (security)...")
    import stat
    file_mode = file_path.stat().st_mode & 0o777
    print(f"   Config file permissions: {oct(file_mode)}")
    if file_mode == 0o600:
        print("   ✅ Secure permissions (owner read/write only)")
    else:
        print(f"   ⚠️  Permissions should be 0o600, got {oct(file_mode)}")
    
    key_file = Path("/tmp/encrypted_config_demo/.keyring/master.key")
    if key_file.exists():
        key_mode = key_file.stat().st_mode & 0o777
        print(f"   Key file permissions: {oct(key_mode)}")
        if key_mode == 0o600:
            print("   ✅ Secure key permissions")
    
    print("\n" + "=" * 60)
    print("Example completed successfully!")
    print("=" * 60)
    print("\nKey points:")
    print("✅ Sensitive fields (keys, tokens, secrets) are automatically encrypted")
    print("✅ Non-sensitive fields (endpoints, buckets) remain readable")
    print("✅ Files are created with secure permissions (0o600)")
    print("✅ Encryption/decryption is transparent to application code")
    print("\nNext steps:")
    print("- Use 'python -m ipfs_kit_py.cli_secure_config migrate-all' to encrypt existing configs")
    print("- Use 'python -m ipfs_kit_py.cli_secure_config rotate-key' to rotate encryption keys")
    print("- See ENCRYPTED_CONFIG_GUIDE.md for complete documentation")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
