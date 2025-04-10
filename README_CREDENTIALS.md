# Secure Credential Management for Storage Backends

This guide explains how to securely configure and manage credentials for various storage backends used by IPFS Kit and the MCP server.

## Secure Credential Storage

IPFS Kit provides a dedicated credential management system that securely stores your credentials in a protected configuration file. This is the recommended approach for managing credentials:

```python
# Import the credential management utilities
from ipfs_kit_py.credential_manager import (
    add_huggingface_credentials,
    add_s3_credentials,
    add_storacha_credentials,
    get_stored_credentials
)

# Store HuggingFace credentials securely
add_huggingface_credentials(
    token="your_huggingface_token_here",
    repo="your_username/repository_name"  # Optional
)

# Store S3 credentials securely
add_s3_credentials(
    access_key="your_aws_access_key",
    secret_key="your_aws_secret_key",
    server="object.lga1.coreweave.com",  # Optional, for non-AWS S3 providers
    bucket="your-test-bucket-name"  # Optional
)

# Store Storacha/Web3.Storage credentials securely
add_storacha_credentials(
    token="your_storacha_token_here"
)
```

### Security Features

The credential management system implements these security measures:

1. **Protected File Storage**: Credentials are stored in `~/.ipfs_kit/config.json` with file permissions set to 0o600 (user read/write only)
2. **Directory Protection**: The `~/.ipfs_kit` directory has permissions set to 0o700 (user access only)
3. **No Hardcoded Credentials**: Credentials are never hardcoded in source files
4. **Memory Protection**: Credentials are only loaded when needed and not kept in memory unnecessarily

## Using the Secure Credential Management Tools

IPFS Kit provides dedicated scripts for managing credentials securely:

```bash
# Store HuggingFace credentials
python setup_hf_credentials.py --token "your_token" --repo "your_repo"

# Store S3 credentials
python setup_s3_credentials.py --access-key "your_key" --secret-key "your_secret" --server "your_s3_server" --bucket "your_bucket"
```

## Retrieving Stored Credentials

In your code, retrieve credentials using the `get_stored_credentials()` function:

```python
from ipfs_kit_py.credential_manager import get_stored_credentials

# Get all stored credentials
creds = get_stored_credentials()

# Access specific backend credentials
hf_creds = creds.get("huggingface", {})
s3_creds = creds.get("s3", {})
storacha_creds = creds.get("storacha", {})

# Use the credentials
hf_token = hf_creds.get("token")
s3_access_key = s3_creds.get("access_key")
```

## Environment Variables

For CI/CD environments or temporary usage, you can also use environment variables:

```bash
# Set HuggingFace credentials
export HUGGINGFACE_TOKEN="your_huggingface_token_here"
export HF_TEST_REPO="your_username/repository_name"

# Set S3 credentials
export AWS_ACCESS_KEY_ID="your_aws_access_key"
export AWS_SECRET_ACCESS_KEY="your_aws_secret_key"
export S3_TEST_BUCKET="your-test-bucket-name"
export S3_ENDPOINT_URL="https://your-s3-endpoint.com"

# Set Storacha credentials
export W3_STORE_TOKEN="your_storacha_token_here"
```

You can also store these in a `.env` file and load them with:

```bash
source .env
```

## Credential Priority

The MCP server checks for credentials in the following order:

1. Environment variables (highest priority)
2. Secure configuration file at `~/.ipfs_kit/config.json` (recommended)
3. Default credential files (like `~/.aws/credentials` for AWS)

## Verifying Storage Backend Credentials

To verify that your credentials are working correctly, run the backend verification test:

```bash
# Test all backends
python test_all_backends.py

# Test a specific backend
python test_all_backends.py --backend huggingface
python test_all_backends.py --backend s3
```

This will attempt to upload a 1MB test file to each configured backend and report the results.

## MCP Server Integration

When using the MCP server, credentials are automatically loaded from the secure storage or environment variables:

```bash
# Start the MCP server with credentials from environment
HUGGINGFACE_TOKEN="your_token" python run_mcp_server.py

# Or use the credentials stored in the secure configuration file (recommended)
python run_mcp_server.py
```

## Production Deployments

For production deployments, consider these additional security measures:

1. **Kubernetes Secrets**: Store credentials as Kubernetes secrets and mount them as environment variables
2. **AWS Secrets Manager/Parameter Store**: Retrieve credentials programmatically at runtime
3. **HashiCorp Vault**: Use a dedicated secrets management solution
4. **Instance Roles**: For AWS deployments, use IAM roles instead of explicit credentials

Example Kubernetes secret:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: storage-credentials
type: Opaque
data:
  HUGGINGFACE_TOKEN: base64encodedtoken
  AWS_ACCESS_KEY_ID: base64encodedkey
  AWS_SECRET_ACCESS_KEY: base64encodedsecret
```

Then mount in your deployment:

```yaml
env:
  - name: HUGGINGFACE_TOKEN
    valueFrom:
      secretKeyRef:
        name: storage-credentials
        key: HUGGINGFACE_TOKEN
```

## Credential Security Checklist

✅ Use the secure credential management system  
✅ Never hardcode credentials in source code  
✅ Protect credential files with appropriate permissions  
✅ Rotate credentials regularly  
✅ Use the principle of least privilege (only required permissions)  
✅ Monitor credential usage through logs  
✅ Implement MFA for credential access where possible