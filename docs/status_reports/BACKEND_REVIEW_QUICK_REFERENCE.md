# Filesystem Backend Architecture - Quick Reference

> **Full Review**: See [FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md](./FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md) for complete documentation

---

## TL;DR Summary

**Problem**: The codebase has **3 separate backend systems** that don't interoperate  
**Impact**: Code duplication, inconsistent interfaces, confusion about which to use  
**Solution**: 4-phase consolidation plan to unify all backends under single interface

---

## Current State at a Glance

### Three Independent Backend Layers

```
┌─────────────────────────────────────────────┐
│ Layer A: backends/ (Legacy)                 │
│ • BackendAdapter base class                 │
│ • 3 implementations: IPFS, S3, Filesystem   │
│ • Focus: Sync, backup, restore operations   │
├─────────────────────────────────────────────┤
│ Layer B: mcp/storage_manager/backends/      │
│ • BackendStorage base class                 │
│ • 9+ implementations                        │
│ • Focus: Content add/get/remove operations  │
├─────────────────────────────────────────────┤
│ Layer C: *_kit.py files (Service Kits)      │
│ • No common base class                      │
│ • 10+ implementations                       │
│ • Focus: Direct service API wrappers        │
└─────────────────────────────────────────────┘
```

### Backend Managers (3 Different Ones!)

| Manager | Location | Purpose | Storage |
|---------|----------|---------|---------|
| **BackendManager** | Root level | YAML config CRUD | `~/.ipfs_kit/backends/*.yaml` |
| **EnhancedBackendManager** | Root level | Adds policies | YAML + JSON |
| **MCP BackendManager** | mcp/storage_manager/ | Runtime registry | In-memory only |

---

## Quick Backend Selection Guide

### By Use Case

| If you need... | Use this backend |
|----------------|------------------|
| **Fast local caching** | Filesystem or IPFS (local) |
| **Content-addressed storage** | IPFS or Storacha |
| **Long-term archival** | Filecoin or S3 Glacier |
| **High-performance object storage** | S3 or MinIO |
| **Decentralized web hosting** | Storacha or IPFS+Pinata |
| **ML models/datasets** | HuggingFace or S3 |
| **Content delivery (CDN)** | Saturn or CloudFlare+IPFS |
| **Fast retrieval** | Lassie or IPFS gateway |
| **Remote server backup** | SSHFS or S3+encryption |

### By Performance

| Backend | Latency | Throughput | Durability | Cost |
|---------|---------|------------|------------|------|
| **Filesystem** | ⚡ Very Low | ⚡⚡⚡ Very High | ⚠️ Medium | 💰 Free |
| **IPFS (local)** | ⚡ Very Low | ⚡⚡ High | ⚠️ Medium | 💰 Free |
| **S3** | ⚡ Low | ⚡⚡⚡ Very High | ✅ Very High | 💰💰 Low-Med |
| **Storacha** | ⚠️ Medium | ⚡⚡ Medium | ✅ Very High | 💰 Free tier |
| **Filecoin** | 🐌 Very High | 🐌 Low | ✅ Very High | 💰 Low |
| **Lassie** | ⚠️ Medium | ⚡⚡ High | N/A | 💰 Free |

---

## Top 6 Issues Found

| # | Issue | Severity | Impact |
|---|-------|----------|--------|
| **1** | Dual base classes (`BackendAdapter` vs `BackendStorage`) | 🔴 Critical | No interoperability between systems |
| **2** | Three backend managers with unclear ownership | 🔴 Critical | Confusion about which to use |
| **3** | Service kits bypass framework | 🟡 Medium | Can't swap backends polymorphically |
| **4** | IPFS implemented 4 separate times | 🟡 Medium | Maintenance burden |
| **5** | Inconsistent naming (Backend/BackendAdapter/Kit) | 🟡 Medium | Code navigation confusion |
| **6** | Config fragmentation (YAML/JSON/env vars) | 🟡 Medium | Inconsistent configuration |

---

## Migration Plan Summary

### Phase 1: Documentation (✅ Complete)
- Document current architecture → **This document**
- Mark legacy systems as deprecated
- Create migration guides

