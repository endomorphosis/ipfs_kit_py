# Testing IPFS Kit Python

This document covers the comprehensive testing ecosystem for IPFS Kit Python.

## Test Structure

The tests are organized by components:

- `test_ipfs_core.py`: Tests for core IPFS functionality
- `test_mcp_comprehensive.py`: Tests for MCP server components
- `test_fsspec_integration.py`: Tests for FSSpec integration
- `test_storage_backends.py`: Tests for storage backends

## Running Tests

You can run all tests with:

```bash
./run_tests.sh
```

Or run a specific category:

```bash
./run_tests.sh core
```

Available categories:
- `core`: Core IPFS operations
- `mcp`: MCP Server components
- `storage`: Storage backends
- `fsspec`: FSSpec integration
- `api`: High-level API
- `tools`: Tool integrations
- `integrations`: Integration tests

Options:
- `--verbose` or `-v`: Enable verbose output
- `--parallel` or `-p`: Run tests in parallel
- `--html-report`: Generate HTML report
- `--junit-xml`: Generate JUnit XML report
- `--report-dir PATH`: Directory to store reports

## Debugging Tests

You can debug failing tests with the debug utility:

```bash
./debug_test.py test/test_file.py::test_function --pdb
```

Options:
- `--pdb`: Use Python debugger
- `--ipdb`: Use IPython debugger (if installed)
- `--trace`: Show full traceback
- `--mock`: Use mock environment
- `--no-capture`: Don't capture stdout/stderr

## Generating Reports

To generate a comprehensive HTML report:

```bash
./generate_test_report.py
```

This will generate a report from the latest test run. You can specify a different report directory with `--report-dir` and output file with `--output`.

## CI Integration

Tests are automatically run on GitHub Actions for each push and pull request. The test results are uploaded as artifacts and can be downloaded from the Actions tab on GitHub.

## Writing New Tests

When writing new tests:

1. Place them in the appropriate category file or create a new file with a `test_` prefix
2. Use the pytest fixtures provided in the conftest.py file
3. Mock external dependencies when possible
4. Add appropriate markers if your test requires specific dependencies

Example:

```python
import pytest

@pytest.mark.requires_fsspec
def test_feature_needing_fsspec():
    # Test code here
    pass
```

## Best Practices

1. Keep test functions focused on testing a single aspect
2. Ensure tests are deterministic and don't depend on external services
3. Use meaningful assertions with helpful messages
4. Clean up any resources created during tests
5. Group related tests in classes for better organization
