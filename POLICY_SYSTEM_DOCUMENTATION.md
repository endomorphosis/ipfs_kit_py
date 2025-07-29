# 🎯 IPFS-Kit Three-Tier Policy System Documentation

## Overview

IPFS-Kit implements a comprehensive **three-tier policy system** that provides fine-grained control over data replication, caching, and storage quotas across all backends. The system is designed to prevent storage overflow while preserving data based on each backend's speed and persistence characteristics.

## 📐 Architecture

### Three-Tier Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                 🌐 Global Pinset Policies                   │
│              (ipfs-kit config pinset-policy)               │
│                                                            │
│  • Replication strategies across all backends             │
│  • Global cache policies and memory limits               │
│  • Performance tiers and auto-tiering rules             │
│  • Geographic distribution preferences                   │
│  • Failover strategies and backend weights              │
└─────────────────────────────────────────────────────────────┘
                              ⬇️ Inherits/Overrides
┌─────────────────────────────────────────────────────────────┐
│                 🪣 Bucket-Level Policies                    │
│               (ipfs-kit bucket policy)                     │
│                                                            │
│  • Per-bucket backend selection and priorities           │
│  • Bucket-specific cache overrides                       │
│  • Performance tiers and access patterns                 │  
│  • Lifecycle management and retention                    │
│  • Auto-tiering with hot/warm/cold backends             │
└─────────────────────────────────────────────────────────────┘
                              ⬇️ Enforces
┌─────────────────────────────────────────────────────────────┐
│               🏪 Backend-Specific Quotas                    │
│           (ipfs-kit backend <name> configure)              │
│                                                            │
│  • Storage quotas and usage limits                       │
│  • Retention policies based on backend characteristics   │
│  • Quota enforcement actions (warn/block/cleanup)        │
│  • Backend-optimized configurations                      │
└─────────────────────────────────────────────────────────────┘
```

### Policy Inheritance Flow

```
Global Defaults → Bucket Overrides → Backend Quotas
      ↓                 ↓               ↓
System-wide      Per-bucket      Hard limits
 behavior        customization   & enforcement
```

## 🌐 Global Pinset Policies

### Purpose
Configure system-wide defaults for all pinsets that apply across the entire IPFS-Kit installation.

### Command Structure
```bash
ipfs-kit config pinset-policy {show,set,reset}
```

### Available Options

#### Replication Strategies
```bash
--replication-strategy {single,multi-backend,tiered,adaptive}
```
- **single**: Use only one backend (highest performance)
- **multi-backend**: Replicate across multiple backends (high availability)
- **tiered**: Use different backends for different access patterns
- **adaptive**: Dynamically adjust based on usage patterns

#### Cache Policies
```bash
--cache-policy {lru,lfu,fifo,mru,adaptive,tiered}
--cache-size N                    # Number of objects
--cache-memory-limit SIZE         # Memory limit (e.g., 4GB)
```

#### Performance Tiers
```bash
--performance-tier {speed-optimized,balanced,persistence-optimized}
```
- **speed-optimized**: Prioritize Arrow, Parquet, local storage
- **balanced**: Mix of speed and persistence backends
- **persistence-optimized**: Prioritize Filecoin, S3, long-term storage

#### Auto-Tiering
```bash
--auto-tier                       # Enable automatic tiering
--hot-tier-duration SECONDS       # Time in hot tier (default: 1 day)
--warm-tier-duration SECONDS      # Time in warm tier (default: 1 week)
```

#### Geographic Distribution
```bash
--geographic-distribution {local,regional,global}
--failover-strategy {immediate,delayed,manual}
```

#### Backend Management
```bash
--preferred-backends "backend1,backend2,backend3"
--exclude-backends "slow-backend1,unreliable-backend2"
--backend-weights "arrow:0.3,s3:0.4,filecoin:0.3"
```

### Example Configurations

#### High-Performance Configuration
```bash
ipfs-kit config pinset-policy set \
  --replication-strategy adaptive \
  --cache-policy lru \
  --cache-size 50000 \
  --cache-memory-limit 8GB \
  --performance-tier speed-optimized \
  --preferred-backends "arrow,parquet,s3" \
  --auto-tier \
  --hot-tier-duration 3600
