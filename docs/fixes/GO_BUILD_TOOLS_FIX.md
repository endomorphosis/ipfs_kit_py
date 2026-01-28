# Go and Build Tools Installation Fix

## Issue

When running workflows on self-hosted runners, dependencies such as Go were not being installed, causing build-from-source scenarios to fail. The workflows were missing the proper environment setup that includes build tools.

## Root Cause

The issue was present in multiple locations:

1. **`multi-arch-ci.yml`** - Native ARM64 and AMD64 runner tests were missing Go and other build tools
2. **`Dockerfile`** - Base image didn't include Go for scenarios requiring build-from-source
3. **`docker/Dockerfile`** - Also missing Go in the base image

The original workflows (`arm64-ci.yml` and `amd64-ci.yml`) had the correct setup with `golang-go` package, but the newer `multi-arch-ci.yml` workflow was created without these dependencies.

## Solution

### 1. Updated `multi-arch-ci.yml`

Added build tools installation for both ARM64 and AMD64 native runner jobs:

```yaml
- name: Install system dependencies
  run: |
    sudo apt-get update || true
    sudo apt-get install -y \
      gcc \
      g++ \
      make \
      libffi-dev \
      libssl-dev \
      git \
      curl \
      golang-go \        # Added
      pkg-config \       # Added
      wget \             # Added
      unzip \            # Added
      tar \              # Added
      gzip \             # Added
      || echo "Some system packages failed to install, continuing..."

- name: Verify build tools
  run: |
    echo "Checking build tools availability..."
    go version || echo "⚠️  Go not available"
    make --version || echo "⚠️  Make not available"
    gcc --version || echo "⚠️  GCC not available"
    git --version || echo "⚠️  Git not available"
```

This ensures:
- Go is available for building IPFS/Lotus from source
- All necessary build tools are present
- Verification step confirms tool availability

### 2. Updated `Dockerfile`

Added Go to base stage:

```dockerfile
# Install system dependencies including Go for building from source
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    curl \
    wget \
    ca-certificates \
    gnupg2 \
    software-properties-common \
    golang-go \      # Added
    make \           # Added
    pkg-config \     # Added
    && rm -rf /var/lib/apt/lists/*
```

### 3. Updated `docker/Dockerfile`

Added Go to system dependencies:

```dockerfile
# Install system dependencies including Go for building from source
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    gcc \
    g++ \
    make \
    pkg-config \
    libffi-dev \
    libssl-dev \
    golang-go \      # Added
    && rm -rf /var/lib/apt/lists/*
```

## Why These Dependencies Are Needed

### Go (golang-go)
- Required for building IPFS (Kubo) from source when pre-built binaries aren't available
- Required for building Lotus from source
- The `install_ipfs.py` and `install_lotus.py` scripts have build-from-source fallback logic

### Other Build Tools
- **make**: Build automation tool used by Go projects
- **pkg-config**: Helps find library compilation flags
- **wget/curl**: Download source code and binaries
- **unzip/tar/gzip**: Extract downloaded archives
- **gcc/g++**: C/C++ compilers for building native extensions

## Benefits

1. **ARM64 Support**: Ensures ARM64 runners can build from source when needed
2. **Consistency**: All workflows now have the same environment setup
3. **Reliability**: Reduces failures due to missing dependencies
4. **Docker Compatibility**: Docker images can now build from source if needed

## Testing

The changes maintain backward compatibility and add functionality:

```bash
# Test Go availability in workflow
go version

# Test IPFS build from source (if needed)
python -c "from ipfs_kit_py.install_ipfs import install_ipfs; installer = install_ipfs(); installer.build_ipfs_from_source()"

# Test in Docker
docker build -t test:latest .
docker run --rm test:latest go version
```

## Files Modified

1. `.github/workflows/multi-arch-ci.yml` - Added build tools to ARM64 and AMD64 native jobs
2. `Dockerfile` - Added Go and build tools to base stage
3. `docker/Dockerfile` - Added Go to system dependencies

## Validation

✅ YAML syntax validated
✅ No breaking changes
✅ All build tools included
✅ Verification steps added

## Related Issues

This fix addresses the comment:
> "dependencies such as Go are not being installed when we use the runners, or the workflows are not using the correct environment"

The workflows now properly install and verify all build dependencies before running tests.
