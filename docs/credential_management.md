# Credential Management

`ipfs-kit-py` often needs to interact with external services that require authentication, such as cloud storage providers (S3, Storacha) or other APIs (Filecoin, potentially IPFS pinning services). The `CredentialManager` class provides a secure and convenient way to store and retrieve credentials for these services.

## Overview

The `CredentialManager` aims to:

*   Provide a unified interface for managing credentials for different services.
*   Store credentials securely (e.g., in a local file with appropriate permissions, potentially using system keyring in the future).
*   Abstract away the details of how credentials are stored and retrieved.
*   Allow multiple named credential sets per service (e.g., "default" S3 account, "backup" S3 account).

## Implementation (`CredentialManager`)

The core logic resides in `ipfs_kit_py/credential_manager.py`:

*   **Initialization**: Can be configured with a storage path or use a default location (e.g., `~/.ipfs_kit/credentials.json`).
*   **Storage**: Currently stores credentials in a JSON file. Each service/name combination gets an entry. **Note:** Storing sensitive credentials in a plain JSON file has security implications. Ensure the file has strict permissions (readable only by the user). Future enhancements might include using system keyrings or environment variables.
*   **Adding Credentials**: Methods like `add_credential`, `add_s3_credentials`, `add_storacha_credentials`, `add_filecoin_credentials` allow adding credentials for specific services.
*   **Retrieving Credentials**: Methods like `get_credential`, `get_s3_credentials`, etc., retrieve stored credentials by service and name (defaulting to "default").
*   **Listing/Removing**: Methods to list available credentials and remove specific entries.

## Configuration

The credential manager itself might have minimal configuration, primarily the storage location:

```python
# Example configuration snippet within main config
config = {
    'credentials': {
        'storage_path': '~/.ipfs_kit/credentials.json', # Default path
        # 'storage_backend': 'file' # Future: 'keyring', 'env_vars'
    }
    # ... other ipfs-kit-py config
}

# Initialization might pick this up, or it might be used internally
from ipfs_kit_py.credential_manager import CredentialManager
# cred_manager = CredentialManager(config=config.get('credentials'))
```

**Security Warning:** The default file storage is convenient but less secure than using environment variables or system keyrings. Avoid committing credential files to version control. Set strict file permissions (`chmod 600 ~/.ipfs_kit/credentials.json`).

## Usage

Credentials are typically managed via the `CredentialManager` instance, which might be accessed through the main `IPFSSimpleAPI` or `IPFSKit` instance, or used directly by components needing external service access.

```python
from ipfs_kit_py.credential_manager import CredentialManager
# Assuming direct usage or access via kit.credentials
cred_manager = CredentialManager()

# --- Adding Credentials ---

# Add default S3 credentials
cred_manager.add_s3_credentials(
    name="default", # Optional, defaults to 'default'
    aws_access_key_id="YOUR_AWS_ACCESS_KEY_ID",
    aws_secret_access_key="YOUR_AWS_SECRET_ACCESS_KEY",
    region_name="us-west-2" # Optional
)
print("Added default S3 credentials.")

# Add credentials for a specific Storacha space
cred_manager.add_storacha_credentials(
    name="my_research_space",
    api_token="YOUR_STORACHA_API_TOKEN",
    space_did="did:web:your-space.storacha.com" # Optional
)
print("Added 'my_research_space' Storacha credentials.")

# Add Filecoin credentials (example, fields might vary)
cred_manager.add_filecoin_credentials(
    name="main_filecoin",
    api_key="YOUR_FILECOIN_API_KEY",
    # api_secret="YOUR_FILECOIN_SECRET" # If applicable
)
print("Added 'main_filecoin' Filecoin credentials.")

# --- Retrieving Credentials ---

# Get default S3 credentials
s3_creds = cred_manager.get_s3_credentials() # Gets 'default'
if s3_creds:
    print(f"Retrieved default S3 Key ID: {s3_creds.get('aws_access_key_id')[:5]}...")
    # Use these credentials with boto3 or other S3 clients
    # import boto3
    # session = boto3.Session(**s3_creds)
    # s3 = session.client('s3')

# Get specific Storacha credentials
storacha_creds = cred_manager.get_storacha_credentials(name="my_research_space")
if storacha_creds:
    print(f"Retrieved Storacha token for 'my_research_space': {storacha_creds.get('api_token')[:5]}...")
    # Use with Storacha client library

# --- Listing Credentials ---
print("\nListing all stored credentials:")
all_creds = cred_manager.list_credentials()
for cred_info in all_creds:
    print(f"- Service: {cred_info['service']}, Name: {cred_info['name']}")

print("\nListing only S3 credentials:")
s3_only = cred_manager.list_credentials(service="s3")
for cred_info in s3_only:
    print(f"- S3 Credential Name: {cred_info['name']}")


# --- Removing Credentials ---
removed = cred_manager.remove_credential(service="filecoin", name="main_filecoin")
if removed:
    print("\nRemoved 'main_filecoin' Filecoin credentials.")
else:
    print("\nFailed to remove 'main_filecoin' Filecoin credentials (maybe not found).")

```

## Integration

Components within `ipfs-kit-py` that interact with external services (like migration tools or potentially storage backends) would use the `CredentialManager` internally to retrieve the necessary credentials based on configuration or user input. For example, an S3 migration tool would likely call `cred_manager.get_s3_credentials(name=...)` to authenticate its S3 client.

## Security Best Practices

*   **Permissions**: Ensure the credential storage file (`~/.ipfs_kit/credentials.json` by default) has strict permissions (e.g., `chmod 600`).
*   **Avoid Hardcoding**: Do not hardcode credentials directly in scripts. Use the `CredentialManager` or environment variables.
*   **Environment Variables**: For production or shared environments, consider storing sensitive keys/secrets in environment variables and configuring components to read from them instead of using the `CredentialManager` file storage.
*   **Secrets Management**: For higher security needs, integrate with dedicated secrets management tools (like HashiCorp Vault, AWS Secrets Manager, etc.). `ipfs-kit-py` might support these in the future.
*   **Regular Rotation**: Rotate API keys and secrets periodically according to the service provider's recommendations. Update them using the `add_credential` methods (which overwrite existing entries).
