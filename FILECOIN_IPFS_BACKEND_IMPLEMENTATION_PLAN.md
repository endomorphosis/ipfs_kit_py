# Comprehensive IPFS/Filecoin Backend Implementation Plan

**Date:** December 19, 2025  
**Version:** 1.0  
**Status:** Planning Phase

---

## Executive Summary

Based on recent changes in the IPFS/Filecoin ecosystem (including Filecoin Pin service, web3.storage evolution, and Lassie retrieval), this plan outlines a comprehensive strategy to modernize and enhance the storage backend architecture of ipfs_kit_py to better leverage these distributed storage mechanisms.

### Key Changes in the Ecosystem

1. **Filecoin Pin** - New unified pinning service for IPFS content with Filecoin backing
2. **Storacha/web3.storage** - Evolution from w3up to Storacha with enhanced API
3. **Lassie** - High-performance content retrieval from IPFS/Filecoin networks
4. **IPNI (InterPlanetary Network Indexer)** - Improved content discovery
5. **Saturn CDN** - Decentralized CDN layer for IPFS content delivery

---

## Current State Analysis

### Existing Backend Implementations

| Backend | Status | Completeness | Issues |
|---------|--------|--------------|--------|
| IPFS (ipfs_backend.py) | ✅ Implemented | 80% | Mock fallback, missing advanced features |
| Filecoin (filecoin_backend.py) | ⚠️ Partial | 40% | Lotus-only, no Filecoin Pin integration |
| Storacha (storacha_backend.py) | ✅ Implemented | 75% | Legacy w3up API, needs update |
| Lassie (lassie_backend.py) | ✅ Implemented | 60% | Basic retrieval only |
| S3 (s3_backend.py) | ✅ Implemented | 90% | Mature |
| HuggingFace (huggingface_backend.py) | ✅ Implemented | 85% | Mature |

### Architecture Strengths

✅ Well-designed abstract base class (`BackendStorage`)  
✅ Unified storage manager with routing capabilities  
✅ Performance monitoring and telemetry  
✅ WebSocket notifications  
✅ MCP (Model Context Protocol) integration  
✅ Multi-backend migration tools  

### Architecture Gaps

❌ No Filecoin Pin service integration  
❌ Missing IPNI (content indexer) support  
❌ No Saturn CDN integration  
❌ Limited CAR (Content Addressable aRchive) file handling  
❌ No unified pinning API across backends  
❌ Missing cross-backend content verification  
❌ Limited support for dag-cbor and advanced IPLD formats  
❌ No gateway fallback chains  

---

## Implementation Plan

### Phase 1: Filecoin Pin Service Integration (Priority: HIGH)

**Timeline:** 2-3 weeks  
**Effort:** Medium-High

#### 1.1 Filecoin Pin Backend Implementation

**File:** `ipfs_kit_py/mcp/storage_manager/backends/filecoin_pin_backend.py`

```python
class FilecoinPinBackend(BackendStorage):
    """
    Backend for Filecoin Pin service - unified IPFS pinning with Filecoin backing.
    
    Features:
    - Pin content to IPFS with automatic Filecoin deals
    - Content retrieval via multiple gateways
    - Deal status monitoring
    - Integration with IPNI for content discovery
    """
```

**Key Features:**
- HTTP API integration with filecoin.cloud
- CID-based content pinning and retrieval
- Deal status tracking and monitoring
- Gateway fallback mechanism (IPFS → Saturn → Lassie)
- Automatic renewal of expiring pins
- Cost estimation and management

**Dependencies:**
```python
requests>=2.28.0
httpx>=0.24.0  # For async operations
multiformats>=0.3.0  # For CID handling
```

#### 1.2 Enhanced Filecoin Backend Modernization

**File:** `ipfs_kit_py/mcp/storage_manager/backends/filecoin_backend.py`

**Enhancements:**
- Add Filecoin Pin service as primary method
- Keep Lotus as fallback for direct chain interaction
- Add deal verification and monitoring
- Implement storage provider reputation tracking
- Add support for FVM (Filecoin Virtual Machine) smart contracts

#### 1.3 Unified Pinning Interface

**File:** `ipfs_kit_py/mcp/storage_manager/pinning/unified_pin_service.py`

