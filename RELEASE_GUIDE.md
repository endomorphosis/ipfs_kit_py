# Release Guide for IPFS Kit v0.2.0

## Overview

This document provides a step-by-step guide to complete the release process for IPFS Kit version 0.2.0. The tag `v0.2.0` has already been created and pushed to the repository.

## Step 1: Create the GitHub Release

### Method 1: Using the GitHub Web UI

1. Go to the GitHub repository: https://github.com/endomorphosis/ipfs_kit_py
2. Navigate to "Releases" in the repository sidebar
3. Click on "Create a new release"
4. In the "Choose a tag" dropdown, select the existing tag `v0.2.0`
5. Set the release title as "Release v0.2.0"
6. Copy and paste the following content in the description:

```markdown
# Release v0.2.0

This release adds WebRTC streaming capabilities, performance optimizations, and several advanced features for improved data handling.

## Key Features

### WebRTC Streaming
- WebRTC streaming for media content from IPFS
- Real-time WebSocket notification system
- Performance benchmarking system for WebRTC streaming

### Advanced Performance Optimizations
- Schema and column optimization for ParquetCIDCache
- Advanced partitioning strategies
- Parallel query execution for analytical operations
- Probabilistic data structures (BloomFilter, HyperLogLog, CountMinSketch, etc.)

### Improved Documentation and Stability
- Comprehensive documentation for all new features
- Fixed syntax errors in test files for better stability
- Improved FSSpec integration in high_level_api.py

## Installation

### Using with pip
```bash
pip install ipfs_kit_py==0.2.0
```

### Using with Docker
```bash
docker pull ghcr.io/endomorphosis/ipfs_kit_py:0.2.0
```

See [CHANGELOG.md](https://github.com/endomorphosis/ipfs_kit_py/blob/main/CHANGELOG.md) for complete details on all changes.
```

7. Choose whether this is a pre-release or not (typically not for a version like 0.2.0)
8. Click "Publish release"

### Method 2: Using the GitHub CLI

If you have the GitHub CLI installed and authenticated, run:

```bash
gh release create v0.2.0 \
  --title "Release v0.2.0" \
  --notes-file release_notes.md \
  --repo endomorphosis/ipfs_kit_py
```

### Method 3: Using the GitHub API

If you prefer to use the GitHub API, you can run:

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/endomorphosis/ipfs_kit_py/releases \
  -d @release_body.json
```

Where `release_body.json` contains the payload with the release information.

## Step 2: Verify GitHub Actions Workflows

The tag push should have triggered several GitHub Actions workflows:

1. **Python Package Workflow**: This will run tests and publish the package to PyPI
2. **Docker Build Workflow**: This will build and publish the Docker image to GitHub Container Registry
3. **Helm Chart Publication**: This will package and publish the Helm chart

You can check the status of these workflows in the "Actions" tab of the GitHub repository.

## Step 3: Verify Package Publication

1. **Check PyPI**: Verify that the new version is available on PyPI:
   ```bash
   pip install ipfs_kit_py==0.2.0
   ```
   or visit https://pypi.org/project/ipfs_kit_py/

2. **Check Docker Image**: Verify that the Docker image is available:
   ```bash
   docker pull ghcr.io/endomorphosis/ipfs_kit_py:0.2.0
   ```

3. **Check Helm Chart**: If applicable, verify that the Helm chart is available.

## Step 4: Update Documentation

If there are any live documentation sites or wikis, make sure they are updated to reflect the new version.

## Step 5: Announce the Release

Consider announcing the release through appropriate channels:
- Project mailing list
- Social media
- Related community forums or chat platforms

## Troubleshooting

If any of the automated processes fail:

1. **PyPI Publication Failure**: Manually build and publish the package:
   ```bash
   python -m build
   python -m twine upload dist/*
   ```

2. **Docker Build Failure**: Manually build and push the Docker image:
   ```bash
   docker build -t ghcr.io/endomorphosis/ipfs_kit_py:0.2.0 .
   docker push ghcr.io/endomorphosis/ipfs_kit_py:0.2.0
   ```

3. **Helm Chart Failure**: Manually package and publish the Helm chart:
   ```bash
   helm package helm/ipfs-kit --destination ./helm-dist
   ```

## Next Steps After Release

1. Start planning for the next release.
2. Create an "Unreleased" section in the CHANGELOG.md file.
3. Collect feedback from users on the new release.