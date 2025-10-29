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
| **Workflow Auto-Fix** | [workflow-failure-autofix.yml](workflow-failure-autofix.yml) | **Automatically detects workflow failures and creates PRs for fixes** |
| **Copilot Auto-Fix** | [copilot-auto-fix.yml](copilot-auto-fix.yml) | **Triggers GitHub Copilot to implement workflow fixes** |

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

## Workflow Failure Auto-Fix System 🤖

This repository includes an automated system that detects workflow failures and helps fix them:

### How It Works

1. **Automatic Detection**: When any workflow fails, the system automatically creates:
   - An issue documenting the failure
   - A draft PR with context for fixing
   - Context files for GitHub Copilot

2. **GitHub Copilot Integration**: You can use GitHub Copilot to automatically fix workflows:
   - Open the auto-created PR in GitHub Copilot Workspace
   - Ask Copilot to analyze and fix the failure
   - Or comment `@copilot /fix-workflow` on the issue

3. **Manual Fixes**: Traditional manual fixing is still supported with enhanced context

### Quick Start

When a workflow fails:
1. Check for auto-created issue with label `workflow-failure`
2. Find the linked draft PR
3. Either:
   - Use GitHub Copilot Workspace to implement the fix
   - Comment `@copilot /fix-workflow` on the issue
   - Manually implement the fix

For detailed documentation, see [WORKFLOW_AUTOFIX.md](WORKFLOW_AUTOFIX.md)

## Additional Resources

For more detailed information on how to use these workflows, please refer to the [CI/CD documentation](/docs/CI_CD.md).