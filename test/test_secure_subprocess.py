import unittest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

from ipfs_kit_py.ipfs import ipfs_py

class TestSecureSubprocessCalls(unittest.TestCase):
    """
    Test cases for secure subprocess command execution in ipfs_kit_py.
    
    These tests verify that subprocess calls are executed securely,
    avoiding shell=True and properly handling command arguments.
    """
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create minimal resources and metadata for testing
        self.resources = {}
        self.metadata = {
            "role": "leecher",  # Use leecher role for simplest setup
            "testing": True,     # Mark as testing to avoid real daemon calls
        }
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name
        
        # Create a test file for operations that need a file
        self.test_file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("This is test content for IPFS operations")

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Clean up the temporary directory
        self.temp_dir.cleanup()
    
    @patch('subprocess.run')
    def test_run_ipfs_command_uses_args_list(self, mock_run):
        """Test that IPFS commands are executed with arg lists, not shell=True."""
        # Mock successful subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Hash": "QmTest123", "Size": "30"}'
        mock_run.return_value = mock_process
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Call a method that executes a command
        result = ipfs.ipfs_add_file(self.test_file_path)
        
        # Verify subprocess.run was called with arg list, not shell=True
        args, kwargs = mock_run.call_args
        self.assertTrue(isinstance(args[0], list))  # First arg should be a list
        self.assertFalse(kwargs.get('shell', False))  # shell should be False or not set
    
    @patch('subprocess.run')
    def test_command_args_properly_escaped(self, mock_run):
        """Test that command arguments are properly escaped."""
        # Mock successful subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Hash": "QmTest123", "Size": "30"}'
        mock_run.return_value = mock_process
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # File path with spaces and special characters
        special_path = os.path.join(self.test_dir, "file with spaces & special 'chars'.txt")
        with open(special_path, "w") as f:
            f.write("Content with special characters: !\"\\'$%&()*+,-./:;<=>?@[]^_`{|}~")
        
        # Call a method that executes a command with the special path
        result = ipfs.ipfs_add_file(special_path)
        
        # Verify the path was included as-is in the args list
        args, kwargs = mock_run.call_args
        self.assertIn(special_path, args[0])
    
    @patch('subprocess.run')
    def test_timeout_handling(self, mock_run):
        """Test that command execution includes proper timeouts."""
        # Mock successful subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Hash": "QmTest123", "Size": "30"}'
        mock_run.return_value = mock_process
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Call a method with a specific timeout
        result = ipfs.run_ipfs_command(["ipfs", "add", self.test_file_path], timeout=10)
        
        # Verify timeout was passed to subprocess.run
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs.get('timeout'), 10)
    
    @patch('subprocess.run')
    def test_stdout_stderr_capture(self, mock_run):
        """Test that stdout and stderr are properly captured."""
        # Mock successful subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Hash": "QmTest123", "Size": "30"}'
        mock_process.stderr = b'Warning: some non-fatal issue'
        mock_run.return_value = mock_process
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Call a method that executes a command
        result = ipfs.run_ipfs_command(["ipfs", "add", self.test_file_path])
        
        # Verify capture_output or stdout/stderr options were used
        args, kwargs = mock_run.call_args
        self.assertTrue(
            kwargs.get('capture_output', False) or 
            (kwargs.get('stdout') is not None and kwargs.get('stderr') is not None)
        )
        
        # Verify stdout and stderr were included in the result
        self.assertEqual(result['stdout'], b'{"Hash": "QmTest123", "Size": "30"}')
        self.assertEqual(result['stderr'], b'Warning: some non-fatal issue')
    
    @patch('subprocess.run')
    def test_banned_commands_blocked(self, mock_run):
        """Test that banned or dangerous commands are blocked."""
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Try to run banned commands
        banned_commands = [
            ["curl", "https://example.com"],
            ["wget", "https://example.com"],
            ["bash", "-c", "echo 'dangerous'"],
            ["sh", "-c", "echo 'dangerous'"],
            ["rm", "-rf", "/"],
            ["nc", "-l", "4444"],
            ["telnet", "example.com", "23"],
        ]
        
        for cmd in banned_commands:
            result = ipfs.run_ipfs_command(cmd)
            
            # Command should be rejected without executing
            self.assertFalse(result['success'])
            self.assertEqual(result['error_type'], 'security_error')
            self.assertIn('blocked', result['error'].lower())
            # Most importantly, verify subprocess.run was not called
            mock_run.assert_not_called()
            mock_run.reset_mock()
    
    @patch('subprocess.run')
    def test_command_failure_handling(self, mock_run):
        """Test that command failures are properly handled."""
        # Mock a failed subprocess result
        mock_run.side_effect = Exception("Test failure")
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Call a method that executes a command
        result = ipfs.run_ipfs_command(["ipfs", "add", self.test_file_path])
        
        # Verify failure was properly handled
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIn('error_type', result)
        self.assertEqual(result['error_type'], 'execution_error')
    
    @patch('subprocess.run')
    def test_check_flag_handling(self, mock_run):
        """Test that the check flag is properly handled."""
        # Mock a successful and then a failed subprocess result
        mock_success = MagicMock()
        mock_success.returncode = 0
        mock_success.stdout = b'{"Success": true}'
        
        mock_run.side_effect = [
            mock_success,  # First call succeeds
            subprocess.CalledProcessError(1, ["ipfs", "add"], stderr=b'Error: failed')  # Second call fails
        ]
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Call with check=True (should raise exception on non-zero exit)
        result1 = ipfs.run_ipfs_command(["ipfs", "version"], check=True)
        self.assertTrue(result1['success'])
        
        # Call with check=False (should not raise exception on non-zero exit)
        result2 = ipfs.run_ipfs_command(["ipfs", "add", "nonexistent"], check=False)
        self.assertFalse(result2['success'])
        self.assertEqual(result2['returncode'], 1)
    
    @patch('subprocess.run')
    def test_json_parsing(self, mock_run):
        """Test that JSON output is properly parsed."""
        # Mock successful subprocess result with JSON output
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Hash": "QmTest123", "Size": 30, "array": [1, 2, 3], "nested": {"key": "value"}}'
        mock_run.return_value = mock_process
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Call a method that parses JSON output
        result = ipfs.ipfs_add_file(self.test_file_path)
        
        # Verify JSON was parsed correctly
        self.assertTrue(result['success'])
        self.assertEqual(result['cid'], 'QmTest123')
        self.assertEqual(result['size'], 30)
        self.assertEqual(result['json_response']['array'], [1, 2, 3])
        self.assertEqual(result['json_response']['nested']['key'], 'value')
    
    @patch('subprocess.run')
    def test_env_variable_handling(self, mock_run):
        """Test that environment variables are properly handled."""
        # Mock successful subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Hash": "QmTest123", "Size": "30"}'
        mock_run.return_value = mock_process
        
        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)
        
        # Call a method with custom environment variables
        env_vars = {"IPFS_PATH": "/custom/path", "CUSTOM_VAR": "value"}
        result = ipfs.run_ipfs_command(
            ["ipfs", "add", self.test_file_path],
            env=env_vars
        )
        
        # Verify environment variables were passed
        args, kwargs = mock_run.call_args
        self.assertIsNotNone(kwargs.get('env'))
        for key, value in env_vars.items():
            self.assertEqual(kwargs['env'].get(key), value)


if __name__ == '__main__':
    unittest.main()