```python
class UnifiedPinService:
    """
    Provides a consistent pinning API across all backends that support it.
    
    Supported backends:
    - IPFS (local daemon pinning)
    - Filecoin Pin (cloud pinning with Filecoin backing)
    - Storacha (w3up pinning)
    - Pinata (3rd party service)
    - Web3.storage (legacy)
    """
    
    async def pin(self, cid: str, name: str, metadata: dict, 
                  backends: list[str] = ["ipfs", "filecoin_pin"]) -> dict
    
    async def unpin(self, cid: str, backends: list[str] = None) -> dict
    
    async def list_pins(self, backend: str = None, 
                       status: str = "pinned") -> list[dict]
    
    async def pin_status(self, cid: str, backend: str = None) -> dict
```

**Integration Points:**
- MCP tool: `pin_content` (with backend selection)
- Dashboard: "Pins" panel with multi-backend view
- CLI: `ipfs-kit pin add/rm/ls`

---

### Phase 2: Enhanced Content Retrieval Layer (Priority: HIGH)

**Timeline:** 2 weeks  
**Effort:** Medium

#### 2.1 Gateway Fallback Chain

**File:** `ipfs_kit_py/mcp/storage_manager/retrieval/gateway_chain.py`

```python
class GatewayChain:
    """
    Implements intelligent gateway fallback for content retrieval.
    
    Priority order:
    1. Local IPFS node (if available)
    2. Lassie (direct retrieval from Filecoin/IPFS)
    3. Saturn CDN nodes (geographically closest)
    4. Public IPFS gateways (ipfs.io, dweb.link, etc.)
    5. Storacha gateways (for pinned content)
    """
    
    async def fetch(self, cid: str, timeout: int = 30) -> bytes
    async def fetch_with_metrics(self, cid: str) -> tuple[bytes, dict]
```

**Features:**
- Parallel gateway racing (fetch from multiple, use fastest)
- Gateway health monitoring and automatic failover
- Geographic routing for Saturn CDN
- Caching layer for frequently accessed content
- Performance metrics per gateway

#### 2.2 Lassie Backend Enhancement

**File:** `ipfs_kit_py/mcp/storage_manager/backends/lassie_backend.py`

**Enhancements:**
- Add IPNI integration for content discovery
- Support for trustless gateway protocol
- Parallel provider fetching
- CAR file streaming support
- Integration with Filecoin retrievals

#### 2.3 Saturn CDN Integration

**File:** `ipfs_kit_py/mcp/storage_manager/backends/saturn_backend.py`

```python
class SaturnBackend(BackendStorage):
    """
    Backend for Saturn CDN - decentralized content delivery network.
    
    Features:
    - Geographic node selection
    - Performance monitoring
    - Caching optimization
    - Fallback to IPFS gateways
    """
```

---

### Phase 3: Advanced IPLD and CAR File Support (Priority: MEDIUM)

**Timeline:** 2 weeks  
**Effort:** Medium

#### 3.1 CAR File Manager

**File:** `ipfs_kit_py/mcp/storage_manager/formats/car_manager.py`

```python
class CARManager:
    """
    Comprehensive CAR (Content Addressable aRchive) file management.
    
    Features:
    - Create CAR files from directories
    - Extract CAR files to filesystem
    - Stream CAR files to/from backends
    - Verify CAR file integrity
    - Convert between CAR v1 and v2 formats
    - Split/merge large CAR files
    """
    
    def create_car(self, path: str, output: str, 
                   codec: str = "dag-pb") -> dict
    
    def extract_car(self, car_file: str, output_dir: str) -> dict
    
    def stream_to_backend(self, car_file: str, 
                         backend: str = "filecoin_pin") -> dict
    
    def verify_car(self, car_file: str) -> dict
```

**Integration:**
- MCP tool: `car_create`, `car_extract`, `car_verify`
- Dashboard: "CARs" panel (already exists, enhance)
- Batch operations for large datasets

#### 3.2 IPLD Format Support

**File:** `ipfs_kit_py/mcp/storage_manager/formats/ipld_codec.py`

**Supported Formats:**
- `dag-pb` (Protocol Buffers) - IPFS default
- `dag-cbor` (CBOR) - Filecoin preferred
- `dag-json` (JSON)
- `raw` (raw bytes)

**Features:**
- Format detection from CID
- Automatic conversion between formats
- Schema validation for dag-cbor
- UnixFS v1/v2 support

---

### Phase 4: Content Discovery and Indexing (Priority: MEDIUM)

**Timeline:** 2 weeks  
**Effort:** Medium

#### 4.1 IPNI Integration

