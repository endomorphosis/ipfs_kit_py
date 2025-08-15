# IPFS-Kit CLI: Bucket Virtual Filesystems & Pin Management Guide

## Executive Summary

The IPFS-Kit CLI provides a **unified bucket-based virtual filesystem interface** that abstracts multiple storage backends (Parquet, Arrow, S3, SSHFS, FTP, Google Drive, GitHub, HuggingFace, etc.) into content-addressed pin storage systems. Each bucket acts as a virtual filesystem where files are stored as content-addressed pins with IPFS hashes, creating a distributed, verifiable storage layer across remote services.

## Core Concepts

### 1. Bucket Virtual Filesystems
- **Buckets**: Logical containers that act as virtual filesystems
- **Pins**: Content-addressed data stored with IPFS hashes (CIDs)
- **Virtual Paths**: Filesystem-like organization within buckets
- **Backend Abstraction**: Storage backend selection is transparent to users
- **Metadata Indices**: Parquet-based indices for fast querying and composition

### 2. Content Addressing & IPFS Integration
- All content is stored with **SHA-256 content hashes** as IPFS CIDs
- Content is **immutable** and **verifiable** across all backends
- **Deduplication** happens automatically via content addressing
- **Cross-backend queries** enable unified data access

### 3. Remote Service Mapping
```
User Files → Content Hash (CID) → Bucket Pin → Backend Storage
    ↓              ↓                  ↓              ↓
Virtual Path → IPFS Hash → Metadata Index → S3/SSHFS/etc
```

## CLI Architecture

### Enhanced Command Structure
```
ipfs-kit-cli
├── bucket           # Bucket virtual filesystem operations
│   ├── create       # Create new buckets
│   ├── list         # List buckets and their pins
│   ├── add-pin      # Add content-addressed pins
│   ├── get-pin      # Retrieve pin content by CID
│   ├── vfs-composition  # Show virtual filesystem structure
│   └── query        # Cross-backend SQL queries
├── daemon           # Daemon and service management
├── pin              # Direct IPFS pin operations
├── backend          # Multi-backend storage operations (15 backends)
├── config           # Configuration and global policy management
└── [other commands] # Health, metrics, logs, etc.
```

## Bucket Virtual Filesystem Operations

### 1. Creating and Managing Buckets

#### Simple Bucket Creation (Abstracted Interface)
```bash
# Using the improved CLI - daemon chooses optimal backend
python improved_bucket_cli.py create my-documents media \
  --description "Personal documents storage"

# Creates bucket with:
# - Automatic backend selection (S3 for media type)
# - VFS index initialization
# - Pin metadata directory structure
```

#### Advanced Bucket Creation (Backend-Specific)
```bash
# Create dataset bucket on Parquet backend
ipfs-kit bucket create parquet ml-models dataset \
  --bucket-type dataset \
  --vfs-structure hybrid \
  --metadata '{"project": "ML Training", "retention": "1-year"}'

# Create media bucket on S3 backend  
ipfs-kit bucket create s3 media-files media \
  --bucket-type media \
  --vfs-structure unixfs \
  --metadata '{"public": false, "compression": "auto"}'

# Create archive bucket on SSHFS backend
ipfs-kit bucket create sshfs backup-archive archive \
  --bucket-type archive \
  --vfs-structure graph \
  --metadata '{"encryption": true, "remote_host": "backup.example.com"}'
```

### 2. Writing Files to Bucket Virtual Filesystems

#### Simple File Addition (Abstracted)
```bash
# Add file with automatic content addressing
python improved_bucket_cli.py add my-documents /path/to/report.pdf \
  --virtual-path "reports/2025/annual-report.pdf" \
  --metadata '{"year": 2025, "type": "annual"}'

# Process:
# 1. Read file content
# 2. Generate SHA-256 hash (IPFS CID)
# 3. Store as pin in bucket's VFS
# 4. Update Parquet indices
# 5. Map virtual path to content hash
```

#### Advanced Pin Addition (Backend-Specific)
```bash
# Add dataset to Parquet bucket with specific CID
ipfs-kit bucket add-pin parquet ml-models \
  QmX7M9CiYXjVQy8h4SomeContentHashHere12345 \
  "datasets/training/model_v2.parquet" \
  /local/path/model_v2.parquet \
  --metadata '{
    "model_version": "2.1",
    "training_date": "2025-07-29",
    "accuracy": 0.95,
    "size_bytes": 1048576
  }'

# Add media file to S3 bucket
ipfs-kit bucket add-pin s3 media-files \
  QmY8N0DjWRkZp9h5SomeImageHashHere67890 \
  "photos/2025/vacation/beach.jpg" \
  /local/photos/beach.jpg \
  --metadata '{
    "location": "Malibu",
    "date": "2025-07-15",
    "camera": "Canon EOS R5",
    "tags": ["vacation", "beach", "sunset"]
  }'

# Add code repository to GitHub bucket
ipfs-kit bucket add-pin github code-repos \
  QmZ9O1EkXSl0q0i6SomeCodeHashHere11111 \
  "projects/ipfs-kit/src/main.py" \
  /local/code/main.py \
  --metadata '{
    "language": "python",
    "commit": "abc123def456",
    "author": "developer@example.com",
    "license": "MIT"
  }'
```

