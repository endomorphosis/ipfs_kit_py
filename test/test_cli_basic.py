import unittest
import os
import tempfile
import json
import sys
import io
from unittest.mock import patch, MagicMock, call, PropertyMock

class TestCLIBasic(unittest.TestCase):
    """
    Basic test cases for the CLI interface in ipfs_kit_py.
    
    Tests only the fundamental commands that are known to be supported.
    """
    
    # No setUp or tearDown needed as each test creates its own temporary files
    
    def test_cli_add_command(self):
        """Test CLI handling of the 'add' command."""
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
            tmp.write(b'Test content')
            test_file_path = tmp.name

        try:
            # Set up mock for parse_args
            args = MagicMock()
            args.command = 'add'
            args.content = test_file_path
            args.pin = True
            args.wrap_with_directory = False
            args.chunker = 'size-262144'
            args.hash = 'sha2-256'
            args.format = 'text'
            args.no_color = False
            args.verbose = False
            args.config = None
            args.param = []

            # Set up mock for IPFSSimpleAPI
            mock_instance = MagicMock()
            mock_instance.add.return_value = {
                'success': True,
                'operation': 'add',
                'cid': 'QmTest123',
                'size': '30',
                'name': os.path.basename(test_file_path)
            }
            
            # Capture stdout
            captured_output = io.StringIO()
            
            # Apply patches and run test
            with patch('ipfs_kit_py.cli.parse_args', return_value=args), \
                 patch('ipfs_kit_py.cli.IPFSSimpleAPI', return_value=mock_instance), \
                 patch('sys.stdout', new=captured_output):
                
                # Import at this point to ensure mocks take effect
                from ipfs_kit_py.cli import main as cli_main
                
                # Run CLI
                exit_code = cli_main()
                
                # Check the exit code
                self.assertEqual(exit_code, 0)
                
                # Verify add was called with the file path
                mock_instance.add.assert_called_once_with(test_file_path, 
                                                           pin=True, 
                                                           wrap_with_directory=False,
                                                           chunker='size-262144',
                                                           hash='sha2-256')
                
                # Verify the output contains success message and CID
                output = captured_output.getvalue()
                self.assertIn('QmTest123', output)
                
        finally:
            # Clean up
            if os.path.exists(test_file_path):
                os.unlink(test_file_path)
    
    def test_cli_get_command(self):
        """Test CLI handling of the 'get' command."""
        # Create a temporary directory for output
        with tempfile.TemporaryDirectory() as temp_dir:
            # Output path for the download
            output_path = os.path.join(temp_dir, "output.txt")
            
            # Set up mock for parse_args
            args = MagicMock()
            args.command = 'get'
            args.cid = 'QmTest123'
            args.output = output_path
            args.timeout = 30
            args.format = 'text'
            args.no_color = False
            args.verbose = False
            args.config = None
            args.param = []
            
            # Set up mock for IPFSSimpleAPI
            mock_instance = MagicMock()
            test_content = b'This is test content from IPFS'
            mock_instance.get.return_value = test_content
            
            # Capture stdout
            captured_output = io.StringIO()
            
            # Apply patches and run test
            with patch('ipfs_kit_py.cli.parse_args', return_value=args), \
                 patch('ipfs_kit_py.cli.IPFSSimpleAPI', return_value=mock_instance), \
                 patch('sys.stdout', new=captured_output):
                
                # Import at this point to ensure mocks take effect
                from ipfs_kit_py.cli import main as cli_main
                
                # Run CLI
                exit_code = cli_main()
                
                # Check the exit code
                self.assertEqual(exit_code, 0)
                
                # Verify get was called with the CID and timeout
                mock_instance.get.assert_called_once_with('QmTest123', timeout=30)
                
                # Verify the output is saved to the file
                self.assertTrue(os.path.exists(output_path))
                with open(output_path, 'rb') as f:
                    content = f.read()
                self.assertEqual(content, test_content)
                
                # Verify success message in output
                output = captured_output.getvalue()
                self.assertIn('success', output.lower())
    
    def test_cli_version_command(self):
        """Test CLI handling of the 'version' command."""
        # Set up mock for parse_args
        args = MagicMock()
        args.command = 'version'
        args.format = 'text'
        args.no_color = False
        args.verbose = False
        args.config = None
        args.param = []
        
        # Set up mock for IPFSSimpleAPI
        mock_instance = MagicMock()
        
        # Capture stdout
        captured_output = io.StringIO()
        
        # Apply patches and run test
        with patch('ipfs_kit_py.cli.parse_args', return_value=args), \
             patch('ipfs_kit_py.cli.IPFSSimpleAPI', return_value=mock_instance), \
             patch('pkg_resources.get_distribution') as mock_dist, \
             patch('sys.stdout', new=captured_output):
            
            # Set version in mock
            mock_dist.return_value.version = '0.1.0'
            
            # Import at this point to ensure mocks take effect
            from ipfs_kit_py.cli import main as cli_main
            
            # Run CLI
            exit_code = cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify the output contains version info
            output = captured_output.getvalue()
            self.assertIn('version', output)
            self.assertIn('0.1.0', output)

if __name__ == '__main__':
    unittest.main()