**File:** `ipfs_kit_py/mcp/storage_manager/discovery/ipni_client.py`

```python
class IPNIClient:
    """
    Integration with InterPlanetary Network Indexer for content discovery.
    
    Features:
    - Find providers for CIDs
    - Query multiple IPNI endpoints
    - Cache provider information
    - Filter providers by capabilities (IPFS, Filecoin, HTTP)
    """
    
    async def find_providers(self, cid: str, 
                           protocol: str = "bitswap") -> list[dict]
    
    async def get_provider_info(self, provider_id: str) -> dict
```

**IPNI Endpoints:**
- https://cid.contact (primary)
- https://index.pinning.services (backup)
- Custom IPNI nodes

#### 4.2 Content Verification System

**File:** `ipfs_kit_py/mcp/storage_manager/verification/content_verifier.py`

```python
class ContentVerifier:
    """
    Cross-backend content verification and integrity checking.
    
    Features:
    - Verify CID matches content hash
    - Check content availability across backends
    - Validate CAR file integrity
    - Monitor content replication status
    """
    
    async def verify_cid(self, cid: str, content: bytes) -> bool
    
    async def check_availability(self, cid: str, 
                                backends: list[str]) -> dict
    
    async def verify_replication(self, cid: str, 
                                min_copies: int = 3) -> dict
```

---

### Phase 5: Storacha Modernization (Priority: MEDIUM)

**Timeline:** 1 week  
**Effort:** Low-Medium

#### 5.1 Update Storacha Backend

**File:** `ipfs_kit_py/mcp/storage_manager/backends/storacha_backend.py`

**Updates:**
- Migrate from legacy w3up API to current Storacha API
- Add support for new authentication methods
- Implement new delegation capabilities
- Add space management features
- Support for proof chains

**API Changes:**
```python
# Old (w3up)
w3.upload(file)

# New (Storacha)
client.store.add(file)  # Store raw content
client.upload.add(car_file)  # Upload CAR
```

#### 5.2 Storacha Space Management

**File:** `ipfs_kit_py/mcp/storage_manager/backends/storacha_space.py`

```python
class StorachaSpaceManager:
    """
    Manage Storacha spaces (storage units).
    
    Features:
    - Create/delete spaces
    - Delegate access to spaces
    - Monitor space usage
    - List content in spaces
    """
```

---

### Phase 6: Smart Routing and Optimization (Priority: LOW)

**Timeline:** 2-3 weeks  
**Effort:** High

#### 6.1 Content-Aware Router Enhancement

**File:** `ipfs_kit_py/mcp/storage_manager/router/enhanced_router.py`

**Enhanced Routing Logic:**

```python
def select_backend(self, content_metadata: dict) -> str:
    """
    Intelligent backend selection based on:
    - Content size (small → IPFS, large → Filecoin)
    - Access frequency (hot → Saturn CDN, cold → Filecoin)
    - Cost constraints (budget-aware routing)
    - Geographic location (latency optimization)
    - Durability requirements (replication level)
    - Content type (video → streaming-optimized backends)
    """
```

**Routing Strategies:**

1. **Hot/Warm/Cold Storage Tiering**
   - Hot: IPFS + Saturn CDN (< 1GB, frequent access)
   - Warm: Filecoin Pin (1-100GB, moderate access)
   - Cold: Filecoin deals (> 100GB, archival)

2. **Cost Optimization**
   - Estimate storage costs across backends
   - Automatic migration to cheaper backends for cold data
   - Batch operations for cost efficiency

3. **Performance Optimization**
   - Geographic routing to nearest nodes
   - Parallel fetching from multiple sources
   - Predictive caching based on access patterns

4. **Durability Optimization**
   - Automatic replication across backends
   - Health monitoring and auto-healing
   - Verification of content integrity

#### 6.2 Intelligent Caching System

**File:** `ipfs_kit_py/mcp/storage_manager/cache/smart_cache.py`

```python
class SmartCache:
    """
    Multi-tier caching with intelligent eviction policies.
    
    Tiers:
    - L1: Memory (LRU, 100MB)
    - L2: Local disk (ARC, 10GB)
    - L3: IPFS node (persistent)
    - L4: Saturn CDN (external)
    """
```

---

### Phase 7: Developer Experience Improvements (Priority: LOW)

**Timeline:** 1 week  
**Effort:** Low

#### 7.1 Enhanced CLI Commands