### 3. Reading Files from Bucket Virtual Filesystems

#### List Bucket Contents
```bash
# Simple listing (abstracted)
python improved_bucket_cli.py files my-documents

# Detailed listing (backend-specific)
ipfs-kit bucket files ml-models --limit 10

# Output shows:
# - Virtual filesystem paths
# - Content hashes (CIDs)
# - File sizes and metadata
# - Storage backend information
```

#### Retrieve Individual Pins by IPFS Hash
```bash
# Get pin content by CID (abstracted)
python improved_bucket_cli.py get my-documents \
  QmX7M9CiYXjVQy8h4SomeContentHashHere12345 \
  --output-path ./downloaded-file.pdf

# Get pin content by CID (backend-specific)
ipfs-kit pin get QmX7M9CiYXjVQy8h4SomeContentHashHere12345 \
  --output ./restored-file.parquet

# Stream pin content to stdout
ipfs-kit pin cat QmY8N0DjWRkZp9h5SomeImageHashHere67890 | display

# Find which bucket contains a specific CID
ipfs-kit bucket find-cid QmZ9O1EkXSl0q0i6SomeCodeHashHere11111
# Output: Found in bucket 'code-repos' (github backend)
```

### 4. Virtual Filesystem Composition and Structure

#### View VFS Composition
```bash
# Show complete virtual filesystem structure
ipfs-kit bucket vfs-composition

# Output example:
# 🗂️ Global VFS Statistics:
#    Total Pins: 156
#    Total Size: 2.3 GB
#    Backends: 5
# 
# 🏗️ Backend Composition:
#    🔧 PARQUET:
#       Pins: 45
#       Size: 890.2 MB
#       Buckets: 3
#         📁 ml-models: 23 pins (650 MB)
#           └── datasets/training/model_v2.parquet (QmX7M9...)
#           └── datasets/validation/test_set.parquet (QmY8N0...)
#         📁 analytics: 12 pins (240.2 MB)
#         📁 research: 10 pins (45.8 MB)
#    
#    🔧 S3:
#       Pins: 67
#       Size: 1.1 GB  
#       Buckets: 2
#         📁 media-files: 45 pins (900 MB)
#           └── photos/2025/vacation/beach.jpg (QmZ9O1...)
#           └── videos/project/demo.mp4 (QmA1B2...)
#         📁 backups: 22 pins (200 MB)
```

#### Filter VFS by Backend or Bucket
```bash
# Show specific backend composition
ipfs-kit bucket vfs-composition --backend parquet

# Show specific bucket composition  
ipfs-kit bucket vfs-composition --bucket ml-models

# Show cross-backend composition for multiple backends
ipfs-kit bucket vfs-composition --backend s3,sshfs,gdrive
```

## MCP Dashboard & Deprecations Visibility

### Deprecation Tracking Overview
The MCP dashboard exposes a machine-readable deprecation registry at `/api/system/deprecations` and mirrors it in the initial WebSocket `system_update` payload. Each entry includes:

| Field | Description |
|-------|-------------|
| endpoint | Deprecated HTTP path |
| remove_in | Planned removal version |
| migration | Mapping of replacement endpoints (when available) |
| hits | Observed request count since the dashboard first started (persisted across restarts) |

### Persistent Hit Counts
Per-endpoint request counts are persisted to `endpoint_hits.json` in the data directory (default: `~/.ipfs_kit`). On clean shutdown or receipt of `SIGTERM`/`SIGINT`, the dashboard writes the file; on startup it reloads and continues counting. This enables longitudinal tracking to prioritize removal of truly unused endpoints sooner.

Data directory layout excerpt:
```
~/.ipfs_kit/
  backends.json
  buckets.json
  pins.json
  endpoint_hits.json   # persisted hit counters
```

### CLI: Listing Deprecated Endpoints
Use the unified CLI command to inspect deprecations:

```bash
ipfs-kit mcp deprecations              # human table output
ipfs-kit mcp deprecations --json       # raw JSON list
```

Enhancement flags for prioritization:

```bash
ipfs-kit mcp deprecations --sort hits           # order by usage (descending add --reverse for ascending)
ipfs-kit mcp deprecations --sort remove_in      # semantic-like version ordering
ipfs-kit mcp deprecations --min-hits 10         # filter out rarely-used endpoints
ipfs-kit mcp deprecations --sort endpoint --reverse  # reverse lexicographic
ipfs-kit mcp deprecations --report-json out/report.json  # write machine-readable report for CI artifacts
```

Flag summary:
* `--sort endpoint|remove_in|hits` – choose column to sort (default: registry order)
* `--reverse` – invert sort order
* `--min-hits N` – include only endpoints with at least N recorded hits
* `--json` – structured output suitable for scripts / CI checks
* `--fail-if-hits-over N` – exit with code 3 if any deprecated endpoint exceeds N hits (for CI gating / removal readiness)
* `--fail-if-missing-migration` – exit with code 4 if any deprecated endpoint lacks a migration mapping (ensures every deprecated path has a documented replacement strategy)

