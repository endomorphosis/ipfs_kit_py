# Dependency Management for IPFS Kit Python

This document describes the comprehensive dependency management system for IPFS Kit Python, which supports multiple hardware architectures and operating systems.

## Supported Platforms

### Operating Systems
- **Linux**: Ubuntu, Debian, Fedora, CentOS, RHEL, Alpine, Arch Linux
- **macOS**: Intel (x86_64) and Apple Silicon (arm64/M1/M2)
- **Windows**: x86_64 (limited support)

### Architectures
- **amd64/x86_64**: Intel and AMD 64-bit processors
- **arm64/aarch64**: ARM 64-bit processors (including Apple Silicon, Raspberry Pi 4+, AWS Graviton)
- **arm**: 32-bit ARM (Raspberry Pi 3 and earlier)

## Dependency Checker

### Usage

The comprehensive dependency checker can be run standalone or as part of Docker initialization:

```bash
# Check dependencies without installing (dry run)
python scripts/check_and_install_dependencies.py --dry-run --verbose

# Check and install missing dependencies
python scripts/check_and_install_dependencies.py --verbose

# Check only Docker support
python scripts/check_and_install_dependencies.py --docker-only

# Save detailed report
python scripts/check_and_install_dependencies.py --report dependency_report.json
```

### What It Checks

1. **Python Version**: Ensures Python 3.8+ (3.11+ recommended)
2. **System Packages**: Build tools, libraries (hwloc, OpenCL), Go compiler
3. **Python Packages**: Core dependencies from pyproject.toml
4. **Docker Support**: Docker installation and functionality

### Features

- **Architecture Detection**: Automatically detects CPU architecture and normalizes names
- **OS Detection**: Identifies Linux distribution and package manager
- **Cross-Platform**: Uses appropriate package manager (apt, yum, dnf, apk, pacman, brew)
- **Non-Invasive**: Can run in dry-run mode to check without modifying system
- **Detailed Reporting**: Generates JSON report with all findings

## Docker Support

### Building Multi-Architecture Images

The Dockerfile supports multi-architecture builds using Docker Buildx:

```bash
# Build for current architecture
docker build -t ipfs-kit-py:latest .

# Build for specific architecture
docker build --platform linux/amd64 -t ipfs-kit-py:amd64 .
docker build --platform linux/arm64 -t ipfs-kit-py:arm64 .

# Build multi-arch image (requires buildx)
docker buildx build --platform linux/amd64,linux/arm64 -t ipfs-kit-py:multi .
```

### Docker Entrypoint

The Docker entrypoint script (`scripts/docker_entrypoint.sh`) automatically:

1. Detects platform and architecture
2. Verifies Python installation
3. Checks system libraries
4. Initializes configuration directories
5. Optionally runs full dependency verification

#### Environment Variables

Configure the container with these environment variables:

```bash
# Enable full dependency verification on startup
IPFS_KIT_VERIFY_DEPS=1

# Data directory (default: /app/data)
IPFS_KIT_DATA_DIR=/custom/data/path

# Log directory (default: /app/logs)
IPFS_KIT_LOG_DIR=/custom/log/path

# Config directory (default: /app/config)
IPFS_KIT_CONFIG_DIR=/custom/config/path

# Log level
LOG_LEVEL=DEBUG
```

#### Example Usage

```bash
# Run with default settings
docker run -p 8000:8000 ipfs-kit-py:latest

# Run with dependency verification
docker run -e IPFS_KIT_VERIFY_DEPS=1 ipfs-kit-py:latest

# Run with custom data directory
docker run -v /host/data:/app/data -e IPFS_KIT_DATA_DIR=/app/data ipfs-kit-py:latest

# Run a custom command
docker run ipfs-kit-py:latest python -c "import ipfs_kit_py; print(ipfs_kit_py.__version__)"

# Interactive shell
docker run -it ipfs-kit-py:latest /bin/bash
```

## Docker Compose Support

Use Docker Compose for more complex setups:

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up ipfs-kit-py

# Start GPU-enabled service (requires NVIDIA Docker)
docker-compose up ipfs-kit-py-gpu

