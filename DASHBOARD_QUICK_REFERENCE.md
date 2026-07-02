# Dashboard Quick Reference Guide

**Last Updated:** 2026-02-02

---

## Quick Decision Matrix

| Your Need | Recommended Dashboard | Why |
|-----------|----------------------|-----|
| **Production with team** | Refactored Unified MCP | Most maintainable, organized code |
| **Maximum features + real-time** | Consolidated MCP | 60+ endpoints, WebSocket/SSE |
| **Quick testing/prototype** | Simple MCP | 9 endpoints, ~350 lines |
| **File storage focus** | Bucket Dashboard | CAR import, specialized operations |
| **Development/testing** | Modernized Comprehensive | Flexible backend loader |

---

## Active Dashboards at a Glance

### 1. Refactored Unified MCP Dashboard ⭐ (Primary)
```
Location: /ipfs_kit_py/mcp/dashboard/refactored_unified_mcp_dashboard.py
Size:     2,749 lines
Port:     8004
```

**Quick Stats:**
- ✅ 36 endpoints
- ✅ Separated templates/static
- ✅ Full MCP integration
- ✅ Service manager
- ❌ No WebSocket
- ❌ No SSE

**Best For:** Production deployments, team projects, maintainability

**Launch:**
```bash
python /ipfs_kit_py/mcp/dashboard/refactored_unified_mcp_dashboard.py
```

---

### 2. Consolidated MCP Dashboard 🚀 (Feature-Complete)
```
Location: /ipfs_kit_py/mcp/dashboard/consolidated_mcp_dashboard.py
Size:     10,663 lines (largest)
Port:     8080
```

**Quick Stats:**
- ✅ 60+ endpoints (most)
- ✅ WebSocket support
- ✅ SSE log streaming
- ✅ Real-time monitoring
- ✅ Self-contained
- ⚠️ Single large file

**Best For:** Production monitoring, real-time updates, comprehensive features

**Launch:**
```bash
python /ipfs_kit_py/mcp/dashboard/consolidated_mcp_dashboard.py
```

---

### 3. Simple MCP Dashboard 💡 (Minimal)
```
Location: /ipfs_kit_py/dashboard/simple_mcp_dashboard.py
Size:     ~350 lines (smallest)
Port:     8080
```

**Quick Stats:**
- ✅ 9 endpoints (minimal)
- ✅ 3-tab UI
- ✅ Basic MCP
- ✅ Peer manager
- ✅ Quick setup
- ❌ No advanced features

**Best For:** Quick testing, learning, prototyping, minimal resources

**Launch:**
```bash
python /ipfs_kit_py/dashboard/simple_mcp_dashboard.py
```

---

### 4. Bucket Dashboard 📦 (Specialized)
```
Location: /ipfs_kit_py/bucket_dashboard.py
Size:     ~550 lines
Port:     8080
```

**Quick Stats:**
- ✅ 13 endpoints
- ✅ CAR import
- ✅ File operations
- ✅ Bucket management
- ✅ IPFS integration
- ❌ No monitoring

**Best For:** File storage, CAR operations, bucket workflows

**Launch:**
```bash
python /ipfs_kit_py/bucket_dashboard.py
```

---

### 5. Modernized Comprehensive Dashboard 🔧 (Loader)
```
Location: /ipfs_kit_py/dashboard/modernized_comprehensive_dashboard.py
Size:     ~150 lines (wrapper)
Port:     Varies
```

**Quick Stats:**
- ✅ Flexible backend
- ✅ Development-friendly
- ✅ Graceful fallback
- ⚠️ Indirect loading
- ⚠️ Debug complexity

**Best For:** Development, testing, experimental features

**Launch:**
```bash
python /ipfs_kit_py/dashboard/modernized_comprehensive_dashboard.py
```

---

## Feature Comparison (Quick View)