### Example JSON Output
```json
[
  {
    "endpoint": "/api/system/overview",
    "remove_in": "3.2.0",
    "migration": {"health":"/api/system/health","status":"/api/mcp/status","metrics":"/api/metrics/system"},
    "hits": 42
  }
]
```

### CI / Policy Integration
Because hit counts persist across restarts, automation (e.g. a pre-release job) can enforce that endpoints below a threshold (e.g. `<5` hits in last week) are safe for removal or trigger warnings when high-usage deprecated endpoints remain.

### UI Banner
The built-in dashboard UI shows a dismissible banner summarizing active deprecations, sourced from the first WebSocket payload (fallback to HTTP if needed) so users get immediate visibility without extra requests.

### JSON Report Export (`--report-json`)

Use `--report-json <PATH>` to generate a machine-readable snapshot that CI pipelines or monitoring jobs can archive without scraping stdout. The report file contains:

Updated nested policy schema (replacing earlier flat `policy.status` form):

```jsonc
{
  "generated_at": "2025-08-14T12:34:56.123456+00:00",  // UTC timestamp
  "deprecated": [ /* filtered & sorted list (after --min-hits / --sort applied) */ ],
  "summary": {
    "count": 1,
    "max_hits": 42
  },
  "policy": {
    "hits_enforcement": {
      "status": "pass" | "violation" | "skipped",
      "threshold": 100,              // evaluated threshold or null
      "violations": [                // endpoints exceeding threshold
        { "endpoint": "/api/system/overview", "hits": 120, "remove_in": "3.2.0", "threshold": 100 }
      ]
    },
    "migration_enforcement": {
      "status": "pass" | "violation" | "skipped",
      "violations": [                // endpoints missing migration mapping
        { "endpoint": "/api/legacy/old", "remove_in": "3.3.0", "hits": 5 }
      ]
    }
  },
  "raw": { /* original /api/system/deprecations response (unfiltered) */ }
}
```

Typical CI usage patterns:

1. Enforce hit threshold only:
```bash
ipfs-kit mcp deprecations \
  --report-json build/deprecations/report.json \
  --fail-if-hits-over 100
```

2. Enforce both hit threshold and migration completeness:
```bash
ipfs-kit mcp deprecations \
  --report-json build/deprecations/report.json \
  --fail-if-hits-over 100 \
  --fail-if-missing-migration
```

3. Example GitHub Actions step (captures exit codes 3/4 distinctly):
```yaml
 - name: Deprecation policy check
   run: |
     set -e
     ipfs-kit mcp deprecations \
       --report-json build/deprecations/report.json \
       --fail-if-hits-over 100 \
       --fail-if-missing-migration || exit_code=$?
     if [ "${exit_code:-0}" -eq 3 ]; then
       echo "High-usage deprecated endpoint(s) detected (hits threshold)." >&2
       exit 3
     elif [ "${exit_code:-0}" -eq 4 ]; then
       echo "Deprecated endpoint(s) missing migration mapping." >&2
       exit 4
     elif [ "${exit_code:-0}" -ne 0 ]; then
       echo "Unexpected failure code: $exit_code" >&2
       exit $exit_code
     fi
   shell: bash
 - name: Upload deprecation report
   uses: actions/upload-artifact@v4
   with:
     name: deprecations-report
     path: build/deprecations/report.json
```

Exit codes reference:

| Code | Meaning |
|------|---------|
| 0 | Success (no violations) |
| 3 | Hits threshold violation (`--fail-if-hits-over`) |
| 4 | Missing migration mapping violation (`--fail-if-missing-migration`) |

Upload `build/deprecations/report.json` as a workflow artifact and visualize trends over time (e.g. diff `summary.max_hits` and counts of `policy.migration_enforcement.violations`).

## Deprecation Governance & Report Schema

The JSON artifact produced by `--report-json` is now governed by a formal JSON Schema at `schemas/deprecations_report.schema.json`. This codifies:

- Stable top-level keys: `generated_at`, `deprecated`, `summary`, `policy`, `raw`.
- Nested policy objects: `policy.hits_enforcement` and `policy.migration_enforcement` (each with `status` + `violations`).
- Backward-compatible allowance for unknown additional properties (schema is permissive for additive evolution).

### Why a Schema?
1. Contract stability for CI & downstream tooling.
2. Safer refactors (tests fail fast on breaking shape changes).
3. Enables automatic documentation generation and validation.

### Lightweight Validation
Current test `test_cli_deprecations_report_schema_file.py` performs structural checks without extra dependencies. To enable full Draft 2020-12 validation later, add `jsonschema` to dependencies and extend the test to run a full schema validation.

### Evolution Guidelines
- Only add new fields (avoid removals/renames) for non-breaking changes.
- Make new fields optional first; after broad adoption, consider making them required via a schema version bump.
- Keep additive changes backward-compatible; document them in CHANGELOG.

