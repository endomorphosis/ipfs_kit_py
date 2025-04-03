# External Storage Backends

IPFS Kit integrates with external storage systems like S3-compatible services and Storacha (formerly Web3.Storage) to provide additional options for content persistence and retrieval, functioning as deeper tiers in a comprehensive storage hierarchy.

## Architecture: Multi-Tier Storage Strategy

IPFS Kit implements a sophisticated multi-tier storage architecture that combines the performance benefits of local caching with the durability advantages of cloud storage:

```
┌─────────────────┐
│  Memory Cache   │ <- Fastest, volatile, capacity-limited (100MB default)
└────────┬────────┘
         │ promotion/demotion based on access patterns
┌────────▼────────┐
│   Disk Cache    │ <- Fast, persistent, size-constrained (1GB default)
└────────┬────────┘
         │ overflow and long-term storage
┌────────▼────────┐
│  IPFS Network   │ <- Distributed, content-addressed, peer discovery
└────────┬────────┘
         │ durability and backup
┌────────▼────────┐┌─────────────────┐
│ Storacha/W3.UP  ││     S3-like     │ <- Cloud persistence, archival storage
└─────────────────┘└─────────────────┘
```

This architecture enables:
1. **Performance optimization**: Hot content stays in memory for fastest access
2. **Cost efficiency**: Selectively persist only valuable content to paid storage
3. **Durability guarantees**: Critical content can be stored in multiple backends
4. **Automatic migration**: Content moves between tiers based on access patterns
5. **Transparent access**: Content retrieval works the same regardless of which tier stores it

## Storacha (Web3.Storage) Integration

The `storacha_kit.py` module provides a comprehensive interface to Storacha (also known as Web3.UP), enabling seamless integration with Web3.Storage's distributed storage infrastructure built on IPFS and Filecoin.

### Key Features

- **Space Management**: Create, list, and manage storage spaces
- **Content Upload**: Store files, directories, and raw data with automatic CAR packaging
- **Batch Operations**: Efficiently process multiple files in a single operation
- **Metadata Tracking**: Store and retrieve metadata alongside content
- **User Authentication**: Support for authorization via DID (Decentralized Identifiers)
- **Rate Limit Management**: Intelligent handling of service rate limits
- **Error Handling**: Standardized error reporting with detailed diagnostics

### Detailed Usage

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with Storacha credentials (from environment variables or config)
kit = ipfs_kit(metadata={
    "storacha_token": "YOUR_TOKEN",  # Can also use W3_STORE_TOKEN env var
    "api_url": "https://up.web3.storage"  # Optional custom endpoint
})

# List available spaces
spaces_result = kit.storacha_kit.space_ls()
if spaces_result["success"]:
    print(f"Available spaces: {spaces_result['spaces']}")
    # Choose a space for operations
    default_space = next(iter(spaces_result["spaces"].values()))
else:
    print(f"Error listing spaces: {spaces_result.get('error')}")

# Upload a file to Storacha (produces a CID)
upload_result = kit.storacha_kit.upload_add(
    space=default_space,
    file="/path/to/important_data.zip",
)

if upload_result["success"]:
    # CID is returned on successful upload
    cid = upload_result["cid"]
    print(f"Uploaded to Storacha with CID: {cid}")
    
    # The content is now persistently stored and can be accessed:
    # 1. Via IPFS directly if the CID is reachable in the network
    content = kit.ipfs_cat(cid)
    
    # 2. Via Web3.Storage gateways
    gateway_url = f"https://{cid}.ipfs.w3s.link"
    
    # 3. Batch upload multiple files
    batch_result = kit.storacha_kit.batch_operations(
        space=default_space,
        files=["/path/to/file1.txt", "/path/to/file2.jpg"],
        cids=["QmExistingCid1", "QmExistingCid2"]  # Optional retrieval
    )
    
    if batch_result["success"]:
        print(f"Batch operation completed with {len(batch_result['upload_results'])} uploads")
else:
    print(f"Upload failed: {upload_result.get('error')}")

# Allocate storage to a space (for enterprise users)
allocation_result = kit.storacha_kit.space_allocate(
    space=default_space,
    amount=100,
    unit="GiB"
)
if allocation_result["success"]:
    print(f"Successfully allocated {allocation_result['allocated']} to space")
