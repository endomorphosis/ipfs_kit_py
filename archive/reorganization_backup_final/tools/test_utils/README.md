# Test Utilities

This directory contains test utilities that are used for development and debugging purposes, but are not part of the regular test suite.

## FSSpec Integration Testing

The FSSpec integration tests verify the functionality of the high-level API's filesystem integration.

### test_fsspec_simple.py

A simple utility to test high_level_api's FSSpec integration without requiring the actual FSSpec package to be installed. It provides mock implementations of:
- `fsspec.spec.AbstractFileSystem`
- `ipfs_kit_py.ipfs_fsspec.IPFSFileSystem`

### test_fsspec_integration.py

A comprehensive test suite for the FSSpec integration in high_level_api.py. This test creates a mock environment to test the get_filesystem method. It also verifies error handling when FSSpec is not available.

### Running the Tests

To run the FSSpec integration tests:

```bash
# From the project root directory
python -m tools.test_utils.test_fsspec_integration
```

## Why Separate from Main Test Suite?

These tests are kept separate from the main test suite because:

1. They have special import requirements that can interfere with the normal test discovery process
2. They mock core libraries in ways that might affect other tests if run in the same process
3. They're primarily used for development and debugging, not for continuous integration

## Adding New Test Utilities

When adding new test utilities:

1. Add a clear docstring explaining the purpose of the utility
2. Add a section to this README explaining how to use it
3. Include sample code or instructions for running the utility
4. If it mocks libraries or overrides imports, add a note about potential side effects