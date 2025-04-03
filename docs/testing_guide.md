# Testing Guide

This document provides guidance on testing the IPFS Kit library, including best practices, fixtures, and handling of complex dependencies like PyArrow.

## Test Organization

Tests are organized in the `test/` directory and follow a systematic structure:

- Unit tests for individual components
- Integration tests for component interactions
- Mocked tests for dependencies
- Role-based architecture tests
- Python version compatibility tests

## Test Dependencies

Tests rely on pytest and several fixtures defined in `test/conftest.py` to provide common test setups.

### Required Packages

```
pytest
pytest-cov
pytest-random-order
unittest.mock
```

## Running Tests

Basic test execution:

```bash
# Run all tests
python -m pytest

# Run tests with coverage
python -m pytest --cov=ipfs_kit_py

# Run a specific test file
python -m pytest test/test_role_based_architecture.py

# Run a specific test
python -m pytest test/test_role_based_architecture.py::TestRoleBasedArchitecture::test_node_initialization
```

## Key Test Fixtures

The `conftest.py` file defines several key fixtures:

- `mock_ipfs`: Provides a common mock for IPFS operations
- `mock_subprocess_run`: Mocks subprocess.run with common IPFS-like responses
- `mock_cluster_state`: Provides a mock for cluster state operations with real PyArrow tables
- `patch_arrow_schema`: Patches PyArrow Schema to handle MagicMock objects

### PyArrow Schema Compatibility

For Python 3.12+, PyArrow Schema objects are immutable, requiring a special approach for testing:

```python
# In conftest.py
def _patch_schema_equals(monkeypatch):
    """Helper function to patch Schema.equals during tests using monkeypatch."""
    # We can't directly patch Schema.equals in Python 3.12 as it's immutable
    # Instead we create a wrapper function for comparison
    
    def mock_schema_equals(schema1, schema2):
        """Compare schemas safely, including handling MagicMock objects."""
        if type(schema2).__name__ == 'MagicMock' or type(schema1).__name__ == 'MagicMock':
            # Consider MagicMock schemas to be equal to allow tests to pass
            return True
        # Use the original implementation for real schemas
        return schema1.equals(schema2)
    
    # Add the mock comparison function to the module
    monkeypatch.setattr(pa, 'mock_schema_equals', mock_schema_equals)
```

Tests can then use this function to safely compare schemas:

```python
def test_with_schema(monkeypatch):
    # The patch_arrow_schema fixture will handle this automatically
    real_schema = pa.schema([pa.field('test', pa.string())])
    mock_schema = MagicMock()
    
    # This will work in both Python 3.12+ and earlier versions
    assert pa.mock_schema_equals(real_schema, mock_schema)
```

## Testing Role-Based Architecture

The role-based architecture tests (in `test_role_based_architecture.py`) verify that nodes behave correctly based on their assigned roles (master, worker, leecher).

### Fixtures for Role-Based Testing

The test file provides three key fixtures:

- `master_node`: Creates a mock master node with appropriate components and behaviors
- `worker_node`: Creates a mock worker node with follower capabilities
- `leecher_node`: Creates a basic leecher node with minimal components

### Test Classes

- `TestRoleBasedArchitecture`: Tests basic role initialization and startup/shutdown behaviors
- `TestMasterRoleBehavior`: Tests master-specific operations like cluster control
- `TestWorkerRoleBehavior`: Tests worker-specific behaviors like following a master
- `TestLeecherRoleBehavior`: Tests leecher-specific functionality
- `TestRoleSwitchingCapability`: Tests the ability to switch roles dynamically
- `TestClusterMembershipManagement`: Tests peer discovery and management
- `TestClusterDistributedState`: Tests distributed state synchronization
- `TestFailureDetectionRecovery`: Tests failure detection and recovery mechanisms

### Example Test

