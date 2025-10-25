# ARM64 Build from Source

This document explains the automatic build-from-source functionality for ARM64 systems when pre-built binaries are not available.

## Overview

The IPFS Kit Python package now includes automatic fallback to building from source when:
- No pre-built binary is available for your ARM64 platform
- Binary download fails
- Binary verification fails
- Binary extraction or installation fails

This ensures that the package can be installed and used on ARM64 systems even when official binaries are not yet available.

## Supported Components

### IPFS (Kubo)
- Automatically builds from the official [ipfs/kubo](https://github.com/ipfs/kubo) repository
- Supports all Kubo versions that can be built from source
- Builds the `ipfs` daemon binary

### Lotus (Filecoin)
- Automatically builds from the official [filecoin-project/lotus](https://github.com/filecoin-project/lotus) repository
- Supports all Lotus versions that can be built from source
- Builds all Lotus binaries:
  - `lotus` - main daemon
  - `lotus-miner` - storage miner
  - `lotus-worker` - seal worker
  - `lotus-gateway` - gateway service

## Requirements

### Build Tools

The following tools are required for building from source:

- **Go** (1.21.5 or later) - Automatically installed if not present
- **Make** - Build automation tool
- **Git** - Version control for cloning repositories
- **GCC/G++** - C/C++ compiler
- **pkg-config** - Package configuration tool

On Ubuntu/Debian ARM64 systems, install with:
```bash
sudo apt-get update
sudo apt-get install -y build-essential git golang-go make gcc g++ pkg-config
```

On macOS ARM64 (M1/M2), install with Homebrew:
```bash
brew install go make git gcc pkg-config
```

### Go Installation

If Go is not installed, the package will automatically:
1. Download the appropriate Go version for your platform (ARM64)
2. Extract it to `~/.local/go`
3. Add it to your PATH
4. Verify the installation

## How It Works

### IPFS Build Process

1. **Detection**: When `install_ipfs.py` cannot find or download a binary
2. **Go Check**: Verifies Go is installed (installs if needed)
3. **Clone**: Clones the Kubo repository from GitHub
4. **Build**: Runs `make build` to compile the IPFS binary
5. **Install**: Copies the built binary to the bin directory
6. **Verify**: Tests that the binary works correctly

Example output:
```
Building IPFS from source (version v0.35.0)...
Go is installed: go version go1.21.5 linux/arm64
Using build directory: /tmp/kubo_build_XXXXX
Cloning Kubo repository...
Building IPFS binary...
Build successful!
Installed built binary to /path/to/bin/ipfs
Verification successful: ipfs version 0.35.0
```

### Lotus Build Process

1. **Detection**: When `install_lotus.py` cannot find or download a binary
2. **Go Check**: Verifies Go is installed (installs if needed)
3. **Tool Check**: Verifies make and git are available
4. **Clone**: Clones the Lotus repository from GitHub
5. **Build**: Runs `make all` to compile all Lotus binaries
6. **Install**: Copies all built binaries to the bin directory
7. **Verify**: Tests that the main lotus binary works correctly

Example output:
```
Building Lotus from source (version v1.24.0)...
Go is installed: go version go1.21.5 linux/arm64
Using build directory: /tmp/lotus_build_XXXXX
Cloning Lotus repository...
Building Lotus binaries (this may take several minutes)...
Build successful!
Installed lotus
Installed lotus-miner
Installed lotus-worker
Installed lotus-gateway
Installed 4 binaries to /path/to/bin
Verification successful: lotus version 1.24.0
```

## Build Time Estimates

Build times vary based on system specifications:

### IPFS (Kubo)
- **ARM64 Server** (NVIDIA DGX): ~3-5 minutes
- **ARM64 Desktop**: ~5-10 minutes
- **Raspberry Pi 4**: ~15-20 minutes

### Lotus
- **ARM64 Server** (NVIDIA DGX): ~10-15 minutes
- **ARM64 Desktop**: ~15-25 minutes
- **Raspberry Pi 4**: ~30-45 minutes

## GitHub Actions Integration

The ARM64 CI workflow automatically tests build-from-source functionality:

```yaml
- name: Install build tools
  run: |
    sudo apt-get install -y golang-go make gcc g++ pkg-config

- name: Test build-from-source fallback
  run: |
    python -c "from ipfs_kit_py.install_ipfs import install_ipfs; ..."
```

This ensures:
1. Build tools are available in the CI environment
2. The build-from-source methods exist and are callable
3. External dependencies can be checked and installed

## Troubleshooting

### Go Installation Fails

If automatic Go installation fails:
```bash
# Manually install Go
wget https://go.dev/dl/go1.21.5.linux-arm64.tar.gz
sudo tar -C /usr/local -xzf go1.21.5.linux-arm64.tar.gz
export PATH=$PATH:/usr/local/go/bin
```

### Build Timeout

If builds timeout (default: 30 minutes for Lotus):
```python
# Increase timeout in your code
from ipfs_kit_py.install_lotus import install_lotus
installer = install_lotus()
# The timeout is hardcoded but can be modified in install_lotus.py
```

### Missing Build Dependencies

If you see errors about missing dependencies:
```bash
# Install all recommended build dependencies
sudo apt-get install -y \
    build-essential \
    git \
    golang-go \
    make \
    gcc \
    g++ \
    pkg-config \
    libssl-dev \
    libffi-dev
```

### Disk Space

Ensure sufficient disk space for builds:
- **IPFS**: ~500 MB
- **Lotus**: ~2 GB

Check available space:
```bash
df -h /tmp
```

## Manual Build

You can also manually trigger a build from source:

### IPFS
```python
from ipfs_kit_py.install_ipfs import install_ipfs

installer = install_ipfs()
success = installer.build_ipfs_from_source(version="v0.35.0")
print(f"Build successful: {success}")
```

### Lotus
```python
from ipfs_kit_py.install_lotus import install_lotus

installer = install_lotus()
success = installer.build_lotus_from_source(version="v1.24.0")
print(f"Build successful: {success}")
```

## Environment Variables

The build process respects the following environment variables:

- `GOARCH` - Target architecture (automatically set to `arm64`)
- `CGO_ENABLED` - Enable cgo (set to `1` for Lotus)
- `GO111MODULE` - Enable Go modules (set to `on`)

## Contributing

To improve the build-from-source functionality:

1. Test on your ARM64 platform
2. Report issues with build logs
3. Submit PRs for platform-specific fixes
4. Add support for additional build configurations

## Related Documentation

- [ARM64 Testing Guide](ARM64_TESTING.md)
- [ARM64 Compatibility Report](../ARM64_COMPATIBILITY_REPORT.md)
- [GitHub Actions Workflows](../.github/workflows/README.md)
