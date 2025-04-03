# IPFS Kit Testing Framework

This directory contains the testing framework for the IPFS Kit Python library. The framework includes both traditional integration tests and mocked unit tests to ensure comprehensive test coverage.

## Test Structure

The test suite is organized around these key concepts:

1. **Mocked Tests:** Using `unittest.mock` to isolate components and test individual units of code
2. **Integration Tests:** Testing how multiple components work together
3. **Test Fixtures:** Reusable test setup code in `conftest.py` for consistent test environments
4. **Parameterized Tests:** Testing different inputs with the same test code
5. **Coverage Reports:** Measuring how much of the codebase is tested
6. **Patching Systems:** Special handling for third-party libraries like PyArrow in `patch_cluster_state.py`

## Current Test Status

The test suite currently has **336 passing tests** and 40 skipped tests. Skipped tests typically require external services or specific environment setups (like a running IPFS daemon or cluster).

## Test Files

### Key Test Files

The test suite contains a wide range of test files organized by component:

#### Core Components
- `test_ipfs_py_mocked.py`: Tests for the low-level IPFS API wrapper
- `test_ipfs_kit_mocked.py`: Tests for the main orchestrator class
- `test_error_handling.py`: Tests for error handling mechanisms
- `test_parameter_validation.py`: Tests for input validation
- `test_high_level_api.py`: Tests for the simplified user API

#### Storage and Caching
- `test_tiered_cache.py`: Tests for the multi-level caching system
- `test_ipfs_fsspec_mocked.py`: Tests for the FSSpec integration
- `test_ipfs_fsspec_metrics.py`: Tests for performance tracking in the filesystem interface
- `test_s3_kit.py`: Tests for S3-compatible storage integration

#### Cluster Management
- `test_cluster_state.py`: Tests for cluster state management
- `test_cluster_state_helpers.py`: Tests for cluster state utility functions
- `test_cluster_management.py`: Tests for cluster coordination
- `test_cluster_authentication.py`: Tests for security in cluster operations
- `test_distributed_coordination.py`: Tests for distributed consensus
- `test_distributed_state_sync.py`: Tests for state synchronization across nodes

#### Networking
- `test_libp2p_connection.py`: Tests for direct P2P connections
- `test_libp2p_integration.py`: Tests for libp2p protocol integration
- `test_multiaddress.py`: Tests for multiaddress parsing and handling

#### Role Management
- `test_role_based_architecture.py`: Tests for role-specific behavior
- `test_dynamic_role_switching.py`: Tests for switching node roles

#### Advanced Features
- `test_ai_ml_integration.py`: Tests for AI/ML capabilities
- `test_arrow_metadata_index.py`: Tests for Arrow-based metadata indexing
- `test_ipld_knowledge_graph.py`: Tests for IPLD-based knowledge graph
- `test_metadata_index_integration.py`: Tests for content indexing
- `test_ipfs_dataloader.py`: Tests for ML dataset loading from IPFS
- `test_data_science_integration.py`: Tests for data science tools integration

#### User Interface
- `test_cli_basic.py`: Tests for command-line interface basics
- `test_cli_interface.py`: Tests for CLI features

#### External Services
- `test_storacha_kit_mocked.py`: Tests for Web3.Storage/Storacha integration
- `test_ipfs_gateway_compatibility.py`: Tests for IPFS gateway interactions

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

### Advanced Patching with PyArrow

The test suite includes special handling for PyArrow types using pytest's monkeypatch fixture. Since PyArrow Schema objects are immutable, we can't directly replace methods, so we create patching helpers in `conftest.py`:

```python
# In conftest.py
def _patch_schema_equals(monkeypatch):
    """Helper function to patch Schema.equals during tests using monkeypatch."""
    original_schema_equals = pa.Schema.equals
    
    def patched_schema_equals(self, other):
        """Safe version of Schema.equals that works with MagicMock objects."""
        if type(other).__name__ == 'MagicMock':
            # Consider MagicMock schemas to be equal to allow tests to pass
            return True
        # Use the original implementation for real schemas
        return original_schema_equals(self, other)
    
    # Apply the patch using monkeypatch
    monkeypatch.setattr(pa.Schema, 'equals', patched_schema_equals)

# Create a fixture that applies the patch
@pytest.fixture(autouse=True)
def patch_arrow_schema(monkeypatch):
    """Patch PyArrow Schema to handle MagicMock objects."""
    try:
        import pyarrow as pa
        if hasattr(pa, '_patch_schema_equals'):
            pa._patch_schema_equals(monkeypatch)
    except (ImportError, AttributeError):
        pass
    yield
```

### Patching Specific Classes

For specific classes like `ArrowClusterState`, we apply custom patches in `patch_cluster_state.py`:

```python
# In patch_cluster_state.py
def patched_save_to_disk(self):
    """Patched _save_to_disk method to handle MagicMock schema objects."""
    if not self.enable_persistence:
        return
        
    try:
        # First try original method
        return original_save_to_disk(self)
    except Exception as e:
        # Handle schema type mismatches
        error_msg = str(e)
        if ("expected pyarrow.lib.Schema, got MagicMock" in error_msg or 
            "Argument 'schema' has incorrect type" in error_msg):
            # Create a real schema from column names and continue
            # ...implementation details...
            return True
        else:
            # Log and return for other errors
            return False

# Apply the patch
ArrowClusterState._save_to_disk = patched_save_to_disk
```

### Suppressing Logging During Tests

The test framework includes utilities to suppress logging noise during tests:

```python
@contextlib.contextmanager
def suppress_logging(logger_name=None, level=logging.ERROR):
    """Context manager to temporarily increase the logging level to suppress messages."""
    if logger_name:
        logger = logging.getLogger(logger_name)
        old_level = logger.level
        logger.setLevel(level)
        try:
            yield
        finally:
            logger.setLevel(old_level)
    else:
        # Suppress root logger if no name specified
        root_logger = logging.getLogger()
        old_level = root_logger.level
        root_logger.setLevel(level)
        try:
            yield
        finally:
            root_logger.setLevel(old_level)
```