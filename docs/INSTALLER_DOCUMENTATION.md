# Installer Documentation

This repository includes installer helpers for optional dependencies used by some IPFS Kit features.

## Overview

- Installer entry points are exposed from the package root (for example: `install_ipfs`, `install_lotus`).
- These are designed to be *optional*: core library functionality and the test suite should run without requiring external daemons.

## Usage

```python
from ipfs_kit_py import install_ipfs

installer = install_ipfs()
# installer.install(...)
```

## Notes

- Some installers may download binaries or interact with the system. Review options/flags before running in CI.
