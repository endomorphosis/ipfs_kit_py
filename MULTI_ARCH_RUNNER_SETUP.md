# Multi-Architecture Testing Setup Guide

**Date:** October 22, 2025  
**Status:** ✅ **Updated - ARM64 Testing Now Optional**

---

## Overview

This document explains the multi-architecture testing setup and how to enable ARM64 testing with self-hosted runners.

---

## Current Configuration

### Default Behavior (No ARM64 Runners Required)

All workflows now run **AMD64 tests only by default**. This ensures CI/CD works without requiring ARM64 self-hosted runners:

- ✅ **AMD64 (x86_64)**: Fully tested on GitHub-hosted `ubuntu-20.04` runners
- 🔄 **ARM64 (aarch64)**: Optional, requires self-hosted runners to be configured
- 🐳 **QEMU Emulation**: Available in `multi-arch-test-parity.yml` for ARM64 testing without dedicated hardware

### Why This Change?

The previous configuration required ARM64 self-hosted runners for all workflows, which caused builds to:
- ❌ Queue indefinitely if runners weren't available
- ❌ Fail after timeout
- ❌ Block PR merges

The new configuration:
- ✅ Runs AMD64 tests immediately on GitHub-hosted runners
- ✅ Allows ARM64 tests when self-hosted runners are available
- ✅ Uses `continue-on-error` for optional ARM64 jobs
- ✅ Provides QEMU-based fallback testing

---

## Workflow Configuration

### Workflows with Optional ARM64 Support

The following workflows have ARM64 support configured but **disabled by default**:

1. **`run-tests.yml`** - Main test suite
   - AMD64: 6 Python versions (3.8-3.13)
   - ARM64: 3 Python versions (3.10, 3.11, 3.12) - *optional*

2. **`daemon-tests.yml`** - Daemon functionality
   - AMD64: 3 Python versions (3.10-3.12)
   - ARM64: 1 Python version (3.11) - *optional*

3. **`cluster-tests.yml`** - Cluster services
   - AMD64: 4 Python versions (3.9-3.12)
   - ARM64: 1 Python version (3.11) - *optional*

4. **`python-package.yml`** - Package validation
   - AMD64: 6 Python versions (3.8-3.13)
   - ARM64: 1 Python version (3.11) - *optional*

5. **`lint.yml`** - Code quality
   - AMD64 only (linting is architecture-independent)

6. **`coverage.yml`** - Test coverage
   - AMD64 only (coverage is architecture-independent)

7. **`security.yml`** - Security scanning
   - AMD64 only (security checks are architecture-independent)

8. **`multi-arch-test-parity.yml`** - Multi-arch validation
   - Uses **QEMU emulation** for ARM64 testing (no self-hosted runners needed)
   - Only runs on main/develop branches to reduce load

---

## Enabling ARM64 Self-Hosted Runners

### Prerequisites

1. **ARM64 Hardware** - Physical ARM64 machine, VM, or cloud instance
2. **GitHub Actions Runner** - Installed and registered with repository
3. **Runner Labels** - Must include: `self-hosted`, `arm64`, `dgx`
4. **Python Versions** - Python 3.8-3.13 available on the runner

### Step 1: Set Up ARM64 Runner

On your ARM64 machine:

```bash
# Download and install GitHub Actions runner
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-arm64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-arm64-2.311.0.tar.gz
tar xzf ./actions-runner-linux-arm64-2.311.0.tar.gz

# Configure the runner
./config.sh --url https://github.com/endomorphosis/ipfs_kit_py \
  --token YOUR_RUNNER_TOKEN \
  --labels self-hosted,arm64,dgx

# Start the runner
./run.sh
```

### Step 2: Install Python Versions

```bash
# Install pyenv for multiple Python versions
curl https://pyenv.run | bash

# Install required Python versions
pyenv install 3.8.18
pyenv install 3.9.18
pyenv install 3.10.13
pyenv install 3.11.7
pyenv install 3.12.1
pyenv install 3.13.0

# Make them available system-wide
pyenv global 3.11.7 3.10.13 3.12.1 3.9.18 3.8.18 3.13.0
```

### Step 3: Install Dependencies

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  libssl-dev \
  libffi-dev \
  python3-dev \
  git \
  curl \
  wget

# Install Go (for some IPFS components)
wget https://go.dev/dl/go1.21.5.linux-arm64.tar.gz
sudo tar -C /usr/local -xzf go1.21.5.linux-arm64.tar.gz
echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
```

### Step 4: Enable ARM64 Jobs in Workflows

Once runners are configured, uncomment ARM64 jobs in workflow files:

**Example: `run-tests.yml`**

```yaml
strategy:
  matrix:
    arch: [amd64]  # <- Change to [amd64, arm64]
    python-version: [3.8, 3.9, '3.10', '3.11', '3.12', '3.13']
```

Or use the include pattern:

```yaml
strategy:
  matrix:
    arch: [amd64]
    python-version: [3.8, 3.9, '3.10', '3.11', '3.12', '3.13']
    include:
      - arch: arm64
        python-version: '3.10'
      - arch: arm64
        python-version: '3.11'
      - arch: arm64
        python-version: '3.12'
