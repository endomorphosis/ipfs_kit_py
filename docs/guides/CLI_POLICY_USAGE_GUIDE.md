# 📖 IPFS-Kit CLI Usage Guide - Policy System

## Overview

This guide covers the comprehensive CLI commands for the three-tier policy system in IPFS-Kit, providing examples and best practices for managing global policies, bucket-level policies, and backend quotas.

## 🌐 Global Pinset Policy Commands

### Show Current Global Policies

```bash
# Display all current global policies
ipfs-kit config pinset-policy show

# Example output:
# Global Pinset Policies:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Replication Strategy: adaptive
# Min Replicas: 2
# Max Replicas: 5
# Cache Policy: lru
# Cache Size: 10000 objects
# Cache Memory Limit: 4GB
# Performance Tier: balanced
# Geographic Distribution: regional
# Auto-Tiering: enabled
# Preferred Backends: filecoin,s3,arrow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Set Global Policies

#### Basic Replication Configuration
```bash
# Set adaptive replication with 2-5 replicas
ipfs-kit config pinset-policy set \
  --replication-strategy adaptive \
  --min-replicas 2 \
  --max-replicas 5

# Set single backend for maximum performance  
ipfs-kit config pinset-policy set \
  --replication-strategy single \
  --preferred-backends "arrow"

# Set multi-backend for high availability
ipfs-kit config pinset-policy set \
  --replication-strategy multi-backend \
  --min-replicas 3 \
  --preferred-backends "filecoin,s3,storacha"
```

#### Cache Configuration
```bash
# Configure LRU cache with memory limit
ipfs-kit config pinset-policy set \
  --cache-policy lru \
  --cache-size 50000 \
  --cache-memory-limit 8GB

# Enable adaptive caching with auto-GC
ipfs-kit config pinset-policy set \
  --cache-policy adaptive \
  --auto-gc \
  --gc-threshold 0.8
```

#### Performance and Tiering
```bash
# Set speed-optimized performance tier
ipfs-kit config pinset-policy set \
  --performance-tier speed-optimized \
  --preferred-backends "arrow,parquet,s3"

# Enable auto-tiering with custom durations
ipfs-kit config pinset-policy set \
  --auto-tier \
  --hot-tier-duration 3600 \    # 1 hour in hot tier
  --warm-tier-duration 86400    # 1 day in warm tier

# Configure persistence-optimized tier
ipfs-kit config pinset-policy set \
  --performance-tier persistence-optimized \
  --preferred-backends "filecoin,storacha,s3"
```

#### Geographic and Failover Configuration
```bash
# Set regional distribution with immediate failover
ipfs-kit config pinset-policy set \
  --geographic-distribution regional \
  --failover-strategy immediate

# Configure global distribution
ipfs-kit config pinset-policy set \
  --geographic-distribution global \
  --failover-strategy delayed
```

#### Backend Preference Management
```bash
# Set backend weights for load balancing
ipfs-kit config pinset-policy set \
  --backend-weights "filecoin:0.4,s3:0.3,arrow:0.3"

# Exclude unreliable backends
ipfs-kit config pinset-policy set \
  --exclude-backends "slow-ftp,unreliable-sshfs"

# Set preferred backend order
ipfs-kit config pinset-policy set \
  --preferred-backends "arrow,parquet,s3,filecoin"
```

### Reset Global Policies
```bash
# Reset all global policies to system defaults
ipfs-kit config pinset-policy reset

# Confirmation prompt:
# ⚠️  This will reset all global pinset policies to defaults.
# Continue? [y/N]: y
# ✅ Global pinset policies reset to defaults
```

## 🪣 Bucket Policy Commands

### Show Bucket Policies

```bash
# Show all bucket policies
ipfs-kit bucket policy show

# Example output:
# Bucket Policies Summary:
# ┌─────────────────┬─────────────────┬──────────────────┬─────────────────┐
# │ Bucket Name     │ Primary Backend │ Performance Tier │ Cache Policy    │
# ├─────────────────┼─────────────────┼──────────────────┼─────────────────┤
# │ ml-training     │ arrow           │ speed-optimized  │ lru             │
# │ long-archive    │ filecoin        │ persistence-opt  │ fifo            │
# │ general-storage │ s3              │ balanced         │ inherit         │
# └─────────────────┴─────────────────┴──────────────────┴─────────────────┘

