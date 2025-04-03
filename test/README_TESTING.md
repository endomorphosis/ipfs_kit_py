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

The test suite currently has **350+ passing tests** and 45+ skipped tests. Skipped tests typically require external services, specific environment setups (like a running IPFS daemon or cluster), or are platform-specific (running only on Linux, Windows, or macOS).

## Test Files

### Key Test Files

The test suite contains a wide range of test files organized by component:

#### Installation and Initialization
- `test_binary_download.py`: Tests for automatic platform-specific binary downloads
- `test_binary_functionality.py`: Tests for downloaded binary functionality
- `test_first_run_initialization.py`: Tests for complete environment initialization
- `test_install_ipfs.py`: Tests for the installation process

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

## Binary Download and Initialization Testing

The IPFS Kit library includes special test suites that verify the automatic binary download and initialization functionality, ensuring the library works correctly across different platforms and hardware architectures.

### Test Fixtures for Binary Testing

The binary download and initialization tests use several useful fixtures:

```python
@pytest.fixture
def temp_bin_dir():
    """Create a temporary bin directory for testing downloads."""
    temp_dir = tempfile.mkdtemp()
    temp_bin_dir = os.path.join(temp_dir, "bin")
    os.makedirs(temp_bin_dir, exist_ok=True)
    
    yield temp_bin_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)

@pytest.fixture
def ensure_binaries():
    """Ensure the IPFS binaries are downloaded for testing."""
    bin_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ipfs_kit_py", "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    # Download binaries if needed
    if platform.system() == "Windows":
        binary_name = "ipfs.exe"
    else:
        binary_name = "ipfs"
    
    binary_path = os.path.join(bin_dir, binary_name)
    if not os.path.exists(binary_path):
        download_binaries()
    
    yield bin_dir

@pytest.fixture
def temp_ipfs_home():
    """Create a temporary IPFS home directory for testing initialization."""
    temp_dir = tempfile.mkdtemp()
    temp_ipfs_path = os.path.join(temp_dir, ".ipfs")
    os.makedirs(temp_ipfs_path, exist_ok=True)
    
    # Save original environment variables
    old_env = {}
    if "IPFS_PATH" in os.environ:
        old_env["IPFS_PATH"] = os.environ["IPFS_PATH"]
    
    # Set environment for tests
    os.environ["IPFS_PATH"] = temp_ipfs_path
    
    yield temp_ipfs_path
    
    # Restore environment
    for key in old_env:
        os.environ[key] = old_env[key]
        
    # Clean up temp directory
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_platform(monkeypatch):
    """Fixture to mock platform information for testing different OS environments."""
    def _set_platform(system, machine):
        monkeypatch.setattr(platform, "system", lambda: system)
        monkeypatch.setattr(platform, "machine", lambda: machine)
        monkeypatch.setattr(platform, "architecture", lambda: ("64bit", ""))
        
        if system == "Linux":
            monkeypatch.setattr(platform, "processor", lambda: "x86_64")
        elif system == "Darwin":
            monkeypatch.setattr(platform, "processor", lambda: "arm")
        elif system == "Windows":
            monkeypatch.setattr(platform, "processor", lambda: "Intel")
            
    return _set_platform
```

### How Binary Downloads Work

The binary download system in IPFS Kit automatically retrieves the appropriate platform-specific binaries when needed. This happens through these mechanisms:

1. **Automatic Import Detection**: When the package is first imported, it checks if binaries exist and downloads them if needed.
2. **ipfs_kit Initialization**: During initialization of the `ipfs_kit` class, it checks if binaries exist with:
   ```python
   # Check if binaries directory exists and has the required binaries
   this_dir = os.path.dirname(os.path.realpath(__file__))
   bin_dir = os.path.join(this_dir, "bin")
   ipfs_bin = os.path.join(bin_dir, "ipfs")
   ipfs_cluster_service_bin = os.path.join(bin_dir, "ipfs-cluster-service")
   
   # On Windows, check for .exe files
   if platform.system() == "Windows":
       ipfs_bin += ".exe"
       ipfs_cluster_service_bin += ".exe"
   
   # Download binaries if they don't exist
   if not os.path.exists(ipfs_bin) or not os.path.exists(ipfs_cluster_service_bin):
       download_binaries()
   ```
