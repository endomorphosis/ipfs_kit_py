# IPFS Kit Testing Framework

This directory contains the testing framework for the IPFS Kit Python library. The framework includes both traditional integration tests and mocked unit tests to ensure comprehensive test coverage.

## Test Structure

The test suite is organized around these key concepts:

1. **Mocked Tests:** Using `unittest.mock` to isolate components and test individual units of code
2. **Integration Tests:** Testing how multiple components work together
3. **Test Fixtures:** Reusable test setup code for consistent test environments
4. **Parameterized Tests:** Testing different inputs with the same test code
5. **Coverage Reports:** Measuring how much of the codebase is tested

## Test Files

### Mocked Unit Tests

These files focus on testing individual components in isolation:

- `test_ipfs_py_mocked.py`: Tests for the low-level IPFS API wrapper
- `test_ipfs_kit_mocked.py`: Tests for the main orchestrator class
- `test_storacha_kit_mocked.py`: Tests for Web3.Storage integration

### Integration Tests

These files test how components work together:

- `test_ipfs_kit.py`: Tests for the main IPFS Kit functionality
- `test_storacha_kit.py`: Tests for Web3.Storage/Storacha functionality
- `test_s3_kit.py`: Tests for S3-compatible storage integration

## Running Tests

### Running Mocked Tests

The mocked tests don't require external dependencies and can be run without an IPFS daemon:

```bash
# Run all mocked tests
python test/run_mocked_tests.py

# Run a specific test file
python test/run_mocked_tests.py test_ipfs_kit_mocked.py
```

### Running Integration Tests

The integration tests require actual IPFS and related services:

```bash
# Run all integration tests
python -m test.test

# Run a specific test
python -m test.test_ipfs_kit
```

## Test Reports

When running mocked tests with the provided runner, the following reports are generated:

1. HTML Test Report: `test/reports/test_report_<timestamp>.html`
2. Coverage Report: `test/reports/coverage/index.html`

## Creating New Tests

### Writing New Mocked Tests

1. Follow the pattern in existing test files
2. Use pytest fixtures for common setup code
3. Use `unittest.mock` to mock out dependencies
4. Focus on testing one unit of functionality at a time

Example:

```python
def test_new_functionality(ipfs_kit_instance):
    # Arrange: Configure mocks
    ipfs_kit_instance.ipfs.some_method.return_value = {"success": True, "data": "test"}
    
    # Act: Call the method being tested
    result = ipfs_kit_instance.some_new_function()
    
    # Assert: Verify the results
    assert result["success"] is True
    assert "expected_key" in result
    ipfs_kit_instance.ipfs.some_method.assert_called_once_with("expected_arg")
```

### Test Best Practices

1. **Isolated Tests**: Each test should be independent and not rely on other tests
2. **Descriptive Names**: Use descriptive test names that explain what's being tested
3. **AAA Pattern**: Arrange, Act, Assert - structure tests in these three phases
4. **Error Testing**: Test both success and error cases
5. **Edge Cases**: Test boundary conditions and unusual inputs
6. **Clean Environment**: Clean up test files and resources after tests complete

## Test Dependencies

The test framework requires these Python packages:

- pytest
- pytest-cov
- pytest-html
- pytest-mock

Install them with:

```bash
pip install pytest pytest-cov pytest-html pytest-mock
```

## Mocking Patterns

### Mocking Subprocess Calls

```python
with patch('subprocess.run') as mock_run:
    # Configure mock
    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.stdout = b'{"success": true}'
    mock_run.return_value = mock_process
    
    # Call the function that uses subprocess
    result = my_function_that_uses_subprocess()
    
    # Assert results
    assert result["success"] is True
    mock_run.assert_called_once()
```

### Mocking HTTP Requests

```python
with patch('requests.post') as mock_post:
    # Configure mock
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": "success"}
    mock_post.return_value = mock_response
    
    # Call the function
    result = my_function_that_uses_requests()
    
    # Assert
    assert result["success"] is True
    mock_post.assert_called_once_with(
        "https://expected-url.com/endpoint",
        json={"expected": "payload"}
    )
```

### Mocking Class Methods

```python
with patch.object(my_instance, 'method_name') as mock_method:
    # Configure mock
    mock_method.return_value = {"success": True}
    
    # Call function that uses the method
    result = my_instance.another_method()
    
    # Assert
    assert result["success"] is True
    mock_method.assert_called_once_with("expected_arg")
```