# Show specific bucket policy
ipfs-kit bucket policy show ml-training

# Example output:
# Bucket Policy: ml-training
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Primary Backend: arrow
# Replication Backends: arrow,parquet,s3
# Performance Tier: speed-optimized
# Cache Policy: lru (overrides global)
# Cache Size: 25000 objects
# Cache Priority: high
# Retention Days: 30
# Max Size: 1TB
# Auto-Tiering: enabled
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Set Bucket Policies

#### High-Performance ML Training Bucket
```bash
ipfs-kit bucket policy set ml-training \
  --primary-backend arrow \
  --replication-backends "arrow,parquet" \
  --performance-tier speed-optimized \
  --access-pattern read-heavy \
  --cache-policy lru \
  --cache-priority high \
  --cache-size 25000 \
  --retention-days 30 \
  --max-size 1TB
```

#### Long-Term Archive Bucket
```bash
ipfs-kit bucket policy set long-term-archive \
  --primary-backend filecoin \
  --replication-backends "filecoin,s3,storacha" \
  --performance-tier persistence-optimized \
  --access-pattern sequential \
  --cache-policy fifo \
  --cache-priority low \
  --retention-days 2555 \    # ~7 years
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
  --access-pattern mixed \
  --max-size 10TB \
  --quota-action warn
```

#### Research Data Bucket
```bash
ipfs-kit bucket policy set research-data \
  --primary-backend synapse \
  --replication-backends "synapse,s3,github" \
  --performance-tier balanced \
  --access-pattern write-heavy \
  --retention-days 365 \
  --max-size 500GB
```

#### Cost-Optimized Bucket
```bash
ipfs-kit bucket policy set cost-optimized \
  --primary-backend s3 \
  --replication-backends "s3,filecoin" \
  --performance-tier persistence-optimized \
  --cache-policy inherit \    # Use global cache policy
  --quota-action auto-delete \
  --retention-days 90
```

### Bucket Policy Templates

```bash
# Apply speed template (Arrow-focused)
ipfs-kit bucket policy template fast-bucket speed

# Apply balanced template
ipfs-kit bucket policy template general-bucket balanced

# Apply archival template (Filecoin-focused)
ipfs-kit bucket policy template archive-bucket archival

# Apply ML template (optimized for ML workloads)
ipfs-kit bucket policy template ml-bucket ml

# Apply research template (versioning and provenance)
ipfs-kit bucket policy template research-bucket research

# List available templates
ipfs-kit bucket policy template --list

# Template Descriptions:
# ┌──────────┬─────────────────────────────────────────────────────────┐
# │ Template │ Description                                             │
# ├──────────┼─────────────────────────────────────────────────────────┤
# │ speed    │ High-performance, Arrow primary, minimal replication   │
# │ balanced │ Mixed backends, adaptive policies, good all-around     │
# │ archival │ Long-term storage, Filecoin primary, high replication  │
# │ ml       │ ML workloads, fast access, temporary retention         │
# │ research │ Research data, versioning, provenance tracking         │
# └──────────┴─────────────────────────────────────────────────────────┘
```

### Copy and Reset Bucket Policies

```bash
# Copy policy from one bucket to another
ipfs-kit bucket policy copy source-bucket destination-bucket

# Example:
ipfs-kit bucket policy copy ml-training ml-inference
# ✅ Copied policy from 'ml-training' to 'ml-inference'

# Reset bucket to global defaults
ipfs-kit bucket policy reset my-bucket

# Confirmation prompt:
# ⚠️  This will reset bucket 'my-bucket' to global policy defaults.
# Continue? [y/N]: y
# ✅ Bucket 'my-bucket' reset to global defaults
```

## 🏪 Backend Configuration Commands

### Filecoin/Lotus Backend (High Persistence, Low Speed)

```bash
# Show current Lotus configuration
ipfs-kit backend lotus status

# Configure with deal-based retention
ipfs-kit backend lotus configure \
  --endpoint "http://127.0.0.1:1234/rpc/v0" \
  --token "your-lotus-token" \
  --quota-size 50TB \
  --quota-action auto-cleanup \
  --retention-policy permanent \
  --min-deal-duration 518400 \    # 1 year in epochs
  --auto-renew \
  --redundancy-level 3 \
  --priority-fee 0.001 \
  --cleanup-expired

# Test Lotus connection
ipfs-kit backend lotus test
```

### Arrow Backend (High Speed, Low Persistence)

