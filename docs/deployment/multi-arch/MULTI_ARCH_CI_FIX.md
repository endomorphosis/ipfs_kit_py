# Multi-Architecture CI/CD and Dependency Fixes

## Overview

This document describes the fixes implemented to address CI/CD issues on ARM64, aarch64, and risc-v platforms, particularly for the NVIDIA DGX Spark runner.

## Issues Addressed

### 1. Missing libp2p Dependencies

**Problem:**
```
INFO:libp2p:Optional dependencies missing: google-protobuf, eth-hash, eth-keys
WARNING:ipfs_kit_py.libp2p.crypto_compat:Failed to import libp2p.crypto.keys
ERROR:ipfs_kit_py.libp2p_peer:Failed to import required libp2p modules
```

**Root Cause:**
- The libp2p optional dependencies were not being installed by default
- Some dependencies (eth-hash, eth-keys) were marked as optional but are actually required for full functionality
- Protobuf version conflicts between different libp2p components

**Solution:**
- Updated `pyproject.toml` and `setup.py` to specify `eth-hash[pycryptodome]` instead of plain `eth-hash`
- Expanded protobuf version range to `>=3.20.0,<5.0.0` for better compatibility
- Made libp2p dependencies more explicit with proper crypto backend specification

**Files Changed:**
- `pyproject.toml` - Updated libp2p extras
- `setup.py` - Updated libp2p extras to match

### 2. Package Manager Lock Issues

**Problem:**
```
WARNING:install_lotus:Package manager is not available: Lock file /var/lib/apt/lists/lock exists but cannot be read
```

**Root Cause:**
- On shared systems like NVIDIA DGX, multiple users/processes may access package managers simultaneously
- Automated systems (like unattended-upgrades) can hold locks for extended periods
- Tests fail when package manager operations time out

**Solution:**
Created `scripts/safe_install.py` that:
- Detects and waits for package manager locks (up to 5 minutes)
- Retries failed installations with exponential backoff
- Installs dependencies individually if bulk installation fails
- Verifies all critical imports after installation

**Usage:**
```bash
python3 scripts/safe_install.py
```

### 3. Multi-Architecture CI/CD

**Problem:**
- No automated testing for ARM64, aarch64, or risc-v platforms
- Manual testing on NVIDIA DGX required for each change
- No verification that dependencies build correctly on non-x86 platforms

**Solution:**
Created `.github/workflows/multi-arch-ci.yml` with:

#### Features:

1. **QEMU-based Multi-Architecture Testing**
   - Tests on amd64, arm64, and armv7 using QEMU emulation
   - Runs on standard GitHub Actions runners
   - Tests multiple Python versions (3.9, 3.10, 3.11)

2. **Native ARM64 Testing**
   - Uses self-hosted runner on NVIDIA DGX
   - Requires runner label: `[self-hosted, ARM64]`
   - Handles package manager locks gracefully
   - Runs ARM64-specific test files

3. **RISC-V Experimental Support**
   - Only runs on manual workflow dispatch
   - Tests basic compatibility with RISC-V architecture
   - Uses QEMU for emulation

4. **Dependency Verification**
   - Verifies all critical dependencies can be installed
   - Creates dependency report artifacts
   - Checks for dependency conflicts

## Installation Instructions

### Standard Installation

```bash
# Install with libp2p support
pip install -e ".[libp2p]"  # libp2p installs from GitHub main
```

### Safe Installation (Recommended for Shared Systems)

```bash
# Use the safe installer
python3 scripts/safe_install.py
```

### Manual Installation with Lock Handling

```bash
# Wait for locks (if needed)
timeout=300
elapsed=0
while [ $elapsed -lt $timeout ]; do
  if ! fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 && \
     ! fuser /var/lib/dpkg/lock >/dev/null 2>&1 && \
     ! fuser /var/lib/apt/lists/lock >/dev/null 2>&1; then
    echo "No locks found"
    break
  fi
  echo "Waiting for locks... ($elapsed/$timeout)"
  sleep 5
  elapsed=$((elapsed + 5))
done

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -e .
pip install -e .[libp2p]
```

## Setting Up Self-Hosted ARM64 Runner

To enable native ARM64 testing on NVIDIA DGX:

### 1. Install GitHub Actions Runner

```bash
# On the DGX machine
cd ~
mkdir actions-runner && cd actions-runner

# Download runner (ARM64 version)
curl -o actions-runner-linux-arm64-2.311.0.tar.gz \
  -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-arm64-2.311.0.tar.gz

# Extract
tar xzf ./actions-runner-linux-arm64-2.311.0.tar.gz

# Configure (replace REPO and TOKEN)
./config.sh --url https://github.com/endomorphosis/ipfs_kit_py \
  --token YOUR_TOKEN \
  --labels self-hosted,ARM64,dgx
```

### 2. Install as Service

```bash
# Install service
sudo ./svc.sh install

# Start service
sudo ./svc.sh start

# Check status
sudo ./svc.sh status
```

### 3. Verify Runner

```bash
# Check runner is connected
./run.sh --once
```

## CI/CD Workflow Details

### Triggers