```bash
# Filecoin Pin commands
ipfs-kit pin add <file> --backend filecoin_pin
ipfs-kit pin ls --backend all --status pinned
ipfs-kit pin status <cid>

# CAR file operations
ipfs-kit car create ./dataset --output dataset.car
ipfs-kit car extract dataset.car ./output
ipfs-kit car upload dataset.car --backend filecoin_pin

# Content verification
ipfs-kit verify cid <cid> --backends ipfs,filecoin_pin,storacha
ipfs-kit verify replication <cid> --min-copies 3

# Gateway testing
ipfs-kit gateway test <cid> --all
ipfs-kit gateway benchmark --cid <cid>

# Backend migration
ipfs-kit migrate content <cid> --from ipfs --to filecoin_pin
ipfs-kit migrate batch --list cids.txt --from ipfs --to filecoin_pin
```

#### 7.2 Enhanced MCP Dashboard

**Enhancements:**

1. **Unified Pins Panel**
   - View pins across all backends in one interface
   - Filter by backend, status, date
   - Bulk pin/unpin operations
   - Pin status monitoring with auto-refresh

2. **Content Discovery Panel**
   - Search for content by CID
   - View provider information
   - Test gateway availability
   - Content verification status

3. **Cost Analytics Panel**
   - Storage cost breakdown by backend
   - Cost projections
   - Optimization recommendations
   - Budget alerts

4. **Performance Metrics Panel**
   - Gateway response times
   - Backend availability statistics
   - Content retrieval success rates
   - Geographic distribution of requests

---

## Technical Dependencies

### New Python Packages

```toml
# Add to pyproject.toml

[project.optional-dependencies]
filecoin_pin = [
    "httpx>=0.24.0",  # Async HTTP client
    "multiformats>=0.3.0",  # CID and multicodec support
]

car_files = [
    "ipld-car>=0.1.0",  # CAR file parsing
    "dag-cbor>=0.3.0",  # CBOR codec for Filecoin
    "cbor2>=5.4.0",  # CBOR encoding/decoding
]

saturn = [
    "httpx>=0.24.0",
    "geoip2>=4.7.0",  # Geographic IP lookup
]

ipni = [
    "httpx>=0.24.0",
    "multiformats>=0.3.0",
]

enhanced_ipfs = [
    "multiformats>=0.3.0",
    "dag-cbor>=0.3.0",
    "ipld-car>=0.1.0",
    "py-cid>=0.3.0",  # CID manipulation
]
```

### External Services

| Service | Purpose | API Documentation |
|---------|---------|-------------------|
| Filecoin Pin | Unified pinning | https://docs.filecoin.io/builder-cookbook/filecoin-pin |
| IPNI | Content discovery | https://docs.cid.contact |
| Saturn CDN | Content delivery | https://saturn.tech/docs |
| Storacha | Cloud storage | https://docs.storacha.network |

---

## Migration Guide

### For Existing Users

#### 1. Update Configuration

```yaml
# ~/.ipfs_kit/backends/filecoin_pin.yaml
type: filecoin_pin
enabled: true
api_endpoint: https://api.filecoin.cloud/v1
api_key: ${FILECOIN_PIN_API_KEY}
default_replication: 3
auto_renew: true
gateway_fallback:
  - https://ipfs.io/ipfs/
  - https://w3s.link/ipfs/
  - https://dweb.link/ipfs/
```

#### 2. Enable New Backends

```bash
# Install additional dependencies
pip install ipfs_kit_py[filecoin_pin,car_files,saturn]

# Configure Filecoin Pin
export FILECOIN_PIN_API_KEY="your_api_key_here"

# Test the new backend
ipfs-kit backend test filecoin_pin
```

#### 3. Migrate Existing Pins

```bash
# List current pins
ipfs-kit pin ls --backend ipfs

# Migrate to Filecoin Pin
ipfs-kit migrate batch \
  --from ipfs \
  --to filecoin_pin \
  --filter "size > 100MB" \
  --dry-run

# Execute migration
ipfs-kit migrate batch \
  --from ipfs \
  --to filecoin_pin \
  --filter "size > 100MB"
```

---

## Testing Strategy

### Unit Tests

