# Backend Testing Guide

**Version**: 2.0  
**Last Updated**: February 2, 2026  
**Related**: [BACKEND_TESTS_IMPLEMENTATION.md](../BACKEND_TESTS_IMPLEMENTATION.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Test Organization](#test-organization)
4. [Running Tests](#running-tests)
5. [Mock Mode Configuration](#mock-mode-configuration)
6. [Writing New Tests](#writing-new-tests)
7. [Shared Fixtures](#shared-fixtures)
8. [Best Practices](#best-practices)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

---

## Overview

This repository uses comprehensive test suites to ensure reliable backend implementations. Tests are organized into:

- **Unit Tests** (`tests/unit/`): Fast, isolated tests with mocked dependencies
- **Integration Tests** (`tests/integration/`): Tests with real or simulated services
- **Error Handling Tests**: Cross-cutting error scenario tests

### Coverage Goals

| Test Type | Current | Target |
|-----------|---------|--------|
| Unit Tests | 70% | 80%+ |
| Integration Tests | 50% | 70%+ |
| Error Handling | 60% | 80%+ |

---

## Quick Start

### Install Dependencies

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-asyncio pytest-mock

# Install backend-specific dependencies (optional)
pip install paramiko  # For SSHFS tests
pip install ftplib    # For FTP tests (built-in)
pip install requests  # For HTTP-based backends
```

### Run All Tests

```bash
# Run all backend tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=ipfs_kit_py --cov-report=html

# Run specific backend tests
pytest tests/unit/test_sshfs_kit.py -v
```

### Run in Mock Mode (Default)

```bash
# Mock mode is enabled by default
pytest tests/unit/ -v

# Explicitly enable mock mode
SSHFS_MOCK_MODE=true FTP_MOCK_MODE=true pytest tests/unit/ -v
```

---

## Test Organization

### Directory Structure

```
tests/
├── unit/                           # Unit tests
│   ├── test_sshfs_kit.py          # SSHFSKit tests (40+ tests)
│   ├── test_ftp_kit.py            # FTPKit tests (45+ tests)
│   ├── test_filecoin_backend_extended.py  # Filecoin tests (30+ tests)
│   ├── test_lassie_kit_extended.py        # Lassie tests (35+ tests)
│   ├── test_huggingface_kit_extended.py   # HuggingFace tests (40+ tests)
│   └── test_backend_error_handling.py     # Universal error tests
├── integration/                    # Integration tests
│   ├── test_ipfs_backend.py
│   ├── test_s3_backend.py
│   └── ...
├── backend_fixtures.py            # Shared test fixtures
└── README_TESTING.md              # This file
```

### Test Naming Convention

- **Files**: `test_<backend>_<type>.py`
- **Classes**: `Test<Backend><Feature>`
- **Methods**: `test_<action>_<scenario>`

**Examples**:
```python
# File: test_sshfs_kit.py
class TestSSHFSKitConnection:
    def test_connect_with_key_auth(self): ...
    def test_connect_failure_handling(self): ...

class TestSSHFSKitFileOperations:
    def test_upload_file(self): ...
    def test_download_file(self): ...
```

---

## Running Tests

### Run Specific Test Suites

```bash
# Run all SSHFSKit tests
pytest tests/unit/test_sshfs_kit.py -v

# Run all FTPKit tests  
pytest tests/unit/test_ftp_kit.py -v

# Run all Filecoin tests
pytest tests/unit/test_filecoin_backend_extended.py -v

# Run all Lassie tests
pytest tests/unit/test_lassie_kit_extended.py -v

# Run all HuggingFace tests
pytest tests/unit/test_huggingface_kit_extended.py -v

# Run error handling tests
pytest tests/unit/test_backend_error_handling.py -v
```

### Run Specific Test Classes

```bash
# Run only initialization tests
pytest tests/unit/test_sshfs_kit.py::TestSSHFSKitInitialization -v

# Run only error handling tests
pytest tests/unit/test_ftp_kit.py::TestFTPKitErrorHandling -v
```

### Run Specific Test Methods

```bash
# Run a single test
pytest tests/unit/test_sshfs_kit.py::TestSSHFSKitInitialization::test_init_with_key_auth -v
```

### Run with Coverage

```bash
# Generate coverage report
pytest tests/unit/ \
  --cov=ipfs_kit_py.sshfs_kit \
  --cov=ipfs_kit_py.ftp_kit \
  --cov=ipfs_kit_py.lassie_kit \
  --cov-report=html \
  --cov-report=term

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run with Markers

```bash
# Run only slow tests
pytest tests/unit/ -m slow -v

# Skip slow tests
pytest tests/unit/ -m "not slow" -v

# Run only mock mode tests
pytest tests/unit/ -m mock -v
```

---

## Mock Mode Configuration

### Environment Variables

Each backend has its own mock mode control:

| Backend | Environment Variable | Default |
|---------|---------------------|---------|
| SSHFS | `SSHFS_MOCK_MODE` | `true` |
| FTP | `FTP_MOCK_MODE` | `true` |
| Filecoin | `FILECOIN_MOCK_MODE` | `true` |
| Lassie | `LASSIE_MOCK_MODE` | `true` |
| HuggingFace | `HF_MOCK_MODE` | `true` |
| S3 | `S3_MOCK_MODE` | `true` |
| IPFS | `IPFS_MOCK_MODE` | `true` |

### Enable Mock Mode (Default)

```bash
# Run with mock mode (safe for CI/CD)
pytest tests/unit/ -v

# Explicitly enable
SSHFS_MOCK_MODE=true pytest tests/unit/test_sshfs_kit.py -v
```

### Disable Mock Mode (Requires Real Services)

```bash
# Run with real backend (requires services running)
SSHFS_MOCK_MODE=false pytest tests/unit/test_sshfs_kit.py -v

# Disable for all backends
SSHFS_MOCK_MODE=false \
FTP_MOCK_MODE=false \
FILECOIN_MOCK_MODE=false \
  pytest tests/unit/ -v
```

### When to Use Each Mode

**Mock Mode** (Default):
- ✅ CI/CD pipelines
- ✅ Fast local development
- ✅ No external dependencies
- ✅ Predictable results

**Real Mode**:
- ✅ Integration testing
- ✅ Performance testing
- ✅ Verifying real behavior
- ❌ Requires services running
- ❌ Slower execution
- ❌ May have flaky results

---

## Writing New Tests

### Test Template

```python
"""
Unit tests for NewBackend

Description of what this backend does and what we're testing.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from ipfs_kit_py.new_backend import NewBackend

# Import shared fixtures
from tests.backend_fixtures import (
    temp_dir,
    temp_file,
    test_content_string,
    test_metadata
)

# Test configuration
MOCK_MODE = os.environ.get("NEW_BACKEND_MOCK_MODE", "true").lower() == "true"


@pytest.fixture
def backend_config():
    """Provide configuration for NewBackend."""
    return {
        "host": "test.example.com",
        "port": 1234,
        "timeout": 30
    }


@pytest.fixture
def new_backend(backend_config):
    """Create NewBackend instance for testing."""
    backend = NewBackend(**backend_config)
    return backend


class TestNewBackendInitialization:
    """Test initialization and configuration."""
    
    def test_init_basic(self, backend_config):
        """Test basic initialization."""
        backend = NewBackend(**backend_config)
        
        assert backend is not None
        assert backend.host == backend_config["host"]
        assert backend.port == backend_config["port"]


class TestNewBackendOperations:
    """Test main operations."""
    
    @pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
    def test_store_content(self, new_backend, test_content_string):
        """Test storing content."""
        result = new_backend.store(test_content_string)
        
        assert isinstance(result, dict)
        assert result.get("success") is True


class TestNewBackendErrorHandling:
    """Test error handling."""
    
    def test_invalid_input(self, new_backend):
        """Test handling of invalid input."""
        with pytest.raises(ValueError):
            new_backend.store(None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

### Best Practices

1. **Use Shared Fixtures**: Import from `tests/backend_fixtures.py`
2. **Mock External Services**: Use `@pytest.mark.skipif(not MOCK_MODE)`
3. **Test Error Scenarios**: Include negative test cases
4. **Clean Up Resources**: Use fixtures with proper teardown
5. **Document Tests**: Add docstrings to all test methods
6. **Use Parametrize**: For testing multiple scenarios

### Example Parametrized Test

```python
import pytest
from tests.backend_fixtures import INVALID_INPUTS

class TestInputValidation:
    
    @pytest.mark.parametrize("name,value", INVALID_INPUTS)
    def test_invalid_inputs(self, backend, name, value):
        """Test various invalid inputs."""
        with pytest.raises((ValueError, TypeError)):
            backend.process(value)
```

---

## Shared Fixtures

### Available Fixtures

Located in `tests/backend_fixtures.py`:

**File Fixtures**:
- `temp_dir` - Temporary directory (auto-cleanup)
- `temp_file` - Temporary text file
- `temp_binary_file` - Temporary binary file
- `large_temp_file` - 10MB test file

**Data Fixtures**:
- `test_content_string` - Test string content
- `test_content_binary` - Test binary content
- `test_content_large` - 1MB test content
- `test_cids` - Sample CIDs (v0, v1, invalid)
- `test_metadata` - Test metadata dict

**Mock Fixtures**:
- `mock_http_success` - Mock 200 response
- `mock_http_not_found` - Mock 404 response
- `mock_http_server_error` - Mock 500 response

**Helper Functions**:
- `assert_result_dict(result, expected_success)` - Validate result format
- `assert_valid_cid(cid)` - Validate CID format
- `get_mock_mode(backend_name)` - Get mock mode for backend

### Using Shared Fixtures

```python
def test_with_shared_fixtures(temp_file, test_content_string, test_metadata):
    """Example using shared fixtures."""
    # temp_file is auto-created and cleaned up
    with open(temp_file, 'r') as f:
        content = f.read()
    
    # test_content_string is ready to use
    assert test_content_string == "Test content for backend storage"
    
    # test_metadata has standard fields
    assert "type" in test_metadata
```

---

## Best Practices

### 1. Test Structure

- **Arrange**: Set up test data and mocks
- **Act**: Execute the operation being tested
- **Assert**: Verify the results

```python
def test_operation(backend, test_content):
    # Arrange
    mock_response = Mock()
    mock_response.status_code = 200
    
    # Act
    with patch('requests.post', return_value=mock_response):
        result = backend.store(test_content)
    
    # Assert
    assert result["success"] is True
```

### 2. Error Testing

Test both success and failure paths:

```python
def test_success_case(backend):
    """Test successful operation."""
    result = backend.operation()
    assert result["success"] is True

def test_failure_case(backend):
    """Test failed operation."""
    with patch('external_call', side_effect=Exception("Error")):
        result = backend.operation()
        assert result["success"] is False
        assert "error" in result
```

### 3. Resource Cleanup

Always clean up created resources:

```python
@pytest.fixture
def backend_with_tracking():
    """Backend with resource tracking."""
    backend = Backend()
    created_resources = []
    
    yield backend, created_resources
    
    # Cleanup
    for resource in created_resources:
        try:
            backend.delete(resource)
        except:
            pass  # Best effort cleanup
```

### 4. Mock External Dependencies

Mock network calls, file system operations, and external APIs:

```python
@pytest.mark.skipif(not MOCK_MODE, reason="Requires mock mode")
def test_network_operation(backend):
    """Test operation with mocked network."""
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        result = backend.fetch_data()
        assert result is not None
```

### 5. Use Descriptive Names

```python
# Good
def test_upload_file_with_invalid_path_raises_error():
    ...

# Bad
def test_upload():
    ...
```

---

## CI/CD Integration

### GitHub Actions

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run unit tests (mock mode)
        env:
          SSHFS_MOCK_MODE: true
          FTP_MOCK_MODE: true
          FILECOIN_MOCK_MODE: true
          LASSIE_MOCK_MODE: true
          HF_MOCK_MODE: true
        run: |
          pytest tests/unit/ -v --cov=ipfs_kit_py --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Local Pre-commit

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run tests before commit
pytest tests/unit/ -v -x

# Check exit code
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
```

---

## Troubleshooting

### Tests Fail with "Module not found"

**Solution**: Install the package in editable mode:
```bash
pip install -e .
```

### Tests Hang or Timeout

**Cause**: Trying to connect to real services in mock mode.

**Solution**: Verify mock mode is enabled:
```bash
pytest tests/unit/test_sshfs_kit.py -v -s  # Check output
SSHFS_MOCK_MODE=true pytest tests/unit/test_sshfs_kit.py -v
```

### Mock Not Working

**Cause**: Mock patch target is incorrect.

**Solution**: Patch where the object is used, not where it's defined:
```python
# Wrong
with patch('paramiko.SSHClient'):
    ...

# Right  
with patch('ipfs_kit_py.sshfs_kit.paramiko.SSHClient'):
    ...
```

### Fixture Not Found

**Cause**: Fixture not imported or not in scope.

**Solution**: Import from backend_fixtures:
```python
from tests.backend_fixtures import temp_dir, temp_file
```

### Tests Pass Locally But Fail in CI

**Cause**: Different environment or missing dependencies.

**Solution**:
1. Check CI logs for specific errors
2. Verify all dependencies in requirements.txt
3. Ensure mock mode is enabled in CI
4. Check for filesystem path differences

---

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [Backend Architecture Review](../FILESYSTEM_BACKEND_ARCHITECTURE_REVIEW.md)
- [Backend Tests Implementation](../BACKEND_TESTS_IMPLEMENTATION.md)

---

## Contributing

### Adding New Backend Tests

1. Create test file: `tests/unit/test_<backend>_kit.py`
2. Use template from this guide
3. Add environment variable for mock mode
4. Include in CI/CD configuration
5. Update this documentation

### Reporting Issues

If tests fail unexpectedly:
1. Run with `-v` flag for verbose output
2. Check mock mode configuration
3. Verify dependencies are installed
4. Create an issue with full error output

---

**Version**: 2.0  
**Maintained by**: Backend Team  
**Last Updated**: February 2, 2026