```

### Implementation Details

Storacha integration uses both HTTP APIs and CLI tools:

1. **HTTP API Interaction**:
   - `upload_add_https` for direct HTTP upload 
   - RESTful endpoints with proper authentication
   - Support for streaming large files

2. **CLI Wrapper**:
   - `run_w3_command` provides access to the w3cli functionality
   - Command output parsing and standardization
   - Cross-platform compatibility (Windows, macOS, Linux)

3. **Standardized Result Format**:
   ```python
   {
       "success": True/False,
       "operation": "operation_name",
       "timestamp": 1234567890.123,
       "correlation_id": "uuid-for-tracking",
       # Operation-specific fields like:
       "cid": "Qm...",
       "space": "did:mailto:...",
       # Error information if failed:
       "error": "Error message",
       "error_type": "ErrorClassName"
   }
   ```

### Error Handling

The storacha_kit implements comprehensive error handling with specialized exception classes:

```python
# Example error handling
try:
    result = kit.storacha_kit.store_add(space, file_path)
    if not result["success"]:
        # Handle specific error types
        if result.get("error_type") == "IPFSConnectionError":
            print("Connection issues, will retry...")
        elif result.get("error_type") == "IPFSValidationError":
            print("Invalid parameters, please check inputs")
except Exception as e:
    print(f"Unexpected error during Storacha operation: {str(e)}")
```

## S3-Compatible Storage Integration

The `s3_kit.py` module provides comprehensive integration with S3-compatible object storage services, supporting both AWS S3 and alternative implementations like MinIO, Wasabi, or Backblaze B2.

### Key Features

- **Complete S3 Operations**: Full support for file and directory operations (copy, move, list, delete)
- **Flexible Configuration**: Support for different authentication methods and endpoints
- **Bucket Management**: Operations for creating, listing, and managing buckets
- **Metadata Preservation**: Maintain metadata through storage operations
- **Streaming Support**: Efficient handling of large files with progress tracking
- **CID-to-Key Mapping**: Intelligent mapping between content identifiers and S3 keys
- **Compatible Interface**: Consistent API across different S3 providers

### Detailed Usage

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit

# Initialize with S3 configuration
kit = ipfs_kit(metadata={
    "s3cfg": {
        "accessKey": "YOUR_ACCESS_KEY",     # or use AWS_ACCESS_KEY_ID env var
        "secretKey": "YOUR_SECRET_KEY",     # or use AWS_SECRET_ACCESS_KEY env var
        "endpoint": "https://s3.amazonaws.com"  # or use custom endpoint for MinIO, etc.
    }
})

# List files in a directory (prefix)
bucket_name = "my-ipfs-bucket"
prefix = "ipfs/QmFolder/"

listing = kit.s3_kit("ls_dir", dir=prefix, bucket_name=bucket_name)
for item in listing:
    print(f"Found S3 object: {item['key']} ({item['size']} bytes)")

# Upload a file to S3 with CID-based key
cid = "QmSomeCID123456789abcdef"
local_file = "/path/to/local_file.dat"
s3_key = f"ipfs/{cid}/original.dat"

upload_result = kit.s3_kit("ul_file", 
    upload_file=local_file,
    path=s3_key,
    bucket=bucket_name
)

if "key" in upload_result:
    print(f"Uploaded file to S3: s3://{bucket_name}/{upload_result['key']}")
    print(f"ETag: {upload_result['e_tag']}")
    print(f"Size: {upload_result['size']} bytes")
    print(f"Last Modified: {upload_result['last_modified']}")
else:
    print("Upload failed")

# Download a file from S3
download_result = kit.s3_kit("dl_file",
    remote_path=s3_key,
    local_path="/path/to/download_destination.dat",
    bucket=bucket_name
)

if "key" in download_result:
    print(f"Downloaded S3 object: {download_result['key']}")
    print(f"Size: {download_result['size']} bytes")
    print(f"Saved to: {download_result['local_path']}")
else:
    print("Download failed")

# Upload an entire directory recursively
upload_dir_result = kit.s3_kit("ul_dir",
    local_path="/path/to/directory",
    remote_path="ipfs/directory_backup/",
    bucket=bucket_name
)

for key, item in upload_dir_result.items():
    print(f"Uploaded: {key} ({item['size']} bytes)")

# Move a file within S3 (copy + delete)
move_result = kit.s3_kit("mv_file",
    src_path="ipfs/original/file.dat",
    dst_path="ipfs/archive/file.dat",
    bucket=bucket_name
)

if "key" in move_result:
    print(f"Moved file to: {move_result['key']}")

# Delete a file
delete_result = kit.s3_kit("rm_file",
    this_path="ipfs/to_delete/file.dat",
    bucket=bucket_name
)

if "key" in delete_result:
    print(f"Deleted file: {delete_result['key']}")
```

### S3 Configuration Options

The S3 integration supports multiple configuration formats:

```python
# Method 1: Using accessKey/secretKey format
s3config = {
    "accessKey": "YOUR_ACCESS_KEY",
    "secretKey": "YOUR_SECRET_KEY",
    "endpoint": "https://s3.amazonaws.com"
}

# Method 2: Using standard AWS SDK naming
s3config = {
    "aws_access_key_id": "YOUR_ACCESS_KEY", 
    "aws_secret_access_key": "YOUR_SECRET_KEY",
    "endpoint_url": "https://s3.amazonaws.com"
}

# You can also specify additional boto3 parameters
s3config.update({
    "region_name": "us-west-2",
    "use_ssl": True,
    "verify": True
})
```