```python
# tests/integration/test_filecoin_pin_backend.py
def test_filecoin_pin_add()
def test_filecoin_pin_retrieve()
def test_filecoin_pin_status()
def test_gateway_fallback()

# tests/integration/test_car_manager.py
def test_car_create()
def test_car_extract()
def test_car_verify()
def test_car_stream()

# tests/integration/test_ipni_discovery.py
def test_find_providers()
def test_provider_selection()

# tests/integration/test_unified_pinning.py
def test_multi_backend_pin()
def test_pin_status_aggregation()
```

### Integration Tests

```python
# tests/e2e/test_content_workflow.py
async def test_full_content_lifecycle():
    """
    End-to-end test:
    1. Upload content via Filecoin Pin
    2. Verify content via IPNI
    3. Retrieve via gateway chain
    4. Verify integrity
    5. Replicate to additional backends
    6. Monitor replication status
    """
```

### Performance Benchmarks

```python
# tests/benchmarks/test_gateway_performance.py
def benchmark_gateway_retrieval():
    """Compare retrieval times across gateways"""

def benchmark_backend_throughput():
    """Measure upload/download throughput per backend"""
```

---

## Monitoring and Observability

### Metrics to Track

```python
# Prometheus metrics
filecoin_pin_requests_total
filecoin_pin_request_duration_seconds
filecoin_pin_errors_total
gateway_response_time_seconds
content_verification_success_rate
backend_availability_status
storage_cost_per_backend
```

### Logging Enhancements

```python
# Structured logging with context
logger.info("Content pinned", extra={
    "cid": cid,
    "backend": "filecoin_pin",
    "size_bytes": size,
    "duration_ms": duration,
    "cost_estimate": cost
})
```

### Health Checks

```python
# Health check endpoints
GET /api/health/backend/filecoin_pin
GET /api/health/gateways
GET /api/health/ipni
```

---

## Security Considerations

### API Key Management

- Store API keys in encrypted configuration
- Support for environment variables
- Integration with secret managers (HashiCorp Vault, AWS Secrets Manager)
- Key rotation support

### Content Validation

- Always verify CID matches content hash
- Validate CAR file integrity before upload
- Check provider reputation before retrieval
- Implement rate limiting for API calls

### Access Control

- Role-based access for pin operations
- Audit logging for all backend operations
- Support for delegated access (Storacha)

---

## Cost Optimization

### Storage Cost Estimates

| Backend | Cost per GB/Month | Best Use Case |
|---------|------------------|---------------|
| IPFS (local) | $0 (self-hosted) | Development, hot data |
| Filecoin Pin | $0.001 - $0.01 | Production, warm data |
| Storacha | $0.05 | Quick uploads, short-term |
| Filecoin Direct | $0.0001 | Long-term archival |
| Saturn CDN | $0 (retrieval) | Content delivery |

### Cost Optimization Strategies

1. **Automatic Tiering**
   - Move cold data to cheaper backends after 30 days
   - Keep hot data in fast, expensive backends

2. **Batch Operations**
   - Bundle small files into CAR files
   - Reduce API call costs

3. **Compression**
   - Compress before upload
   - Automatic decompression on retrieval

4. **Deduplication**
   - Check if content already exists before upload
   - Share CIDs across users/applications

---

## Success Metrics

### Technical KPIs

- ✅ **Backend Coverage:** Support for 6+ storage backends
- ✅ **Retrieval Success Rate:** > 99.9% across gateway chain
- ✅ **Average Retrieval Time:** < 2 seconds for cached content
- ✅ **Cost Reduction:** 50% decrease in storage costs via intelligent routing
- ✅ **Test Coverage:** > 90% for new backend code

### User Experience KPIs

- ✅ **Setup Time:** < 5 minutes from install to first pin
- ✅ **API Simplicity:** Single command for cross-backend operations
- ✅ **Documentation Quality:** Complete examples for all features
- ✅ **Dashboard Usability:** All backend operations accessible via UI

---

## Timeline Summary

| Phase | Duration | Priority | Dependencies |
|-------|----------|----------|--------------|
| **Phase 1:** Filecoin Pin Integration | 2-3 weeks | HIGH | None |
| **Phase 2:** Enhanced Content Retrieval | 2 weeks | HIGH | Phase 1 |
| **Phase 3:** CAR and IPLD Support | 2 weeks | MEDIUM | Phase 1 |
| **Phase 4:** Content Discovery (IPNI) | 2 weeks | MEDIUM | Phase 1, 2 |
| **Phase 5:** Storacha Modernization | 1 week | MEDIUM | None |
| **Phase 6:** Smart Routing | 2-3 weeks | LOW | Phase 1, 2, 3 |
| **Phase 7:** Developer Experience | 1 week | LOW | All phases |

