import os
import sys
import unittest
import subprocess
from unittest.mock import patch, MagicMock
import importlib.util

# Add parent directory to path so we can import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the installer module
spec = importlib.util.spec_from_file_location("install_libp2p",
                                             os.path.join(os.path.dirname(__file__),
                                                         "..", "install_libp2p.py"))
install_libp2p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(install_libp2p)

class TestLibP2PInstaller(unittest.TestCase):

    def test_check_dependency_installed(self):
        """Test dependency checking when dependency is installed."""
        # Mock libp2p as installed
        with patch.dict('sys.modules', {'libp2p': MagicMock(__version__='0.1.5')}):
            installed, version = install_libp2p.check_dependency('libp2p')
            self.assertTrue(installed)
            self.assertEqual(version, '0.1.5')

    def test_check_dependency_not_installed(self):
        """Test dependency checking when dependency is not installed."""
        # Mock ImportError for a non-existent package
        with patch('importlib.import_module', side_effect=ImportError):
            installed, version = install_libp2p.check_dependency('nonexistent-package')
            self.assertFalse(installed)
            self.assertIsNone(version)

    def test_special_case_google_protobuf(self):
        """Test handling of google-protobuf package."""
        # Mock google.protobuf as installed
        with patch.dict('sys.modules', {
            'google': MagicMock(),
            'google.protobuf': MagicMock(__version__='3.19.4')
        }):
            installed, version = install_libp2p.check_dependency('google-protobuf')
            self.assertTrue(installed)
            self.assertEqual(version, '3.19.4')

    def test_install_dependencies(self):
        """Test dependency installation process."""
        # Simply check that installation succeeds when all is well
        with patch('subprocess.check_call', return_value=0):
            # Force will bypass the first check and always try to install
            result = install_libp2p.install_dependencies(force=True)
            self.assertTrue(result)

    def test_install_dependencies_already_installed(self):
        """Test skipping installation when already installed."""
        # Capture check_dependency calls
        with patch.object(install_libp2p, 'check_dependency', return_value=(True, '1.0.0')) as mock_dep:
            with patch.object(subprocess, 'check_call') as mock_call:
                # Force it to go through the whole check path
                install_libp2p.install_dependencies(force=False)

                # It should check each dependency but not install anything
                self.assertEqual(mock_dep.call_count, len(install_libp2p.REQUIRED_DEPENDENCIES))
                mock_call.assert_not_called()

    def test_verify_libp2p_functionality(self):
        """Test verification of libp2p functionality."""
        # Set up all the necessary mocks
        mocks = {
            'libp2p': MagicMock(),
            'libp2p.crypto': MagicMock(),
            'libp2p.crypto.keys': MagicMock(generate_key_pair=MagicMock(return_value=MagicMock())),
            'multiaddr': MagicMock(Multiaddr=MagicMock(return_value=MagicMock()))
        }

        with patch.dict('sys.modules', mocks):
            with patch('importlib.import_module', side_effect=lambda module: mocks.get(module, MagicMock())):
                # Test the function directly with minimal mocking
                result = install_libp2p.verify_libp2p_functionality()
                self.assertTrue(result)

    def test_install_dependencies_auto(self):
        """Test the auto-installation function."""
        with patch.object(install_libp2p, 'install_dependencies', return_value=True) as mock_install:
            with patch.object(install_libp2p, 'verify_libp2p_functionality', return_value=True) as mock_verify:
                # Run the auto-install function
                result = install_libp2p.install_dependencies_auto(force=False, verbose=True)

                # Verify results
                self.assertTrue(result)
                mock_install.assert_called_once_with(force=False, verbose=True)
                mock_verify.assert_called_once()

if __name__ == '__main__':
    unittest.main()
