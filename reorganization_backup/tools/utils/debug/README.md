# Debug Utilities

This directory contains debugging scripts used for troubleshooting and analyzing various components of the ipfs_kit_py project. These scripts are primarily used during development and debugging rather than as part of the formal test suite.

## Available Scripts

- **debug_high_level_api.py**: Debugging tool for the high-level API
- **debug_ipfs_model.py**: Tests the IPFS model's check_daemon_status method
- **debug_lotus_client.py**: Debugging utility for the Lotus client interaction
- **debug_prefetch.py**: Analyze and debug the prefetch functionality

## Usage

These scripts can be run directly from the command line. For example:

```bash
python utils/debug/debug_ipfs_model.py
```

Some of these scripts produce detailed logs that can be used to diagnose issues.

## Note

These utilities are not formal tests and are not intended to be run as part of the automated test suite. For formal tests, please use the test directory.