### Advanced Operations

The S3 integration supports additional advanced operations:

```python
# Create directory (prefix) in S3
mkdir_result = kit.s3_kit("mk_dir", 
    dir="ipfs/new_directory/",
    bucket=bucket_name,
    s3_config=s3config
)

# Upload with progress tracking
def progress_callback(bytes_transferred):
    print(f"Transferred: {bytes_transferred} bytes")

upload_result = kit.s3_kit.s3_upload_object(
    f=open(local_file, 'rb'),
    bucket=bucket_name,
    key=s3_key,
    s3_config=s3config,
    progress_callback=progress_callback
)

# Using session management for efficient operations
# The session is reused for multiple operations
session = kit.s3_kit.get_session(s3config)
```

## Integration with Tiered Caching System

The external storage backends integrate seamlessly with IPFS Kit's tiered caching system, providing additional storage layers beyond the local caches. This is managed through the `TieredCacheManager` that implements an Adaptive Replacement Cache (ARC) algorithm.

### Storage Tiers Hierarchy

```
1. Memory Cache (ARCache) - Fastest, volatile
   ↑↓ Automatic promotion/demotion based on access patterns
2. Disk Cache (DiskCache) - Fast, persistent
   ↑↓ Overflow and long-term storage migration
3. IPFS Network - Distributed, content-addressed
   ↑↓ Durability and backup
4. External backends (Storacha, S3) - Cloud archival
```

### Integration Points

The `TieredCacheManager` implements intelligent cache management with:

1. **Adaptive Replacement Algorithm**: Balances between frequency and recency
2. **Heat Scoring**: Sophisticated algorithm to determine content value
3. **Automatic Migration**: Content moves between tiers based on access patterns
4. **Cache Admission Policy**: Smart decisions about what enters higher tiers
5. **Eviction Strategy**: Data-driven decisions about what to remove from each tier

External backends are integrated through these mechanisms:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
from ipfs_kit_py.tiered_cache import TieredCacheManager

# Configure tiered cache with external backend integration
kit = ipfs_kit(metadata={
    "cache_config": {
        "memory_cache_size": 200 * 1024 * 1024,  # 200MB
        "local_cache_size": 2 * 1024 * 1024 * 1024,  # 2GB
        "local_cache_path": "/path/to/cache",
        "external_backends": {
            "storacha": {
                "enabled": True,
                "space": "default-space",
                "promotion_threshold": 10,  # Access count before migration
                "demotion_threshold": 30    # Days of no access before demotion
            },
            "s3": {
                "enabled": True,
                "bucket": "ipfs-content-cache",
                "key_prefix": "ipfs/",
                "promotion_threshold": 5,
                "demotion_threshold": 60
            }
        }
    }
})

# The cache manager integrates all tiers
cache_manager = kit.get_cache_manager()

# Access content through unified interface 
# (automatically retrieves from appropriate tier)
content = cache_manager.get("QmSomeCID")

# Store content (automatically placed in appropriate tiers)
cache_manager.put("QmSomeCID", content, metadata={"type": "important_document"})

# Get cache statistics including external backends
stats = cache_manager.get_stats()
print(f"Memory cache: {stats['memory_cache']['utilization']:.1%} used")
print(f"Disk cache: {stats['disk_cache']['utilization']:.1%} used")
print(f"External backends: {stats.get('external_backends', {})}")

# Force content to specific tier
cache_manager.promote_to_tier("QmSomeCID", "storacha")
```

### Cache Heat Scoring

The TieredCacheManager uses a sophisticated heat scoring algorithm to make intelligent decisions about content placement:

```
heat_score = (frequency_factor * frequency_weight + recency * recency_weight) * 
             boost_factor * (1 + log(1 + age / 86400))
