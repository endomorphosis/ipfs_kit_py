import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, PropertyMock, call, patch


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

    @patch('subprocess.run')  # Prevent actual subprocess from running
    @patch('subprocess.Popen')  # Prevent actual subprocess from running
    def test_cli_add_command(self, mock_popen, mock_run):
        """Test CLI handling of the 'add' command."""
        # Setup subprocess mocks to avoid resource warnings
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = (b'', b'')
        mock_popen.return_value.stdout = None
        mock_popen.return_value.stderr = None
        mock_popen.return_value.pid = 9999  # Use a fake pid
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b''
        mock_run.return_value.stderr = b''
        
        # Add to tracked mocks
        self.subprocess_mocks.extend([mock_popen, mock_run])
        
        # Create a temporary file for testing
        test_file_path = None
        try:
            # Create a temporary file without using a file handle that could be left open
            fd, test_file_path = tempfile.mkstemp(suffix=".txt")
            os.close(fd)  # Close immediately to avoid resource leak
            with open(test_file_path, 'wb') as temp_file:
                temp_file.write(b"Test content")
            
            # Track temporary file for cleanup
            self.temp_files.append(test_file_path)

            # Set up mock for parse_args
            args = MagicMock()
            args.command = "add"
            args.file = test_file_path
            args.pin = True
            args.wrap_with_directory = False
            args.chunker = "size-262144"
            args.hash = "sha2-256"
            args.format = "text"
            args.no_color = False
            args.verbose = False
            args.config = None
            args.param = []
            args.timeout = 30  # Add timeout attribute
            args.timeout_add = 60  # Add command-specific timeout
            
            # Add function handling needed by the updated CLI code
            def handle_add(api, args, kwargs):
                return api.add(
                    args.file,
                    pin=args.pin,
                    wrap_with_directory=args.wrap_with_directory,
                    chunker=args.chunker,
                    hash=args.hash
                )
            args.func = handle_add

            # Set up mock for IPFSSimpleAPI
            mock_instance = MagicMock()
            mock_instance.add.return_value = {
                "success": True,
                "operation": "add",
                "cid": "QmTest123",
                "size": "30",
                "name": os.path.basename(test_file_path),
            }

            # Capture stdout
            captured_output = io.StringIO()

            # Apply patches and store them to track for cleanup
            mock_patches = []
            patch1 = patch("ipfs_kit_py.cli.parse_args", return_value=args)
            patch2 = patch("ipfs_kit_py.cli.IPFSSimpleAPI", return_value=mock_instance)
            patch3 = patch("sys.stdout", new=captured_output)
            
            # Start patches and store the mocks for cleanup
            mock1 = patch1.start()
            mock2 = patch2.start()
            mock3 = patch3.start()
            
            # Add mocks to tracking list for cleanup
            self.subprocess_mocks.extend([mock1, mock2, mock3])
            
            try:
                # Import at this point to ensure mocks take effect
                from ipfs_kit_py.cli import main as cli_main

                # Run CLI
                exit_code = cli_main()

                # Check the exit code
                self.assertEqual(exit_code, 0)

                # Verify add was called with the file path
                mock_instance.add.assert_called_once_with(
                    test_file_path,
                    pin=True,
                    wrap_with_directory=False,
                    chunker="size-262144",
                    hash="sha2-256",
                )

                # Verify the output contains success message and CID
                output = captured_output.getvalue()
                self.assertIn("QmTest123", output)
            finally:
                # Stop all patches explicitly to ensure cleanup
                patch1.stop()
                patch2.stop()
                patch3.stop()
        finally:
            # Cleanup is handled by tearDown which removes files in self.temp_files
            pass

    @patch('subprocess.run')  # Prevent actual subprocess from running
    @patch('subprocess.Popen')  # Prevent actual subprocess from running
    def test_cli_get_command(self, mock_popen, mock_run):
        """Test CLI handling of the 'get' command."""
        # Setup subprocess mocks to avoid resource warnings
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = (b'', b'')
        mock_popen.return_value.stdout = None
        mock_popen.return_value.stderr = None
        mock_popen.return_value.pid = 9999  # Use a fake pid
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b''
        mock_run.return_value.stderr = b''
        
        # Add to tracked mocks
        self.subprocess_mocks.extend([mock_popen, mock_run])
        
        # Create a temporary directory and file path
        temp_dir = tempfile.mkdtemp()
        try:
            # Track for cleanup
            self.temp_files.append(temp_dir)  # Add whole directory for cleanup
            
            # Output path for the download
            output_path = os.path.join(temp_dir, "output.txt")

            # Set up mock for parse_args
            args = MagicMock()
            args.command = "get"
            args.cid = "QmTest123"
            args.output = output_path
            args.timeout = 30  # Add timeout attribute
            args.timeout_get = 30  # Add command-specific timeout
            args.format = "text"
            args.no_color = False
            args.verbose = False
            args.config = None
            args.param = []
            
            # Add function handling needed by the updated CLI code
            def handle_get(api, args, kwargs):
                result = api.get(args.cid, timeout=30)
                if args.output:
                    with open(args.output, "wb") as f:
                        f.write(result)
                    return {"success": True, "message": f"Content saved to {args.output}"}
                return result
            args.func = handle_get

            # Set up mock for IPFSSimpleAPI
            mock_instance = MagicMock()
            test_content = b"This is test content from IPFS"
            mock_instance.get.return_value = test_content

            # Capture stdout using a context manager to ensure closure
            captured_output = io.StringIO()

            # Apply patches and store them for better cleanup
            patch1 = patch("ipfs_kit_py.cli.parse_args", return_value=args)
            patch2 = patch("ipfs_kit_py.cli.IPFSSimpleAPI", return_value=mock_instance)
            patch3 = patch("sys.stdout", new=captured_output)
            
            # Start patches explicitly for better cleanup
            mock1 = patch1.start()
            mock2 = patch2.start()
            mock3 = patch3.start()
            
            # Add to tracked mocks
            self.subprocess_mocks.extend([mock1, mock2, mock3])
            
            try:
                # Import at this point to ensure mocks take effect
                from ipfs_kit_py.cli import main as cli_main

                # Run CLI
                exit_code = cli_main()

                # Check the exit code
                self.assertEqual(exit_code, 0)

                # Verify get was called with the CID and timeout
                mock_instance.get.assert_called_once_with("QmTest123", timeout=30)

                # Verify the output is saved to the file
                self.assertTrue(os.path.exists(output_path))
                with open(output_path, "rb") as f:
                    content = f.read()
                self.assertEqual(content, test_content)

                # Verify success message in output
                output_text = captured_output.getvalue()
                self.assertIn("success", output_text.lower())
            finally:
                # Stop patches explicitly
                patch1.stop()
                patch2.stop()
                patch3.stop()
                
                # Clear reference to context manager objects that might hold file handles
                captured_output = None
                
        finally:
            # Cleanup is handled by tearDown, which will remove temp_dir
            pass

    @patch('subprocess.run')  # Prevent actual subprocess from running
    @patch('subprocess.Popen')  # Prevent actual subprocess from running
    def test_cli_version_command(self, mock_popen, mock_run):
        """Test CLI handling of the 'version' command."""
        # Setup subprocess mocks to avoid resource warnings
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = (b'', b'')
        mock_popen.return_value.stdout = None
        mock_popen.return_value.stderr = None
        mock_popen.return_value.pid = 9999  # Use a fake pid
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = b''
        mock_run.return_value.stderr = b''
        
        # Add to tracked mocks
        self.subprocess_mocks.extend([mock_popen, mock_run])
        
        # Set up mock for parse_args
        args = MagicMock()
        args.command = "version"
        args.format = "text"
        args.no_color = False
        args.verbose = False
        args.config = None
        args.param = []
        
        # Add function handling needed by the updated CLI code
        def handle_version(api, args, kwargs):
            return {
                "ipfs_kit_py_version": "0.1.0",
                "python_version": "3.x.x",
                "platform": "test",
                "ipfs_daemon_version": "unknown"
            }
        args.func = handle_version

        # Set up mock for IPFSSimpleAPI
        mock_instance = MagicMock()

        # Capture stdout
        captured_output = io.StringIO()

        # Apply patches and store them for better cleanup
        patch1 = patch("ipfs_kit_py.cli.parse_args", return_value=args)
        patch2 = patch("ipfs_kit_py.cli.IPFSSimpleAPI", return_value=mock_instance)
        patch3 = patch("importlib.metadata.version", return_value="0.1.0")
        patch4 = patch("sys.stdout", new=captured_output)
        
        # Start patches explicitly for better cleanup
        mock1 = patch1.start()
        mock2 = patch2.start()
        mock3 = patch3.start()
        mock4 = patch4.start()
        
        # Add to tracked mocks
        self.subprocess_mocks.extend([mock1, mock2, mock3, mock4])
        
        try:
            # Import at this point to ensure mocks take effect
            from ipfs_kit_py.cli import main as cli_main

            # Run CLI
            exit_code = cli_main()

            # Check the exit code
            self.assertEqual(exit_code, 0)

            # Verify the output contains version info
            output = captured_output.getvalue()
            self.assertIn("version", output)
            self.assertIn("0.1.0", output)
        finally:
            # Stop patches explicitly
            patch1.stop()
            patch2.stop()
            patch3.stop()
            patch4.stop()


if __name__ == "__main__":
    unittest.main()