```

---

## QEMU-Based ARM64 Testing (No Runners Required)

The `multi-arch-test-parity.yml` workflow includes QEMU-based testing that works **without self-hosted runners**:

```yaml
test-docker-qemu:
  name: Docker Test on ${{ matrix.platform }}
  runs-on: ubuntu-latest
  strategy:
    matrix:
      platform: [linux/amd64, linux/arm64]
```

This approach:
- ✅ Runs ARM64 tests via QEMU emulation
- ✅ No dedicated hardware required
- ✅ Works on standard GitHub-hosted runners
- ⚠️  Slower than native ARM64 (but sufficient for CI/CD)

---

## Verification

### Check Runner Status

```bash
# List registered runners
gh api /repos/endomorphosis/ipfs_kit_py/actions/runners

# Check runner labels
gh api /repos/endomorphosis/ipfs_kit_py/actions/runners | \
  jq '.runners[] | {name, status, labels: .labels[].name}'
```

### Test ARM64 Jobs

```bash
# Manually trigger a workflow with ARM64 support
gh workflow run run-tests.yml

# Monitor the run
gh run list --workflow=run-tests.yml
gh run view <run-id>
```

### Expected Behavior

**Without ARM64 Runners:**
- ✅ AMD64 jobs run successfully
- ⚠️  ARM64 jobs are skipped (if using include pattern)
- ✅ Workflow passes overall

**With ARM64 Runners:**
- ✅ AMD64 jobs run on GitHub-hosted runners
- ✅ ARM64 jobs run on self-hosted runners
- ✅ Both architectures tested

---

## Troubleshooting

### Issue: Workflow Queued Forever

**Symptom:** Workflow shows "queued" status indefinitely

**Cause:** ARM64 jobs waiting for self-hosted runners that aren't available

**Solution:**
1. Ensure ARM64 matrix is set to `[amd64]` only (default configuration)
2. Or set up ARM64 self-hosted runners (see above)
3. Or rely on QEMU-based testing in `multi-arch-test-parity.yml`

### Issue: ARM64 Runner Not Found

**Symptom:** Error message "No runner matching the labels found"

**Cause:** Runner labels don't match workflow requirements

**Solution:**
```bash
# Reconfigure runner with correct labels
cd actions-runner
./config.sh remove
./config.sh --url https://github.com/endomorphosis/ipfs_kit_py \
  --token YOUR_TOKEN \
  --labels self-hosted,arm64,dgx
```

### Issue: Python Version Not Available

**Symptom:** `python3.X: command not found` on ARM64 runner

**Solution:**
```bash
# Install missing Python version
pyenv install 3.11.7
pyenv global 3.11.7 system

# Verify
python3.11 --version
```

---

## Architecture Decision

### Why AMD64-Only by Default?

1. **Reliability**: GitHub-hosted runners are always available
2. **Speed**: No waiting for self-hosted runners
3. **Cost**: No dedicated ARM64 hardware required
4. **Flexibility**: ARM64 can be enabled when needed

### When to Enable ARM64 Testing?

Enable ARM64 self-hosted runner testing when:
- 🎯 Deploying to ARM64 production systems
- 🐛 Debugging architecture-specific issues
- 🔍 Performance testing on ARM64
- ✅ ARM64 runners are reliably available

### Alternative: QEMU Testing

For basic ARM64 validation without dedicated hardware:
- Use `multi-arch-test-parity.yml` with QEMU
- Runs ARM64 tests in Docker containers
- Slower but requires no additional infrastructure

---

## Performance Comparison

| Method | Speed | Coverage | Setup Required | Cost |
|--------|-------|----------|----------------|------|
| AMD64 GitHub-hosted | ⚡⚡⚡ Fast | Full | None | Free |
| ARM64 Self-hosted | ⚡⚡⚡ Fast | Full | Significant | Hardware |
| ARM64 QEMU | ⚡ Slow | Basic | Minimal | Free |

---

## Monitoring

### Track Workflow Performance

```bash
# Check recent runs
gh run list --workflow=run-tests.yml --limit 10

# View specific run with timing
gh run view <run-id> --log

# Download artifacts
gh run download <run-id>
```

### Metrics to Watch

- **Queue time**: Should be < 1 minute for AMD64
- **Execution time**: 5-15 minutes typical for test suite
- **Failure rate**: Target < 5% (excluding flaky tests)
- **ARM64 availability**: Monitor self-hosted runner uptime

---

## Summary

✅ **Default configuration works without ARM64 runners**  
✅ **All critical tests run on AMD64**  
✅ **ARM64 support available when runners are configured**  
✅ **QEMU-based fallback testing available**  
✅ **CI/CD no longer blocked by missing ARM64 infrastructure**

---

**Last Updated:** October 22, 2025  
**Configuration Version:** 2.0 (AMD64-first approach)  
**Status:** Production Ready
