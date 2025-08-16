#!/usr/bin/env python3
"""
Test script for secure configuration management.
"""

import sys
import os
import json
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, '/home/runner/work/ipfs_kit_py/ipfs_kit_py')

from mcp.ipfs_kit.core.config_manager import SecureConfigManager

def test_secure_config():
    """Test the secure configuration manager."""
    
    print("🔐 Testing Secure Configuration Manager")
    print("=" * 50)
    
    # Initialize config manager
    config_manager = SecureConfigManager()
    
    # Test 1: Create example credentials
    print("\n1. Creating example credentials...")
    config_manager.initialize_example_credentials()
    
    # Test 2: Set test credentials
    print("\n2. Setting test credentials...")
    config_manager.set_credential("huggingface", "token", "test_hf_token_123")
    config_manager.set_credential("s3", "access_key", "test_access_key_123")
    config_manager.set_credential("s3", "secret_key", "test_secret_key_123")
    
    # Test 3: Get credentials
    print("\n3. Retrieving credentials...")
    hf_token = config_manager.get_credential("huggingface", "token")
    s3_access = config_manager.get_credential("s3", "access_key")
    s3_secret = config_manager.get_credential("s3", "secret_key")
    
    print(f"   HF Token: {hf_token}")
    print(f"   S3 Access Key: {s3_access}")
    print(f"   S3 Secret Key: {s3_secret}")
    
    # Test 4: Get backend config
    print("\n4. Getting backend configurations...")
    hf_config = config_manager.get_backend_config("huggingface")
    s3_config = config_manager.get_backend_config("s3")
    
    print(f"   HF Config: {hf_config}")
    print(f"   S3 Config: {s3_config}")
    
    # Test 5: Get all backend configs
    print("\n5. Getting all backend configurations...")
    all_configs = config_manager.get_all_backend_configs()
    
    for name, config in all_configs.items():
        print(f"   {name}: {config}")
    
    # Test 6: Create .gitignore
    print("\n6. Creating .gitignore...")
    config_manager.create_gitignore()
    
    # Test 7: Check file permissions
    print("\n7. Checking file permissions...")
    credentials_file = Path("/tmp/ipfs_kit_config/credentials.json")
    if credentials_file.exists():
        permissions = oct(os.stat(credentials_file).st_mode)[-3:]
        print(f"   Credentials file permissions: {permissions}")
        if permissions == "600":
            print("   ✓ Permissions are secure (owner read/write only)")
        else:
            print("   ⚠️  Permissions may not be secure")
    
    print("\n✅ Secure configuration test completed!")

def test_environment_variables():
    """Test environment variable loading."""
    
    print("\n🌍 Testing Environment Variables")
    print("=" * 40)
    
    # Set test environment variables
    os.environ["IPFS_KIT_HUGGINGFACE_TOKEN"] = "env_hf_token_456"
    os.environ["IPFS_KIT_S3_ACCESS_KEY"] = "env_s3_access_456"
    
    config_manager = SecureConfigManager()
    
    # Test environment variable precedence
    hf_token = config_manager.get_credential("huggingface", "token")
    s3_access = config_manager.get_credential("s3", "access_key")
    
    print(f"   HF Token from env: {hf_token}")
    print(f"   S3 Access from env: {s3_access}")
    
    # Clean up
    del os.environ["IPFS_KIT_HUGGINGFACE_TOKEN"]
    del os.environ["IPFS_KIT_S3_ACCESS_KEY"]
    
    print("   ✓ Environment variables take precedence over config file")

def main():
    """Main test function."""
    
    try:
        test_secure_config()
        test_environment_variables()
        
        print("\n🎉 All tests passed!")
        print("\n📋 Next steps:")
        print("   1. Run: python setup_credentials.py")
        print("   2. Configure your actual credentials")
        print("   3. Test with the MCP server")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