### Phase 2: Interface Unification (Short-term)
- Create `UnifiedBackend` base class
- Build adapter wrappers for existing backends
- Update new code to use unified interface

### Phase 3: Manager Consolidation (Medium-term)
- Merge 3 managers into `UnifiedBackendManager`
- Add config persistence + runtime registry
- Include policy support as optional feature

### Phase 4: Kit Integration (Long-term)
- Wrap all service kits with standard adapters
- Complete migration to unified architecture
- Deprecate old implementations

---

## Which Backend System Should I Use? (Decision Tree)

```
Are you writing NEW code?
├─ YES
│  └─ Use Layer B (MCP BackendStorage)
│     └─ File: ipfs_kit_py/mcp/storage_manager/backends/*
│
└─ NO (maintaining existing code)
   ├─ Is it in backends/ directory?
   │  └─ Use Layer A (BackendAdapter)
   │
   ├─ Is it in mcp/storage_manager/?
   │  └─ Use Layer B (BackendStorage)
   │
   └─ Is it using *_kit.py directly?
      └─ Use Layer C (Service Kit)
```

**Rule of thumb**: For new features, prefer **Layer B (BackendStorage)** until unification is complete.

---

## Supported Backend Types

### Layer A (BackendAdapter) - 3 types
- ✅ IPFS
- ✅ S3 (+ MinIO, DigitalOcean)
- ✅ Filesystem (+ SSHFS)

### Layer B (BackendStorage) - 9 types
- ✅ IPFS
- ✅ IPFS Advanced (clustering)
- ✅ S3
- ✅ Storacha
- ✅ Filecoin
- ✅ Filecoin Pin
- ✅ Lassie
- ✅ Saturn
- ✅ HuggingFace

### Layer C (Service Kits) - 10+ types
- ✅ S3Kit
- ✅ StorachaKit / EnhancedStorachaKit
- ✅ LassieKit
- ✅ LotusKit (Filecoin)
- ✅ HuggingFaceKit
- ✅ SSHFSKit
- ✅ FTPKit
- ✅ Aria2Kit
- ✅ SynapseKit
- ✅ GDriveKit
- ✅ GitHubKit

**Total**: 20+ storage backend implementations across all layers

---

## Quick Code Examples

### Layer A (BackendAdapter) Usage

```python
from ipfs_kit_py.backends import get_backend_adapter

# Factory pattern
backend = get_backend_adapter(
    backend_type='s3',
    backend_name='my_s3',
    config_manager=config_mgr
)

# Async operations
health = await backend.health_check()
await backend.sync_pins()
await backend.backup_buckets()
```

### Layer B (BackendStorage) Usage

```python
from ipfs_kit_py.mcp.storage_manager.backends.ipfs_backend import IPFSBackend

# Direct instantiation
backend = IPFSBackend(
    resources={'ipfs_host': 'localhost', 'ipfs_port': 5001},
    metadata={'backend_name': 'my_ipfs'}
)

# Content operations
result = backend.add_content(b"Hello, IPFS!")
cid = result['identifier']
content = backend.get_content(cid)
```

### Layer C (Service Kit) Usage

```python
from ipfs_kit_py.s3_kit import S3Kit

# Direct service integration
kit = S3Kit(
    access_key=os.getenv('AWS_ACCESS_KEY_ID'),
    secret_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Direct API calls
kit.upload_file('local.txt', 'my-bucket', 'remote.txt')
kit.download_file('my-bucket', 'remote.txt', 'download.txt')
```

---

## Configuration Quick Reference

### Standard Backend Config (YAML)

```yaml
# ~/.ipfs_kit/backends/my_backend.yaml
name: my_backend
type: s3

connection:
  endpoint_url: https://s3.amazonaws.com
  region: us-east-1
  bucket_name: my-bucket

credentials:
  access_key_id: ${AWS_ACCESS_KEY_ID}
  secret_access_key: ${AWS_SECRET_ACCESS_KEY}

operational:
  timeout: 30
  retry_count: 3

policies:
  storage_quota_gb: 1000
  retention_days: 90
```

