# Secure Credential Management for IPFS Kit

This document explains how to securely manage credentials for the IPFS Kit MCP server.

## 🔐 Security Overview

The IPFS Kit now uses a secure credential management system that:

- **Never stores credentials in code** - All secrets are loaded from secure config files or environment variables
- **Uses file permissions** - Credential files have 600 permissions (owner read/write only)
- **Supports environment variables** - Environment variables take precedence over config files
- **Excludes files from git** - Credential files are automatically excluded from version control

## 📁 File Structure

```
/tmp/ipfs_kit_config/
├── credentials.json          # Secure credential storage (600 permissions)
├── credentials.example.json  # Example credential file
├── backend_configs.json      # Backend configurations (without credentials)
├── .env.example             # Example environment variables
└── .gitignore               # Excludes credential files from git
```

## 🚀 Quick Setup

### 1. Run the Setup Script

```bash
python setup_credentials.py
```

This interactive script will guide you through:
- Setting up Hugging Face tokens
- Configuring S3 credentials
- Setting up Storacha tokens
- Creating secure config files with proper permissions

### 2. Alternative: Manual Setup

Create `/tmp/ipfs_kit_config/credentials.json`:

```json
{
  "huggingface": {
    "token": "hf_your_actual_token_here"
  },
  "s3": {
    "access_key": "your_s3_access_key",
    "secret_key": "your_s3_secret_key"
  },
  "storacha": {
    "token": "your_storacha_token"
  }
}
```

Set secure permissions:
```bash
chmod 600 /tmp/ipfs_kit_config/credentials.json
```

### 3. Alternative: Environment Variables

Set environment variables (these take precedence):

```bash
export IPFS_KIT_HUGGINGFACE_TOKEN="hf_your_token_here"
export IPFS_KIT_S3_ACCESS_KEY="your_s3_access_key"
export IPFS_KIT_S3_SECRET_KEY="your_s3_secret_key"
export IPFS_KIT_STORACHA_TOKEN="your_storacha_token"
```

## 🛠️ Environment Variable Format

All environment variables follow the pattern:
```
IPFS_KIT_{SERVICE}_{CREDENTIAL_TYPE}
```

Examples:
- `IPFS_KIT_HUGGINGFACE_TOKEN`
- `IPFS_KIT_S3_ACCESS_KEY`
- `IPFS_KIT_S3_SECRET_KEY`
- `IPFS_KIT_STORACHA_TOKEN`

## 🔍 How It Works

### Credential Loading Priority

1. **Environment Variables** (highest priority)
2. **Credential Files** (`credentials.json`)
3. **Default/Empty** (lowest priority)

### Backend Configuration

The `SecureConfigManager` class:
- Loads default backend configurations
- Injects credentials securely at runtime
- Never stores credentials in backend config files
- Provides clean separation between config and secrets

### File Permissions

- `credentials.json`: 600 (owner read/write only)
- Configuration files: Standard permissions
- Example files: Standard permissions

## 🧪 Testing

Test the secure configuration:

```bash
python test_secure_config.py
```

This will:
- Test credential storage and retrieval
- Verify environment variable precedence
- Check file permissions
- Validate backend configuration injection

## 📋 Migration from Legacy System

If you're migrating from the old hardcoded system:

1. **Remove hardcoded credentials** from any Python files
2. **Run the setup script** to configure credentials securely
3. **Update .gitignore** to exclude credential files
4. **Test the new system** with the MCP server

## 🚨 Security Best Practices

### ✅ Do:
- Use environment variables for production deployments
- Set proper file permissions (600) on credential files
- Keep credential files out of version control
- Use different credentials for different environments
- Regularly rotate your credentials

### ❌ Don't:
- Commit credential files to git
- Share credential files via email or chat
- Use the same credentials across multiple projects
- Store credentials in code comments or documentation
- Use weak or default credentials

## 🔧 Troubleshooting

### Missing Credentials

If you see warnings like:
```
⚠️  No credential found for huggingface token
```

1. Check if the credential file exists: `/tmp/ipfs_kit_config/credentials.json`
2. Verify the file has correct permissions: `ls -la /tmp/ipfs_kit_config/credentials.json`
3. Check the JSON format is valid: `python -m json.tool /tmp/ipfs_kit_config/credentials.json`
4. Try setting environment variables as a fallback

### Permission Errors

If you get permission errors:
```bash
chmod 600 /tmp/ipfs_kit_config/credentials.json
```

### Environment Variable Issues

Test environment variables:
```bash
echo $IPFS_KIT_HUGGINGFACE_TOKEN
```

## 📚 API Reference

### SecureConfigManager

```python
from mcp.ipfs_kit.core.config_manager import SecureConfigManager

config_manager = SecureConfigManager()

# Get a credential
token = config_manager.get_credential("huggingface", "token")

# Set a credential
config_manager.set_credential("huggingface", "token", "hf_new_token")

# Get backend config with credentials injected
config = config_manager.get_backend_config("huggingface")

# Get all backend configs
all_configs = config_manager.get_all_backend_configs()
```

### Environment Variables

```python
import os

# Set environment variables
os.environ["IPFS_KIT_HUGGINGFACE_TOKEN"] = "hf_token"

# Environment variables take precedence
config_manager = SecureConfigManager()
token = config_manager.get_credential("huggingface", "token")  # Returns "hf_token"
```

## 🔄 Updates and Maintenance

### Updating Credentials

1. **Via Setup Script**: Run `python setup_credentials.py` again
2. **Via API**: Use `SecureConfigManager.set_credential()`
3. **Via Environment Variables**: Update your environment

### Backup and Recovery

- **Backup**: Copy `/tmp/ipfs_kit_config/credentials.json` to a secure location
- **Recovery**: Restore the file and set proper permissions
- **Migration**: Use the setup script to migrate to a new system

## 🆘 Support

If you encounter issues:

1. **Check the logs** for credential-related warnings
2. **Run the test script** to verify configuration
3. **Review file permissions** and paths
4. **Check environment variables** and their precedence
5. **Validate JSON syntax** in credential files

For additional support, review the main project documentation or create an issue in the repository.