| Feature | Unified | Consolidated | Simple | Bucket | Comprehensive |
|---------|:-------:|:------------:|:------:|:------:|:-------------:|
| **Endpoints** | 36 | 60+ ⭐ | 9 | 13 | Varies |
| **Size (lines)** | 2.7K | 10.6K | 0.35K ⭐ | 0.55K | 0.15K |
| **WebSocket** | ❌ | ✅ | ❌ | ❌ | ✅ |
| **SSE** | ❌ | ✅ | ❌ | ❌ | ✅ |
| **MCP Protocol** | Full | Full | Basic | Partial | Full |
| **Real-time** | ❌ | ✅ ⭐ | ❌ | ❌ | ✅ |
| **Organized Code** | ✅ ⭐ | ❌ | ✅ | ✅ | N/A |
| **CAR Import** | ❌ | ❌ | ❌ | ✅ ⭐ | ❌ |
| **Single File** | ❌ | ✅ | ✅ | ✅ | ❌ |
| **Maintainability** | High ⭐ | Medium | High | High | N/A |

⭐ = Stands out in this category

---

## Common Endpoints (All Dashboards)

```
GET  /                              # Main dashboard UI
GET  /api/buckets                   # List buckets
POST /api/buckets/{name}/upload     # Upload to bucket
```

---

## Unique Features by Dashboard

### Refactored Unified MCP Only
- Separated templates/ and static/ directories
- ComprehensiveServiceManager integration
- Cache-based state (backends_cache, pins_cache)
- Service analytics endpoint

### Consolidated MCP Only
- WebSocket endpoint: `GET /ws`
- SSE log streaming: `GET /api/logs/stream`
- Real-time monitoring capabilities
- 60+ comprehensive endpoints
- Health check endpoint

### Simple MCP Only
- 3-tab simplified UI
- Peer manager (libp2p) integration
- Minimal resource footprint
- Caselaw endpoint: `GET /mcp/caselaw`

### Bucket Dashboard Only
- CAR import from file: `POST /api/buckets/import-car`
- CAR import from CID: `POST /api/buckets/import-car-from-cid`
- Specialized file path management
- Mimetype detection

---

## Migration Guide

### From Simple → Unified
**When:** Need more features but want maintainability

**Changes:**
- More endpoints (9 → 36)
- Service manager integration
- Separated asset structure
- ~5 minutes migration time

### From Simple → Consolidated
**When:** Need comprehensive features + real-time

**Changes:**
- Many more endpoints (9 → 60+)
- WebSocket support required
- SSE streaming
- ~15 minutes migration time

### From Unified → Consolidated
**When:** Need real-time monitoring

**Changes:**
- Add WebSocket handling
- Implement SSE streaming
- More endpoints
- ~10 minutes migration time

---

## File Locations Quick Reference

### Active Production Files
```
/ipfs_kit_py/mcp/dashboard/refactored_unified_mcp_dashboard.py
/ipfs_kit_py/mcp/dashboard/consolidated_mcp_dashboard.py
/ipfs_kit_py/dashboard/simple_mcp_dashboard.py
/ipfs_kit_py/bucket_dashboard.py
/ipfs_kit_py/dashboard/modernized_comprehensive_dashboard.py
```

### Deprecated (Reference Only)
```
/deprecated_dashboards/          # 40+ legacy versions
/archive/legacy_code/legacy_dashboards/
```

### Development/Testing
```
/scripts/development/            # Experimental versions
/examples/                       # Example implementations
```

### Tests
```
/tests/test_*dashboard*.py       # ~22 test files
```

---

## Port Usage

| Dashboard | Default Port | Configurable |
|-----------|--------------|--------------|
| Refactored Unified MCP | 8004 | ✅ Yes |
| Consolidated MCP | 8080 | ✅ Yes |
| Simple MCP | 8080 | ✅ Yes |
| Bucket Dashboard | 8080 | ✅ Yes |
| Modernized Comprehensive | Varies | ✅ Yes |

**Note:** Check for port conflicts when running multiple dashboards

---

## Authentication Status

| Dashboard | Auth Support | Notes |
|-----------|--------------|-------|
| All Active Dashboards | ❌ Disabled | Config fields present but not enforced |

**Security Note:** Do not expose dashboards directly to public internet without additional security measures

---

## Resource Requirements

