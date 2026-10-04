# Docker Multi-Architecture Support - Quick Start

## Overview

IPFS Kit Python supports Docker deployment across multiple architectures:
- **Linux**: amd64 (x86_64), arm64 (aarch64)
- **macOS**: Intel (x86_64), Apple Silicon (arm64)
- **Windows**: x86_64 (via Docker Desktop with WSL2)

## Quick Start

### 1. Build Docker Image

```bash
# Build for your current architecture
docker build -t ipfs-kit-py:latest .

# Or build for a specific architecture
docker build --platform linux/amd64 -t ipfs-kit-py:amd64 .
docker build --platform linux/arm64 -t ipfs-kit-py:arm64 .
```

### 2. Run Container

```bash
# Basic usage
docker run -p 8000:8000 ipfs-kit-py:latest

# With persistent data
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ipfs-kit-py:latest

# With dependency verification on startup
docker run -e IPFS_KIT_VERIFY_DEPS=1 ipfs-kit-py:latest
```

### 3. Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f ipfs-kit-py

# Stop services
docker-compose down
```

## Available Docker Targets

| Target | Purpose | Command |
|--------|---------|---------|
| `production` | Minimal runtime image | `docker build --target production -t ipfs-kit-py:prod .` |
| `development` | Full dev environment | `docker build --target development -t ipfs-kit-py:dev .` |
| `testing` | Test runner | `docker build --target testing -t ipfs-kit-py:test .` |
| `documentation` | MkDocs server | `docker build --target documentation -t ipfs-kit-py:docs .` |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `IPFS_KIT_VERIFY_DEPS` | Enable full dependency verification | `0` |
| `IPFS_KIT_DATA_DIR` | Data directory path | `/app/data` |
| `IPFS_KIT_LOG_DIR` | Log directory path | `/app/logs` |
| `IPFS_KIT_CONFIG_DIR` | Config directory path | `/app/config` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `PYTHONUNBUFFERED` | Python output buffering | `1` |

## Dependency Verification

Check dependencies before or after building:

```bash
# Check on your host system (requires Python)
python scripts/check_and_install_dependencies.py --dry-run --verbose

# Inside a running container
docker run ipfs-kit-py:latest \
  python /app/scripts/check_and_install_dependencies.py --dry-run
```

## Multi-Architecture Testing

Test builds across architectures:

```bash
# Requires Docker buildx
./scripts/test_docker_multiarch.sh

# Or manually
docker buildx build --platform linux/amd64,linux/arm64 -t ipfs-kit-py:multi .
```

## Troubleshooting

### Build Failures

1. **Clear Docker cache:**
   ```bash
   docker builder prune -a
   docker build --no-cache -t ipfs-kit-py:latest .
   ```

2. **Check build logs:**
   ```bash
   docker build --progress=plain -t ipfs-kit-py:latest . 2>&1 | tee build.log
   ```

### Runtime Issues

1. **Check container logs:**
   ```bash
   docker logs container_name
   ```

2. **Verify dependencies inside container:**
   ```bash
   docker run -e IPFS_KIT_VERIFY_DEPS=1 ipfs-kit-py:latest
   ```

3. **Interactive debugging:**
   ```bash
   docker run -it ipfs-kit-py:latest /bin/bash
   ```

## For More Information

- **Full Documentation**: See `DEPENDENCY_MANAGEMENT.md`
- **Implementation Details**: See `DOCKER_MULTIARCH_SUMMARY.md`
- **Dependency Installer**: `scripts/check_and_install_dependencies.py --help`
- **Lotus Installation**: `scripts/install/install_lotus.py --help`

## CI/CD Integration

GitHub Actions example:

```yaml
- name: Build Docker Image
  run: docker build -t ipfs-kit-py:${{ github.sha }} .

- name: Test Docker Image  
  run: |
    docker run ipfs-kit-py:${{ github.sha }} \
      python -c "import ipfs_kit_py; print('OK')"
```

## Security

- Containers run as non-root user `appuser` by default
- Minimal attack surface in production images
- Regular dependency updates via Dependabot
- Health checks enabled for monitoring

## Performance

- Multi-stage builds minimize image size
- Python bytecode compilation disabled in containers
- Pip caching configured for faster rebuilds
- Architecture-specific optimizations where available
