# Multi-Architecture Support

## Overview

The `ipfs_kit_py` package supports multiple hardware architectures to ensure compatibility across different systems:

- **x86_64 (AMD64)**: Standard Intel/AMD 64-bit processors
- **ARM64 (AArch64)**: 64-bit ARM processors (including Apple Silicon, NVIDIA Jetson, Raspberry Pi 4+)

## Supported Platforms

### Linux
- x86_64/AMD64 (Ubuntu, Debian, RHEL, etc.)
- ARM64/AArch64 (Raspberry Pi OS, Ubuntu ARM, etc.)

### macOS
- x86_64 (Intel Macs)
- ARM64 (Apple Silicon M1/M2/M3)

## CI/CD Pipeline

The project uses GitHub Actions workflows to test on both architectures:

### Workflows

1. **multi-arch-ci.yml**: Main multi-architecture testing workflow
   - Tests on AMD64 using QEMU emulation
   - Tests on ARM64 using QEMU emulation
   - Tests on native self-hosted ARM64 runners
   - Tests on native self-hosted AMD64 runners

2. **arm64-ci.yml**: Dedicated ARM64 testing on self-hosted runners
   - Uses labels: `[self-hosted, arm64, dgx]`
   - Tests Python 3.8, 3.9, 3.10, 3.11

3. **amd64-ci.yml**: Dedicated AMD64 testing on self-hosted runners
   - Uses labels: `[self-hosted, amd64]`
   - Tests Python 3.8, 3.9, 3.10, 3.11

### Self-Hosted Runner Setup

#### ARM64 Runner Labels
```yaml
runs-on: [self-hosted, arm64]
```

#### AMD64 Runner Labels
```yaml
runs-on: [self-hosted, amd64]
```

Make sure your self-hosted runners are configured with the appropriate labels to ensure jobs are routed to the correct architecture.

## Docker Multi-Architecture Support

### Building Multi-Arch Images

The project's Dockerfiles support multi-architecture builds using Docker Buildx:

```bash
# Build for both architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t ipfs-kit-py:latest \
  --push \
  .
```

### Using Platform-Specific Images

```bash
# Pull and run AMD64 image
docker run --platform linux/amd64 ipfs-kit-py:latest

# Pull and run ARM64 image
docker run --platform linux/arm64 ipfs-kit-py:latest
```

### Multi-Arch Build Arguments

The Dockerfiles use build arguments to handle architecture-specific builds:

```dockerfile
ARG TARGETPLATFORM
ARG BUILDPLATFORM

FROM python:3.11-slim

RUN echo "Building on $BUILDPLATFORM, targeting $TARGETPLATFORM"
```

## Package Installation

### Architecture Detection

The package automatically detects your architecture during installation:

```python
from ipfs_kit_py.install_ipfs import install_ipfs

installer = install_ipfs()
hardware_info = installer.get_hardware_info()

print(f"Detected architecture: {hardware_info['machine']}")
print(f"System: {hardware_info['system']}")
```

### Binary Installation

The package handles architecture-specific binary downloads:

- **IPFS (Kubo)**: Downloads the correct binary for your architecture
- **Lotus**: Downloads the correct binary for your architecture
- **IPFS Cluster**: Downloads the correct binary for your architecture

If a pre-built binary is not available for your architecture, the package can build from source.

### Building from Source

For architectures without pre-built binaries:

```python
from ipfs_kit_py.install_ipfs import install_ipfs

installer = install_ipfs()

# Build IPFS from source
installer.build_ipfs_from_source()
```

Requirements for building from source:
- Go 1.19 or later
- GCC/G++
- Make
- Git

## Testing Multi-Architecture Support

### Running Architecture Tests

```bash
# Run architecture-specific tests
pytest tests/test_architecture_support.py -v

# Run on specific architecture (using Docker)
docker run --platform linux/arm64 ipfs-kit-py:latest pytest tests/test_architecture_support.py -v
```

### Verify Architecture Detection

```python
import platform
from ipfs_kit_py.install_ipfs import install_ipfs

print(f"Python reports: {platform.machine()}")

installer = install_ipfs()
platform_str = installer.get_platform()
print(f"Package detects: {platform_str}")
```

## Known Limitations

### ARM64 Limitations
- Some dependencies may require building from source
- First-time setup may take longer due to compilation
- QEMU emulation is slower than native execution

### Architecture-Specific Dependencies
- `libp2p`: May require additional build tools on ARM64
- Native extensions: Check that all Python packages support your architecture

## Troubleshooting

### Issue: Wrong Architecture Binary Downloaded

**Solution**: Verify platform detection:
```python
from ipfs_kit_py.install_ipfs import install_ipfs
installer = install_ipfs()
print(installer.get_hardware_info())
```

### Issue: Docker Build Fails on ARM64

**Solution**: Ensure QEMU is installed and Docker Buildx is set up:
```bash
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes
docker buildx create --use
docker buildx inspect --bootstrap
```

### Issue: Tests Fail on Specific Architecture

**Solution**: Check the CI logs for architecture-specific errors and verify that all dependencies are available for your architecture.

## Contributing

When adding new dependencies or features:

1. Test on both AMD64 and ARM64 architectures
2. Use the multi-arch CI workflow
3. Ensure Docker images build for both platforms
4. Update architecture-related documentation

## References

- [Docker Multi-Platform Builds](https://docs.docker.com/build/building/multi-platform/)
- [GitHub Actions Self-Hosted Runners](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Python Platform Detection](https://docs.python.org/3/library/platform.html)
