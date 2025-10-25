# Encrypted Configuration Storage Guide

## Overview

The IPFS Kit now supports encrypted storage of sensitive configuration data (credentials, API keys, tokens) using industry-standard Fernet symmetric encryption from the `cryptography` library.

## Features

✅ **Automatic Encryption** - Sensitive fields are automatically detected and encrypted  
✅ **Secure Key Management** - Encryption keys stored in `~/.ipfs_kit/.keyring/` with 0o600 permissions  
✅ **Backward Compatible** - Works with existing plain JSON configs  
✅ **Easy Migration** - One-command migration from plain to encrypted  
✅ **Key Rotation** - Support for rotating encryption keys  
✅ **Master Password** - Optional password-based key derivation  
✅ **Selective Encryption** - Only sensitive fields are encrypted, metadata remains readable  

## Installation

Install the `cryptography` library:

```bash
pip install cryptography
```

## Quick Start

### Enable Encryption for New Configs

```python
from ipfs_kit_py.secure_config import SecureConfigManager

# Create manager with encryption enabled
manager = SecureConfigManager(enable_encryption=True)

# Save config with automatic encryption
config = {
    "backends": {
        "s3_main": {
            "type": "s3",
            "config": {
                "endpoint": "https://s3.amazonaws.com",
                "access_key": "AKIA...",          # Will be encrypted
                "secret_key": "SECRET123",         # Will be encrypted
                "bucket": "my-bucket",            # NOT encrypted (not sensitive)
                "region": "us-east-1"             # NOT encrypted (not sensitive)
            }
        }
    }
}

manager.save_config("backends.json", config)

# Load and decrypt
loaded_config = manager.load_config("backends.json")
# All sensitive fields automatically decrypted
```

### Migrate Existing Plain Configs

```bash
# Migrate a specific file
python -m ipfs_kit_py.cli_secure_config migrate backends.json

# Migrate all config files
python -m ipfs_kit_py.cli_secure_config migrate-all

# Check encryption status
python -m ipfs_kit_py.cli_secure_config status
```

## Sensitive Field Detection

The following field names are automatically detected as sensitive and encrypted:

- `password`
- `secret` (including `secret_key`, `client_secret`)
- `key` (including `api_key`, `access_key`, `private_key`)
- `token` (including `auth_token`, `bearer_token`, `api_token`)
- `credential`

**Examples:**
```python
# These will be ENCRYPTED:
{
    "access_key": "AKIA123",
    "secret_key": "secret",
    "api_token": "token123",
    "password": "mypassword"
}

# These will NOT be encrypted:
{
    "endpoint": "https://api.example.com",
    "bucket": "my-bucket",
    "region": "us-east-1",
    "name": "backend_name"
}
```

## Encrypted File Format

Encrypted fields are stored in a special format:

```json
{
  "backends": {
    "s3_main": {
      "type": "s3",
      "config": {
        "endpoint": "https://s3.amazonaws.com",
        "access_key": {
          "__encrypted__": true,
          "version": "v1",
          "value": "gAAAAABh..."
        },
        "secret_key": {
          "__encrypted__": true,
          "version": "v1",
          "value": "gAAAAABh..."
        },
        "bucket": "my-bucket",
        "region": "us-east-1"
      }
    }
  }
}
```

## CLI Commands

### Check Encryption Status

```bash
python -m ipfs_kit_py.cli_secure_config status
```

Output:
```
Encryption Status:
==================================================
Encryption Enabled: True
Cryptography Library: ✅ Available
Encryption Key: ✅ Exists
Key Location: /home/user/.ipfs_kit/.keyring/master.key
Config Directory: /home/user/.ipfs_kit
Keyring Directory: /home/user/.ipfs_kit/.keyring
```

### Migrate Single File

```bash
python -m ipfs_kit_py.cli_secure_config migrate backends.json
```

Creates backup: `backends.json.backup.20250117_120000`

### Migrate All Files

```bash
# Interactive (asks for confirmation)
python -m ipfs_kit_py.cli_secure_config migrate-all

# Non-interactive
python -m ipfs_kit_py.cli_secure_config migrate-all --yes
```

### Rotate Encryption Key

```bash
# Interactive
python -m ipfs_kit_py.cli_secure_config rotate-key

# Non-interactive
python -m ipfs_kit_py.cli_secure_config rotate-key --yes
```

This will:
1. Load all configs with old key
2. Backup old key
3. Generate new key
4. Re-encrypt all configs with new key

