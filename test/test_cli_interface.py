import unittest
import os
import tempfile
import json
import sys
import io
from unittest.mock import patch, MagicMock, call

class TestCLIInterface(unittest.TestCase):
    """
    Test cases for the CLI interface in ipfs_kit_py.
    
    These tests verify that the command-line interface correctly parses
    arguments, executes commands, and displays output in a user-friendly way.
    """
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = self.temp_dir.name
        
        # Create a test file for operations that need a file
        self.test_file_path = os.path.join(self.test_dir, "test_file.txt")
        with open(self.test_file_path, "w") as f:
            f.write("This is test content for IPFS operations")
        
        # Import the module under test (the CLI module)
        from ipfs_kit_py.cli import main as cli_main
        self.cli_main = cli_main

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Clean up the temporary directory
        self.temp_dir.cleanup()
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_add_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'add' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'add',
            2: self.test_file_path
        }[i] if i < 3 else IndexError()
        mock_argv.__len__.return_value = 3
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_add_file.return_value = {
            'success': True,
            'operation': 'ipfs_add_file',
            'cid': 'QmTest123',
            'size': '30',
            'name': 'test_file.txt'
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_add_file was called with the file path
            mock_instance.ipfs_add_file.assert_called_once_with(self.test_file_path)
            
            # Verify the output contains success message and CID
            output = captured_output.getvalue()
            self.assertIn('Added', output)
            self.assertIn('QmTest123', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_cat_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'cat' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'cat',
            2: 'QmTest123'
        }[i] if i < 3 else IndexError()
        mock_argv.__len__.return_value = 3
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_cat.return_value = {
            'success': True,
            'operation': 'ipfs_cat',
            'data': b'This is test content from IPFS'
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_cat was called with the CID
            mock_instance.ipfs_cat.assert_called_once_with('QmTest123')
            
            # Verify the output contains the file content
            output = captured_output.getvalue()
            self.assertIn('This is test content from IPFS', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_pin_add_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'pin add' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'pin',
            2: 'add',
            3: 'QmTest123'
        }[i] if i < 4 else IndexError()
        mock_argv.__len__.return_value = 4
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_add_pin.return_value = {
            'success': True,
            'operation': 'ipfs_add_pin',
            'cid': 'QmTest123',
            'pinned': True
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_add_pin was called with the CID
            mock_instance.ipfs_add_pin.assert_called_once_with('QmTest123')
            
            # Verify the output contains success message
            output = captured_output.getvalue()
            self.assertIn('Pinned', output)
            self.assertIn('QmTest123', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_pin_rm_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'pin rm' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'pin',
            2: 'rm',
            3: 'QmTest123'
        }[i] if i < 4 else IndexError()
        mock_argv.__len__.return_value = 4
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_remove_pin.return_value = {
            'success': True,
            'operation': 'ipfs_remove_pin',
            'cid': 'QmTest123',
            'unpinned': True
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_remove_pin was called with the CID
            mock_instance.ipfs_remove_pin.assert_called_once_with('QmTest123')
            
            # Verify the output contains success message
            output = captured_output.getvalue()
            self.assertIn('Unpinned', output)
            self.assertIn('QmTest123', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_pin_ls_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'pin ls' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'pin',
            2: 'ls'
        }[i] if i < 3 else IndexError()
        mock_argv.__len__.return_value = 3
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_ls_pinset.return_value = {
            'success': True,
            'operation': 'ipfs_ls_pinset',
            'pins': {
                'QmPin1': {'type': 'recursive'},
                'QmPin2': {'type': 'direct'},
                'QmPin3': {'type': 'indirect'}
            }
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_ls_pinset was called
            mock_instance.ipfs_ls_pinset.assert_called_once()
            
            # Verify the output contains all pins
            output = captured_output.getvalue()
            self.assertIn('QmPin1', output)
            self.assertIn('QmPin2', output)
            self.assertIn('QmPin3', output)
            self.assertIn('recursive', output)
            self.assertIn('direct', output)
            self.assertIn('indirect', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_get_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'get' command."""
        # Output path for the download
        output_path = os.path.join(self.test_dir, "output")
        
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'get',
            2: 'QmTest123',
            3: '-o',
            4: output_path
        }[i] if i < 5 else IndexError()
        mock_argv.__len__.return_value = 5
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_get.return_value = {
            'success': True,
            'operation': 'ipfs_get',
            'cid': 'QmTest123',
            'output_path': output_path
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_get was called with the CID and output path
            mock_instance.ipfs_get.assert_called_once_with('QmTest123', output_path)
            
            # Verify the output contains success message
            output = captured_output.getvalue()
            self.assertIn('Downloaded', output)
            self.assertIn('QmTest123', output)
            self.assertIn(output_path, output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_swarm_peers_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'swarm peers' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'swarm',
            2: 'peers'
        }[i] if i < 3 else IndexError()
        mock_argv.__len__.return_value = 3
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_swarm_peers.return_value = {
            'success': True,
            'operation': 'ipfs_swarm_peers',
            'peers': [
                {'addr': '/ip4/10.0.0.1/tcp/4001', 'peer': 'QmPeer1'},
                {'addr': '/ip4/10.0.0.2/tcp/4001', 'peer': 'QmPeer2'},
                {'addr': '/ip4/10.0.0.3/tcp/4001', 'peer': 'QmPeer3'}
            ]
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_swarm_peers was called
            mock_instance.ipfs_swarm_peers.assert_called_once()
            
            # Verify the output contains all peers
            output = captured_output.getvalue()
            self.assertIn('QmPeer1', output)
            self.assertIn('QmPeer2', output)
            self.assertIn('QmPeer3', output)
            self.assertIn('/ip4/10.0.0.1/tcp/4001', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_swarm_connect_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'swarm connect' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'swarm',
            2: 'connect',
            3: '/ip4/10.0.0.1/tcp/4001/p2p/QmPeer1'
        }[i] if i < 4 else IndexError()
        mock_argv.__len__.return_value = 4
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_swarm_connect.return_value = {
            'success': True,
            'operation': 'ipfs_swarm_connect',
            'peer': '/ip4/10.0.0.1/tcp/4001/p2p/QmPeer1',
            'connected': True
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_swarm_connect was called with the peer address
            mock_instance.ipfs_swarm_connect.assert_called_once_with('/ip4/10.0.0.1/tcp/4001/p2p/QmPeer1')
            
            # Verify the output contains success message
            output = captured_output.getvalue()
            self.assertIn('Connected', output)
            self.assertIn('QmPeer1', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_id_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'id' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'id'
        }[i] if i < 2 else IndexError()
        mock_argv.__len__.return_value = 2
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_id.return_value = {
            'success': True,
            'operation': 'ipfs_id',
            'id': 'QmMyPeerId',
            'public_key': 'PUBKEY123',
            'addresses': [
                '/ip4/127.0.0.1/tcp/4001/p2p/QmMyPeerId',
                '/ip4/192.168.1.1/tcp/4001/p2p/QmMyPeerId'
            ],
            'agent_version': 'go-ipfs/0.10.0',
            'protocol_version': 'ipfs/0.1.0'
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify ipfs_id was called
            mock_instance.ipfs_id.assert_called_once()
            
            # Verify the output contains peer info
            output = captured_output.getvalue()
            self.assertIn('QmMyPeerId', output)
            self.assertIn('PUBKEY123', output)
            self.assertIn('/ip4/127.0.0.1/tcp/4001/p2p/QmMyPeerId', output)
            self.assertIn('go-ipfs/0.10.0', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_daemon_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'daemon' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'daemon'
        }[i] if i < 2 else IndexError()
        mock_argv.__len__.return_value = 2
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.daemon_start.return_value = {
            'success': True,
            'operation': 'daemon_start',
            'daemon_running': True
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify daemon_start was called
            mock_instance.daemon_start.assert_called_once()
            
            # Verify the output contains success message
            output = captured_output.getvalue()
            self.assertIn('Daemon', output)
            self.assertIn('started', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_shutdown_command(self, mock_ipfs_kit, mock_argv):
        """Test CLI handling of the 'shutdown' command."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'shutdown'
        }[i] if i < 2 else IndexError()
        mock_argv.__len__.return_value = 2
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.daemon_stop.return_value = {
            'success': True,
            'operation': 'daemon_stop',
            'daemon_running': False
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify daemon_stop was called
            mock_instance.daemon_stop.assert_called_once()
            
            # Verify the output contains success message
            output = captured_output.getvalue()
            self.assertIn('Daemon', output)
            self.assertIn('stopped', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_error_handling(self, mock_ipfs_kit, mock_argv):
        """Test CLI error handling for failed operations."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'add',
            2: 'nonexistent_file.txt'
        }[i] if i < 3 else IndexError()
        mock_argv.__len__.return_value = 3
        
        # Mock IPFS kit instance with error result
        mock_instance = MagicMock()
        mock_instance.ipfs_add_file.return_value = {
            'success': False,
            'operation': 'ipfs_add_file',
            'error': 'File does not exist',
            'error_type': 'file_error'
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code (should be non-zero for error)
            self.assertNotEqual(exit_code, 0)
            
            # Verify the output contains error message
            output = captured_output.getvalue()
            self.assertIn('Error', output)
            self.assertIn('File does not exist', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_progress_display(self, mock_ipfs_kit, mock_argv):
        """Test CLI progress display for long-running operations."""
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'add',
            2: '-r',
            3: self.test_dir
        }[i] if i < 4 else IndexError()
        mock_argv.__len__.return_value = 4
        
        # Mock IPFS kit instance with progress updates
        mock_instance = MagicMock()
        
        # Simulate progress callbacks
        def add_with_progress(*args, **kwargs):
            # Call the progress callback if provided
            if 'progress_callback' in kwargs:
                progress_cb = kwargs['progress_callback']
                # Simulate progress updates
                progress_cb(0.0, "Starting upload")
                progress_cb(0.25, "25% complete")
                progress_cb(0.5, "50% complete")
                progress_cb(0.75, "75% complete")
                progress_cb(1.0, "Upload complete")
            
            return {
                'success': True,
                'operation': 'ipfs_add_directory',
                'directory_cid': 'QmDirTest',
                'files': [
                    {'cid': 'QmFile1', 'name': 'file1.txt'},
                    {'cid': 'QmFile2', 'name': 'file2.txt'}
                ]
            }
        
        mock_instance.ipfs_add_directory.side_effect = add_with_progress
        mock_ipfs_kit.return_value = mock_instance
        
        # Capture stdout during execution
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        try:
            # Run the CLI
            exit_code = self.cli_main()
            
            # Check the exit code
            self.assertEqual(exit_code, 0)
            
            # Verify progress was displayed
            output = captured_output.getvalue()
            self.assertIn('25%', output)
            self.assertIn('50%', output)
            self.assertIn('75%', output)
            self.assertIn('complete', output)
            
        finally:
            # Reset stdout
            sys.stdout = sys.__stdout__
    
    @patch('sys.argv')
    @patch('ipfs_kit_py.ipfs_kit.ipfs_kit')
    def test_cli_colorized_output(self, mock_ipfs_kit, mock_argv):
        """Test CLI colorized output for better readability."""
        # This test checks if colorization markers are in the output
        # Actual colors depend on the colorization library used
        
        # Mock command-line arguments
        mock_argv.__getitem__.side_effect = lambda i: {
            0: 'ipfs_kit',
            1: 'id'
        }[i] if i < 2 else IndexError()
        mock_argv.__len__.return_value = 2
        
        # Mock IPFS kit instance
        mock_instance = MagicMock()
        mock_instance.ipfs_id.return_value = {
            'success': True,
            'operation': 'ipfs_id',
            'id': 'QmMyPeerId',
            'addresses': ['/ip4/127.0.0.1/tcp/4001/p2p/QmMyPeerId']
        }
        mock_ipfs_kit.return_value = mock_instance
        
        # Patch the colorization function to check if it's called
        with patch('ipfs_kit_py.cli.colorize') as mock_colorize:
            # Mock colorize to return a special marker for testing
            mock_colorize.side_effect = lambda text, color: f"[{color}]{text}[/{color}]"
            
            # Capture stdout during execution
            captured_output = io.StringIO()
            sys.stdout = captured_output
            
            try:
                # Run the CLI
                exit_code = self.cli_main()
                
                # Check the exit code
                self.assertEqual(exit_code, 0)
                
                # Verify colorize was called for important parts
                output = captured_output.getvalue()
                self.assertIn('[green]', output)  # Success messages in green
                self.assertIn('[blue]', output)   # Peer IDs in blue
                
            finally:
                # Reset stdout
                sys.stdout = sys.__stdout__


if __name__ == '__main__':
    unittest.main()