3. **User Control**: The automatic download can be disabled through the metadata parameter:
   ```python
   kit = ipfs_kit(metadata={"auto_download_binaries": False})
   ```

### Binary Download Testing

The `test_binary_download.py` file contains tests that verify:

1. **Platform Detection**: Ensures the library correctly identifies the current OS (Windows, macOS, Linux) and hardware architecture (x86_64, ARM, etc.)
2. **URL Construction**: Validates that correct binary distribution URLs are constructed for different platforms
3. **Download Process**: Tests the binary download functionality with mocked network requests
4. **Platform-Specific Binary Handling**: Verifies platform-specific binary naming and path handling (e.g., .exe extension on Windows)
5. **Auto-Download Behavior**: Confirms that binaries are automatically downloaded when first imported
6. **User Control Options**: Verifies that users can disable automatic binary downloads with metadata options

Key test cases include:

```python
def test_detect_current_platform(self):
    """Test that the installer correctly detects the current platform."""
    installer = install_ipfs({}, {})  # pass empty dicts for resources and metadata
    platform_str = installer.dist_select()
    
    # The platform string should be in the format "system arch"
    system, arch = platform_str.split()
    
    # Verify system is correctly detected
    assert system.lower() == platform.system().lower()
    
    # Verify architecture is one of the valid values
    assert arch in ["x86_64", "x86", "arm64", "arm"]

def test_disable_auto_download(self):
    """Test that auto-download can be disabled."""
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    
    # Make sure binaries appear to be missing
    with patch('os.path.exists', return_value=False):
        # Mock the download_binaries function
        with patch('ipfs_kit_py.download_binaries') as mock_download:
            # Initialize ipfs_kit with auto_download disabled
            kit = ipfs_kit(metadata={"auto_download_binaries": False})
            
            # Verify download_binaries was NOT called
            mock_download.assert_not_called()
```

### Binary Functionality Testing

The `test_binary_functionality.py` file tests that downloaded binaries work correctly:

1. **Binary Existence**: Checks that platform-specific binaries exist and are in the correct location
2. **Execute Permissions**: Verifies binaries have proper execution permissions
3. **Architecture Validation**: Ensures downloaded binaries match the system architecture
4. **Command Execution**: Tests that binaries execute correctly and return expected version information
5. **Integration with IPFS Kit**: Confirms that IPFS Kit properly uses the downloaded binaries
6. **Platform-Specific Variations**: Handles differences between Windows, macOS, and Linux binaries

Key test cases include:

```python
def test_binary_is_executable(self, ensure_binaries):
    """Test that the binary is executable."""
    bin_dir = ensure_binaries
    
    # Get the appropriate binary path
    binary_name = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
    binary_path = os.path.join(bin_dir, binary_name)
    
    # Check if binary exists
    assert os.path.exists(binary_path), f"Binary {binary_name} doesn't exist"
    
    # Check if binary is executable (skip on Windows as permissions work differently)
    if platform.system() != "Windows":
        assert os.access(binary_path, os.X_OK), f"Binary {binary_name} is not executable"

def test_binary_returns_version(self, ensure_binaries):
    """Test that the binary returns a version number."""
    bin_dir = ensure_binaries
    
    # Get the appropriate binary path
    binary_name = "ipfs.exe" if platform.system() == "Windows" else "ipfs"
    binary_path = os.path.join(bin_dir, binary_name)
    
    # Run the version command
    try:
        result = subprocess.run(
            [binary_path, "version"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        # Check if the output contains version information
        assert "ipfs version" in result.stdout.lower(), \
            f"Binary doesn't return expected version output: {result.stdout}"
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Binary execution failed: {e}")
    except FileNotFoundError:
        pytest.fail(f"Binary not found at {binary_path}")
```

### First Run Initialization Testing

The `test_first_run_initialization.py` file tests the complete initialization process:

