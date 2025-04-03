# External Storage Backends

IPFS Kit integrates with external storage systems like S3-compatible services and Storacha (formerly Web3.Storage) to provide additional options for content persistence and retrieval, often acting as fallback or archival tiers.

## Storacha (Web3.Storage) Integration

The `storacha_kit.py` module provides an interface to interact with Storacha, allowing you to upload content (which gets pinned on IPFS via Storacha's infrastructure) and potentially retrieve it.

**Key Features:**

-   Upload data (files, bytes, directories) to Storacha.
-   Retrieve content using Storacha gateways or directly via IPFS CIDs.
-   Manage uploads and spaces (depending on Storacha API capabilities).

**Usage:**

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# ipfs_kit automatically initializes storacha_kit
kit = ipfs_kit()

# Ensure you have configured Storacha credentials (e.g., via environment variables
# or a configuration mechanism if implemented in storacha_kit.py)

# Upload a file
try:
    # Assuming storacha_kit has an 'upload_file' method
    if hasattr(kit, 'storacha_kit') and hasattr(kit.storacha_kit, 'upload_file'):
        upload_result = kit.storacha_kit.upload_file("my_dataset.zip")
        if upload_result.get("success"):
            print(f"Uploaded to Storacha, CID: {upload_result.get('cid')}")
        else:
            print(f"Storacha upload failed: {upload_result.get('error')}")
    else:
        print("storacha_kit or upload_file method not available.")

    # Content added via storacha_kit might also be accessible via standard IPFS methods
    # if the CID is known and reachable on the IPFS network.
    # cid = upload_result.get('cid')
    # if cid:
    #    content = kit.ipfs_cat(cid)

except Exception as e:
    print(f"An error occurred during Storacha operation: {e}")

```

*Note: The exact methods and capabilities depend on the implementation within `storacha_kit.py` and the Storacha API it targets.*

## S3-Compatible Storage Integration

The `s3_kit.py` module provides an interface for interacting with S3-compatible object storage services (like AWS S3, MinIO, etc.). This can be used as a persistent storage layer or a fallback retrieval source.

**Key Features:**

-   Upload content to S3 buckets.
-   Download content from S3 buckets.
-   List bucket contents.
-   Potentially map IPFS CIDs to S3 object keys (requires specific implementation logic).

**Usage:**

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# ipfs_kit automatically initializes s3_kit
kit = ipfs_kit()

# Ensure S3 credentials and endpoint are configured (e.g., via environment
# variables or a configuration mechanism if implemented in s3_kit.py)
# Common env vars: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_ENDPOINT_URL

# Upload a file to S3
try:
    # Assuming s3_kit has an 'upload_file' method
    if hasattr(kit, 's3_kit') and hasattr(kit.s3_kit, 'upload_file'):
        # Example: Uploading with a specific key (e.g., derived from CID)
        cid = "QmSomeCID..."
        s3_key = f"ipfs/{cid}"
        bucket_name = "my-ipfs-bucket"

        upload_result = kit.s3_kit.upload_file(
            local_path="my_local_file.dat",
            bucket=bucket_name,
            key=s3_key
        )
        if upload_result.get("success"):
            print(f"Uploaded to S3: s3://{bucket_name}/{s3_key}")
        else:
            print(f"S3 upload failed: {upload_result.get('error')}")
    else:
        print("s3_kit or upload_file method not available.")

    # Download from S3
    # Assuming s3_kit has a 'download_file' method
    if hasattr(kit, 's3_kit') and hasattr(kit.s3_kit, 'download_file'):
        download_result = kit.s3_kit.download_file(
            bucket=bucket_name,
            key=s3_key,
            local_path="downloaded_file.dat"
        )
        if download_result.get("success"):
            print(f"Downloaded from S3 to downloaded_file.dat")
        else:
            print(f"S3 download failed: {download_result.get('error')}")

except Exception as e:
    print(f"An error occurred during S3 operation: {e}")
```

*Note: The exact methods depend on the implementation within `s3_kit.py`. Integration often involves mapping IPFS CIDs to S3 object keys, which requires specific logic within the application or potentially within the `TieredCacheManager` or `MetadataIndex`.*

## Integration with Tiered Caching & Metadata

Both Storacha and S3 can act as tiers within the `TieredCacheManager` or have their content locations tracked by the `MetadataIndex`. This allows `ipfs_kit` to automatically fetch content from these backends if it's not available locally or on faster tiers. Configuration for this integration would typically happen within the `TieredCacheManager` setup or the `MetadataIndex` record structure.