| Dashboard | Memory | CPU | Disk I/O | Network |
|-----------|--------|-----|----------|---------|
| Refactored Unified | Medium | Low | Medium | Low |
| Consolidated | High | Medium | High | Medium |
| Simple | Low ⭐ | Low ⭐ | Low ⭐ | Low ⭐ |
| Bucket | Low | Low | High | Medium |
| Comprehensive | Varies | Varies | Varies | Varies |

⭐ = Most efficient in category

---

## Development Commands

### Running Tests
```bash
# Test specific dashboard
pytest tests/test_simple_dashboard.py
pytest tests/test_consolidated_dashboard_fixes.py
pytest tests/test_modernized_dashboard.py

# Test all dashboards
pytest tests/test_*dashboard*.py

# Test with coverage
pytest --cov=ipfs_kit_py.dashboard tests/
```

### Linting
```bash
# Check dashboard code
flake8 ipfs_kit_py/dashboard/
flake8 ipfs_kit_py/mcp/dashboard/

# Format code
black ipfs_kit_py/dashboard/
black ipfs_kit_py/mcp/dashboard/
```

### Running Development Versions
```bash
# Run from scripts/development
python scripts/development/consolidated_mcp_dashboard.py
python scripts/development/modernized_comprehensive_dashboard_complete.py
```

---

## Troubleshooting

### Dashboard Won't Start
1. Check port availability: `lsof -i :8080` or `lsof -i :8004`
2. Verify dependencies: `pip install -r requirements.txt`
3. Check logs in terminal output

### Static Assets Not Loading (Unified)
1. Verify templates/ directory exists
2. Check static/ directory exists
3. Ensure correct path resolution in app

### WebSocket Connection Failed (Consolidated)
1. Check browser console for errors
2. Verify WebSocket endpoint: `/ws`
3. Check firewall/proxy settings

### CAR Import Failed (Bucket)
1. Verify CAR file format
2. Check CID validity
3. Ensure IPFS daemon running

---

## Configuration Files

### Default Config Locations
```
~/.ipfs_kit/                     # Main config directory
~/.ipfs_kit/config.yaml          # Main configuration
~/.ipfs_kit/buckets/             # Bucket storage
~/.ipfs_kit/pins/                # Pin storage
```

### Environment Variables
```bash
# Port configuration
export DASHBOARD_PORT=8080
export MCP_DASHBOARD_PORT=8004

# IPFS configuration
export IPFS_PATH=/path/to/ipfs

# Debug mode
export DEBUG=true
```

---

## API Documentation

### MCP Protocol Endpoints (All Dashboards)
```
POST /mcp/tools/call             # Execute MCP tool
GET  /mcp/tools/list             # List available tools
POST /mcp/initialize             # Initialize MCP server (Unified)
POST /mcp/                       # MCP JSON-RPC (Consolidated)
```

### Common REST Endpoints
```
GET  /api/buckets                # List buckets
POST /api/buckets                # Create bucket
GET  /api/buckets/{name}         # Bucket details
POST /api/buckets/{name}/upload  # Upload file
GET  /api/system/overview        # System info (Unified, Consolidated)
GET  /api/logs                   # Get logs (Unified, Consolidated)
```

### Real-time Endpoints (Consolidated Only)
```
GET  /ws                         # WebSocket connection
GET  /api/logs/stream            # SSE log streaming
```

---

## Additional Resources

- **Full Analysis:** See `DASHBOARD_ANALYSIS_REPORT.md` for complete details
- **Architecture Docs:** See `MCP_INTEGRATION_ARCHITECTURE.md`
- **General Docs:** See `README.md`

---

## Quick Command Reference

```bash
# Clone repository
git clone https://github.com/endomorphosis/ipfs_kit_py.git
cd ipfs_kit_py

# Install dependencies
pip install -r requirements.txt

# Run primary dashboard
python ipfs_kit_py/mcp/dashboard/refactored_unified_mcp_dashboard.py

# Run simple dashboard
python ipfs_kit_py/dashboard/simple_mcp_dashboard.py

# Run consolidated dashboard
python ipfs_kit_py/mcp/dashboard/consolidated_mcp_dashboard.py

# Run tests
pytest tests/test_*dashboard*.py

# View dashboard in browser
open http://localhost:8080
open http://localhost:8004  # For Unified MCP
```

---

**End of Quick Reference**
