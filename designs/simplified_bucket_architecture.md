# Simplified Bucket Architecture Design

## Overview

Redesign the bucket structure to eliminate redundancy by treating each bucket as a VFS and using VFS indices to store bucket metadata pointing to IPFS CIDs.

## Current Structure Issues

```
~/.ipfs_kit/buckets/test-bucket/
├── bucket_registry.json          # Redundant registry
├── cross_bucket.duckdb           # Could be centralized
└── test-bucket/                  # Redundant nesting
    ├── car/
    ├── files/                    # Redundant directory structure
    │   ├── bin/, etc/, home/, tmp/, usr/, var/
    ├── knowledge/
    ├── metadata/
    │   └── bucket_metadata.json  # Should be in VFS index
    ├── parquet/
    └── vectors/
```

## New Simplified Structure

```
~/.ipfs_kit/
├── vfs_indices/
│   ├── test-bucket.parquet           
│   ├── media-bucket.parquet
│   └── archive-bucket.parquet
│   ├── test-bucket.car # these should actually be named with the IPFS CID's            
│   ├── media-bucket.car
│   └── archive-bucket.car
├── bucket_registry.parquet  # Central registry of bucket->VFS mappings using the IPFS cid of the vfs index
├── bucket-config/              # Bucket policies and configurations
│   ├── test-bucket.yaml         # Backup/retention policies, and pointer to the vfs config
│   ├── media-bucket.yaml
│   └── archive-bucket.yaml
└── bucket_registry.parquet          # Central cross-bucket analytics
```

## VFS Index Schema

Each VFS index database contains:

```sql
-- File entries table - core VFS functionality
CREATE TABLE files (
    path TEXT PRIMARY KEY,         -- Virtual file path
    cid TEXT NOT NULL,            -- IPFS content hash
    size INTEGER,                 -- File size in bytes
    mime_type TEXT,               -- MIME type
    created_at TIMESTAMP,         -- Creation timestamp
    modified_at TIMESTAMP,        -- Last modification
    attributes JSON               -- Additional file attributes
);

-- Bucket metadata table - replaces bucket_metadata.json
CREATE TABLE bucket_metadata (
    key TEXT PRIMARY KEY,
    value TEXT                    -- JSON values for complex data
);

-- Directory structure table - virtual directories
CREATE TABLE directories (
    path TEXT PRIMARY KEY,
    parent_path TEXT,
    created_at TIMESTAMP,
    attributes JSON
);

-- Search indices for performance
CREATE INDEX idx_files_cid ON files(cid);
CREATE INDEX idx_files_path ON files(path);
CREATE INDEX idx_files_modified ON files(modified_at);
```

## Bucket Configuration YAML Schema

```yaml
# test-bucket.yaml - Configuration and policies (NOT content)
bucket:
  name: test-bucket
  type: dataset                   # general, dataset, knowledge, media, archive, temp
  vfs_structure: hybrid          # unixfs, graph, vector, hybrid
  
# Backup and retention policies
policies:
  retention:
    max_age_days: 365
    cleanup_policy: archive      # delete, archive, compress
  
  backup:
    auto_backup: true
    backup_frequency: daily      # hourly, daily, weekly
    backup_backends:
      - filecoin
      - s3
  
  replication:
    min_replicas: 2
    preferred_backends:
      - ipfs
      - filecoin
    
# Performance and caching
performance:
  cache_policy: aggressive       # none, conservative, aggressive
  prefetch_enabled: true
  
# Access control (future)
access:
  public_read: false
  allowed_users: []
  
# Metadata
metadata:
  description: "Test bucket with new structure"
  tags: [test, development]
  created_at: "2025-07-29T22:55:36.330703"
  created_by: "unified_interface"
```

## Central Bucket Registry

```yaml
# bucket_registry.yaml - Maps bucket names to VFS indices
buckets:
  test-bucket:
    vfs_index: "/home/devel/.ipfs_kit/vfs_indices/test-bucket.parquet"
    config_file: "/home/devel/.ipfs_kit/bucket_configs/test-bucket.yaml"
    type: dataset
    vfs_structure: hybrid
    created_at: "2025-07-29T22:55:36.330703"
    root_cid: "QmTestRoot123"
    
  media-bucket:
    vfs_index: "/home/devel/.ipfs_kit/vfs_indices/media-bucket.parquet"
    config_file: "/home/devel/.ipfs_kit/bucket_configs/media-bucket.yaml"
    type: media
    vfs_structure: unixfs
    created_at: "2025-07-29T23:00:00.000000"
    root_cid: "QmMediaRoot456"

# Global settings
settings:
  default_backend: ipfs
  cross_bucket_analytics: true
  vfs_index_format: parquet        # sqlite, duckdb, parquet
```

## Benefits

1. **Eliminates redundancy** - No nested bucket directories
2. **Centralized VFS indices** - All file->CID mappings in one place per bucket
3. **Separation of concerns** - Policies in YAML, content refs in VFS
4. **Efficient queries** - SQL queries across VFS indices
5. **Better scalability** - Central registry tracks all buckets
6. **Content addressing** - All files referenced by IPFS CID
7. **Policy flexibility** - YAML configs for complex policies

## Migration Strategy

1. Create new directory structure
2. Extract metadata from existing buckets to VFS indices
3. Create YAML configs from existing metadata
4. Update bucket registry format
5. Update bucket VFS manager to use new structure
6. Maintain backward compatibility during transition
