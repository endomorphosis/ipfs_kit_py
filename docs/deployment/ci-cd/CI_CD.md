# CI/CD Pipeline Documentation

This document describes the comprehensive CI/CD (Continuous Integration/Continuous Deployment) pipeline for the IPFS Kit Python project.

## Overview

The IPFS Kit Python project uses GitHub Actions to automate testing, building, publishing, and deploying the software. The CI/CD pipeline ensures:

1. Code quality through automated testing and linting
2. Security through dependency scanning and container image scanning
3. Automated releases for Python packages, Docker images, and Helm charts
4. Continuous documentation updates
5. Automated dependency management

## Workflow Files

The CI/CD pipeline consists of multiple workflow files located in the `.github/workflows/` directory:

| Workflow File | Purpose |
|---------------|---------|
| `workflow.yml` | Main Python package testing, building, and publishing |
| `docker.yml` | Docker image building, testing, and publishing |
| `release.yml` | Automated release management |
| `dependencies.yml` | Dependency scanning and updates |
| `pages.yml` | Documentation and Helm chart publishing |

## Main Workflow (`workflow.yml`)

The main workflow handles Python package testing, building, and publishing:

### Triggers
- Push to `main` or `master` branches
- Pull requests to `main` or `master` branches
- Tags starting with `v` (for releases)

### Jobs

#### 1. Test
- Runs tests on multiple Python versions (3.8, 3.9, 3.10, 3.11)
- Uses `pytest` to run the test suite

#### 2. Lint
- Checks code formatting with `black`
- Checks import sorting with `isort`

#### 3. Build
- Builds distribution packages (wheel and source)
- Uploads artifacts for publishing

#### 4. Publish to PyPI
- Runs when a tag is pushed with the format `v*` (e.g., `v0.1.0`)
- Publishes the package to PyPI using trusted publishing

#### 5. Publish to TestPyPI
- Runs on pushes to `main` or `master` branches
- Publishes the package to TestPyPI for testing before official release

## Docker Workflow (`docker.yml`)

Handles Docker image building, testing, and publishing:

### Triggers
- Push to `main` or `master` branches
- Pull requests to `main` or `master` branches
- Tags starting with `v` (for releases)
- Manual triggering

### Jobs

#### 1. Docker Lint
- Lints Dockerfile and docker-compose.yml using hadolint
- Checks for best practices and potential issues

#### 2. Build and Test
- Builds Docker image for testing
- Runs container tests to ensure the image works properly
- Performs security scanning with Trivy

#### 3. Publish
- Publishes Docker image to GitHub Container Registry (ghcr.io)
- Tags images based on:
  - Branch name (for main/master)
  - Semantic version (for tags)
  - Short SHA (for all builds)
- Builds multi-platform images for both AMD64 and ARM64

#### 4. Helm Lint
- Validates Helm chart syntax and structure

#### 5. Deploy to Staging
- Deploys to Kubernetes staging environment on pushes to main/master
- Uses Helm for deployment
- Verifies deployment success

## Release Workflow (`release.yml`)

Automates the release process:

### Triggers
- Manual triggering with inputs for version and release type

### Inputs
- `version`: Specific version to release (optional)
- `release_type`: Type of release (patch, minor, major)
- `draft`: Whether to create a draft release

### Jobs

#### 1. Prepare Release
- Calculates new version based on release type or uses specified version
- Updates version in files (pyproject.toml, setup.py)
- Updates CHANGELOG.md
- Creates release branch and pull request
- Creates release tag and GitHub release

## Dependencies Workflow (`dependencies.yml`)

Manages dependencies and security:

### Triggers
- Weekly schedule (Monday at 7:00 UTC)
- Manual triggering

### Jobs

#### 1. Check Dependencies
- Runs safety check for security vulnerabilities
- Checks for dependency updates using pip-compile
- Creates pull request for dependency updates if available
- Includes detailed information about changes and security issues

## Pages Workflow (`pages.yml`)

Publishes documentation and Helm charts:

### Triggers
- Push to `main` or `master` branches (only for specific paths)
- Manual triggering

### Jobs

#### 1. Build Documentation
- Builds documentation using MkDocs
- Generates API documentation
- Packages Helm charts and creates Helm repository
- Deploys to GitHub Pages

## How to Use the CI/CD Pipeline

### For Regular Development

1. Create a feature branch from `main`
2. Make changes and push to your branch
3. Create a pull request to `main`
4. The CI pipeline will automatically run tests and linting
5. Once approved and merged, the changes will be included in the next release

### For Releasing a New Version

#### Automated Release (Recommended)

1. Go to the Actions tab in the GitHub repository
2. Select the "Release Management" workflow
3. Click "Run workflow"
4. Choose the release type (patch, minor, major) or specify a version
5. Choose whether to create a draft release
6. Click "Run workflow"
7. The workflow will create a PR for the release
8. Once the PR is approved and merged, the release will be automatically published

#### Manual Release

1. Update version in pyproject.toml and setup.py
2. Update CHANGELOG.md
3. Commit changes and push
4. Create a tag with the version number (e.g., `v0.1.0`)
5. Push the tag
6. The CI pipeline will automatically build and publish the release

### For Updating Dependencies

1. Go to the Actions tab in the GitHub repository
2. Select the "Dependency Management" workflow
3. Click "Run workflow"
4. Review and approve the automatically created PR

## Environment Variables and Secrets

The CI/CD pipeline requires the following secrets to be configured:

| Secret | Purpose |
|--------|---------|
| `GITHUB_TOKEN` | Automatically provided by GitHub Actions |
| `RELEASE_TOKEN` | Personal access token with repo scope for release automation |
| `KUBE_CONFIG_STAGING` | Kubernetes configuration for staging environment |

## Best Practices

1. Always write tests for new features
2. Keep dependencies up to date by approving dependency update PRs
3. Follow semantic versioning for releases
4. Include detailed information in CHANGELOG.md
5. Review automated PRs carefully

## Troubleshooting

### Common Issues

#### Failed Tests
- Check the test logs for details
- Run tests locally to debug: `pytest -xvs`

#### Failed Dependency Updates
- Check for incompatible dependencies
- Manually update problematic dependencies

#### Failed Docker Builds
- Check the Docker build logs
- Try building locally: `docker build -t ipfs-kit-py:test .`

#### Failed Deployments
- Check Kubernetes logs
- Verify credentials and configuration

### Getting Help

If you encounter issues with the CI/CD pipeline, please:

1. Check the workflow logs in the GitHub Actions tab
2. Review this documentation for guidance
3. Create an issue in the GitHub repository if the problem persists