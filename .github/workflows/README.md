# IPFS Kit Python CI/CD Workflows

This directory contains GitHub Actions workflows for Continuous Integration (CI) and Continuous Deployment (CD) of the IPFS Kit Python project.

## Workflow Files Overview

| Workflow | File | Description |
|----------|------|-------------|
| Python Package | [workflow.yml](workflow.yml) | Tests, builds, and publishes the Python package |
| Docker | [docker.yml](docker.yml) | Builds, tests, and publishes Docker images |
| Release Management | [release.yml](release.yml) | Manages the release process |
| Dependency Management | [dependencies.yml](dependencies.yml) | Manages dependencies and security updates |
| GitHub Pages | [pages.yml](pages.yml) | Builds and deploys documentation and Helm charts |
| ARM64 CI/CD | [arm64-ci.yml](arm64-ci.yml) | Tests on self-hosted ARM64 runners |
| AMD64 CI/CD | [amd64-ci.yml](amd64-ci.yml) | Tests on self-hosted AMD64 runners |
| Multi-Architecture CI | [multi-arch-ci.yml](multi-arch-ci.yml) | Tests across multiple architectures using QEMU and self-hosted runners |
| AMD64 Python Package | [amd64-python-package.yml](amd64-python-package.yml) | AMD64-optimized Python package CI using GitHub-hosted runners |
| AMD64 Release | [amd64-release.yml](amd64-release.yml) | AMD64-focused release pipeline |

## Workflow Diagrams

### Python Package Workflow

```
┌─────────────┐     ┌─────────┐     ┌───────┐     ┌─────────────────┐
│ Test Python │────►│  Lint   │────►│ Build │────►│Publish to TestPyPI│
└─────────────┘     └─────────┘     └───────┘     └─────────────────┘
                                       │
                                       │ (if tagged)
                                       ▼
                                 ┌─────────────┐
                                 │Publish to PyPI│
                                 └─────────────┘
```

### Docker Workflow

```
┌────────────┐     ┌───────────────┐     ┌─────────┐     ┌───────────────┐     ┌───────────────┐
│ Docker Lint│────►│Build and Test │────►│ Publish │────►│   Helm Lint   │────►│Deploy to Staging│
└────────────┘     └───────────────┘     └─────────┘     └───────────────┘     └───────────────┘
                         │
                         │
                         ▼
                  ┌──────────────┐
                  │Security Scan │
                  └──────────────┘
```

### Release Workflow

```
┌─────────────────┐     ┌───────────────┐     ┌─────────────┐     ┌──────────────┐
│Calculate Version│────►│Update Files   │────►│Create Branch│────►│Create PR     │
└─────────────────┘     └───────────────┘     └─────────────┘     └──────────────┘
                                                                        │
                                                                        │ (if not draft)
                                                                        ▼
                                                                  ┌───────────────┐
                                                                  │Create Release │
                                                                  └───────────────┘
```

## Required Secrets

For these workflows to function properly, the following secrets must be configured in the repository settings:

- `RELEASE_TOKEN`: A personal access token with repo permission for creating releases and branches
- `KUBE_CONFIG_STAGING`: Kubernetes configuration for the staging environment

## Additional Resources

For more detailed information on how to use these workflows, please refer to the [CI/CD documentation](/docs/CI_CD.md).

## Architecture-Specific Workflows

### Self-Hosted Runners

The repository uses self-hosted runners for testing on specific architectures:

#### ARM64 Runners
- **Label**: `[self-hosted, arm64, dgx]`
- **Workflow**: [arm64-ci.yml](arm64-ci.yml)
- **Purpose**: Tests the package on ARM64 architecture (NVIDIA DGX systems)
- **Python Versions**: 3.8, 3.9, 3.10, 3.11
- **Features**:
  - Build-from-source capability testing
  - ARM64-specific monitoring and logging
  - Docker image building for ARM64

#### AMD64 Runners
- **Label**: `[self-hosted, amd64]`
- **Workflow**: [amd64-ci.yml](amd64-ci.yml)
- **Purpose**: Tests the package on AMD64 architecture
- **Python Versions**: 3.8, 3.9, 3.10, 3.11
- **Features**:
  - Build-from-source capability testing
  - AMD64-specific monitoring and logging
  - Docker image building for AMD64

### Multi-Architecture Testing

The [multi-arch-ci.yml](multi-arch-ci.yml) workflow provides comprehensive testing across:
- **QEMU-based testing**: amd64, arm64, armv7
- **Native self-hosted testing**: ARM64 (NVIDIA DGX), AMD64
- **Experimental RISC-V support** (manual trigger only)

### GitHub-Hosted vs Self-Hosted

| Runner Type | Workflows | Use Case |
|-------------|-----------|----------|
| GitHub-hosted (ubuntu-latest) | amd64-python-package.yml, amd64-release.yml | Standard AMD64 testing and releases |
| Self-hosted ARM64 | arm64-ci.yml, multi-arch-ci.yml | Native ARM64 testing and validation |
| Self-hosted AMD64 | amd64-ci.yml, multi-arch-ci.yml | Native AMD64 testing on custom hardware |