# Start development service
docker-compose up ipfs-kit-py-dev

# Run tests
docker-compose --profile testing up ipfs-kit-py-test

# View logs
docker-compose logs -f ipfs-kit-py
```

## System Dependencies

### Linux (Debian/Ubuntu)

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    git \
    curl \
    wget \
    hwloc \
    libhwloc-dev \
    mesa-opencl-icd \
    ocl-icd-opencl-dev \
    golang-go
```

### Linux (Fedora/CentOS/RHEL)

```bash
sudo dnf install -y \
    gcc gcc-c++ make \
    git \
    curl \
    wget \
    hwloc hwloc-devel \
    opencl-headers \
    ocl-icd-devel \
    golang
```

### Linux (Alpine)

```bash
sudo apk add \
    build-base \
    git \
    curl \
    wget \
    hwloc hwloc-dev \
    opencl-headers \
    opencl-icd-loader-dev \
    go
```

### macOS

```bash
# Install Homebrew first if not already installed
# https://brew.sh/

brew install hwloc go
```

### Windows

For Windows, most dependencies are bundled with Python packages. However, you may need:

1. **Visual C++ Build Tools**: Download from Microsoft
2. **Git**: https://git-scm.com/download/win
3. **Go**: https://golang.org/dl/ (optional, for building from source)

## Python Package Installation

### Standard Installation

```bash
# Install with all dependencies
pip install -e .

# Install with specific extras
pip install -e ".[api,full]"      # API and all features
pip install -e ".[dev,test]"      # Development and testing
pip install -e ".[arrow,libp2p]"  # Arrow and libp2p support (libp2p installs from GitHub main)
```

### Architecture-Specific Notes

#### ARM64/aarch64

Some Python packages may need to be built from source on ARM64. The installation may take longer:

```bash
# Install build dependencies first
sudo apt-get install -y python3-dev

# Install with increased timeout
pip install --timeout=300 -e .
```

#### Apple Silicon (M1/M2)

```bash
# Use Rosetta for x86_64 packages if needed
arch -x86_64 pip install -e .

# Or use native ARM64
pip install -e .
```

## Troubleshooting

### Common Issues

#### 1. Package Manager Locks (Linux)

If you see errors about package manager locks:

```bash
# Wait for other package managers to finish, or:
sudo rm /var/lib/dpkg/lock-frontend
sudo rm /var/lib/dpkg/lock
sudo dpkg --configure -a
```

#### 2. hwloc Library Not Found

```bash
# Linux
sudo ldconfig -p | grep hwloc  # Check if installed
sudo apt-get install --reinstall libhwloc-dev

# macOS
brew reinstall hwloc
```

#### 3. Python Package Build Failures

```bash
# Ensure development headers are installed
sudo apt-get install -y python3-dev build-essential

# Try upgrading pip and setuptools
pip install --upgrade pip setuptools wheel

# Install specific package with verbose output
pip install -v package_name
```

#### 4. Docker Build Failures

```bash
# Clear Docker cache
docker builder prune -a

# Build with no cache
docker build --no-cache -t ipfs-kit-py:latest .

# Check build logs
docker build --progress=plain -t ipfs-kit-py:latest .
```

### Getting Help

1. Run dependency checker with verbose output:
   ```bash
   python scripts/check_and_install_dependencies.py --verbose --report report.json
   ```

2. Check the generated report:
   ```bash
   cat report.json | jq .
   ```

3. Review Docker logs:
   ```bash
   docker logs container_name
   ```

4. Open an issue with:
   - Platform information (OS, architecture)
   - Dependency report JSON
   - Error messages
   - Steps to reproduce

## CI/CD Integration

The dependency checker integrates with GitHub Actions workflows:

```yaml
- name: Check Dependencies
  run: |
    python scripts/check_and_install_dependencies.py --verbose
```

See `.github/workflows/` for complete examples across different architectures.

## References

- [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Docker Multi-Platform Builds](https://docs.docker.com/build/building/multi-platform/)
- [Python Packaging Guide](https://packaging.python.org/)
- [hwloc Documentation](https://www.open-mpi.org/projects/hwloc/)
