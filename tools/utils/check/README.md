# Check Utilities

This directory contains utility scripts used for checking and validating various aspects of the ipfs_kit_py project. These scripts are primarily used during development and troubleshooting rather than as part of the formal test suite.

## Available Scripts

- **check_and_fix_storage_backends.py**: Validates and fixes storage backend configurations
- **check_api.py**: Tests API endpoints accessibility and functionality
- **check_high_level_api_syntax.py**: Verifies syntax of high_level_api.py without executing
- **check_libp2p_availability.py**: Checks libp2p library availability and compatibility
- **check_lotus_path.py**: Validates Lotus installation and environment configuration
- **check_server.py**: Tests server connectivity and status
- **check_syntax.py**: Advanced syntax validation for Python modules
- **check_syntax_simple.py**: Simple syntax validation for Python modules
- **check_webrtc_deps.py**: Validates WebRTC dependencies

## Usage

These scripts can be run directly from the command line. For example:

```bash
python utils/check/check_api.py
```

## Note

These utilities are not formal tests and are not intended to be run as part of the automated test suite. For formal tests, please use the test directory.