```bash
# Configure Arrow with memory management
ipfs-kit backend arrow configure \
  --memory-quota 16GB \
  --quota-action spill-to-disk \
  --retention-policy temporary \
  --session-retention 48 \       # 48 hours
  --spill-to-disk \
  --compression-level 3 \
  --memory-pool-size 8GB

# Check Arrow memory usage
ipfs-kit backend arrow status

# Example output:
# Arrow Backend Status:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Memory Usage: 12.5GB / 16GB (78%)
# Spill-to-Disk: 2.3GB
# Active Sessions: 15
# Retention Policy: temporary (48h)
# Compression: Level 3 (snappy)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### S3 Backend (Moderate Speed, High Persistence)

```bash
# Configure S3 with lifecycle policies
ipfs-kit backend s3 configure \
  --access-key your-access-key \
  --secret-key your-secret-key \
  --region us-west-2 \
  --account-quota 10TB \
  --quota-action auto-tier \
  --retention-policy lifecycle \
  --auto-delete-after 365 \
  --cost-optimization \
  --transfer-acceleration \
  --monitoring-enabled

# Check S3 usage and costs
ipfs-kit backend s3 status

# Example output:
# S3 Backend Status:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Storage Used: 7.2TB / 10TB (72%)
# Monthly Cost: $145.67 (estimated)
# Objects: 2,847,293
# Lifecycle Policies: 15 active
# Transfer Acceleration: enabled
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Parquet Backend (Balanced Characteristics)

```bash
# Configure Parquet with compression
ipfs-kit backend parquet configure \
  --storage-quota 5TB \
  --quota-action auto-compact \
  --retention-policy access-based \
  --compression-algorithm snappy \
  --auto-compaction \
  --metadata-caching \
  --partition-size 128MB \
  --row-group-size 64MB

# Check Parquet efficiency
ipfs-kit backend parquet status

# Example output:
# Parquet Backend Status:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Storage Used: 3.1TB / 5TB (62%)
# Compression Ratio: 4.2:1 (snappy)
# Files: 145,892
# Last Compaction: 2 hours ago
# Metadata Cache Hit Rate: 94.2%
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### GitHub Backend (Version Control)

```bash
# Configure GitHub with LFS
ipfs-kit backend github configure \
  --token your-github-token \
  --default-org your-organization \
  --default-repo your-default-repo \
  --storage-quota 1GB \
  --lfs-quota 100GB \
  --quota-action lfs-migrate \
  --retention-policy indefinite \
  --auto-lfs \
  --collaboration-level private \
  --branch-protection

# Check GitHub usage
ipfs-kit backend github status
```

### HuggingFace Backend (AI/ML Models)

```bash
# Configure HuggingFace Hub
ipfs-kit backend huggingface configure \
  --token your-hf-token \
  --default-org your-organization \
  --cache-dir ~/.cache/huggingface \
  --storage-quota 1GB \
  --lfs-quota 1TB \
  --quota-action upgrade-prompt \
  --model-versioning commit-based \
  --cache-retention 30 \
  --auto-update \
  --collaboration-level public

# List your HF repositories
ipfs-kit backend huggingface list
```

### Google Drive Backend (Personal/Business Cloud)

```bash
# Configure Google Drive
ipfs-kit backend gdrive configure \
  --credentials ~/.config/gdrive/credentials.json \
  --default-folder "IPFS-Kit Data" \
  --shared-drive team-drive-id \
  --storage-quota 15GB \
  --quota-action upgrade-prompt \
  --retention-policy indefinite \
  --version-retention 100 \
  --auto-trash-days 30 \
  --sharing-level private \
  --sync-offline

# Check Drive storage
ipfs-kit backend gdrive status
```

### Storacha Backend (Web3 Storage)

```bash
# Configure Storacha/Web3.Storage
ipfs-kit backend storacha configure \
  --api-key your-storacha-key \
  --endpoint "https://api.web3.storage" \
  --storage-quota 1TB \
  --quota-action warn \
  --retention-policy deal-based \
  --deal-duration 180 \         # 180 days
  --auto-renew \
  --redundancy-level 3 \
  --ipfs-gateway "https://w3s.link"

