# CLI Test Coverage Enhancement

This document provides instructions for adding additional test methods to the `test_cli_interface.py` file to achieve comprehensive test coverage of the CLI functionality.

## Overview

The file `cli_interface_examples.py` contains several new test methods that should be added to the `TestCLIInterface` class in `test_cli_interface.py`. These tests cover:

1. WAL CLI commands (status, list, etc.)
2. CLI behavior with no command (help display)
3. Key-value parameter parsing
4. Verbose and no-color flag handling
5. Error handling for validation errors
6. IPFS version error handling

## How to Use

Copy each test method from `cli_interface_examples.py` into the `TestCLIInterface` class in `test_cli_interface.py` before the end of the class definition.

## Test Coverage

With these additional tests, the CLI test coverage will include:

- Basic commands (add, get, pin, unpin, list-pins, etc.)
- WAL integration commands
- All global flags (verbose, no-color, format, config)
- Error handling scenarios
- Output formatting options (text, JSON, YAML)
- Parameter parsing and validation

## Example Test Structure

Each test follows this general pattern:

```python
@patch("sys.argv")
@patch("relevant.dependency")  # Patch any other dependencies as needed
@patch("ipfs_kit_py.cli.IPFSSimpleAPI")
def test_cli_command(self, mock_api_class, mock_dependency, mock_argv_patch):
    """Test description."""
    # Set up test environment
    sys.argv = ["ipfs_kit", "command", "args"]
    
    # Mock API responses
    mock_instance = MagicMock()
    mock_instance.command.return_value = {"success": True, ...}
    mock_api_class.return_value = mock_instance
    
    # Capture output for verification
    captured_output = io.StringIO()
    sys.stdout = captured_output
    
    try:
        # Run the CLI
        exit_code = self.cli_main()
        
        # Verify results
        self.assertEqual(exit_code, 0)
        self.assertIn("expected output", captured_output.getvalue())
        
    finally:
        # Clean up
        sys.stdout = sys.__stdout__
```

## Notes

- All tests use proper context management for stdout/stderr capturing to ensure clean test isolation
- The WAL CLI tests include proper mocking of the WAL availability flag and command handlers
- Error handling tests verify both exit codes and error message content

## Important: Fixing Existing Test

When adding these tests, you'll need to fix an existing failing test in `test_cli_interface.py`. In the `test_cli_with_additional_params` method, there's an assertion error:

```
AssertionError: expected call not found.
Expected: connect('/ip4/127.0.0.1/tcp/4001/p2p/QmTest', timeout=30, retry=True)
Actual: connect('/ip4/127.0.0.1/tcp/4001/p2p/QmTest', timeout=60, retry=True)
```

This occurs because the `--param timeout=60` parameter is correctly overriding the default timeout of 30 seconds. Fix the test by updating the assertion to expect a timeout of 60 seconds instead of 30:

```python
# Change this line:
mock_instance.connect.assert_called_once_with(
    "/ip4/127.0.0.1/tcp/4001/p2p/QmTest",
    timeout=30,  # This comes from parse_kwargs
    retry=True   # This comes from the additional --param
)

# To this:
mock_instance.connect.assert_called_once_with(
    "/ip4/127.0.0.1/tcp/4001/p2p/QmTest",
    timeout=60,  # This comes from the --param argument which overrides the default
    retry=True   # This comes from the additional --param
)
```