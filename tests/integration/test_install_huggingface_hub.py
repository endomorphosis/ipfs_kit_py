"""Tests for the Hugging Face Hub installer script.

These tests validate the functionality of the Hugging Face Hub installer script
in the ipfs_kit_py package. They test dependency checking, installation, and
verification functions.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path to import the script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import install_huggingface_hub


class TestInstallHuggingFaceHub(unittest.TestCase):
    """Test cases for the install_huggingface_hub.py script."""

    def test_check_dependency(self):
        """Test the check_dependency function."""
        # Test with an installed module
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.__version__ = "1.0.0"
            mock_import.return_value = mock_module
            
            installed, version = install_huggingface_hub.check_dependency("test_package")
            
            self.assertTrue(installed)
            self.assertEqual(version, "1.0.0")
            mock_import.assert_called_once_with("test_package")
            
        # Test with a package that doesn't have a __version__ attribute
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            # No __version__ attribute
            mock_import.return_value = mock_module
            
            installed, version = install_huggingface_hub.check_dependency("test_package")
            
            self.assertTrue(installed)
            self.assertEqual(version, "unknown")
            
        # Test with an uninstalled module
        with patch('importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError("No module named 'test_package'")
            
            installed, version = install_huggingface_hub.check_dependency("test_package")
            
            self.assertFalse(installed)
            self.assertIsNone(version)

    def test_install_dependencies_all_installed(self):
        """Test installing dependencies when all are already installed."""
        # Mock all dependencies as already installed
        with patch('install_huggingface_hub.check_dependency') as mock_check:
            mock_check.return_value = (True, "1.0.0")
            
            result = install_huggingface_hub.install_dependencies()
            
            self.assertTrue(result)
            # Verify we checked all required dependencies
            self.assertEqual(mock_check.call_count, len(install_huggingface_hub.REQUIRED_DEPENDENCIES))

    def test_main_functions(self):
        """Test the main function with different scenarios."""
        # Test successful installation and verification
        with patch('install_huggingface_hub.install_dependencies') as mock_install, \
             patch('install_huggingface_hub.verify_huggingface_hub_functionality') as mock_verify, \
             patch('argparse.ArgumentParser.parse_args') as mock_args:
            
            # Scenario 1: Successful installation and verification
            mock_install.return_value = True
            mock_verify.return_value = True
            mock_args.return_value = MagicMock(force=False, verbose=False)
            
            return_code = install_huggingface_hub.main()
            
            self.assertEqual(return_code, 0)
            mock_install.assert_called_once_with(force=False, verbose=False)
            mock_verify.assert_called_once()
            
            # Reset mocks for next scenario
            mock_install.reset_mock()
            mock_verify.reset_mock()
            
            # Scenario 2: Successful installation but verification failure
            mock_install.return_value = True
            mock_verify.return_value = False
            
            return_code = install_huggingface_hub.main()
            
            self.assertEqual(return_code, 1)
            mock_install.assert_called_once()
            mock_verify.assert_called_once()
            
            # Reset mocks for next scenario
            mock_install.reset_mock()
            mock_verify.reset_mock()
            
            # Scenario 3: Installation failure
            mock_install.return_value = False
            
            return_code = install_huggingface_hub.main()
            
            self.assertEqual(return_code, 1)
            mock_install.assert_called_once()
            # Verify should not be called if installation fails
            mock_verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()