### Decrypt and View Config

```bash
python -m ipfs_kit_py.cli_secure_config decrypt backends.json
```

Outputs decrypted JSON to stdout.

## Python API

### Basic Usage

```python
from ipfs_kit_py.secure_config import SecureConfigManager

# Initialize
manager = SecureConfigManager(
    data_dir="~/.ipfs_kit",           # Config directory
    enable_encryption=True,            # Enable encryption
    master_password=None               # Optional master password
)

# Save encrypted config
config = {"backends": {...}}
manager.save_config("backends.json", config, encrypt=True)

# Load and decrypt
loaded = manager.load_config("backends.json", decrypt=True)

# Get encryption status
status = manager.get_encryption_status()
```

### With Master Password

```python
# Use password-based key derivation
manager = SecureConfigManager(
    enable_encryption=True,
    master_password="my-secure-password"
)

# Key will be derived from password using PBKDF2
manager.save_config("backends.json", config)
```

### Migration

```python
# Migrate plain config to encrypted
success = manager.migrate_to_encrypted("backends.json")

if success:
    print("Migration successful")
    print("Backup created automatically")
```

### Key Rotation

```python
# Rotate encryption key and re-encrypt all configs
success = manager.rotate_key()

if success:
    print("Key rotated successfully")
    print("All configs re-encrypted")
    print("Old key backed up")
```

### Convenience Functions

```python
from ipfs_kit_py.secure_config import save_secure_config, load_secure_config

# Quick save
save_secure_config("backends.json", config)

# Quick load
loaded = load_secure_config("backends.json")
```

## Integration with Dashboard

The encrypted config module integrates seamlessly with the dashboard:

```python
# In dashboard code
from ipfs_kit_py.secure_config import SecureConfigManager

class Dashboard:
    def __init__(self, config):
        self.secure_config = SecureConfigManager(
            data_dir=config.get('data_dir'),
            enable_encryption=config.get('enable_encryption', True)
        )
    
    async def _get_backend_configs(self):
        """Get backend configurations with automatic decryption."""
        config = self.secure_config.load_config("backends.json")
        return config.get("backends", {})
    
    async def _update_backend_config(self, backend_name, config_data):
        """Save backend config with automatic encryption."""
        backends = self.secure_config.load_config("backends.json") or {"backends": {}}
        backends["backends"][backend_name] = config_data
        self.secure_config.save_config("backends.json", backends)
```

## Security Considerations

### ✅ What's Protected

- **Credential Files**: Config files have 0o600 permissions (owner read/write only)
- **Encryption Keys**: Keys stored in `.keyring/` with 0o600 permissions
- **Sensitive Fields**: Automatically encrypted using Fernet (AES-128-CBC)
- **Key Derivation**: PBKDF2 with 100,000 iterations for password-based keys

### ⚠️ Important Notes

1. **Key Storage**: The encryption key is stored on disk. If an attacker gains access to your user account, they can decrypt the configs. For higher security, consider:
   - Using master password mode
   - Storing keys in system keychain/keyring
   - Using hardware security modules (HSMs)

2. **Backup Keys**: When rotating keys, old keys are backed up. Delete old backups securely when no longer needed.

3. **Plain Text Fallback**: The system supports plain JSON for backward compatibility. Ensure encryption is enabled in production.

4. **Memory Security**: Decrypted values exist in memory. Use secure memory practices for highly sensitive deployments.

### Best Practices

1. **Enable Encryption in Production**
   ```python
   manager = SecureConfigManager(enable_encryption=True)
   ```

2. **Use Strong Master Passwords**
   ```python
   manager = SecureConfigManager(master_password="use-a-strong-password-here")
   ```

3. **Regular Key Rotation**
   ```bash
   # Rotate keys every 90 days
   python -m ipfs_kit_py.cli_secure_config rotate-key
   ```

4. **Secure Backups**
   - Encrypt backup files if storing off-system
   - Delete old key backups securely

5. **File Permissions**
   ```bash
   # Verify permissions
   ls -la ~/.ipfs_kit/backends.json        # Should be -rw------- (0o600)
   ls -la ~/.ipfs_kit/.keyring/master.key  # Should be -rw------- (0o600)
   ```

## Troubleshooting

### Encryption Not Working

**Problem**: Files saved in plain text despite encryption enabled