### Schema Versioning (`report_version`)
Each generated report now includes a `report_version` (semantic version). Bump rules:
* PATCH: Purely additive (new optional fields) or documentation clarifications.
* MINOR: New required fields OR behavior changes that remain backward-compatible for existing keys.
* MAJOR: Removals, renames, or structural changes to existing required fields.

Automation can pin to a major.minor (e.g. `^1.0.0`) ensuring compatible evolution. Tests assert presence and semantic format.

### Exit Codes (For Quick Reference)
| Code | Meaning |
|------|---------|
| 0 | No policy violations |
| 3 | Hits threshold violation (`--fail-if-hits-over`) |
| 4 | Missing migration mapping (`--fail-if-missing-migration`) |

Use these codes in CI to gate merges or releases based on deprecation policy health.


### 5. Cross-Backend Querying with SQL

#### Query Pins Across All Backends
```bash
# Find all pins larger than 100MB
ipfs-kit bucket query "
  SELECT backend, bucket, file_path, size, content_hash 
  FROM unified_vfs 
  WHERE size > 104857600 
  ORDER BY size DESC
"

# Find all pins by file type
ipfs-kit bucket query "
  SELECT backend, COUNT(*) as pin_count, SUM(size) as total_size
  FROM unified_vfs 
  WHERE file_path LIKE '%.parquet'
  GROUP BY backend
"

# Find pins with specific metadata
ipfs-kit bucket query "
  SELECT file_path, content_hash, metadata_json
  FROM unified_vfs 
  WHERE JSON_EXTRACT(metadata_json, '$.model_version') = '2.1'
"

# Cross-backend deduplication analysis
ipfs-kit bucket query "
  SELECT content_hash, COUNT(*) as replica_count, 
         GROUP_CONCAT(backend) as backends
  FROM unified_vfs 
  GROUP BY content_hash 
  HAVING replica_count > 1
"
```

#### Backend-Specific Queries
```bash
# Query only Parquet backend
ipfs-kit bucket query "
  SELECT * FROM vfs_parquet_ml_models 
  WHERE created_at > '2025-07-01'
" --backends parquet

# Query across S3 and SSHFS backends
ipfs-kit bucket query "
  SELECT backend, bucket, AVG(size) as avg_size
  FROM unified_vfs 
  WHERE backend IN ('s3', 'sshfs')
  GROUP BY backend, bucket
" --backends s3,sshfs
```

## Remote Service Mapping & Backend Architecture

### 1. Bucket-to-Backend Mapping

Each bucket is mapped to a specific storage backend, but the mapping is transparent:

```
Bucket Name     Backend      Remote Service           Directory Structure
-----------     -------      --------------           -------------------
ml-models    → parquet   → ~/.ipfs_kit/buckets/    → /parquet/ml-models/
media-files  → s3        → Amazon S3 bucket        → s3://my-ipfs-bucket/
code-repos   → github    → GitHub repository       → github.com/user/repo
backup-arch  → sshfs     → Remote SSH server       → /mnt/backup/archives/
documents    → gdrive    → Google Drive folder     → /drive/ipfs-documents/
```

### 2. Pin Metadata Indices Structure

The system maintains Parquet-based indices for fast querying:

```
~/.ipfs_kit/
├── bucket_registry.parquet          # Global bucket registry
├── buckets/                          # Per-backend bucket storage
│   ├── parquet/ml-models/
│   │   ├── metadata/bucket_metadata.json
│   │   └── parquet/file_metadata.parquet
│   ├── s3/media-files/
│   │   ├── metadata/bucket_metadata.json  
│   │   └── parquet/file_metadata.parquet
│   └── github/code-repos/
│       ├── metadata/bucket_metadata.json
│       └── parquet/file_metadata.parquet
├── pin_metadata/                     # Content-addressed pin storage
│   ├── parquet/ml-models/
│   │   ├── QmX7M9...123.parquet     # Pin metadata as Parquet
│   │   └── QmY8N0...456.parquet
│   ├── s3/media-files/
│   │   ├── QmZ9O1...789.parquet
│   │   └── QmA1B2...000.parquet
│   └── [backend]/[bucket]/
│       └── [content-hash].parquet
└── vfs_indices/                      # Virtual filesystem indices
    ├── parquet/ml-models/
    │   └── vfs_index.parquet        # VFS structure as Parquet
    ├── s3/media-files/
    │   └── vfs_index.parquet
    └── [backend]/[bucket]/
        └── vfs_index.parquet
```

### 3. Content Hash to Remote Service Mapping

#### Parquet Backend Mapping
```bash
# Content stored locally in structured format
Pin CID: QmX7M9CiYXjVQy8h4SomeContentHashHere12345
Remote Path: ~/.ipfs_kit/buckets/parquet/ml-models/data/model_v2.parquet
Metadata: ~/.ipfs_kit/pin_metadata/parquet/ml-models/QmX7M9...123.parquet
VFS Index: ~/.ipfs_kit/vfs_indices/parquet/ml-models/vfs_index.parquet
```