```

#### High-Availability Configuration
```bash
ipfs-kit config pinset-policy set \
  --replication-strategy multi-backend \
  --min-replicas 3 \
  --max-replicas 5 \
  --cache-policy adaptive \
  --performance-tier balanced \
  --geographic-distribution regional \
  --failover-strategy immediate
```

#### Archival Configuration
```bash
ipfs-kit config pinset-policy set \
  --replication-strategy tiered \
  --performance-tier persistence-optimized \
  --preferred-backends "filecoin,s3,storacha" \
  --cache-policy fifo \
  --auto-tier \
  --warm-tier-duration 604800
```

## 🪣 Bucket-Level Policies

### Purpose
Override global settings on a per-bucket basis for specific use cases and workloads.

### Command Structure
```bash
ipfs-kit bucket policy {show,set,copy,template,reset} [BUCKET_NAME]
```

### Available Options

#### Backend Selection
```bash
--primary-backend {s3,filecoin,arrow,parquet,ipfs,storacha,sshfs,ftp}
--replication-backends "backend1,backend2,backend3"
```

#### Cache Configuration
```bash
--cache-policy {lru,lfu,fifo,mru,adaptive,inherit}
--cache-size N                    # Override global cache size
--cache-priority {low,normal,high,critical}
--cache-ttl SECONDS              # Cache time-to-live
```

#### Performance Optimization
```bash
--performance-tier {speed-optimized,balanced,persistence-optimized,inherit}
--access-pattern {random,sequential,write-heavy,read-heavy,mixed}
```

#### Lifecycle Management
```bash
--retention-days N               # Data retention period
--max-size SIZE                  # Maximum bucket size
--quota-action {warn,block,auto-archive,auto-delete}
```

#### Auto-Tiering
```bash
--auto-tier                      # Enable bucket-level auto-tiering
--hot-backend BACKEND            # Backend for frequently accessed data
--warm-backend BACKEND           # Backend for occasionally accessed data  
--cold-backend BACKEND           # Backend for rarely accessed data
--archive-backend BACKEND        # Backend for archived data
```

### Example Configurations

#### ML Training Bucket (High-Speed)
```bash
ipfs-kit bucket policy set ml-training \
  --primary-backend arrow \
  --replication-backends "arrow,parquet" \
  --performance-tier speed-optimized \
  --access-pattern read-heavy \
  --cache-policy lru \
  --cache-priority high \
  --retention-days 30
```

#### Long-Term Archive Bucket
```bash
ipfs-kit bucket policy set long-term-archive \
  --primary-backend filecoin \
  --replication-backends "filecoin,s3,storacha" \
  --performance-tier persistence-optimized \
  --access-pattern sequential \
  --retention-days 2555 \
  --max-size 100TB \
  --quota-action auto-archive
```

#### Multi-Tier Production Bucket
```bash
ipfs-kit bucket policy set production-data \
  --auto-tier \
  --hot-backend arrow \
  --warm-backend parquet \
  --cold-backend s3 \
  --archive-backend filecoin \
  --cache-policy adaptive \
  --max-size 10TB \
  --quota-action warn
```

### Policy Templates

Pre-defined templates for common use cases:

```bash
# Apply templates
ipfs-kit bucket policy template my-bucket {speed,balanced,archival,ml,research}

