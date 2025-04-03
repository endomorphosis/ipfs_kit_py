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