**Total Estimated Time:** 12-15 weeks (3-4 months)

---

## Risk Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Filecoin Pin API changes | Medium | High | Version pinning, abstraction layer |
| Gateway downtime | High | Medium | Multi-gateway fallback |
| IPNI service issues | Medium | Medium | Cache provider info, fallback to DHT |
| CAR file compatibility | Low | Medium | Thorough testing, format validation |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Increased complexity | High | Medium | Comprehensive docs, abstraction layers |
| Breaking changes | Low | High | Semantic versioning, deprecation notices |
| Cost overruns | Medium | Medium | Cost monitoring, usage alerts |

---

## Community and Support

### Documentation Deliverables

1. **User Guide:** Getting started with new backends
2. **API Reference:** Complete API documentation for all new classes
3. **Migration Guide:** Step-by-step migration from old to new APIs
4. **Examples Repository:** 20+ code examples for common use cases
5. **Video Tutorials:** Screen recordings of key workflows

### Community Engagement

- **Blog Posts:** Announce each phase completion
- **Discord/Slack:** Dedicated channel for backend discussions
- **GitHub Discussions:** Open forum for questions and feedback
- **Monthly Office Hours:** Live Q&A sessions

---

## Appendix A: API Design Examples

### Filecoin Pin Backend API

```python
from ipfs_kit_py.mcp.storage_manager.backends import FilecoinPinBackend

# Initialize backend
backend = FilecoinPinBackend(
    resources={"api_key": "your_key"},
    metadata={"replication": 3}
)

# Pin content
result = await backend.add_content(
    content=file_bytes,
    metadata={
        "name": "my-dataset",
        "tags": ["ml", "training-data"]
    }
)
# Returns: {"cid": "bafybeib...", "status": "pinned", "deal_ids": [...]}

# Check pin status
status = await backend.get_metadata("bafybeib...")
# Returns: {"status": "pinned", "deals": [...], "size": 1024000}

# Retrieve content
content = await backend.get_content("bafybeib...")
# Returns: {"success": True, "data": bytes, "source": "gateway"}
```

### Unified Pinning Service API

```python
from ipfs_kit_py.mcp.storage_manager.pinning import UnifiedPinService

pin_service = UnifiedPinService()

# Pin to multiple backends
result = await pin_service.pin(
    cid="bafybeib...",
    name="my-content",
    metadata={"description": "Important dataset"},
    backends=["ipfs", "filecoin_pin", "storacha"]
)
# Returns: {
#   "ipfs": {"status": "pinned", "cid": "..."},
#   "filecoin_pin": {"status": "queued", "request_id": "..."},
#   "storacha": {"status": "pinned", "space_did": "..."}
# }

# Check status across backends
status = await pin_service.pin_status("bafybeib...")
# Returns: {
#   "cid": "bafybeib...",
#   "backends": {
#     "ipfs": {"status": "pinned", "timestamp": "..."},
#     "filecoin_pin": {"status": "active", "deals": [...]},
#     "storacha": {"status": "pinned", "proof": "..."}
#   }
# }

# List all pins
pins = await pin_service.list_pins(backend="all", status="pinned")
# Returns: [{"cid": "...", "backends": [...], "metadata": {...}}, ...]
```

### Gateway Chain API

```python
from ipfs_kit_py.mcp.storage_manager.retrieval import GatewayChain

gateway = GatewayChain(
    gateways=[
        {"url": "https://ipfs.io/ipfs/", "priority": 1},
        {"url": "https://w3s.link/ipfs/", "priority": 2},
        {"url": "https://dweb.link/ipfs/", "priority": 3}
    ],
    enable_lassie=True,
    enable_saturn=True
)

# Fetch with automatic fallback
content, metrics = await gateway.fetch_with_metrics("bafybeib...")
# Returns: (bytes, {
#   "source": "saturn",
#   "duration_ms": 234,
#   "size_bytes": 1024000,
#   "gateway_used": "https://saturn-node-42.example.com"
# })

# Test all gateways
health = await gateway.test_all()
# Returns: {
#   "https://ipfs.io/ipfs/": {"available": True, "latency_ms": 150},
#   "saturn": {"available": True, "latency_ms": 45},
#   "lassie": {"available": True, "latency_ms": 89}
# }
```

---

## Appendix B: Configuration Examples

### Complete Backend Configuration