### Policy Config (JSON)

```json
{
  "backend_name": "my_backend",
  "storage_quota": {
    "enabled": true,
    "quota_gb": 1000,
    "warning_threshold_percent": 80
  },
  "retention": {
    "enabled": true,
    "retention_days": 90,
    "auto_cleanup": true
  },
  "replication": {
    "enabled": true,
    "min_replicas": 2,
    "target_backends": ["ipfs_primary", "s3_backup"]
  }
}
```

---

## Testing Quick Reference

### Required Tests Per Backend

✅ **Unit Tests**:
- Init with valid/invalid config
- Health check (healthy + unhealthy)
- Content operations (add/get/remove)
- Error handling
- Timeout handling

✅ **Integration Tests**:
- Real backend connection
- Large file handling (>100MB)
- Concurrent operations
- Network failure recovery

✅ **E2E Tests**:
- Backend switching
- Multi-backend sync
- Failover scenarios

### Test Command

```bash
# Run all backend tests
pytest tests/backends/

# Run specific backend
pytest tests/backends/test_ipfs_backend.py

# Run integration tests
pytest tests/integration/ -m backend_integration
```

---

## Common Tasks

### Add a New Backend

1. Choose appropriate layer (prefer Layer B for new code)
2. Implement `BackendStorage` interface (Layer B)
3. Add to `StorageType` enum
4. Create configuration schema
5. Write unit tests
6. Write integration tests
7. Update documentation
8. Add examples

### Configure a Backend via CLI

```bash
# Create backend
ipfs-kit backend create my_s3 --type s3 \
  --bucket-name my-bucket \
  --region us-east-1

# List backends
ipfs-kit backend list

# Show backend
ipfs-kit backend show my_s3

# Test connection
ipfs-kit backend test my_s3

# Update backend
ipfs-kit backend update my_s3 --timeout 60

# Delete backend
ipfs-kit backend remove my_s3
```

### Check Backend Health

```python
# Method 1: Via manager
from ipfs_kit_py.backend_manager import BackendManager

mgr = BackendManager()
backends = mgr.list_backends()

# Method 2: Via adapter (Layer A)
from ipfs_kit_py.backends import get_backend_adapter

adapter = get_backend_adapter('s3', 'my_s3', config_mgr)
health = await adapter.health_check()
print(f"Healthy: {health['healthy']}")
print(f"Response time: {health['response_time_ms']}ms")

# Method 3: Via MCP manager (Layer B)
from ipfs_kit_py.mcp.storage_manager.backend_manager import BackendManager

mcp_mgr = BackendManager()
health = mcp_mgr.check_backend_health('my_s3')
```

---

## File Locations Reference

```
ipfs_kit_py/
├── backends/                          # Layer A (Legacy)
│   ├── base_adapter.py                # BackendAdapter base
│   └── *_backend.py                   # Implementations
│
├── mcp/storage_manager/               # Layer B (MCP)
│   ├── backend_base.py                # BackendStorage base
│   ├── backend_manager.py             # MCP manager
│   └── backends/                      # Implementations
│
├── backend_manager.py                 # Root manager
├── enhanced_backend_manager.py        # Enhanced manager
└── *_kit.py                          # Layer C (Kits)

Config files:
~/.ipfs_kit/
├── backends/*.yaml                    # Backend configs
├── policies/*.json                    # Policy configs
└── backends_metadata/                 # Backend metadata
```

---

## Next Steps

1. **Read full review**: [FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md](./FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md)
2. **Stakeholder review**: Validate findings and recommendations
3. **Plan Phase 2**: Begin interface unification design
4. **Track progress**: Create issues for each migration phase
5. **Start migration**: Implement `UnifiedBackend` interface

---

## Questions?

- **Full documentation**: [FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md](./FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md)
- **Architecture issues**: See Section 4 of full review
- **Migration plan**: See Section 7 of full review
- **Code examples**: See Section 8 of full review
- **Testing strategy**: See Section 9 of full review

**Last Updated**: February 2, 2026