# Check Storacha deals
ipfs-kit backend storacha status
```

### Synapse Backend (Research Data)

```bash
# Configure Synapse
ipfs-kit backend synapse configure \
  --endpoint "https://repo-prod.prod.sagebase.org" \
  --api-key your-synapse-key \
  --storage-quota 100GB \
  --quota-action archive \
  --retention-policy project-based \
  --version-limit 10 \
  --sharing-level team \
  --provenance-tracking \
  --doi-minting

# Check Synapse projects
ipfs-kit backend synapse status
```

### SSHFS Backend (Remote Filesystem)

```bash
# Configure SSHFS
ipfs-kit backend sshfs configure \
  --hostname remote-server.com \
  --username your-username \
  --port 22 \
  --private-key ~/.ssh/id_rsa \
  --remote-path /data/ipfs-kit \
  --storage-quota 1TB \
  --quota-action cleanup \
  --cleanup-policy lru \
  --retention-days 90 \
  --network-resilience \
  --auto-reconnect \
  --connection-timeout 30

# Test SSHFS connection
ipfs-kit backend sshfs test
```

### FTP Backend (Legacy Protocol)

```bash
# Configure FTP
ipfs-kit backend ftp configure \
  --host ftp.example.com \
  --username your-username \
  --password your-password \
  --port 21 \
  --use-tls \
  --passive \
  --remote-path /data \
  --storage-quota 500GB \
  --quota-action block \
  --retention-policy time-based \
  --retention-days 30 \
  --max-file-age 180 \
  --bandwidth-limit 10MB/s \
  --legacy-compatibility

# Test FTP connection
ipfs-kit backend ftp test
```

## 🔍 Monitoring and Status Commands

### System-Wide Status

```bash
# Overall system status
ipfs-kit status

# Policy system status
ipfs-kit policy status

# Backend health check
ipfs-kit backend test

# Quota usage summary
ipfs-kit quota summary

# Example output:
# IPFS-Kit Quota Usage Summary:
# ┌─────────────┬─────────────┬─────────────┬─────────────┬────────────┐
# │ Backend     │ Used        │ Quota       │ Usage %     │ Status     │
# ├─────────────┼─────────────┼─────────────┼─────────────┼────────────┤
# │ Filecoin    │ 35.2TB      │ 50TB        │ 70.4%       │ ✅ Healthy │
# │ Arrow       │ 12.5GB      │ 16GB        │ 78.1%       │ ⚠️  High    │
# │ S3          │ 7.2TB       │ 10TB        │ 72.0%       │ ✅ Healthy │
# │ Parquet     │ 3.1TB       │ 5TB         │ 62.0%       │ ✅ Healthy │
# │ GitHub      │ 850MB       │ 1GB         │ 85.0%       │ ⚠️  High    │
# └─────────────┴─────────────┴─────────────┴─────────────┴────────────┘
```

### Individual Backend Status

```bash
# Detailed backend status
ipfs-kit backend lotus status --detailed
ipfs-kit backend arrow status --detailed
ipfs-kit backend s3 status --detailed

# Backend performance metrics
ipfs-kit backend lotus metrics
ipfs-kit backend arrow metrics

# Backend configuration
ipfs-kit backend lotus config
```

## 🧪 Testing and Validation

### Policy Validation

```bash
# Validate all policies
ipfs-kit policy validate

# Validate specific bucket
ipfs-kit policy validate --bucket my-bucket

# Simulate storage operation
ipfs-kit policy simulate \
  --bucket ml-training \
  --size 100GB \
  --access-pattern read-heavy

# Example output:
# Policy Simulation Results:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bucket: ml-training
# Operation: Store 100GB, read-heavy access
# 
# Selected Backends:
# - Primary: Arrow (12.5GB available, ⚠️ insufficient)
# - Fallback: Parquet (1.9TB available, ✅ sufficient)
# 
# Estimated Performance:
# - Write Speed: 850 MB/s (Parquet)
# - Read Speed: 2.1 GB/s (cached)
# - Replication Time: 2 minutes
# 
# Recommendations:
# - Consider increasing Arrow memory quota
# - Enable spill-to-disk for Arrow backend
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Backend Testing