```yaml
# ~/.ipfs_kit/config.yaml

backends:
  # IPFS local node
  ipfs:
    type: ipfs
    enabled: true
    api_url: http://localhost:5001
    gateway_url: http://localhost:8080
    
  # Filecoin Pin service
  filecoin_pin:
    type: filecoin_pin
    enabled: true
    api_endpoint: https://api.filecoin.cloud/v1
    api_key: ${FILECOIN_PIN_API_KEY}
    default_replication: 3
    auto_renew: true
    max_deal_duration_days: 540  # ~18 months
    
  # Storacha (web3.storage)
  storacha:
    type: storacha
    enabled: true
    api_endpoint: https://up.web3.storage
    space_did: ${STORACHA_SPACE_DID}
    delegation_proof: ${STORACHA_DELEGATION}
    
  # Lassie retrieval
  lassie:
    type: lassie
    enabled: true
    parallel_providers: 5
    timeout_seconds: 60
    enable_ipni: true
    
  # Saturn CDN
  saturn:
    type: saturn
    enabled: true
    orchestrator_url: https://orchestrator.saturn.ms
    enable_geographic_routing: true
    
  # S3 (for comparison)
  s3:
    type: s3
    enabled: true
    bucket: my-ipfs-backup
    region: us-west-2
    
# Routing rules
routing:
  strategy: smart  # Options: smart, cost, performance, durability
  
  rules:
    # Small files → IPFS + Filecoin Pin
    - condition: "size < 100MB"
      backends: ["ipfs", "filecoin_pin"]
      
    # Large files → Filecoin Pin only
    - condition: "size >= 100MB"
      backends: ["filecoin_pin"]
      
    # Frequently accessed → Add Saturn
    - condition: "access_count > 100"
      backends: ["ipfs", "saturn", "filecoin_pin"]
      
    # Archival → Filecoin only
    - condition: "tags.contains('archive')"
      backends: ["filecoin_pin"]
      replication: 5

# Gateway configuration
gateways:
  chain:
    - url: http://localhost:8080  # Local IPFS
      priority: 1
      timeout: 5
    - service: lassie  # Lassie retrieval
      priority: 2
      timeout: 30
    - service: saturn  # Saturn CDN
      priority: 3
      timeout: 10
    - url: https://ipfs.io/ipfs/
      priority: 4
      timeout: 30
    - url: https://w3s.link/ipfs/
      priority: 5
      timeout: 30
      
  parallel_fetch: true  # Race multiple gateways
  cache_duration_seconds: 3600

# Cost management
cost:
  budget_per_month_usd: 100
  alert_threshold_percent: 80
  auto_optimize: true  # Automatically migrate to cheaper backends
  
# Monitoring
monitoring:
  enabled: true
  metrics_endpoint: http://localhost:9090/metrics
  log_level: info
  
# Security
security:
  encrypt_api_keys: true
  key_storage: environment  # Options: environment, vault, keyring
  enable_audit_log: true
```

---

## Appendix C: Example Workflows

### Workflow 1: Pin Large Dataset with Filecoin Backing

```python
import asyncio
from ipfs_kit_py.mcp.storage_manager import UnifiedStorageManager
from ipfs_kit_py.mcp.storage_manager.formats import CARManager

async def pin_large_dataset():
    # Initialize managers
    storage = UnifiedStorageManager()
    car_manager = CARManager()
    
    # Create CAR file from directory
    print("Creating CAR file...")
    car_result = car_manager.create_car(
        path="./my-dataset",
        output="my-dataset.car",
        codec="dag-cbor"  # Filecoin preferred format
    )
    print(f"Created CAR: {car_result['cid']}, size: {car_result['size']} bytes")
    
    # Upload to Filecoin Pin
    print("Pinning to Filecoin...")
    pin_result = await storage.add_content(
        content=open("my-dataset.car", "rb"),
        backend="filecoin_pin",
        metadata={
            "name": "my-dataset",
            "description": "ML training dataset",
            "tags": ["ml", "training"],
            "replication": 5
        }
    )
    print(f"Pinned! CID: {pin_result['cid']}")
    print(f"Deal IDs: {pin_result['deal_ids']}")
    
    # Monitor pin status
    while True:
        status = await storage.get_metadata(
            identifier=pin_result['cid'],
            backend="filecoin_pin"
        )
        print(f"Status: {status['status']}, Active deals: {len(status['deals'])}")
        
        if status['status'] == 'active':
            print("Dataset is now active on Filecoin!")
            break
        
        await asyncio.sleep(60)  # Check every minute

asyncio.run(pin_large_dataset())
```