**Solution**:
```bash
# Check if cryptography is installed
python -c "from cryptography.fernet import Fernet; print('OK')"

# If not, install it
pip install cryptography

# Verify encryption status
python -m ipfs_kit_py.cli_secure_config status
```

### Cannot Decrypt Configs

**Problem**: `DecryptionError` when loading configs

**Possible causes**:
1. Wrong encryption key
2. Corrupted config file
3. Config encrypted with different key

**Solution**:
```bash
# Check if key exists
ls -la ~/.ipfs_kit/.keyring/master.key

# Try loading backup
python -m ipfs_kit_py.cli_secure_config decrypt backends.json.backup.TIMESTAMP
```

### Migration Failed

**Problem**: Migration command fails

**Solution**:
```bash
# Check file permissions
ls -la ~/.ipfs_kit/backends.json

# Verify file is valid JSON
python -c "import json; json.load(open('~/.ipfs_kit/backends.json'))"

# Try manual migration
python -c "
from ipfs_kit_py.secure_config import SecureConfigManager
manager = SecureConfigManager(enable_encryption=True)
manager.migrate_to_encrypted('backends.json')
"
```

## Examples

### Complete Backend Configuration

```python
from ipfs_kit_py.secure_config import SecureConfigManager

manager = SecureConfigManager(enable_encryption=True)

config = {
    "backends": {
        "s3_production": {
            "type": "s3",
            "description": "Production S3 storage",
            "config": {
                "endpoint": "https://s3.amazonaws.com",
                "access_key": "AKIAIOSFODNN7EXAMPLE",      # ENCRYPTED
                "secret_key": "wJalrXUtnFEMI/K7MDENG...",  # ENCRYPTED
                "bucket": "prod-bucket",
                "region": "us-east-1"
            }
        },
        "hf_models": {
            "type": "huggingface",
            "description": "HuggingFace model storage",
            "config": {
                "token": "hf_AbCdEfGhIjKlMnOpQrStUvWx...",  # ENCRYPTED
                "endpoint": "https://huggingface.co"
            }
        },
        "gdrive_backup": {
            "type": "gdrive",
            "description": "Google Drive backup",
            "config": {
                "credentials_path": "/path/to/credentials.json",
                "token": "ya29.a0AfH6SMBx..."              # ENCRYPTED
            }
        }
    }
}

# Save with encryption
manager.save_config("backends.json", config)

# Load with decryption
loaded = manager.load_config("backends.json")

# Access decrypted values
s3_key = loaded["backends"]["s3_production"]["config"]["access_key"]
print(f"Access key: {s3_key}")  # Original value, decrypted
```

### Gradual Migration

```python
# Step 1: Enable encryption for new configs only
manager = SecureConfigManager(enable_encryption=True)

# Step 2: Migrate one backend at a time
manager.migrate_to_encrypted("backends.json")

# Step 3: Verify migration
loaded = manager.load_config("backends.json")
assert loaded is not None

# Step 4: Migrate other configs
for config_file in ["pins.json", "buckets.json"]:
    manager.migrate_to_encrypted(config_file)

# Step 5: Update dashboard to use encrypted configs
# (Dashboard automatically handles encryption when using SecureConfigManager)
```

## Performance

Encryption/decryption overhead is minimal:

- **Encryption**: ~0.1ms per field
- **Decryption**: ~0.1ms per field
- **File I/O**: Dominant factor (~10-100ms)

For typical configs with 5-10 sensitive fields, total overhead is <1ms.

## Future Enhancements

Potential improvements:

1. **System Keychain Integration** - Store keys in OS keychain (macOS Keychain, GNOME Keyring, Windows Credential Manager)
2. **Hardware Security Module (HSM)** support
3. **Asymmetric Encryption** - Use public/private key pairs
4. **Multi-user Support** - Different keys for different users
5. **Audit Logging** - Track config access and modifications
6. **Secret Rotation** - Automatic credential rotation

## Support

For issues or questions:

1. Check this guide and troubleshooting section
2. Review test file: `tests/test_secure_config.py`
3. Check encryption status: `python -m ipfs_kit_py.cli_secure_config status`
4. File an issue on GitHub

## Summary

Encrypted configuration storage provides:

✅ **Security** - AES-128-CBC encryption for sensitive fields  
✅ **Ease of Use** - Automatic encryption/decryption  
✅ **Compatibility** - Works with existing code  
✅ **Flexibility** - Optional master passwords, key rotation  
✅ **Production Ready** - Secure defaults, comprehensive tests  

Enable it today to protect your production credentials!
