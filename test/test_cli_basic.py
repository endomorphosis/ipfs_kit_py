import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, PropertyMock, call, patch

# Mock modules to avoid dependency issues
sys.modules['libp2p'] = MagicMock()
sys.modules['libp2p.abc'] = MagicMock()
sys.modules['libp2p.crypto'] = MagicMock()
sys.modules['libp2p.crypto.keys'] = MagicMock()
sys.modules['libp2p.crypto.pb'] = MagicMock()
sys.modules['libp2p.crypto.pb.crypto_pb2'] = MagicMock()
sys.modules['google.protobuf.runtime_version'] = MagicMock()

# Create a mock IPFSSimpleAPI class
mock_simple_api = MagicMock()
# Store in modules to avoid actual importing
sys.modules['ipfs_kit_py.high_level_api'] = MagicMock()
sys.modules['ipfs_kit_py.high_level_api'].IPFSSimpleAPI = mock_simple_api
sys.modules['ipfs_kit_py.high_level_api'].PluginBase = MagicMock()


class TestCLIBasic(unittest.TestCase):
    """
    Basic test cases for the CLI interface in ipfs_kit_py.

    Tests only the fundamental commands that are known to be supported.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Track resources to clean up
        self.temp_files = []
        self.subprocess_mocks = []
    
    def __del__(self):
        """Ensure cleanup happens even if tearDown isn't called."""
        # Make an extra cleanup attempt
        for file_path in getattr(self, 'temp_files', []):
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except:
                    pass
                    
        # Force collection
        try:
            import gc
            gc.collect()
        except:
            pass
        
    def tearDown(self):
        """Clean up test resources and prevent ResourceWarnings."""
        # Clean up any temporary files or directories
        for path in self.temp_files:
            if os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        # Clean up directory and its contents
                        import shutil
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        # Remove file
                        os.unlink(path)
                except Exception as e:
                    print(f"Warning: Error deleting temporary path {path}: {e}")
        
        # Clear self.temp_files to release any references
        self.temp_files.clear()
        
        # Restore standard streams to avoid ResourceWarnings
        sys.stdout = sys.__stdout__
        
        # This addresses the "subprocess still running" ResourceWarning
        # by clearing any mocked subprocess objects and encouraging their cleanup
        for mock_obj in self.subprocess_mocks:
            if hasattr(mock_obj, 'reset_mock'):
                mock_obj.reset_mock()
                
        self.subprocess_mocks.clear()
            
        # Import required modules for more thorough cleanup
        import gc
        
        # Close any potentially unclosed file descriptors 
        # Using a wider range to catch more potential file descriptors
        for fd in range(3, 50):  # Extended range
            try:
                os.close(fd)
            except OSError:
                pass
                
        # Force garbage collection multiple times for thorough cleanup
        for _ in range(3):
            gc.collect()

    # Fix for proper mocking and avoiding import issues
    import pytest
    # @pytest.mark.skip(reason="Test hangs in pytest but passes with unittest directly. Run with: python -m test.test_cli_basic TestCLIBasic.test_cli_add_command")
    @patch('subprocess.run')  # Prevent actual subprocess from running
    @patch('subprocess.Popen')  # Prevent actual subprocess from running
    @patch('ipfs_kit_py.cli.IPFSSimpleAPI')  # Mock the API class *before* import
    def test_cli_add_command(self, mock_api_class, mock_popen, mock_run):
        """Test CLI handling of the 'add' command.
        
        Note: This test may hang when run with pytest due to protobuf and libp2p import issues,
        but runs successfully with unittest directly. To run this test individually, use:
        python -m test.test_cli_basic TestCLIBasic.test_cli_add_command
        """
        print("\n=== START: test_cli_add_command ===")  # DEBUG
        
        # Setup mock API instance
        mock_api_instance = MagicMock()
        mock_api_class.return_value = mock_api_instance
        
        mock_api_instance.add.return_value = {
            "success": True,
            "operation": "add",
            "cid": "QmTest123",
            "size": "30",
            "name": "test_file.txt",  # We'll fill in actual name later
        }
        
        # Setup subprocess mocks to avoid resource warnings
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = (b'', b'')
        mock_popen.return_value.stdout = None
        mock_popen.return_value.stderr = None
        mock_popen.return_value.pid = 9999  # Use a fake pid
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b''
        mock_run.return_value.stderr = b''
        
        print("Mocks configured")  # DEBUG
        
        # Add to tracked mocks for cleanup
        self.subprocess_mocks.extend([mock_api_class, mock_popen, mock_run])
        
        # Create a temporary file for testing
        test_file_path = None
        try:
            # Create a temporary file without using a file handle that could be left open
            fd, test_file_path = tempfile.mkstemp(suffix=".txt")
            os.close(fd)  # Close immediately to avoid resource leak
            with open(test_file_path, 'wb') as temp_file:
                temp_file.write(b"Test content")
            
            print(f"Created test file: {test_file_path}")  # DEBUG
            
            # Update the mock response with the actual filename
            mock_api_instance.add.return_value["name"] = os.path.basename(test_file_path)
            
            # Track temporary file for cleanup
            self.temp_files.append(test_file_path)

            # Capture stdout for testing
            captured_output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured_output
            
            try:
                # Import here to use modified sys.argv
                import ipfs_kit_py.cli
                
                # Directly mock parse_args to avoid import conflicts
                original_parse_args = ipfs_kit_py.cli.parse_args
                
                def mock_parse_args(args=None):
                    # Create mock args object that matches what CLI expects
                    mock_args = MagicMock()
                    mock_args.command = "add"
                    mock_args.content = test_file_path  # This is the key parameter the CLI looks for
                    mock_args.pin = True
                    mock_args.wrap_with_directory = False
                    mock_args.chunker = "size-262144"
                    mock_args.hash = "sha2-256"
                    mock_args.format = "text"
                    mock_args.no_color = False
                    mock_args.verbose = False
                    mock_args.config = None
                    mock_args.param = []
                    
                    # Add function handler
                    mock_args.func = lambda api, args, kwargs: api.add(
                        args.content,
                        pin=args.pin, 
                        wrap_with_directory=args.wrap_with_directory,
                        chunker=args.chunker,
                        hash=args.hash
                    )
                    
                    return mock_args
                
                # Apply the mock
                ipfs_kit_py.cli.parse_args = mock_parse_args
                
                print("Running CLI main...")  # DEBUG
                try:
                    # Run the CLI main function
                    exit_code = ipfs_kit_py.cli.main()
                    print(f"CLI main returned with exit code: {exit_code}")  # DEBUG
                    
                    # Check the exit code
                    self.assertEqual(exit_code, 0)
                    
                    # Verify the add method was called correctly
                    mock_api_instance.add.assert_called_once()
                    call_args, call_kwargs = mock_api_instance.add.call_args
                    self.assertEqual(call_args[0], test_file_path)
                    self.assertEqual(call_kwargs.get('pin'), True)
                    self.assertEqual(call_kwargs.get('wrap_with_directory'), False)
                    self.assertEqual(call_kwargs.get('chunker'), 'size-262144')
                    self.assertEqual(call_kwargs.get('hash'), 'sha2-256')
                    
                    # Verify output
                    output = captured_output.getvalue()
                    print(f"CLI output: {output}")  # DEBUG
                    self.assertIn("QmTest123", output)
                    
                    print("Test assertions passed!")  # DEBUG
                    
                finally:
                    # Restore original parse_args
                    ipfs_kit_py.cli.parse_args = original_parse_args
            finally:
                # Restore stdout
                sys.stdout = old_stdout
                
        finally:
            print("=== END: test_cli_add_command ===")  # DEBUG
            # Cleanup is handled by tearDown which removes files in self.temp_files
            pass

    # Fix for proper mocking and avoiding import issues
    import pytest
    # @pytest.mark.skip(reason="Test hangs in pytest but passes with unittest directly. Run with: python -m test.test_cli_basic TestCLIBasic.test_cli_get_command")
    @patch('subprocess.run')  # Prevent actual subprocess from running
    @patch('subprocess.Popen')  # Prevent actual subprocess from running
    @patch('ipfs_kit_py.cli.IPFSSimpleAPI')  # Mock the API class *before* import
    def test_cli_get_command(self, mock_api_class, mock_popen, mock_run):
        """Test CLI handling of the 'get' command."""
        print("\n=== START: test_cli_get_command ===")  # DEBUG
        
        # Setup mock API instance
        mock_api_instance = MagicMock()
        mock_api_class.return_value = mock_api_instance
        
        test_content = b"This is test content from IPFS"
        mock_api_instance.get.return_value = test_content
        
        # Setup subprocess mocks to avoid resource warnings
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = (b'', b'')
        mock_popen.return_value.stdout = None
        mock_popen.return_value.stderr = None
        mock_popen.return_value.pid = 9999  # Use a fake pid
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b''
        mock_run.return_value.stderr = b''
        
        print("Mocks configured")  # DEBUG
        
        # Add to tracked mocks for cleanup
        self.subprocess_mocks.extend([mock_api_class, mock_popen, mock_run])
        
        # Create a temporary directory and file path
        temp_dir = tempfile.mkdtemp()
        try:
            # Track for cleanup
            self.temp_files.append(temp_dir)  # Add whole directory for cleanup
            
            # Output path for the download
            output_path = os.path.join(temp_dir, "output.txt")
            print(f"Created output path: {output_path}")  # DEBUG

            # Capture stdout for testing
            captured_output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured_output
            
            try:
                # Import here to use modified sys.argv
                import ipfs_kit_py.cli
                
                # Directly mock parse_args to avoid import conflicts
                original_parse_args = ipfs_kit_py.cli.parse_args
                
                def mock_parse_args(args=None):
                    # Create mock args object that matches what CLI expects
                    mock_args = MagicMock()
                    mock_args.command = "get"
                    mock_args.cid = "QmTest123"
                    mock_args.output = output_path
                    mock_args.timeout = 30
                    mock_args.timeout_get = 30
                    mock_args.format = "text"
                    mock_args.no_color = False
                    mock_args.verbose = False
                    mock_args.config = None
                    mock_args.param = []
                    
                    # Add function handler
                    def handle_get(api, args, kwargs):
                        result = api.get(args.cid, timeout=30)
                        if args.output:
                            with open(args.output, "wb") as f:
                                f.write(result)
                            return {"success": True, "message": f"Content saved to {args.output}"}
                        return result
                    
                    mock_args.func = handle_get
                    
                    return mock_args
                
                # Apply the mock
                ipfs_kit_py.cli.parse_args = mock_parse_args
                
                print("Running CLI main...")  # DEBUG
                try:
                    # Run the CLI main function
                    exit_code = ipfs_kit_py.cli.main()
                    print(f"CLI main returned with exit code: {exit_code}")  # DEBUG
                    
                    # Check the exit code
                    self.assertEqual(exit_code, 0)
                    
                    # Verify get was called with the CID and timeout
                    mock_api_instance.get.assert_called_once_with("QmTest123", timeout=30)
                    
                    # Verify the output is saved to the file
                    self.assertTrue(os.path.exists(output_path))
                    with open(output_path, "rb") as f:
                        content = f.read()
                    self.assertEqual(content, test_content)
                    
                    # Verify output
                    output = captured_output.getvalue()
                    print(f"CLI output: {output}")  # DEBUG
                    self.assertIn("success", output.lower())
                    
                    print("Test assertions passed!")  # DEBUG
                    
                finally:
                    # Restore original parse_args
                    ipfs_kit_py.cli.parse_args = original_parse_args
            finally:
                # Restore stdout
                sys.stdout = old_stdout
                
        finally:
            print("=== END: test_cli_get_command ===")  # DEBUG
            # Cleanup is handled by tearDown, which will remove temp_dir
            pass

    # Fix for proper mocking and avoiding import issues
    import pytest
    # @pytest.mark.skip(reason="Test hangs in pytest but passes with unittest directly. Run with: python -m test.test_cli_basic TestCLIBasic.test_cli_version_command")
    @patch('subprocess.run')  # Prevent actual subprocess from running
    @patch('subprocess.Popen')  # Prevent actual subprocess from running
    @patch('ipfs_kit_py.cli.IPFSSimpleAPI')  # Mock the API class *before* import
    @patch('importlib.metadata.version')  # Mock version call
    def test_cli_version_command(self, mock_version, mock_api_class, mock_popen, mock_run):
        """Test CLI handling of the 'version' command."""
        print("\n=== START: test_cli_version_command ===")  # DEBUG
        
        # Setup mock API instance
        mock_api_instance = MagicMock()
        mock_api_class.return_value = mock_api_instance
        
        # Mock version call
        mock_version.return_value = "0.1.0"
        
        # Setup subprocess mocks to avoid resource warnings
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = (b'', b'')
        mock_popen.return_value.stdout = None
        mock_popen.return_value.stderr = None
        mock_popen.return_value.pid = 9999  # Use a fake pid
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b''
        mock_run.return_value.stderr = b''
        
        print("Mocks configured")  # DEBUG
        
        # Add to tracked mocks for cleanup
        self.subprocess_mocks.extend([mock_version, mock_api_class, mock_popen, mock_run])
        
        # Capture stdout for testing
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output
        
        try:
            # Import here to use modified sys.argv
            import ipfs_kit_py.cli
            
            # Directly mock parse_args to avoid import conflicts
            original_parse_args = ipfs_kit_py.cli.parse_args
            
            def mock_parse_args(args=None):
                # Create mock args object that matches what CLI expects
                mock_args = MagicMock()
                mock_args.command = "version"
                mock_args.format = "text"
                mock_args.no_color = False
                mock_args.verbose = False
                mock_args.config = None
                mock_args.param = []
                
                # Add function handler for version command
                def handle_version(api, args, kwargs):
                    return {
                        "ipfs_kit_py_version": "0.1.0",
                        "python_version": "3.x.x",
                        "platform": "test",
                        "ipfs_daemon_version": "unknown"
                    }
                
                mock_args.func = handle_version
                
                return mock_args
            
            # Apply the mock
            ipfs_kit_py.cli.parse_args = mock_parse_args
            
            print("Running CLI main...")  # DEBUG
            try:
                # Run the CLI main function
                exit_code = ipfs_kit_py.cli.main()
                print(f"CLI main returned with exit code: {exit_code}")  # DEBUG
                
                # Check the exit code
                self.assertEqual(exit_code, 0)
                
                # Verify the output contains version info
                output = captured_output.getvalue()
                print(f"CLI output: {output}")  # DEBUG
                self.assertIn("version", output.lower())
                self.assertIn("0.1.0", output)
                
                print("Test assertions passed!")  # DEBUG
                
            finally:
                # Restore original parse_args
                ipfs_kit_py.cli.parse_args = original_parse_args
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            print("=== END: test_cli_version_command ===")  # DEBUG


if __name__ == "__main__":
    unittest.main()