### Workflow 2: Intelligent Content Retrieval

```python
from ipfs_kit_py.mcp.storage_manager.retrieval import GatewayChain
from ipfs_kit_py.mcp.storage_manager.discovery import IPNIClient

async def retrieve_with_best_performance():
    # Initialize clients
    gateway = GatewayChain()
    ipni = IPNIClient()
    
    cid = "bafybeib..."
    
    # Find providers via IPNI
    print("Discovering providers...")
    providers = await ipni.find_providers(cid, protocol="bitswap")
    print(f"Found {len(providers)} providers")
    
    # Test gateway health
    print("Testing gateways...")
    gateway_health = await gateway.test_all()
    available = [g for g, h in gateway_health.items() if h['available']]
    print(f"Available gateways: {len(available)}")
    
    # Fetch content with automatic fallback
    print("Fetching content...")
    content, metrics = await gateway.fetch_with_metrics(cid)
    
    print(f"Retrieved {len(content)} bytes in {metrics['duration_ms']}ms")
    print(f"Source: {metrics['source']}")
    print(f"Gateway: {metrics['gateway_used']}")
    
    return content

content = asyncio.run(retrieve_with_best_performance())
```

### Workflow 3: Cost-Optimized Storage Migration

```python
from ipfs_kit_py.mcp.storage_manager import UnifiedStorageManager
from ipfs_kit_py.mcp.storage_manager.pinning import UnifiedPinService

async def optimize_storage_costs():
    storage = UnifiedStorageManager()
    pin_service = UnifiedPinService()
    
    # List all pins across backends
    all_pins = await pin_service.list_pins(backend="all")
    
    # Analyze costs
    total_cost = 0
    migrations = []
    
    for pin in all_pins:
        # Calculate current cost
        current_cost = calculate_cost(pin)
        
        # Determine optimal backend
        optimal_backend = determine_optimal_backend(pin)
        
        if optimal_backend != pin['current_backend']:
            estimated_savings = current_cost - calculate_cost_for_backend(
                pin, optimal_backend
            )
            
            if estimated_savings > 0.01:  # Minimum $0.01 savings
                migrations.append({
                    'cid': pin['cid'],
                    'from': pin['current_backend'],
                    'to': optimal_backend,
                    'savings': estimated_savings
                })
    
    # Sort by savings
    migrations.sort(key=lambda x: x['savings'], reverse=True)
    
    print(f"Found {len(migrations)} optimization opportunities")
    print(f"Potential monthly savings: ${sum(m['savings'] for m in migrations):.2f}")
    
    # Execute migrations
    for migration in migrations[:10]:  # Top 10 savings
        print(f"Migrating {migration['cid']} from {migration['from']} to {migration['to']}")
        
        # Pin to new backend
        await pin_service.pin(
            cid=migration['cid'],
            backends=[migration['to']],
            metadata={"migration": True}
        )
        
        # Unpin from old backend (after verification)
        await asyncio.sleep(60)  # Wait for pin to stabilize
        await pin_service.unpin(
            cid=migration['cid'],
            backends=[migration['from']]
        )
        
        print(f"  ✓ Saved ${migration['savings']:.4f}/month")

asyncio.run(optimize_storage_costs())
```

---

## Next Steps

1. **Review and Approve Plan** - Stakeholder review and approval (1 week)
2. **Phase 1 Kickoff** - Begin Filecoin Pin integration (Week 2)
3. **Continuous Integration** - Set up CI/CD for new backends (Week 2)
4. **Documentation Sprint** - Start writing user guides (Week 3)
5. **Community Preview** - Alpha release for testing (Week 8)
6. **Beta Release** - Public beta with documentation (Week 12)
7. **GA Release** - General availability (Week 16)

---

**Document Version:** 1.0  
**Last Updated:** December 19, 2025  
**Author:** GitHub Copilot CLI  
**Status:** Ready for Review  

---

## Feedback and Contributions

This is a living document. Please provide feedback via:
- GitHub Issues: https://github.com/endomorphosis/ipfs_kit_py/issues
- GitHub Discussions: https://github.com/endomorphosis/ipfs_kit_py/discussions
- Pull Requests: Improvements and corrections welcome!

For questions or clarifications, please reach out to the maintainers.
