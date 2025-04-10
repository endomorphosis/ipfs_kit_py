# Authentication Integration Guide

This document explains how to integrate credential authentication with the MCP server and storage backends in ipfs_kit_py.

## Overview

The ipfs_kit_py library provides several tools for managing credentials securely:

1. `manage_credentials.py` - Interactive CLI tool for adding/updating credentials
2. `update_mcp_server.py` - Script to update the running MCP server with credentials
3. Configuration stored in `~/.ipfs_kit/config.json` with restricted permissions

## Interactive Credential Management

The credential management tool provides a simple interactive interface:

```bash
# Add credentials interactively
python manage_credentials.py

# Show current credentials
python manage_credentials.py --show

# Export credentials to environment variables
python manage_credentials.py --export
```

## Starting the MCP Server with Credentials

The update script automatically loads credentials and starts/restarts the MCP server:

```bash
python update_mcp_server.py
```

This will:
1. Load credentials from the configuration file
2. Detect if any credentials are missing
3. Prompt to start/restart the server with the credentials
4. Start the MCP server with the credential environment variables

## Integration with Claude Code

When using Claude Code to work with ipfs_kit_py, follow these steps:

1. Use `manage_credentials.py` to securely store your credentials:
   ```
   python manage_credentials.py
   ```

2. When prompted by Claude for HuggingFace or other credentials, reference the credential management tools:
   ```
   I've added my HuggingFace credentials using manage_credentials.py. 
   Please proceed with testing using those stored credentials.
   ```

3. To test with the stored credentials:
   ```
   # First update the server with credentials
   python update_mcp_server.py
   
   # Then run the tests
   python test_all_backends.py
   ```

## Security Considerations

- Credentials are stored in `~/.ipfs_kit/config.json` with 600 permissions (user-readable only)
- The `.env` file created by the export option also uses 600 permissions
- Never commit credential files to version control
- The MCP server only loads credentials on startup (requires restart to apply changes)
- Environment variables take precedence over stored configuration

## Configuration File Structure

```json
{
  "credentials": {
    "huggingface": {
      "token": "your_huggingface_token",
      "test_repo": "username/repo"
    },
    "aws": {
      "access_key_id": "your_aws_access_key",
      "secret_access_key": "your_aws_secret_key",
      "region": "us-east-1"
    },
    "s3": {
      "test_bucket": "test-bucket"
    },
    "storacha": {
      "token": "your_web3_storage_token"
    }
  }
}
```

## Implementation Details

The credential management system implements:

1. **Secure storage** - Configs saved with proper permissions
2. **Easy access** - Simple CLI interface for management
3. **Environment precedence** - Environment variables override stored credentials
4. **Secure input** - Password fields don't echo to terminal
5. **Flexible export** - Export stored credentials to environment variables
6. **Server integration** - Seamless integration with MCP server

By using these tools, you can securely integrate credentials with Claude Code without directly sharing sensitive tokens in conversations.