# Available templates:
# - speed: High-performance, Arrow-based
# - balanced: Mixed backends, adaptive policies  
# - archival: Long-term storage, Filecoin-based
# - ml: Machine learning workloads, optimized for training
# - research: Research data, versioning and provenance
```

## 🏪 Backend-Specific Quotas & Retention

### Purpose
Prevent storage overflow and manage data lifecycle based on each backend's characteristics.

### Backend Characteristics Matrix

| Backend | Speed | Persistence | Specialization | Default Quota Strategy |
|---------|-------|-------------|----------------|----------------------|
| **Filecoin/Lotus** | Low | Very High | Decentralized storage | Deal-based, permanent retention |
| **Arrow** | Very High | Low | In-memory processing | Memory-based, temporary retention |
| **Parquet** | High | Medium | Columnar data | Storage-based, access-driven |
| **S3** | Medium | High | Cloud storage | Account-based, lifecycle policies |
| **GitHub** | Medium | High | Version control | Repository-based, LFS for large files |
| **HuggingFace** | Medium | Medium | AI/ML models | Hub-based, model versioning |
| **Google Drive** | Medium | High | Personal/business | Storage-based, sharing levels |
| **Storacha** | Low | Very High | Web3 storage | Filecoin-backed, deal-based |
| **Synapse** | Medium | High | Research data | Project-based, provenance tracking |
| **SSHFS** | Variable | Variable | Remote filesystem | Network-dependent, resilience-focused |
| **FTP** | Low-Medium | Variable | Legacy protocol | Server-based, bandwidth-limited |

### Configuration by Backend

#### Filecoin/Lotus (High Persistence, Low Speed)
```bash
ipfs-kit backend lotus configure \
  --quota-size 50TB \
  --quota-action auto-cleanup \
  --retention-policy permanent \
  --min-deal-duration 518400 \
  --auto-renew \
  --redundancy-level 3 \
  --cleanup-expired
```

**Key Features:**
- Deal-based storage with automatic renewal
- High redundancy for data safety
- Permanent retention by default
- Automatic cleanup of expired deals

#### Arrow (High Speed, Low Persistence)  
```bash
ipfs-kit backend arrow configure \
  --memory-quota 16GB \
  --quota-action spill-to-disk \
  --retention-policy temporary \
  --session-retention 48 \
  --spill-to-disk \
  --compression-level 3
```

**Key Features:**
- Memory-based storage with disk spillover
- Temporary retention for processing workloads
- Session-based cleanup
- High-performance compression

#### S3 (Moderate Speed, High Persistence)
```bash
ipfs-kit backend s3 configure \
  --account-quota 10TB \
  --quota-action auto-tier \
  --retention-policy lifecycle \
  --auto-delete-after 365 \
  --cost-optimization \
  --transfer-acceleration
```

**Key Features:**
- Account-wide quota management
- Lifecycle policies with storage classes
- Cost optimization features
- Transfer acceleration for performance

#### Parquet (Balanced Characteristics)
```bash
ipfs-kit backend parquet configure \
  --storage-quota 5TB \
  --quota-action auto-compact \
  --retention-policy access-based \
  --compression-algorithm snappy \
  --auto-compaction \
  --metadata-caching
```

**Key Features:**
- Columnar storage optimization
- Access-based retention policies
- Automatic compaction for efficiency
- Metadata caching for performance

#### GitHub (Version Control, Collaboration)
```bash
ipfs-kit backend github configure \
  --storage-quota 1GB \
  --lfs-quota 10GB \
  --quota-action lfs-migrate \
  --retention-policy indefinite \
  --auto-lfs \
  --collaboration-level private \
  --branch-protection
```

**Key Features:**
- Git LFS for large files
- Automatic migration to LFS when needed
- Branch protection rules
- Collaboration controls

#### HuggingFace (AI/ML Focus)
```bash
ipfs-kit backend huggingface configure \
  --storage-quota 1GB \
  --lfs-quota 100GB \
  --quota-action upgrade-prompt \
  --model-versioning commit-based \
  --cache-retention 30 \
  --auto-update \
  --collaboration-level private
```

**Key Features:**
- Model and dataset versioning
- Large file support via Git LFS
- Community collaboration features
- Automatic model updates

#### Google Drive (Personal/Business Cloud)
```bash
ipfs-kit backend gdrive configure \
  --storage-quota 15GB \
  --quota-action upgrade-prompt \
  --retention-policy indefinite \
  --version-retention 100 \
  --auto-trash-days 30 \
  --sharing-level private \
  --sync-offline
```

**Key Features:**
- Personal/business storage quotas
- File versioning with limits
- Sharing and collaboration controls
- Offline synchronization

#### Storacha (Web3 Storage)
```bash
ipfs-kit backend storacha configure \
  --storage-quota 1TB \
  --quota-action warn \
  --retention-policy deal-based \
  --deal-duration 180 \
  --auto-renew \
  --redundancy-level 3 \
  --ipfs-gateway "https://gateway.example.com"
