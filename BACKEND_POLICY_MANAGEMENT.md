# Backend Policy Management

This document provides comprehensive documentation for the storage backend policy management system implemented in IPFS Kit. The system enables administrators to define and enforce storage quotas, traffic quotas, replication policies, retention policies, and cache policies across all storage backends.

For detailed API documentation and usage examples, see [Backend Policy Management](docs/backend_policy_management.md).

## Quick Start

### 1. View Current Backend Policies

```bash
# List all backends with policy status
curl http://localhost:8000/api/v0/storage/backends

# Get complete policy set for a backend
curl http://localhost:8000/api/v0/storage/backends/s3_demo/policies
```

### 2. Set Storage Quota

```bash
curl -X PUT http://localhost:8000/api/v0/storage/backends/s3_demo/policies/storage_quota \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "max_size": 100,
    "max_size_unit": "gb",
    "warn_threshold": 0.8,
    "max_files": 10000
  }'
```

### 3. Configure Replication Policy

```bash
curl -X PUT http://localhost:8000/api/v0/storage/backends/cluster/policies/replication \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "strategy": "simple",
    "min_redundancy": 2,
    "max_redundancy": 4,
    "preferred_backends": ["ipfs", "s3"]
  }'
```

### 4. Monitor Quota Usage

```bash
# Check quota usage for a backend
curl http://localhost:8000/api/v0/storage/backends/s3_demo/quota-usage

# Get all policy violations
curl http://localhost:8000/api/v0/storage/policy-violations
```

## Policy Types

- **Storage Quota**: Size limits, file count limits, usage monitoring
- **Traffic Quota**: Bandwidth limits, request rate limits, daily transfer limits  
- **Replication**: Redundancy requirements, backend preferences, geographic distribution
- **Retention**: Data lifecycle management, compliance requirements, archival policies
- **Cache**: Cache size limits, eviction policies, promotion/demotion thresholds

## Integration Points

The policy system integrates with existing IPFS Kit components:

- **TieredCacheManager**: Applies cache policies and manages tier promotion/demotion
- **LifecycleManager**: Enforces retention policies and compliance requirements
- **ClusterManager**: Implements replication policies across cluster nodes
- **ResourceTracker**: Monitors quota usage and generates violation alerts

## Files Added

- `ipfs_kit_py/backend_policies.py` - Policy data models and validation
- `ipfs_kit_py/storage_backends_api.py` - Extended with policy management endpoints
- `docs/backend_policy_management.md` - Complete API documentation
- `test_storage_backend_policies.py` - Comprehensive test suite
- `test_policy_integration.py` - Integration validation tests

## Testing

Run the policy system tests:

```bash
# Test policy models and API structure
python test_storage_backend_policies.py

# Test integration points  
python test_policy_integration.py
```

The policy management system provides a unified interface for managing all storage backend policies while maintaining compatibility with existing IPFS Kit infrastructure.