```bash
# Test all backends
ipfs-kit backend test --all

# Test specific backend
ipfs-kit backend arrow test --verbose

# Test backend connectivity
ipfs-kit backend s3 test --connectivity

# Test backend performance
ipfs-kit backend parquet test --performance

# Example output:
# Backend Test Results:
# ┌─────────────┬──────────────┬─────────────┬─────────────┬──────────────┐
# │ Backend     │ Connectivity │ Auth        │ Performance │ Overall      │
# ├─────────────┼──────────────┼─────────────┼─────────────┼──────────────┤
# │ Filecoin    │ ✅ Connected  │ ✅ Valid    │ 🐌 Slow     │ ✅ Healthy   │
# │ Arrow       │ ✅ Connected  │ ✅ Valid    │ ⚡ Fast     │ ⚠️  Memory   │
# │ S3          │ ✅ Connected  │ ✅ Valid    │ 🚀 Good     │ ✅ Healthy   │
# │ Parquet     │ ✅ Connected  │ ✅ Valid    │ 🚀 Good     │ ✅ Healthy   │
# │ GitHub      │ ✅ Connected  │ ✅ Valid    │ 🚀 Good     │ ⚠️  Quota    │
# │ SSHFS       │ ❌ Failed     │ ❌ Auth     │ ❌ N/A      │ ❌ Failed    │
# └─────────────┴──────────────┴─────────────┴─────────────┴──────────────┘
```

## 📊 Analytics and Reporting

### Policy Usage Analytics

```bash
# Policy effectiveness report
ipfs-kit analytics policy-usage --timeframe 30d

# Backend efficiency metrics
ipfs-kit analytics backend-efficiency --backend arrow

# Cost analysis
ipfs-kit analytics costs --breakdown-by-backend

# Storage trends
ipfs-kit analytics storage-trends --timeframe 90d

# Example output:
# Storage Trends (Last 90 Days):
# 
# ┌─────────────┬─────────────┬─────────────┬─────────────┐
# │ Backend     │ Growth Rate │ Efficiency  │ Cost Trend  │
# ├─────────────┼─────────────┼─────────────┼─────────────┤
# │ Filecoin    │ +2.1TB/mo   │ 94.2%       │ ↗️ +5.2%    │
# │ Arrow       │ +0.8GB/day  │ 78.1%       │ ↗️ +12.1%   │
# │ S3          │ +1.5TB/mo   │ 89.7%       │ ↘️ -2.3%    │
# │ Parquet     │ +0.9TB/mo   │ 91.4%       │ ↗️ +1.8%    │
# └─────────────┴─────────────┴─────────────┴─────────────┘
```

### Export Configuration

```bash
# Export all policies to JSON
ipfs-kit config export --format json --output policies.json

# Export specific bucket policies
ipfs-kit bucket policy export my-bucket --format yaml

# Export backend configurations (sensitive data masked)
ipfs-kit backend export --mask-secrets --format json

# Import policies from file
ipfs-kit config import --file policies.json --merge

# Backup entire configuration
ipfs-kit config backup --output ipfs-kit-backup-$(date +%Y%m%d).tar.gz
```

## 🔧 Advanced Configuration Examples

### Multi-Environment Setup

```bash
# Development environment
ipfs-kit config pinset-policy set \
  --replication-strategy single \
  --cache-policy lru \
  --performance-tier speed-optimized \
  --preferred-backends "arrow"

# Staging environment  
ipfs-kit config pinset-policy set \
  --replication-strategy multi-backend \
  --min-replicas 2 \
  --cache-policy adaptive \
  --performance-tier balanced

# Production environment
ipfs-kit config pinset-policy set \
  --replication-strategy adaptive \
  --min-replicas 3 \
  --max-replicas 5 \
  --cache-policy tiered \
  --performance-tier balanced \
  --geographic-distribution regional \
  --failover-strategy immediate
```

### Compliance Configuration

```bash
# GDPR compliance bucket
ipfs-kit bucket policy set gdpr-data \
  --primary-backend s3 \
  --replication-backends "s3,github" \
  --retention-days 2555 \    # 7 years
  --quota-action block \     # Never auto-delete
  --access-pattern write-heavy

# HIPAA compliance bucket
ipfs-kit bucket policy set hipaa-data \
  --primary-backend synapse \
  --replication-backends "synapse,s3" \
  --retention-days 2190 \    # 6 years
  --quota-action archive \
  --cache-priority critical
```

### Development Workflow