```

**Key Features:**
- Filecoin-backed decentralized storage
- Deal-based retention with auto-renewal
- IPFS gateway integration
- Web3 storage economics

#### Synapse (Research Data)
```bash
ipfs-kit backend synapse configure \
  --storage-quota 100GB \
  --quota-action archive \
  --retention-policy project-based \
  --version-limit 10 \
  --sharing-level team \
  --provenance-tracking \
  --doi-minting
```

**Key Features:**
- Research-focused data management
- Provenance tracking for reproducibility
- DOI minting for publications
- Team collaboration features

#### SSHFS (Remote Filesystem)
```bash
ipfs-kit backend sshfs configure \
  --storage-quota 1TB \
  --quota-action cleanup \
  --cleanup-policy lru \
  --retention-days 90 \
  --network-resilience \
  --auto-reconnect \
  --connection-timeout 30
```

**Key Features:**
- Network-resilient remote storage
- Automatic reconnection handling
- LRU-based cleanup policies
- Connection timeout management

#### FTP (Legacy Protocol)
```bash
ipfs-kit backend ftp configure \
  --storage-quota 500GB \
  --quota-action block \
  --retention-policy time-based \
  --retention-days 30 \
  --max-file-age 180 \
  --bandwidth-limit 10MB/s \
  --legacy-compatibility
```

**Key Features:**
- Legacy FTP protocol support
- Bandwidth limiting
- Time-based retention policies
- Compatibility mode for old servers

## 🔄 Policy Interaction & Inheritance

### Inheritance Rules

1. **Global policies** set the baseline for all operations
2. **Bucket policies** override global settings for specific buckets
3. **Backend quotas** enforce hard limits regardless of higher-level policies

### Conflict Resolution

When policies conflict, the following precedence applies:

```
Backend Hard Limits > Bucket Policies > Global Policies > System Defaults
```

### Example Interaction

```bash
# Global policy: balanced performance, 3 replicas
ipfs-kit config pinset-policy set \
  --performance-tier balanced \
  --min-replicas 3 \
  --preferred-backends "s3,filecoin,arrow"

# Bucket policy: override for high-speed bucket
ipfs-kit bucket policy set speed-bucket \
  --performance-tier speed-optimized \
  --primary-backend arrow \
  --min-replicas 1  # Override global minimum

# Backend quota: enforce Arrow memory limit
ipfs-kit backend arrow configure \
  --memory-quota 8GB \
  --quota-action spill-to-disk

# Result: speed-bucket uses Arrow primarily with 1 replica,
# but is limited by 8GB memory quota with disk spillover
```

## 📊 Monitoring & Reporting

### Policy Status Commands

```bash
# View all policies
ipfs-kit config pinset-policy show     # Global policies
ipfs-kit bucket policy show           # All bucket policies  
ipfs-kit bucket policy show my-bucket # Specific bucket

# View backend quotas
ipfs-kit backend lotus status         # Filecoin quota usage
ipfs-kit backend arrow status         # Arrow memory usage
ipfs-kit backend s3 status            # S3 account usage
```

### Policy Validation

```bash
# Validate policy configuration
ipfs-kit policy validate              # Check all policies
ipfs-kit policy validate --bucket my-bucket  # Check specific bucket
ipfs-kit policy simulate --bucket my-bucket --size 1TB  # Simulate storage
```

### Usage Analytics

```bash
# View policy effectiveness
ipfs-kit analytics policy-usage       # Policy usage statistics
ipfs-kit analytics backend-efficiency # Backend performance metrics
ipfs-kit analytics quota-utilization  # Quota usage across backends
```

## 🛠️ Advanced Use Cases

### Multi-Tenant Configuration

```bash
# Tenant A: High-performance workloads
ipfs-kit bucket policy set tenant-a-data \
  --primary-backend arrow \
  --performance-tier speed-optimized \
  --cache-priority high

# Tenant B: Cost-optimized archival
ipfs-kit bucket policy set tenant-b-archive \
  --primary-backend filecoin \
  --performance-tier persistence-optimized \
  --cache-priority low
