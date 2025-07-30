# Bucket → VFS Refactor Design

## Problem Analysis
The current bucket structure is redundant and overly complex:
- `~/.ipfs_kit/buckets/bucket-name/` contains duplicate data
- VFS indices are separate from bucket data
- Bucket configs mixed with bucket file content
- Multiple sources of truth for bucket metadata

## Current Structure (Redundant)
```
~/.ipfs_kit/
├── buckets/
│   └── test-bucket/
│       ├── bucket_registry.json      # Redundant metadata
│       ├── cross_bucket.duckdb       # Redundant database
│       └── test-bucket/              # Redundant file storage
│           ├── files/
│           └── metadata/
├── vfs_indices/
│   └── test-bucket/                  # VFS index (where real data should be)
├── pin_metadata/
│   └── test-bucket/                  # Pin metadata (partially redundant)
└── bucket_index/                     # Another index layer
```

## New Structure (Clean VFS-Based)
```
~/.ipfs_kit/
├── vfs_indices/
│   ├── bucket-name-1/               # Direct VFS → CID mapping
│   │   ├── index.parquet            # File path → IPFS CID mappings
│   │   ├── metadata.parquet         # File metadata (size, mtime, etc.)
│   │   └── content_index.duckdb     # Content search index
│   ├── bucket-name-2/
│   └── bucket-name-3/
├── bucket_registry.yaml             # Central bucket registry
├── bucket_configs/
│   ├── bucket-name-1.yaml          # Retention/backup policies
│   ├── bucket-name-2.yaml          # Per-bucket configuration
│   └── default.yaml                # Default bucket policies
└── pin_metadata/                    # Consolidated pin metadata
    └── consolidated.parquet         # All pins across all buckets
```

## Key Architecture Changes

### 1. Bucket = VFS Index
- Each bucket is directly represented as a VFS index directory
- VFS index contains all file→CID mappings for that bucket
- No separate bucket directory structure needed

### 2. Central Bucket Registry
`~/.ipfs_kit/bucket_registry.yaml`:
```yaml
buckets:
  dataset-papers:
    type: dataset
    vfs_index: dataset-papers
    created_at: "2025-07-29T10:00:00Z"
    backend_bindings:
      - s3://my-bucket/papers/
      - ipfs://cluster
    total_files: 1543
    total_size: "2.4GB"
    last_sync: "2025-07-29T15:30:00Z"
  
  media-collection:
    type: media
    vfs_index: media-collection
    created_at: "2025-07-29T11:00:00Z"
    backend_bindings:
      - gdrive://folder/media
      - lotus://deals
    total_files: 892
    total_size: "15.2GB"
    last_sync: "2025-07-29T16:00:00Z"

# Global bucket statistics
statistics:
  total_buckets: 2
  total_files: 2435
  total_size: "17.6GB"
  last_updated: "2025-07-29T16:00:00Z"
```

### 3. Separate Configuration Files
`~/.ipfs_kit/bucket_configs/dataset-papers.yaml`:
```yaml
# Bucket policies and configuration (NOT file content)
bucket_name: dataset-papers
type: dataset

# Backup and retention policies
backup:
  enabled: true
  frequency: daily
  retention_days: 365
  destinations:
    - s3://backup-bucket/papers/
    - ipfs://cluster

replication:
  min_replicas: 2
  max_replicas: 5
  geographic_distribution: true

# Performance settings
cache:
  enabled: true
  policy: lru
  size_mb: 512
  ttl_seconds: 3600

# Access controls
access:
  public_read: false
  api_access: true
  web_interface: true
```

### 4. VFS Index Structure
`~/.ipfs_kit/vfs_indices/dataset-papers/`:
```
index.parquet          # Core file→CID mappings
├── file_path (string)         # Virtual file path
├── ipfs_cid (string)          # IPFS Content ID
├── file_size (int64)          # File size in bytes
├── modified_time (timestamp)   # Last modification time
├── content_type (string)      # MIME type
└── checksum_sha256 (string)   # SHA256 for integrity

metadata.parquet       # Extended file metadata
├── file_path (string)         # Virtual file path (foreign key)
├── tags (list<string>)        # User tags
├── description (string)       # File description
├── custom_metadata (json)     # User-defined metadata
└── search_keywords (string)   # Full-text search terms

content_index.duckdb   # Content search capabilities
├── Full-text search index
├── Content-based queries
└── Cross-file relationships
```

## Implementation Benefits

### 1. Eliminated Redundancy
- Remove `~/.ipfs_kit/buckets/` entirely
- Single source of truth: VFS indices
- Bucket metadata in central registry
- Configuration separated from content

### 2. Cleaner Data Model
```python
# Simple bucket operations
bucket = Bucket("dataset-papers")
bucket.add_file("paper.pdf", ipfs_cid="Qm...")  # → VFS index
bucket.list_files()                              # ← VFS index
bucket.get_config()                              # ← YAML config
bucket.update_policy(retention_days=180)         # → YAML config
```

### 3. Better Performance
- Direct VFS index access (no bucket wrapper layer)
- Single Parquet file reads for file listings
- Central registry for bucket discovery
- Reduced filesystem traversal

### 4. Simplified CLI Commands
```bash
# Bucket management (no backend complexity)
ipfs-kit bucket create dataset-papers --type dataset
ipfs-kit bucket list                              # Read registry.yaml
ipfs-kit bucket config dataset-papers            # Show YAML config
ipfs-kit bucket files dataset-papers             # Read VFS index directly

# VFS operations (direct index access)
ipfs-kit vfs add dataset-papers/paper.pdf Qm...  # Write to VFS index
ipfs-kit vfs list dataset-papers                 # Read VFS index
ipfs-kit vfs search dataset-papers "machine learning"  # Query content index
```

## Migration Strategy

### Phase 1: Create New Structure
1. Create `bucket_registry.yaml` from existing bucket data
2. Create `bucket_configs/` with YAML files from existing bucket metadata
3. Ensure VFS indices contain all current file mappings

### Phase 2: Update Code
1. Modify bucket commands to use VFS indices directly
2. Update bucket registry management
3. Implement YAML config management

### Phase 3: Remove Redundancy
1. Migrate data from `buckets/` to consolidated structure
2. Remove `buckets/` and `bucket_index/` directories
3. Update documentation and tests

## File Operations Flow

### Adding Files
```
File Input → IPFS Pin → VFS Index Update → Registry Update
1. ipfs-kit vfs add bucket/file.txt (content)
2. Calculate/pin IPFS CID
3. Add file_path→cid mapping to VFS index
4. Update bucket registry statistics
```

### Listing Files
```
Bucket List → VFS Index Read → File Metadata
1. ipfs-kit bucket files dataset-papers
2. Read ~/.ipfs_kit/vfs_indices/dataset-papers/index.parquet
3. Join with metadata.parquet for extended info
4. Display file listings with CIDs
```

### Configuration Management
```
Bucket Config → YAML File → Policy Application
1. ipfs-kit bucket config dataset-papers --retention-days 180
2. Update ~/.ipfs_kit/bucket_configs/dataset-papers.yaml
3. Apply new policies to bucket operations
4. Update registry with policy summary
```

This architecture eliminates redundancy while maintaining all functionality through a clean VFS-based approach.