#### S3 Backend Mapping  
```bash
# Content stored in Amazon S3
Pin CID: QmY8N0DjWRkZp9h5SomeImageHashHere67890
Remote Path: s3://my-ipfs-bucket/media-files/QmY8N0DjWRkZp9h5/beach.jpg
Metadata: ~/.ipfs_kit/pin_metadata/s3/media-files/QmY8N0...456.parquet
VFS Index: ~/.ipfs_kit/vfs_indices/s3/media-files/vfs_index.parquet
```

#### GitHub Backend Mapping
```bash
# Content stored in GitHub repository
Pin CID: QmZ9O1EkXSl0q0i6SomeCodeHashHere11111  
Remote Path: github.com/user/ipfs-content/QmZ9O1EkXSl0q0i6/main.py
Metadata: ~/.ipfs_kit/pin_metadata/github/code-repos/QmZ9O1...789.parquet
VFS Index: ~/.ipfs_kit/vfs_indices/github/code-repos/vfs_index.parquet
```

#### SSHFS Backend Mapping
```bash
# Content stored on remote SSH server
Pin CID: QmA1B2C3D4E5F6SomeArchiveHashHere2222
Remote Path: user@backup.example.com:/storage/ipfs/QmA1B2C3D4E5F6/archive.tar.gz
Metadata: ~/.ipfs_kit/pin_metadata/sshfs/backup-arch/QmA1B2...000.parquet  
VFS Index: ~/.ipfs_kit/vfs_indices/sshfs/backup-arch/vfs_index.parquet
```

### 4. Pin Metadata Structure

Each pin's metadata is stored as a Parquet record:

```python
# Pin metadata schema
{
    "content_hash": "QmX7M9CiYXjVQy8h4SomeContentHashHere12345",
    "cid": "QmX7M9CiYXjVQy8h4SomeContentHashHere12345", 
    "backend": "parquet",
    "bucket": "ml-models",
    "file_path": "datasets/training/model_v2.parquet",
    "size": 1048576,
    "status": "active",
    "created_at": "2025-07-29T14:30:00Z",
    "metadata_json": '{"model_version": "2.1", "accuracy": 0.95}'
}
```

### 5. VFS Index Structure

Virtual filesystem indices enable fast queries:

```python
# VFS index schema  
{
    "files": {
        "datasets/training/model_v2.parquet": {
            "cid": "QmX7M9CiYXjVQy8h4SomeContentHashHere12345",
            "size": 1048576,
            "backend": "parquet", 
            "bucket": "ml-models",
            "status": "active",
            "created_at": "2025-07-29T14:30:00Z",
            "metadata": {"model_version": "2.1", "accuracy": 0.95}
        }
    },
    "metadata": {
        "backend": "parquet",
        "bucket_name": "ml-models", 
        "pin_count": 23,
        "total_size": 681574400,
        "last_updated": "2025-07-29T15:45:00Z"
    }
}
```

## Advanced Bucket Operations

### 1. Bucket Synchronization and Index Management
```bash
# Synchronize all bucket indices
ipfs-kit bucket sync-indices

# Synchronize specific backend
ipfs-kit bucket sync-indices --backend parquet

# Synchronize specific bucket
ipfs-kit bucket sync-indices --backend s3 --bucket media-files

# Show directory structure in ~/.ipfs_kit/
ipfs-kit bucket directory-structure
```

### 2. Content Verification and Integrity
```bash
# Verify content integrity by re-hashing
ipfs-kit pin status QmX7M9CiYXjVQy8h4SomeContentHashHere12345

# Verify all pins in a bucket
ipfs-kit bucket verify ml-models

# Find orphaned pins (metadata without content)
ipfs-kit bucket find-orphans

# Find missing metadata (content without proper indices)
ipfs-kit bucket find-missing-metadata
```

### 3. Cross-Backend Migration and Replication
```bash
# Replicate bucket across multiple backends
ipfs-kit bucket replicate ml-models --from parquet --to s3,sshfs

# Migrate bucket to different backend
ipfs-kit bucket migrate media-files --from s3 --to gdrive

# Show replication status
ipfs-kit bucket replication-status ml-models
```

### 4. Bucket Analytics and Monitoring
```bash
# Show detailed bucket analytics
ipfs-kit bucket analytics ml-models

# Show pin distribution across backends
ipfs-kit bucket pin-distribution

# Show storage usage by backend
ipfs-kit bucket storage-usage

# Export bucket metadata to CSV
ipfs-kit bucket export ml-models --format csv --output ./ml-models-export.csv
```

## CLI Usage Patterns

### 1. Data Science Workflow
```bash
# Create dataset bucket
ipfs-kit bucket create parquet research-data dataset \
  --metadata '{"project": "ML Research", "access": "team"}'

# Add training datasets
ipfs-kit bucket add-pin parquet research-data \
  $(sha256sum train.parquet | cut -d' ' -f1) \
  "datasets/training/v1.parquet" train.parquet \
  --metadata '{"split": "train", "samples": 100000}'

# Query dataset inventory
ipfs-kit bucket query "
  SELECT file_path, size, JSON_EXTRACT(metadata_json, '$.samples') as samples
  FROM vfs_parquet_research_data
  WHERE file_path LIKE '%training%'
"

# Retrieve dataset by content hash
ipfs-kit pin get QmDatasetHashHere123 --output ./restored-dataset.parquet
```