- **Push:** Runs on main, develop, and copilot/** branches
- **Pull Request:** Runs on PRs to main and develop
- **Manual:** Can be triggered via workflow_dispatch

### Jobs

#### 1. test-multi-arch
- Runs on: `ubuntu-latest` with QEMU
- Architectures: amd64, arm64, armv7
- Python versions: 3.9, 3.10, 3.11
- Uses Docker containers for isolation

#### 2. test-arm64-native
- Runs on: `[self-hosted, ARM64]` (NVIDIA DGX)
- Only on: push to branches or manual trigger
- Features:
  - Lock detection and waiting
  - Retry logic for network issues
  - ARM64-specific test execution
  - Test summary generation

#### 3. test-riscv
- Runs on: `ubuntu-latest` with QEMU
- Only on: manual workflow_dispatch
- Experimental RISC-V support

#### 4. verify-dependencies
- Runs on: `ubuntu-latest`
- Verifies all dependencies install correctly
- Creates dependency report

## Dependency Matrix

| Dependency | Purpose | ARM64 | RISC-V | Notes |
|------------|---------|-------|--------|-------|
| protobuf | Protocol buffers | ✅ | ✅ | Version 5.26-7.0 |
| eth-hash | Ethereum hashing | ✅ | ✅ | Needs pycryptodome backend |
| eth-keys | Ethereum keys | ✅ | ⚠️ | May need compilation |
| libp2p | P2P networking | ✅ | ⚠️ | Requires protobuf |
| cryptography | Encryption | ✅ | ✅ | System libs needed |
| multiaddr | Multiaddress | ✅ | ✅ | Pure Python |

## Troubleshooting

### Issue: "Failed to import libp2p modules"

**Solution:**
```bash
# Install libp2p extras explicitly
pip install -e .[libp2p]

# Verify installation
python -c "from google.protobuf import descriptor; print('✓ protobuf')"
python -c "import eth_hash; print('✓ eth-hash')"
python -c "import eth_keys; print('✓ eth-keys')"
```

### Issue: "Package manager lock" errors

**Solution:**
```bash
# Use the safe installer
python3 scripts/safe_install.py

# Or wait manually
sudo fuser -v /var/lib/dpkg/lock-frontend
# Kill process if safe, or wait
```

### Issue: "Protobuf version conflict"

**Solution:**
```bash
# Uninstall conflicting versions
pip uninstall protobuf google-protobuf

# Install compatible version
pip install 'protobuf>=3.20.0,<5.0.0'
```

### Issue: Tests fail on ARM64 but pass on x86

**Solution:**
```bash
# Check architecture-specific issues
python test_arm64_complete.py

# Verify system dependencies
ldd /path/to/compiled/module.so
```

## Testing Locally

### Test on ARM64 (if available)

```bash
# Install
python3 scripts/safe_install.py

# Run tests
python -m pytest tests/ -v --tb=short -k "not test_full"

# Run ARM64-specific tests
python test_arm64_complete.py
python test_arm64_installation.py
```

### Test with QEMU (on x86)

```bash
# Install QEMU
sudo apt-get install qemu-user-static binfmt-support

# Build for ARM64
docker buildx build --platform linux/arm64 -t test-arm64 .

# Run tests in container
docker run --rm test-arm64 pytest tests/ -v
```

## Performance Considerations

### QEMU Emulation
- **Speed:** 5-10x slower than native
- **Memory:** Requires more RAM
- **Suitable for:** Quick compatibility checks

### Native ARM64
- **Speed:** Native performance
- **Memory:** Normal usage
- **Suitable for:** Full test suite, benchmarks

### Recommendation
- Use QEMU for PR checks
- Use native ARM64 for release testing
- Use native ARM64 for performance-critical code

## Future Improvements

1. **Caching**
   - Cache pip packages between runs
   - Cache Docker layers
   - Reduce build times by 50%

2. **Parallel Testing**
   - Run test shards in parallel
   - Reduce total test time
   - Better resource utilization

3. **Matrix Expansion**
   - Add more architectures (ppc64le, s390x)
   - Test more Python versions
   - Test different OS versions

4. **Artifact Management**
   - Store test results longer
   - Generate coverage reports
   - Track performance metrics over time

## References

- [GitHub Actions ARM64 Runners](https://github.com/actions/runner/releases)
- [Docker Multi-Architecture Builds](https://docs.docker.com/build/building/multi-platform/)
- [QEMU User Emulation](https://www.qemu.org/docs/master/user/main.html)
- [Python Cryptography on ARM](https://cryptography.io/en/latest/)

## Summary

✅ **Fixed Issues:**
- Missing libp2p dependencies (protobuf, eth-hash, eth-keys)
- Package manager lock conflicts on shared systems
- Lack of multi-architecture CI/CD

✅ **New Features:**
- Multi-architecture GitHub Actions workflow
- Safe installation script for shared systems
- Native ARM64 testing support
- Dependency verification job

✅ **Platforms Supported:**
- x86_64 (amd64)
- ARM64 (aarch64)
- ARMv7
- RISC-V (experimental)

The implementation ensures that ipfs_kit_py builds and tests correctly across all major architectures, with special support for NVIDIA DGX ARM64 systems.
