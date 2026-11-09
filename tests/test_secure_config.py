#!/usr/bin/env python3
"""
Tests for secure configuration storage.

Tests encryption, decryption, key management, and migration functionality.
"""

import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ipfs_kit_py.secure_config import SecureConfigManager, CRYPTOGRAPHY_AVAILABLE


def test_encryption_status():
    """Test encryption status check."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SecureConfigManager(data_dir=tmpdir, enable_encryption=True)
        status = manager.get_encryption_status()
        
        assert 'encryption_enabled' in status
        assert 'cryptography_available' in status
        assert 'key_exists' in status
        
        print("✅ Encryption status check works")


def test_save_and_load_encrypted():
    """Test saving and loading encrypted config."""
    if not CRYPTOGRAPHY_AVAILABLE:
        print("⚠️  Skipping encryption test (cryptography not installed)")
        return
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SecureConfigManager(data_dir=tmpdir, enable_encryption=True)
        
        # Test config with sensitive data
        config = {
            "backends": {
                "s3_main": {
                    "type": "s3",
                    "config": {
                        "endpoint": "https://s3.amazonaws.com",
                        "access_key": "AKIAIOSFODNN7EXAMPLE",
                        "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
                        "bucket": "my-bucket",
                        "region": "us-east-1"
                    }
                }
            }
        }
        
        # Save encrypted
        success = manager.save_config("test.json", config, encrypt=True)
        assert success, "Failed to save config"
        
        # Verify file exists
        config_file = Path(tmpdir) / "test.json"
        assert config_file.exists(), "Config file not created"
        
        # Read raw file to verify encryption
        with open(config_file, 'r') as f:
            raw_data = json.load(f)
        
        # Check that sensitive field is encrypted
        access_key_data = raw_data["backends"]["s3_main"]["config"]["access_key"]
        assert isinstance(access_key_data, dict), "Sensitive field not encrypted"
        assert "__encrypted__" in access_key_data, "Missing encryption marker"
        assert access_key_data["__encrypted__"] == True, "Encryption marker not set"
        
        # Load and decrypt
        loaded_config = manager.load_config("test.json", decrypt=True)
        assert loaded_config is not None, "Failed to load config"
        
        # Verify decrypted data matches original
        assert loaded_config["backends"]["s3_main"]["config"]["access_key"] == "AKIAIOSFODNN7EXAMPLE"
        assert loaded_config["backends"]["s3_main"]["config"]["secret_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        
        # Verify non-sensitive fields are not encrypted
        assert loaded_config["backends"]["s3_main"]["type"] == "s3"
        assert loaded_config["backends"]["s3_main"]["config"]["endpoint"] == "https://s3.amazonaws.com"
        
        print("✅ Encryption and decryption work correctly")


def test_sensitive_field_detection():
    """Test detection of sensitive fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SecureConfigManager(data_dir=tmpdir)
        
        # Test various field names
        assert manager._is_sensitive_field("password")
        assert manager._is_sensitive_field("secret_key")
        assert manager._is_sensitive_field("access_key")
        assert manager._is_sensitive_field("api_token")
        assert manager._is_sensitive_field("bearer_token")
        
        # Non-sensitive fields
        assert not manager._is_sensitive_field("endpoint")
        assert not manager._is_sensitive_field("bucket")
        assert not manager._is_sensitive_field("region")
        assert not manager._is_sensitive_field("name")
        
        print("✅ Sensitive field detection works")