### 2. Media Archive Workflow
```bash
# Create media archive across multiple backends
ipfs-kit bucket create s3 media-primary media
ipfs-kit bucket create sshfs media-backup archive

# Add photos with metadata
for photo in *.jpg; do
  cid=$(ipfs add --only-hash "$photo" | cut -d' ' -f2)
  ipfs-kit bucket add-pin s3 media-primary "$cid" "photos/2025/$photo" "$photo" \
    --metadata "{\"date\": \"$(date -I)\", \"camera\": \"Canon\", \"location\": \"Beach\"}"
done

# Replicate to backup
ipfs-kit bucket replicate media-primary --to sshfs media-backup

# Find photos by location
ipfs-kit bucket query "
  SELECT file_path, content_hash 
  FROM vfs_s3_media_primary 
  WHERE JSON_EXTRACT(metadata_json, '$.location') = 'Beach'
"
```

### 3. Code Repository Workflow
```bash
# Create code archive on GitHub
ipfs-kit bucket create github code-archive archive

# Add source files with git metadata
git log --oneline | head -5 | while read commit message; do
  for file in src/*.py; do
    cid=$(ipfs add --only-hash "$file" | cut -d' ' -f2)
    ipfs-kit bucket add-pin github code-archive "$cid" \
      "commits/$commit/$(basename $file)" "$file" \
      --metadata "{\"commit\": \"$commit\", \"message\": \"$message\"}"
  done
done

# Query code history
ipfs-kit bucket query "
  SELECT JSON_EXTRACT(metadata_json, '$.commit') as commit,
         COUNT(*) as files
  FROM vfs_github_code_archive
  GROUP BY commit
"
```

## Benefits of Bucket Virtual Filesystems

### 1. **Content Addressing & Deduplication**
- Automatic deduplication across all backends via IPFS hashes
- Verifiable content integrity with cryptographic hashes
- Immutable content references that work across time and systems

### 2. **Backend Abstraction**
- Users work with logical buckets, not storage implementation details
- Transparent backend selection based on content type and policies
- Easy migration between backends without changing content addresses

### 3. **Unified Querying**
- SQL queries across multiple storage backends
- Fast analytics via Parquet-based indices
- Cross-backend correlation and analysis

### 4. **Scalable Architecture**
- Distributed storage across 15+ different backend types
- Policy-driven placement and replication
- Automatic tiering and lifecycle management

### 5. **Developer Experience**
- Simple, intuitive CLI for complex distributed storage
- Filesystem-like operations with content addressing benefits
- Rich metadata support for application-specific use cases

This architecture enables treating diverse storage backends (S3, GitHub, SSH servers, Google Drive, etc.) as a unified, content-addressed virtual filesystem where every piece of content is verifiable, deduplicatable, and queryable across the entire distributed system.

## Policy System Examples

### Complete Multi-Tier Configuration

#### 1. Set Global Policies
```bash
# Configure system-wide defaults
ipfs-kit config pinset-policy set \
  --replication-strategy adaptive \
  --min-replicas 2 \
  --max-replicas 5 \
  --cache-policy lru \
  --cache-size 10000 \
  --cache-memory-limit 4GB \
  --performance-tier balanced \
  --auto-tier \
  --preferred-backends "filecoin,s3,arrow"
```

#### 2. Configure Backend Quotas
```bash
# High-persistence, low-speed backend (Filecoin)
ipfs-kit backend lotus configure \
  --quota-size 50TB \
  --retention-policy permanent \
  --auto-renew \
  --redundancy-level 3

# High-speed, low-persistence backend (Arrow)  
ipfs-kit backend arrow configure \
  --memory-quota 16GB \
  --retention-policy temporary \
  --session-retention 48 \
  --spill-to-disk

# Balanced backend (S3)
ipfs-kit backend s3 configure \
  --account-quota 10TB \
  --retention-policy lifecycle \
  --cost-optimization \
  --auto-delete-after 365
```

#### 3. Set Bucket-Level Policies
```bash
# High-performance ML training bucket
ipfs-kit bucket policy set ml-training \
  --primary-backend arrow \
  --replication-backends "arrow,parquet" \
  --performance-tier speed-optimized \
  --cache-priority high \
  --retention-days 30

# Long-term archive bucket
ipfs-kit bucket policy set archive \
  --primary-backend filecoin \
  --replication-backends "filecoin,s3,storacha" \
  --performance-tier persistence-optimized \
  --retention-days 2555 \
  --quota-action auto-archive

# Multi-tier production bucket
ipfs-kit bucket policy set production \
  --auto-tier \
  --hot-backend arrow \
  --warm-backend parquet \
  --cold-backend s3 \
  --archive-backend filecoin
```

## Policy System Examples