1. **IPFS Initialization**: Tests initialization of the IPFS daemon and configuration
2. **Role-Based Setup**: Verifies different initialization paths for master, worker, and leecher roles
3. **Filesystem Initialization**: Tests creation of IPFS directory structure
4. **Service Initialization**: Tests initialization of IPFS Cluster services
5. **Integration Testing**: Verifies that Storacha and other components initialize correctly
6. **CLI Initialization**: Tests command-line interface initialization and functionality
7. **Custom Resource Handling**: Tests initialization with different resource configurations
8. **Error Handling**: Verifies graceful handling of initialization errors

Key test cases include:

```python
@patch('subprocess.run')
def test_role_specific_initialization(self, mock_run, temp_ipfs_home):
    """Test role-specific initialization (master, worker, leecher)."""
    # Mock subprocess return values for all possible commands
    def mock_subprocess_run(*args, **kwargs):
        cmd = args[0] if args else kwargs.get('args', [''])[0]
        
        mock_process = MagicMock()
        mock_process.returncode = 0
        
        # Simulate different responses based on command
        if 'id' in cmd or 'config' in cmd:
            mock_process.stdout = b'{"ID": "test-peer-id"}'
        elif 'init' in cmd:
            mock_process.stdout = b'initialized IPFS node'
        else:
            mock_process.stdout = b'command executed successfully'
            
        return mock_process
    
    mock_run.side_effect = mock_subprocess_run
    
    # Test master role initialization
    with patch('os.path.exists', return_value=True):  # Assume binaries exist
        with patch('ipfs_kit_py.download_binaries'):
            # Initialize with master role
            master_kit = ipfs_kit(metadata={
                "role": "master",
                "ipfs_path": temp_ipfs_home,
                "cluster_name": "test-cluster"
            })
            
            # Verify master-specific attributes or methods
            assert hasattr(master_kit, "ipfs_cluster_service"), "Master should have cluster service"
            assert master_kit.metadata.get("role") == "master", "Role should be master"
```

### Testing Platform-Specific Behavior

The binary download tests use platform mocking to test behavior across different operating systems without actually needing multiple OS environments:

```python
def test_platform_specific_binary_names(self, mock_platform, temp_bin_dir):
    """Test that the correct binary names are used for each platform."""
    # Test Linux
    mock_platform("Linux", "x86_64")
    with patch('ipfs_kit_py.install_ipfs.os.path.dirname') as mock_dirname:
        mock_dirname.return_value = os.path.dirname(temp_bin_dir)
        installer = install_ipfs({}, {})
        binary_path = os.path.join(installer.bin_path, "ipfs")
        assert "ipfs" in binary_path
        assert ".exe" not in binary_path
    
    # Test Windows
    mock_platform("Windows", "AMD64")
    with patch('ipfs_kit_py.install_ipfs.os.path.dirname') as mock_dirname:
        mock_dirname.return_value = os.path.dirname(temp_bin_dir)
        installer = install_ipfs({}, {})
        binary_path = os.path.join(installer.bin_path, "ipfs.exe")
        assert "ipfs.exe" in binary_path
```

### Integration with the ipfs_kit Class

The tests verify that the automatic download mechanism is properly integrated with the ipfs_kit class:

```python
def test_ipfs_kit_initialization_download(self):
    """Test that ipfs_kit class triggers binary downloads if needed."""
    from ipfs_kit_py.ipfs_kit import ipfs_kit
    
    # Make sure binaries appear to be missing
    with patch('os.path.exists', return_value=False):
        # Mock the download_binaries function
        with patch('ipfs_kit_py.download_binaries') as mock_download:
            # Initialize ipfs_kit with auto_download enabled
            kit = ipfs_kit(metadata={"auto_download_binaries": True})
            
            # Verify download_binaries was called
            mock_download.assert_called_once()
```

### Test Coverage Considerations

The binary download tests aim to cover:

1. **Deterministic Platform Detection**: Tests that we consistently detect the OS and architecture
2. **URL Generation**: Verifies that we build correct download URLs for each platform
3. **Download Process**: Tests the actual download and extraction process
4. **Integration**: Verifies that downloaded binaries can be used by the rest of the library
5. **Error Handling**: Ensures graceful behavior when downloads fail
6. **User Control**: Confirms that users can control automatic download behavior

These tests provide confidence that the library will work correctly across Windows, macOS, and Linux environments with minimal user configuration.

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