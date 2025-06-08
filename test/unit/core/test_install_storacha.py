import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import importlib.util

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the installer module
spec = importlib.util.spec_from_file_location("install_storacha", 
                                             os.path.join(os.path.dirname(__file__), 
                                                         "..", "install_storacha.py"))
install_storacha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install_storacha)

class TestStorachaInstaller(unittest.TestCase):
    
    def test_check_dependency_installed(self):
        """Test dependency checking when dependency is installed."""
        # Mock requests as installed
        with patch.dict('sys.modules', {'requests': MagicMock(__version__='2.28.1')}):
            installed, version = install_storacha.check_dependency('requests')
            self.assertTrue(installed)
            self.assertEqual(version, '2.28.1')
    
    def test_check_dependency_not_installed(self):
        """Test dependency checking when dependency is not installed."""
        # Mock ImportError for a non-existent package
        with patch('importlib.import_module', side_effect=ImportError):
            installed, version = install_storacha.check_dependency('nonexistent-package')
            self.assertFalse(installed)
            self.assertIsNone(version)
    
    def test_package_name_mapping(self):
        """Test handling of packages where the name differs from module name."""
        # Mock yaml as installed (for pyyaml package)
        with patch.dict('sys.modules', {'yaml': MagicMock(__version__='6.0')}):
            installed, version = install_storacha.check_dependency('pyyaml')
            self.assertTrue(installed)
            self.assertEqual(version, '6.0')

    @patch('subprocess.run')
    def test_check_npm_installed(self, mock_run):
        """Test checking if npm is installed."""
        # Mock successful subprocess call
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'8.19.3\n'
        mock_run.return_value = mock_process
        
        self.assertTrue(install_storacha.check_npm_installed())
        
        # Mock subprocess failure
        mock_run.side_effect = FileNotFoundError
        self.assertFalse(install_storacha.check_npm_installed())
    
    @patch('subprocess.run')
    def test_check_w3_cli_installed(self, mock_run):
        """Test checking if W3 CLI is installed."""
        # Mock successful subprocess call
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = '0.8.2\n'
        mock_run.return_value = mock_process
        
        installed, version = install_storacha.check_w3_cli_installed()
        self.assertTrue(installed)
        self.assertEqual(version, '0.8.2')
        
        # Mock subprocess failure
        mock_run.side_effect = FileNotFoundError
        installed, version = install_storacha.check_w3_cli_installed()
        self.assertFalse(installed)
        self.assertIsNone(version)

    @patch('install_storacha.check_w3_cli_installed')
    def test_verify_functionality(self, mock_check_w3):
        """Test verification of storacha functionality."""
        # Create a separate test function that mocks only what's needed
        def test_verify():
            # Mock test function to avoid import issues 
            with patch('install_storacha.check_w3_cli_installed') as mock_w3:
                # Mock successful W3 CLI check
                mock_w3.return_value = (True, '0.8.2')
                
                # Mock subprocess run for the W3 command test
                with patch('subprocess.run') as mock_run:
                    mock_process = MagicMock()
                    mock_process.returncode = 0
                    mock_process.stdout = 'Usage: w3 command [options]'
                    mock_run.return_value = mock_process
                    
                    # Call the function under test
                    return install_storacha.verify_storacha_functionality()
        
        # Call the test function that contains all necessary mocks
        self.assertTrue(test_verify())

if __name__ == '__main__':
    unittest.main()