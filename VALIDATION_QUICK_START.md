# Quick Reference: MCP Dashboard and CI/CD Validation

## Quick Start

### Start MCP Dashboard
```bash
# Start in background
ipfs-kit mcp start --port 8004

# Start in foreground
ipfs-kit mcp start --port 8004 --foreground

# Check status
ipfs-kit mcp status --port 8004

# Stop
ipfs-kit mcp stop --port 8004
```

### Access Dashboard
```
http://127.0.0.1:8004/
```

## Validation Scripts

### 1. Validate MCP Dashboard
```bash
python scripts/validation/mcp_dashboard_validation.py
```

**Tests:**
- Server health check
- UI accessibility
- MCP tools endpoint
- Buckets API
- Services API

**Output:** `test_results/mcp_dashboard_validation.json`

### 2. Validate CI/CD Workflows
```bash
python scripts/validation/cicd_workflow_validation.py
```

**Tests:**
- YAML syntax validation
- Architecture support detection
- Python version coverage
- Multi-arch workflow identification

**Output:** `test_results/cicd_workflow_validation.json`

## Architecture Testing

### x86_64 (AMD64)
```bash
# Works on standard GitHub Actions runners
# Validation script runs automatically
python scripts/validation/mcp_dashboard_validation.py
```

### ARM64 (aarch64)
```bash
# Requires ARM64 hardware or self-hosted runner
# On ARM64 system:
git clone https://github.com/endomorphosis/ipfs_kit_py
cd ipfs_kit_py
python -m pip install -e ".[api,dev]"
ipfs-kit mcp start --port 8004
python scripts/validation/mcp_dashboard_validation.py
```

## CI/CD Workflows

### Key Workflows

**AMD64:**
- `amd64-ci.yml` - Main AMD64 CI pipeline
- `amd64-release.yml` - AMD64 releases
- `amd64-python-package.yml` - Package publishing

**ARM64:**
- `arm64-ci.yml` - Main ARM64 CI pipeline

**Multi-Architecture:**
- `multi-arch-ci.yml` - Combined AMD64 + ARM64
- `multi-arch-build.yml` - Multi-arch Docker builds

### Trigger Workflows
```bash
# Via GitHub CLI (requires authentication)
gh workflow run amd64-ci.yml
gh workflow run arm64-ci.yml

# Via git push (automatic)
git push origin main
```

## Validation Results

### Current Status (October 22, 2025)

**MCP Dashboard:**
- ✅ Status: Fully functional
- ✅ Tools: 94 available
- ✅ UI: All components working
- ✅ APIs: All endpoints operational

**CI/CD:**
- ✅ Total Workflows: 36
- ✅ Valid: 36 (100%)
- ✅ AMD64 Coverage: 35 workflows
- ✅ ARM64 Coverage: 2 workflows

## Common Issues

### Issue: Dashboard Won't Start
```bash
# Check if port is in use
lsof -i :8004

# Try different port
ipfs-kit mcp start --port 8005

# Check logs
tail -f ~/.ipfs_kit/mcp_8004.log
```

### Issue: API Not Responding
```bash
# Check server status
ipfs-kit mcp status --port 8004

# Restart server
ipfs-kit mcp stop --port 8004
ipfs-kit mcp start --port 8004
```

### Issue: Validation Script Fails
```bash
# Ensure dependencies installed
pip install httpx

# Ensure dashboard is running
ipfs-kit mcp status --port 8004
```

## Screenshot Capture

### Using Playwright
```bash
# Install playwright
pip install playwright
playwright install chromium

# Start dashboard
ipfs-kit mcp start --port 8004

# Run playwright tests (examples in playwright_tests/)
pytest playwright_tests/
```

## Documentation

- **Full Report:** `MCP_DASHBOARD_VALIDATION_REPORT.md`
- **CI/CD Guide:** `CI_CD_VALIDATION_GUIDE.md`
- **ARM64 Testing:** `ARM64_TESTING.md`
- **Workflow Status:** `CI_CD_VERIFICATION_REPORT.md`

## Contact

For issues or questions:
- Repository: https://github.com/endomorphosis/ipfs_kit_py
- Issues: https://github.com/endomorphosis/ipfs_kit_py/issues