```

### Disaster Recovery Setup

```bash
# Primary region configuration
ipfs-kit config pinset-policy set \
  --geographic-distribution regional \
  --min-replicas 2 \
  --failover-strategy immediate

# DR bucket with cross-region replication
ipfs-kit bucket policy set disaster-recovery \
  --replication-backends "filecoin,s3,storacha" \
  --geographic-distribution global \
  --min-replicas 3
```

### Cost Optimization

```bash
# Cost-optimized global policy
ipfs-kit config pinset-policy set \
  --backend-weights "filecoin:0.6,s3:0.3,arrow:0.1" \
  --auto-tier \
  --warm-tier-duration 86400

# Cost-optimized S3 configuration
ipfs-kit backend s3 configure \
  --retention-policy lifecycle \
  --cost-optimization \
  --auto-delete-after 90
```

## 🔧 Best Practices

### 1. Start with Global Policies
Configure sensible global defaults before setting bucket-specific policies.

### 2. Match Backends to Use Cases
- **Arrow**: Real-time processing, ML training
- **Filecoin**: Long-term archival, compliance
- **S3**: General-purpose cloud storage
- **Parquet**: Analytics and data science

### 3. Monitor Quota Usage
Regularly check backend quotas to prevent unexpected storage limits.

### 4. Use Auto-Tiering
Enable auto-tiering for buckets with varying access patterns.

### 5. Test Policy Changes
Use policy simulation before applying changes to production buckets.

### 6. Document Custom Policies
Maintain documentation for custom bucket policies and backend configurations.

## 🚨 Troubleshooting

### Common Issues

#### Quota Exceeded Errors
```bash
# Check quota usage
ipfs-kit backend <name> status

# Increase quota or enable cleanup
ipfs-kit backend <name> configure --quota-action auto-cleanup
```

#### Performance Issues
```bash
# Check current performance tier
ipfs-kit bucket policy show my-bucket

# Switch to speed-optimized
ipfs-kit bucket policy set my-bucket --performance-tier speed-optimized
```

#### Replication Failures
```bash
# Check backend availability
ipfs-kit backend test

# Adjust replication settings
ipfs-kit bucket policy set my-bucket --min-replicas 1
```

#### Policy Conflicts
```bash
# Validate policy configuration  
ipfs-kit policy validate --bucket my-bucket

# Reset to global defaults
ipfs-kit bucket policy reset my-bucket
```

## 📚 Reference

### Complete Command Reference

#### Global Pinset Policy Commands
```bash
ipfs-kit config pinset-policy show
ipfs-kit config pinset-policy set [OPTIONS]
ipfs-kit config pinset-policy reset
```

#### Bucket Policy Commands
```bash
ipfs-kit bucket policy show [BUCKET]
ipfs-kit bucket policy set BUCKET [OPTIONS]
ipfs-kit bucket policy copy SOURCE DEST
ipfs-kit bucket policy template BUCKET TEMPLATE
ipfs-kit bucket policy reset BUCKET
```

#### Backend Configuration Commands
```bash
ipfs-kit backend <name> configure [OPTIONS]
ipfs-kit backend <name> status
ipfs-kit backend <name> test
```

### Configuration Files

Policies are stored in:
- Global: `~/.ipfs-kit/config/global-policies.json`
- Buckets: `~/.ipfs-kit/config/bucket-policies.json`
- Backends: `~/.ipfs-kit/config/backend-quotas.json`

### API Integration

The policy system is fully integrated with the IPFS-Kit API:

```python
# Python API example
from ipfs_kit_py import PolicyManager

pm = PolicyManager()

# Set global policy
pm.set_global_policy(
    replication_strategy="adaptive",
    cache_policy="lru",
    performance_tier="balanced"
)

# Set bucket policy
pm.set_bucket_policy(
    bucket="my-bucket",
    primary_backend="arrow",
    performance_tier="speed-optimized"
)

# Configure backend quota
pm.configure_backend(
    backend="arrow",
    memory_quota="8GB",
    retention_policy="temporary"
)
```

---

**The IPFS-Kit Three-Tier Policy System provides comprehensive control over data storage, replication, and lifecycle management across all backends while respecting each backend's unique characteristics and performance profiles.**