```

Where:
- `frequency_factor`: Non-linear scaling of access count
- `recency`: Recent access increases score (decays over time)
- `boost_factor`: Extra score for recently accessed content
- `age`: Bonus for content that has been valuable for longer periods

This heat score determines:
1. Which content stays in memory vs. disk cache
2. What gets evicted when cache is full
3. What gets prioritized for promotion to higher tiers
4. What gets demoted to cloud storage for archival

### Error Handling in Multi-Tier Storage

The tiered storage system implements robust error handling with fallbacks:

```python
# Example of multi-tier retrieval with fallbacks
def get_with_fallbacks(cid):
    # Try local caches first
    content = cache_manager.get(cid)
    if content:
        return content
        
    # Try IPFS network
    try:
        content = kit.ipfs_cat(cid)
        if content:
            # Cache for future access
            cache_manager.put(cid, content)
            return content
    except Exception as e:
        logger.warning(f"IPFS retrieval failed: {e}, trying external backends")
    
    # Try Storacha
    try:
        content = kit.storacha_kit.get_content(cid)
        if content:
            cache_manager.put(cid, content)
            return content
    except Exception as e:
        logger.warning(f"Storacha retrieval failed: {e}, trying S3")
    
    # Try S3 as last resort
    try:
        s3_key = f"ipfs/{cid}"
        content = kit.s3_kit.get_object(bucket="ipfs-backup", key=s3_key)
        if content:
            cache_manager.put(cid, content)
            return content
    except Exception as e:
        logger.error(f"All retrieval methods failed for {cid}")
    
    return None
```

## Integration with FSSpec

The external storage backends can also be used with the FSSpec integration, providing a familiar filesystem interface:

```python
from ipfs_kit_py.ipfs_kit import ipfs_kit
import pandas as pd

# Initialize with both S3 and Storacha configured
kit = ipfs_kit(metadata={
    "s3cfg": {...},
    "storacha_token": "...",
})

# Get FSSpec-compatible filesystem
fs = kit.get_filesystem()

# The filesystem provides a unified interface to all backends
df = pd.read_csv("ipfs://QmSomeCID/data.csv")  # Transparently retrieves from any tier

# Write data that will be stored locally and potentially in cloud backends
# based on tiering policies
with fs.open("ipfs://myproject/results.csv", "w") as f:
    df.to_csv(f)
    
# The CID of the new file can be used to access it from any backend
new_cid = fs.get_cid("ipfs://myproject/results.csv")
print(f"Data now available at ipfs://{new_cid}")
```

## Best Practices for Storage Backends

When working with multiple storage backends, consider the following best practices:

### 1. Content Placement Strategy

Develop a clear content placement strategy based on:
- **Content importance**: Critical content should be in multiple backends
- **Access patterns**: Frequently accessed content in faster tiers
- **Cost considerations**: Expensive storage only for valuable content
- **Durability requirements**: High-value content needs multiple copies

### 2. Mapping CIDs to Backend-specific Identifiers

```python
# Consistent mapping between CIDs and backend-specific keys
def get_s3_key_from_cid(cid, prefix="ipfs"):
    """Generate consistent S3 key from CID."""
    # Use hierarchical structure for better performance
    return f"{prefix}/{cid[:2]}/{cid[2:4]}/{cid}"
    
def get_metadata_path(cid):
    """Generate path for metadata storage."""
    return f"metadata/{cid[:4]}/{cid}.json"
```

### 3. Content Verification and Integrity

Always verify content integrity when retrieving from external backends:

```python
def verify_content_integrity(cid, content):
    """Verify content matches its CID."""
    import multihash
    calculated_cid = multihash.to_b58_string(multihash.digest(content, "sha2-256"))
    return cid == calculated_cid
```

### 4. Metadata and Content Separation

Store metadata separately from content for efficient operations:

```python
# Store content and metadata separately
content_cid = kit.ipfs_add(content)
metadata = {
    "content_cid": content_cid,
    "title": "Important Document",
    "created": time.time(),
    "tags": ["important", "document"],
    "backends": ["local", "storacha", "s3"]
}

# Store metadata in index
metadata_cid = kit.ipfs_add_json(metadata)

# Track in Arrow index for efficient queries
index.add_record({
    "cid": content_cid,
    "metadata_cid": metadata_cid,
    "storage_locations": {
        "storacha": {"space": "default-space"},
        "s3": {"bucket": "content-bucket", "key": f"ipfs/{content_cid}"}
    }
})
```

### 5. Error Recovery and Fallbacks

Implement robust error recovery with fallbacks between backends:

```python
# Progressive retrieval strategy
def get_with_fallbacks(cid, retries=3, backoff=1.5):
    backends = ["memory", "disk", "ipfs", "storacha", "s3"]
    errors = {}
    
    for backend in backends:
        for attempt in range(retries):
            try:
                if backend == "memory" or backend == "disk":
                    content = cache_manager.get(cid)
                    if content:
                        return content
                elif backend == "ipfs":
                    content = kit.ipfs.cat(cid)
                    return content
                elif backend == "storacha":
                    content = kit.storacha_kit.get_content(cid)
                    return content
                elif backend == "s3":
                    content = kit.s3_kit.get_object(bucket="ipfs-backup", key=f"ipfs/{cid}")
                    return content
            except Exception as e:
                errors[f"{backend}-{attempt}"] = str(e)
                time.sleep(backoff ** attempt)
    
    # All backends failed
    raise ContentRetrievalError(f"Failed to retrieve {cid} from any backend: {errors}")
```
