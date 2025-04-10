# LibP2P Testing and Dependency Management

This document describes how to properly handle libp2p dependencies for testing and development.

## LibP2P Dependency Installation

The libp2p functionality in ipfs_kit_py requires several dependencies that must be installed for full functionality. The test suite is designed to handle both scenarios:

1. When dependencies are installed: Tests use mocks but can verify actual functionality
2. When dependencies are missing: Tests still run, but skip sections that require the actual dependencies

### Environment Variables for Dependency Control

You can control dependency installation behavior with these environment variables:

- `IPFS_KIT_AUTO_INSTALL_DEPS=1`: Automatically install missing dependencies during testing
- `IPFS_KIT_FORCE_INSTALL_DEPS=1`: Reinstall all dependencies even if some are already available
- `IPFS_KIT_TEST_ACTUAL_DEPS=1`: Run tests that check the actual dependency status

### Required Dependencies

The following dependencies are required for full libp2p functionality:

- `libp2p`: Main libp2p protocol implementation
- `multiaddr`: Multiaddress parsing and handling
- `base58`: Base58 encoding/decoding for CIDs
- `cryptography`: Cryptographic operations for libp2p

### Optional Dependencies

These optional dependencies enhance libp2p functionality:

- `google-protobuf`: Protocol buffer support for advanced protocols
- `eth-hash`: For Ethereum hash functionality (optional)
- `eth-keys`: For Ethereum key handling (optional)

## Installing Dependencies

There are several ways to install the LibP2P dependencies:

### 1. Using Package Extras (Recommended)

The simplest way to install all required dependencies is by using the package extras:

```bash
# For regular installation:
pip install ipfs_kit_py[libp2p]

# For development mode (when working on the codebase):
pip install -e ".[libp2p]"
```

This will install all required and optional dependencies for LibP2P functionality.

### 2. Using Environment Variables for Auto-installation

You can also let the package auto-install dependencies when needed:

```bash
# Enable auto-installation
export IPFS_KIT_AUTO_INSTALL_DEPS=1

# Force reinstallation if needed
export IPFS_KIT_FORCE_INSTALL_DEPS=1
```

### 3. Manual Installation

You can install dependencies manually:

```bash
pip install libp2p multiaddr base58 cryptography
```

For optional dependencies:

```bash
pip install google-protobuf eth-hash eth-keys
```

## Running Tests with Dependency Handling

The test suite integrates with the `install_libp2p.py` script to properly handle dependencies. You can run the tests in different modes:

### Without Installing Dependencies

```bash
# Run tests with mocks, even if dependencies are missing
python -m pytest test/test_mcp_libp2p_model.py
```

### Auto-Installing Dependencies

```bash
# Run tests with auto-installation of missing dependencies
IPFS_KIT_AUTO_INSTALL_DEPS=1 python -m pytest test/test_mcp_libp2p_model.py
```

### Force Reinstallation

```bash
# Run tests and force reinstallation of all dependencies
IPFS_KIT_FORCE_INSTALL_DEPS=1 python -m pytest test/test_mcp_libp2p_model.py
```

### Testing with Actual Dependencies

```bash
# Run tests that check actual dependency status
IPFS_KIT_TEST_ACTUAL_DEPS=1 python -m pytest test/test_mcp_libp2p_model.py::test_actual_dependency_status
```

## Dependency Installation Process

When you run tests with auto-installation enabled, the following process occurs:

1. The test file imports `install_dependencies_auto` from `install_libp2p.py`
2. It checks if dependencies are already installed using `check_dependency`
3. If dependencies are missing and auto-install is enabled, it calls `install_dependencies_auto`
4. The installer first tries to install the package with extras (`ipfs_kit_py[libp2p]`)
5. If that fails, it falls back to installing individual dependencies
6. Installation results are logged and reflected in the `HAS_DEPENDENCIES` flag
7. Tests run with the appropriate mocking based on dependency status

## Programmatically Installing Dependencies

You can also install dependencies programmatically in your own code:

```python
from install_libp2p import install_dependencies_auto

# Check if dependencies are available and install if needed
success = install_dependencies_auto(force=False, verbose=True)

if success:
    print("All libp2p dependencies successfully installed!")
else:
    print("Failed to install some dependencies")
```

You can also check if the libp2p extra was installed:

```python
from ipfs_kit_py.libp2p import HAS_LIBP2P, HAS_LIBP2P_EXTRA

if HAS_LIBP2P_EXTRA:
    print("Package was installed with libp2p extras")
elif HAS_LIBP2P:
    print("libp2p dependencies are available (installed individually)")
else:
    print("libp2p dependencies are missing")
```

## Implementation Notes

The test files use several techniques to handle dependencies:

1. **Early dependency checking**: Dependencies are checked at import time
2. **Conditional imports**: Import paths are adjusted based on dependency availability
3. **Mocked dependencies**: Key classes like `IPFSLibp2pPeer` are mocked to allow tests to run without actual dependencies
4. **Flexible fixtures**: Test fixtures adapt based on dependency status
5. **Status reporting**: Dependency status is logged for transparency

## Troubleshooting

If you encounter issues with dependencies:

1. **Use package extras**: Instead of individual dependencies, try `pip install ipfs_kit_py[libp2p]`
2. **Check logs**: Look for detailed installation logs showing which dependencies failed
3. **Manual installation**: Try installing dependencies manually with `pip install libp2p multiaddr base58 cryptography`
4. **Verify paths**: Make sure the `install_libp2p.py` script is in the expected location
5. **Check permissions**: Ensure you have permissions to install packages
6. **Virtual environment**: Consider using a virtual environment to avoid system dependency conflicts
7. **Version conflicts**: If you encounter conflicts, try installing specific versions of problematic packages

### Common Issues:

#### Missing Dependencies Despite Installing with Extras

If you installed with extras but dependencies are still reported as missing:

```
WARNING: Missing libp2p dependencies despite libp2p extra being installed
```

This can happen if pip didn't correctly process the extras. Try reinstalling with:

```bash
pip uninstall -y ipfs_kit_py
pip install ipfs_kit_py[libp2p]
```

#### Dependency Version Conflicts

If you see error messages like:

```
ERROR: Cannot install libp2p>=0.1.5 and multiaddr>=0.0.9 because these package versions have conflicting dependencies.
```

Try installing the dependencies one by one with `--no-dependencies` flag:

```bash
pip install libp2p==0.1.5 --no-dependencies
pip install multiaddr==0.0.9
pip install base58==2.1.1
pip install cryptography==38.0.0
```

#### Import Errors When Running Code

If your code runs fine during tests but fails with import errors in production:

```python
ImportError: No module named 'libp2p'
```

Make sure you're properly handling the dependency check in your code:

```python
from ipfs_kit_py.libp2p import HAS_LIBP2P

if HAS_LIBP2P:
    # Use libp2p functionality
else:
    # Use fallback or display appropriate message
```