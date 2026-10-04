# Lotus Dependencies Docker Pre-installation Fix

## Problem
The Lotus installer (`install_lotus.py`) was attempting to install system dependencies (hwloc, OpenCL libraries) at runtime inside Docker containers, causing:
- Package manager lock conflicts and timeouts
- Heavy download attempts during daemon startup
- API not binding because initialization was blocked
- Repeated installation attempts even when environment flags disabled auto-install

## Root Cause
The installer's `_install_system_dependencies()` method is called during `__init__`, and while it checked for the hwloc library before attempting installation, the check paths didn't include architecture-specific directories like `/usr/lib/x86_64-linux-gnu/`.

## Solution

### 1. Pre-install Lotus Dependencies in Docker Images
Updated both `deployment/docker/Dockerfile` and `deployment/docker/Dockerfile.enhanced` to install all required Lotus system dependencies during the image build:

```dockerfile
# Install system dependencies including Lotus prerequisites
# This ensures the installer will detect they're already present and skip installation
RUN apt-get update && apt-get install -y \
    # ... other dependencies ...
    hwloc \
    libhwloc-dev \
    mesa-opencl-icd \
    ocl-icd-opencl-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Packages added:**
- `hwloc` - Hardware locality library (provides libhwloc.so)
- `libhwloc-dev` - Development headers for hwloc
- `mesa-opencl-icd` - OpenCL Installable Client Driver (ICD) loader
- `ocl-icd-opencl-dev` - OpenCL development files

### 2. Improved Library Detection in Installer
Enhanced `_check_hwloc_library_direct()` in `ipfs_kit_py/install_lotus.py` to check architecture-specific library paths:

```python
lib_paths = [
    "/usr/lib", 
    "/usr/lib/x86_64-linux-gnu",  # Debian/Ubuntu x86_64
    "/usr/lib/aarch64-linux-gnu",  # Debian/Ubuntu ARM64
    "/usr/lib/arm-linux-gnueabihf",  # Debian/Ubuntu ARM32
    "/usr/local/lib", 
    "/lib", 
    "/lib64", 
    "/usr/lib64",
    # ... macOS and Windows paths ...
]
```

This ensures the installer detects libraries installed by the package manager in their actual locations.

## How It Works

1. **Build Time**: Docker image build installs hwloc and OpenCL packages via apt
2. **Container Startup**: When ipfs-kit daemon starts and imports lotus_kit
3. **Installer Init**: `install_lotus.__init__()` calls `_install_system_dependencies()`
4. **Early Detection**: `_check_hwloc_library_direct()` scans standard library paths
5. **Detection Success**: Finds `/usr/lib/x86_64-linux-gnu/libhwloc.so.15`
6. **Skip Installation**: Returns `True` immediately, skipping all package manager operations
7. **Fast Startup**: Daemon initialization completes without blocking or errors

## Verification

Test locally (with hwloc installed):
```bash
python -c "
import os
os.environ['IPFS_KIT_AUTO_INSTALL_DEPS'] = '0'
from ipfs_kit_py.install_lotus import install_lotus
installer = install_lotus(metadata={'auto_install_deps': False})
print(f'hwloc found: {installer._check_hwloc_library_direct()}')
"
```

Expected output:
```
INFO - Found hwloc library: /usr/lib/x86_64-linux-gnu/libhwloc.so
INFO - Found libhwloc library installed on the system
hwloc found: True
```

## Benefits

1. **No Runtime Installation**: All dependencies present at build time
2. **Faster Container Startup**: No package manager operations during daemon init
3. **No Lock Conflicts**: No apt/dpkg lock waiting or timeouts
4. **Environment Flag Respected**: With deps pre-installed, auto-install flags work as intended
5. **Cross-Architecture Support**: Detection works for amd64, arm64, armhf
6. **Predictable Behavior**: Containers behave identically regardless of external package manager state

## Testing

To rebuild and test:

```bash
# Rebuild the image
docker build -f deployment/docker/Dockerfile.enhanced -t ipfs-kit:test .

# Run daemon-only mode
docker run --rm --name ipfs-kit-daemon-test \
  -p 9999:9999 \
  -e IPFS_KIT_AUTO_INSTALL_DEPS=0 \
  -e IPFS_KIT_AUTO_INSTALL_LOTUS_DEPS=0 \
  ipfs-kit:test daemon-only

# Check API health (should respond quickly)
curl http://localhost:9999/api/v1/status
```

Expected: API responds within seconds with `{"status": "ok", "running": true, ...}`

## Related Changes

- Also updated environment flag handling in `lotus_kit.py` and `storacha_kit.py` to respect `IPFS_KIT_AUTO_INSTALL_*_DEPS` flags
- Deferred heavy IPFSKit import in daemon to avoid import-time side effects
- Added lazy import for BucketVFSManager to handle optional dependencies gracefully

## Files Modified

1. `deployment/docker/Dockerfile` - Added Lotus dependencies to apt install
2. `deployment/docker/Dockerfile.enhanced` - Added Lotus dependencies to apt install  
3. `ipfs_kit_py/install_lotus.py` - Enhanced library path detection
4. `ipfs_kit_py/lotus_kit.py` - Respect environment flags for auto-install
5. `ipfs_kit_py/storacha_kit.py` - Respect environment flags for auto-install
6. `mcp/ipfs_kit/daemon/ipfs_kit_daemon.py` - Lazy imports and improved error handling