```bash
# Feature development bucket (temporary)
ipfs-kit bucket policy set feature-dev \
  --primary-backend arrow \
  --performance-tier speed-optimized \
  --retention-days 7 \
  --quota-action auto-delete

# Code review bucket  
ipfs-kit bucket policy set code-review \
  --primary-backend github \
  --replication-backends "github,s3" \
  --retention-days 90 \
  --branch-protection

# Release archive bucket
ipfs-kit bucket policy set releases \
  --primary-backend filecoin \
  --replication-backends "filecoin,s3,github" \
  --retention-days 1825 \    # 5 years
  --quota-action warn
```

## 🚨 Troubleshooting Guide

### Common Error Messages and Solutions

#### "Quota exceeded for backend X"
```bash
# Check current usage
ipfs-kit backend X status

# Solution 1: Increase quota
ipfs-kit backend X configure --quota-size 20GB

# Solution 2: Enable auto-cleanup
ipfs-kit backend X configure --quota-action auto-cleanup

# Solution 3: Change bucket's primary backend
ipfs-kit bucket policy set my-bucket --primary-backend different-backend
```

#### "Policy validation failed"
```bash
# Check policy conflicts
ipfs-kit policy validate --verbose

# Fix common issues:
# - Ensure backend is configured before use
ipfs-kit backend arrow configure --memory-quota 8GB

# - Adjust replication requirements
ipfs-kit bucket policy set my-bucket --min-replicas 1
```

#### "Backend connection failed"
```bash
# Test specific backend
ipfs-kit backend X test --verbose

# Common fixes:
# - Check credentials
ipfs-kit backend s3 configure --access-key new-key --secret-key new-secret

# - Verify endpoints
ipfs-kit backend lotus configure --endpoint http://localhost:1234/rpc/v0

# - Test network connectivity
ipfs-kit backend sshfs test --connectivity
```

#### "Cache memory exceeded"
```bash
# Check cache usage
ipfs-kit config pinset-policy show

# Increase cache memory limit
ipfs-kit config pinset-policy set --cache-memory-limit 8GB

# Enable cache garbage collection
ipfs-kit config pinset-policy set --auto-gc --gc-threshold 0.8
```

### Performance Optimization

```bash
# Profile current performance
ipfs-kit analytics performance --detailed

# Optimize for speed
ipfs-kit config pinset-policy set \
  --performance-tier speed-optimized \
  --preferred-backends "arrow,parquet"

# Optimize for throughput
ipfs-kit config pinset-policy set \
  --replication-strategy single \
  --cache-policy lru \
  --cache-size 100000

# Optimize for storage efficiency
ipfs-kit config pinset-policy set \
  --performance-tier persistence-optimized \
  --auto-tier \
  --preferred-backends "filecoin,storacha"
```

## 📚 Command Reference Summary

### Quick Reference Table

| Command Category | Command | Purpose |
|------------------|---------|---------|
| **Global Policies** | `config pinset-policy show` | Show global policies |
| | `config pinset-policy set [OPTIONS]` | Set global policies |
| | `config pinset-policy reset` | Reset to defaults |
| **Bucket Policies** | `bucket policy show [BUCKET]` | Show bucket policies |
| | `bucket policy set BUCKET [OPTIONS]` | Set bucket policy |
| | `bucket policy copy SRC DEST` | Copy policies |
| | `bucket policy template BUCKET TEMPLATE` | Apply template |
| | `bucket policy reset BUCKET` | Reset bucket |
| **Backend Config** | `backend NAME configure [OPTIONS]` | Configure backend |
| | `backend NAME status` | Show backend status |
| | `backend NAME test` | Test backend |
| **Monitoring** | `status` | System status |
| | `policy validate` | Validate policies |
| | `analytics [TYPE]` | Usage analytics |
| **Maintenance** | `config export` | Export configuration |
| | `config import` | Import configuration |
| | `config backup` | Backup configuration |

### Most Used Commands

```bash
# Daily operations
ipfs-kit status                          # Check system health
ipfs-kit quota summary                   # Check storage usage
ipfs-kit backend test --all             # Test all backends

# Policy management
ipfs-kit bucket policy show             # Review bucket policies
ipfs-kit policy validate               # Validate configuration
ipfs-kit analytics policy-usage        # Check policy effectiveness

# Configuration
ipfs-kit config pinset-policy show     # Review global settings
ipfs-kit backend STATUS status         # Check specific backend
ipfs-kit config backup                 # Backup configuration
```

---

**This CLI guide provides comprehensive coverage of the IPFS-Kit three-tier policy system. Use these commands to effectively manage your distributed storage infrastructure with fine-grained control over replication, caching, and quotas.**