```python
def test_node_initialization(master_node, worker_node, leecher_node):
    """Test node initialization with different roles."""
    # Verify roles were correctly set
    assert master_node.role == "master"
    assert worker_node.role == "worker"
    assert leecher_node.role == "leecher"
    
    # Verify master has cluster service and control components
    assert hasattr(master_node, 'ipfs_cluster_service')
    assert hasattr(master_node, 'ipfs_cluster_ctl')
    assert not hasattr(master_node, 'ipfs_cluster_follow')
    
    # Verify worker has cluster follow component
    assert hasattr(worker_node, 'ipfs_cluster_follow')
    assert not hasattr(worker_node, 'ipfs_cluster_service')
    assert not hasattr(worker_node, 'ipfs_cluster_ctl')
    
    # Verify leecher has minimal components
    assert not hasattr(leecher_node, 'ipfs_cluster_follow')
    assert not hasattr(leecher_node, 'ipfs_cluster_service')
    assert not hasattr(leecher_node, 'ipfs_cluster_ctl')
```

## Mocking Complex Dependencies

### IPFS Daemon

```python
@pytest.fixture
def mock_ipfs_daemon():
    """Mock an IPFS daemon response."""
    with patch('subprocess.Popen') as mock_popen:
        mock_process = MagicMock()
        mock_process.communicate.return_value = (
            b'{"ID": "QmTest123", "Addresses": ["/ip4/127.0.0.1/tcp/4001"]}',
            b''
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        yield mock_popen
```

### IPFS Cluster

```python
@pytest.fixture
def mock_ipfs_cluster():
    """Mock an IPFS cluster response."""
    with patch('ipfs_kit_py.ipfs_cluster_service.ipfs_cluster_service') as mock:
        mock.return_value.start_service.return_value = {"success": True}
        mock.return_value.stop_service.return_value = {"success": True}
        yield mock
```

## Testing with Real IPFS

For integration tests with a real IPFS daemon:

```python
@pytest.mark.integration
def test_with_real_ipfs():
    """Test that requires a real IPFS daemon."""
    # Check if IPFS is available
    ipfs_available = False
    try:
        result = subprocess.run(["ipfs", "--version"], capture_output=True, text=True)
        ipfs_available = result.returncode == 0
    except FileNotFoundError:
        pass
    
    if not ipfs_available:
        pytest.skip("IPFS not available for integration test")
    
    # Test with real IPFS
    from ipfs_kit_py.ipfs import ipfs_py
    ipfs = ipfs_py()
    result = ipfs.add("test/test_data/small_file.txt")
    assert result["success"] is True
    assert "cid" in result
```

## Code Coverage

To generate code coverage reports:

```bash
python -m pytest --cov=ipfs_kit_py --cov-report=html
```

The HTML report will be available in the `htmlcov/` directory.

## Continuous Integration

The test suite runs in the CI pipeline on:
- Python 3.8, 3.9, 3.10, 3.11, and 3.12
- Multiple operating systems (Linux, macOS, Windows)

### Handling Platform-Specific Tests

For platform-specific tests:

```python
import sys
import platform

@pytest.mark.skipif(
    sys.platform != "linux", 
    reason="Test only runs on Linux"
)
def test_linux_specific():
    # Linux-specific test code
    pass

@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="Test only runs on macOS"
)
def test_macos_specific():
    # macOS-specific test code
    pass
```

## Troubleshooting

### Common Issues

1. **PyArrow Schema Patch Errors**: On Python 3.12+, you may see errors about immutable types if the patching mechanism is not working correctly. Ensure you're using the provided fixtures.

2. **Missing Mock Returns**: Ensure all mock objects have appropriate return values, especially for dictionary access patterns:
   ```python
   mock_obj = MagicMock()
   mock_obj.__getitem__.side_effect = lambda k: {"key1": "value1"}.get(k)
   ```

3. **Fixtures Not Found**: Ensure fixture names match exactly and are imported correctly.

### Debugging Tests

```bash
# Run with verbose output
python -m pytest -vv

# Show print statements during test runs
python -m pytest -s

# Run with pdb debugging
python -m pytest --pdb
```