### Complete Multi-Tier Configuration

#### 1. Set Global Policies
```bash
# Configure system-wide defaults
ipfs-kit config pinset-policy set \
  --replication-strategy adaptive \
  --min-replicas 2 \
  --max-replicas 5 \
  --cache-policy lru \
  --cache-size 10000 \
  --cache-memory-limit 4GB \
  --performance-tier balanced \
  --auto-tier \
  --preferred-backends "filecoin,s3,arrow"
```

#### 2. Configure Backend Quotas
```bash
# High-persistence, low-speed backend (Filecoin)
ipfs-kit backend lotus configure \
  --quota-size 50TB \
  --retention-policy permanent \
  --auto-renew \
  --redundancy-level 3

# High-speed, low-persistence backend (Arrow)  
ipfs-kit backend arrow configure \
  --memory-quota 16GB \
  --retention-policy temporary \
  --session-retention 48 \
  --spill-to-disk

# Balanced backend (S3)
ipfs-kit backend s3 configure \
  --account-quota 10TB \
  --retention-policy lifecycle \
  --cost-optimization \
  --auto-delete-after 365
```

#### 3. Set Bucket-Level Policies
```bash
# High-performance ML training bucket
ipfs-kit bucket policy set ml-training \
  --primary-backend arrow \
  --replication-backends "arrow,parquet" \
  --performance-tier speed-optimized \
  --cache-priority high \
  --retention-days 30

# Long-term archive bucket
ipfs-kit bucket policy set archive \
  --primary-backend filecoin \
  --replication-backends "filecoin,s3,storacha" \
  --performance-tier persistence-optimized \
  --retention-days 2555 \
  --quota-action auto-archive

# Multi-tier production bucket
ipfs-kit bucket policy set production \
  --auto-tier \
  --hot-backend arrow \
  --warm-backend parquet \
  --cold-backend s3 \
  --archive-backend filecoin
```

## Data Sources and Architecture

### Real Data Integration
- **Bucket Registry**: Global bucket registry stored as Parquet with JSON backup
- **Pin Metadata**: Content-addressed pins stored in Parquet format with metadata
- **VFS Indices**: Virtual filesystem structure stored as Parquet for fast querying
- **Program State**: 4 Parquet files for lock-free daemon status monitoring
- **Configuration Files**: 5 config files from ~/.ipfs_kit/ for system settings
- **Operational Data**: Pins, WAL operations, FS journal from Parquet

### Parquet-First Storage Architecture
The system now prioritizes Parquet storage over JSON for all metadata:

```
Data Type           Primary Format    Backup Format    Benefits
---------           --------------    -------------    --------
Bucket Registry  →  .parquet         .json            Fast queries, analytics
Pin Metadata     →  .parquet         .json            Structured storage, dedup
VFS Indices      →  .parquet         .json            SQL queries, composition
Program State    →  .parquet         none             Lock-free daemon status
Analytics Data   →  .parquet         none             Performance metrics
```

### Lock-Free Architecture
```
CLI Commands → Program State Parquet → Lock-free status
            ↓
       VFS Indices → Fast bucket queries  
            ↓
     Pin Metadata → Content addressing
            ↓
     Backend APIs → Storage operations
```

### Directory Structure Overview
```
~/.ipfs_kit/
├── bucket_registry.parquet          # Global bucket registry (PRIMARY)
├── bucket_registry.json             # Backup compatibility format
├── buckets/                          # Per-backend bucket storage
│   └── [backend]/[bucket]/
│       ├── metadata/bucket_metadata.json
│       └── parquet/file_metadata.parquet
├── pin_metadata/                     # Content-addressed pin storage
│   └── [backend]/[bucket]/
│       └── [content-hash].parquet   # Pin metadata as Parquet
├── vfs_indices/                      # Virtual filesystem indices
│   └── [backend]/[bucket]/
│       └── vfs_index.parquet        # VFS structure as Parquet
└── program_state/parquet/           # Lock-free daemon status
    ├── system_state.parquet
    ├── network_state.parquet
    ├── storage_state.parquet
    └── files_state.parquet
```

## Advanced Usage Patterns

### Development Workflow
```bash
# Setup development environment
ipfs-kit config pinset-policy set --performance-tier speed-optimized
ipfs-kit bucket policy set dev-bucket --primary-backend arrow --retention-days 7

# Production deployment
ipfs-kit config pinset-policy set --replication-strategy adaptive --min-replicas 3
ipfs-kit bucket policy set prod-bucket --auto-tier --retention-days 365
```

### Multi-Backend Replication
```bash
# Configure for high availability
ipfs-kit config pinset-policy set \
  --replication-strategy multi-backend \
  --geographic-distribution global \
  --failover-strategy immediate

ipfs-kit bucket policy set critical-data \
  --replication-backends "filecoin,s3,storacha,github" \
  --min-replicas 4
```

### Cost Optimization
```bash
# Cost-optimized global policy
ipfs-kit config pinset-policy set \
  --backend-weights "filecoin:0.6,s3:0.3,arrow:0.1" \
  --auto-tier \
  --warm-tier-duration 86400

# Enable S3 cost optimization
ipfs-kit backend s3 configure --cost-optimization --retention-policy lifecycle
```