def test_backward_compatibility():
    """Test backward compatibility with plain JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SecureConfigManager(data_dir=tmpdir, enable_encryption=False)
        
        config = {
            "backends": {
                "ipfs_local": {
                    "type": "ipfs",
                    "config": {
                        "api_url": "http://localhost:5001"
                    }
                }
            }
        }
        
        # Save without encryption
        success = manager.save_config("plain.json", config, encrypt=False)
        assert success, "Failed to save plain config"
        
        # Load without decryption
        loaded_config = manager.load_config("plain.json", decrypt=False)
        assert loaded_config is not None, "Failed to load plain config"
        assert loaded_config == config, "Config mismatch"
        
        print("✅ Backward compatibility with plain JSON works")


def test_migration():
    """Test migration from plain to encrypted format."""
    if not CRYPTOGRAPHY_AVAILABLE:
        print("⚠️  Skipping migration test (cryptography not installed)")
        return
    
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        
        # Create plain config file
        plain_config = {
            "backends": {
                "hf_models": {
                    "type": "huggingface",
                    "config": {
                        "token": "hf_secret_token_12345",
                        "endpoint": "https://huggingface.co"
                    }
                }
            }
        }
        
        config_file = data_dir / "backends.json"
        with open(config_file, 'w') as f:
            json.dump(plain_config, f)
        
        # Migrate to encrypted
        manager = SecureConfigManager(data_dir=tmpdir, enable_encryption=True)
        success = manager.migrate_to_encrypted("backends.json")
        assert success, "Migration failed"
        
        # Verify backup was created
        backups = list(data_dir.glob("backends.json.backup.*"))
        assert len(backups) > 0, "Backup not created"
        
        # Load and verify encrypted data
        loaded_config = manager.load_config("backends.json", decrypt=True)
        assert loaded_config is not None, "Failed to load migrated config"
        assert loaded_config["backends"]["hf_models"]["config"]["token"] == "hf_secret_token_12345"
        
        print("✅ Migration from plain to encrypted works")


def test_key_rotation():
    """Test encryption key rotation."""
    if not CRYPTOGRAPHY_AVAILABLE:
        print("⚠️  Skipping key rotation test (cryptography not installed)")
        return
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SecureConfigManager(data_dir=tmpdir, enable_encryption=True)
        
        # Create encrypted configs
        config1 = {
            "backends": {
                "s3_test": {
                    "config": {
                        "access_key": "ORIGINAL_KEY_1",
                        "secret_key": "ORIGINAL_SECRET_1"
                    }
                }
            }
        }
        
        config2 = {
            "backends": {
                "gdrive_test": {
                    "config": {
                        "token": "ORIGINAL_TOKEN_2"
                    }
                }
            }
        }
        
        manager.save_config("config1.json", config1, encrypt=True)
        manager.save_config("config2.json", config2, encrypt=True)
        
        # Rotate key
        success = manager.rotate_key()
        assert success, "Key rotation failed"
        
        # Verify backup key was created
        keyring_dir = Path(tmpdir) / ".keyring"
        backups = list(keyring_dir.glob("master.key.backup.*"))
        assert len(backups) > 0, "Key backup not created"
        
        # Verify configs can still be decrypted with new key
        loaded1 = manager.load_config("config1.json", decrypt=True)
        loaded2 = manager.load_config("config2.json", decrypt=True)
        
        assert loaded1["backends"]["s3_test"]["config"]["access_key"] == "ORIGINAL_KEY_1"
        assert loaded2["backends"]["gdrive_test"]["config"]["token"] == "ORIGINAL_TOKEN_2"
        
        print("✅ Key rotation works correctly")


def test_file_permissions():
    """Test that files are created with secure permissions."""
    if not CRYPTOGRAPHY_AVAILABLE:
        print("⚠️  Skipping permissions test (cryptography not installed)")
        return
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = SecureConfigManager(data_dir=tmpdir, enable_encryption=True)
        
        config = {"test": "data"}
        manager.save_config("test.json", config)
        
        config_file = Path(tmpdir) / "test.json"
        key_file = Path(tmpdir) / ".keyring" / "master.key"
        
        # Check file permissions (0o600 = owner read/write only)
        import stat
        config_mode = config_file.stat().st_mode & 0o777
        key_mode = key_file.stat().st_mode & 0o777
        
        assert config_mode == 0o600, f"Config file has wrong permissions: {oct(config_mode)}"
        assert key_mode == 0o600, f"Key file has wrong permissions: {oct(key_mode)}"
        
        print("✅ File permissions are secure (0o600)")


def run_all_tests():
    """Run all tests."""
    print("Running Secure Configuration Tests")
    print("=" * 50)
    
    tests = [
        test_encryption_status,
        test_sensitive_field_detection,
        test_backward_compatibility,
        test_save_and_load_encrypted,
        test_migration,
        test_key_rotation,
        test_file_permissions
    ]
    
    failed = 0
    for test in tests:
        try:
            print(f"\nRunning {test.__name__}...")
            test()
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 50)
    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