## Benefits of Enhanced CLI

1. **Comprehensive Control**: Fine-grained policies across all storage tiers
2. **Multi-Backend Support**: 15 different storage backends with unified interface
3. **Lock-Free Operations**: Daemon status without API locks or blocking
4. **Real Data Integration**: All commands use actual stored data when available
5. **Policy Inheritance**: Hierarchical policy system reduces configuration complexity
6. **Automated Management**: Auto-tiering and lifecycle management
7. **Production Ready**: Comprehensive monitoring, logging, and health checks

## Quick Reference

### Most Common Commands
```bash
# System status and health
ipfs-kit daemon status                  # Daemon status
ipfs-kit health                         # System health
ipfs-kit metrics                        # Performance metrics

# Policy management
ipfs-kit config pinset-policy show     # Global policies
ipfs-kit bucket policy show            # Bucket policies
ipfs-kit backend test                   # Backend health

# Content operations
ipfs-kit pin add <hash>                 # Pin content
ipfs-kit bucket list                    # List buckets
ipfs-kit backend s3 upload file.txt    # Upload to S3
```

This enhanced CLI provides a comprehensive, production-ready interface for managing distributed storage with fine-grained policy control across all backends while maintaining ease of use and operational transparency.

## Real Data Sources

### Configuration Files (5 sources)
1. **package_config.yaml** - Package settings and version info
2. **s3_config.yaml** - S3 storage configuration (region, endpoint)
3. **lotus_config.yaml** - Lotus node configuration (URL, token)
4. **wal/config.json** - Write-Ahead Log settings (enabled, batch size)
5. **fs_journal/config.json** - Filesystem journal settings (enabled, monitor path)

### Program State Data (4 Parquet files)
1. **system_state.parquet** - System performance and health metrics
2. **network_state.parquet** - Network connectivity and peer information
3. **storage_state.parquet** - Storage usage and repository information
4. **files_state.parquet** - File operations and management state

### Operational Data
- **Pin Data**: 3 pins tracked in Parquet format
- **WAL Operations**: 1 operation logged with timestamps
- **FS Journal**: 2 filesystem operations monitored

## Enhanced Features

### Program State Integration
- **Lock-Free Access**: Read daemon status without API locks
- **Rich Metrics**: Bandwidth (1KB/s in, 2KB/s out), repository size (976.6KB)
- **Network Status**: Connected peers (5), IPFS version (0.29.0)
- **Real-Time Updates**: Last updated timestamps from daemon

### Configuration Management
- **Multi-Format Support**: YAML and JSON configuration files
- **Validation**: Comprehensive config file validation with error reporting
- **Source Tracking**: Display which files provide each configuration value

### Data Integration Architecture
```
Daemon → Writes to Parquet → CLI reads lock-free
       ↓
   DuckDB synchronizes periodically
       ↓
   Real-time status without daemon locks
```

## Usage Examples

### Check Daemon Status (Enhanced)
```bash
ipfs-kit daemon status
```
**Output**: Program state metrics, network status, storage info, performance data

### View Configuration (Enhanced)
```bash
ipfs-kit config show
```
**Output**: All 5 config files displayed with sources

### Validate Configuration (Enhanced)
```bash
ipfs-kit config validate
```
**Output**: Real file validation results

### View Real Pin Data
```bash
ipfs-kit pin list
```
**Output**: Pins from Parquet data with timestamps

### View WAL Operations
```bash
ipfs-kit wal show
```
**Output**: Real WAL operations from Parquet

## Technical Implementation

### ParquetDataReader Enhancements
- **Config Integration**: `read_configuration()`, `get_config_value()`
- **Program State**: `read_program_state()`, `get_current_daemon_status()`
- **Multi-Format**: YAML and JSON config file parsing
- **Error Handling**: Graceful fallbacks and comprehensive error reporting

### CLI Architecture
- **Real Data Priority**: Program state → Config files → API calls
- **Lock-Free Design**: No daemon API locks for status checking
- **Comprehensive Display**: Rich formatting with emojis and structured output

## Benefits

1. **Lock-Free Operations**: Daemon status without API locks or daemon interaction
2. **Real Data Integration**: All commands use actual stored data when available
3. **Comprehensive Monitoring**: Rich performance metrics and status information
4. **Configuration Management**: Real config file integration with validation
5. **Operational Transparency**: View actual stored operations (pins, WAL, FS journal)
6. **Fallback Architecture**: Graceful degradation when data sources unavailable

## Data Architecture Summary

The CLI now provides a sophisticated multi-tier data access strategy:
- **Tier 1**: Program state Parquet files (fastest, lock-free)
- **Tier 2**: Configuration files (reliable, persistent)
- **Tier 3**: Operational Parquet data (pins, WAL, FS journal)
- **Tier 4**: API calls (fallback when needed)

This architecture enables comprehensive system monitoring and management without the traditional limitations of daemon API dependencies.
