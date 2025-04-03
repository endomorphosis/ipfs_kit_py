"""
Tests for graceful handling of optional dependencies.

This test suite verifies that the package correctly handles cases
where optional dependencies are missing, providing graceful degradation
and helpful error messages.

To fully test all scenarios, run this test suite with different
combinations of dependencies installed:

1. With only core dependencies:
   pip install -e .

2. With arrow dependencies:
   pip install -e ".[arrow]"

3. With fsspec dependencies:
   pip install -e ".[fsspec]"

4. With all dependencies:
   pip install -e ".[full]"
"""

import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestDependencyHandling(unittest.TestCase):
    """Tests for graceful handling of optional dependencies."""

    def test_core_package_import(self):
        """Verify that the main package can be imported without errors."""
        import ipfs_kit_py

        self.assertIsNotNone(ipfs_kit_py)

    def test_arrow_module_import(self):
        """Verify that arrow_metadata_index module can be imported without errors."""
        import ipfs_kit_py.arrow_metadata_index

        self.assertIsNotNone(ipfs_kit_py.arrow_metadata_index)

        # Check for correct flag settings
        self.assertIsInstance(ipfs_kit_py.arrow_metadata_index.ARROW_AVAILABLE, bool)

        # Verify placeholder imports exist when PyArrow is not available
        if not ipfs_kit_py.arrow_metadata_index.ARROW_AVAILABLE:
            self.assertIsNone(ipfs_kit_py.arrow_metadata_index.pa)
            self.assertIsNone(ipfs_kit_py.arrow_metadata_index.pc)
            self.assertIsNone(ipfs_kit_py.arrow_metadata_index.pq)
            self.assertIsNone(ipfs_kit_py.arrow_metadata_index.ac)
            self.assertIsNone(ipfs_kit_py.arrow_metadata_index.dataset)

    def test_arrow_metadata_index_class(self):
        """Test behavior when trying to create ArrowMetadataIndex without PyArrow."""
        from ipfs_kit_py.arrow_metadata_index import ARROW_AVAILABLE, ArrowMetadataIndex

        if not ARROW_AVAILABLE:
            # Should raise a helpful error message when PyArrow is not installed
            with self.assertRaises(ImportError) as context:
                index = ArrowMetadataIndex()

            # Verify the error message is helpful
            self.assertIn("PyArrow is required", str(context.exception))
            self.assertIn("pip install ipfs_kit_py[arrow]", str(context.exception))
        else:
            # Test that the class can be instantiated when PyArrow is available
            try:
                index = ArrowMetadataIndex()
                self.assertIsNotNone(index)
            except Exception as e:
                # This could be a legitimate error related to initialization,
                # but not from missing dependencies
                self.fail(f"ArrowMetadataIndex creation failed with PyArrow installed: {e}")

    def test_ai_ml_integration_import(self):
        """Verify that ai_ml_integration module can be imported without errors."""
        import ipfs_kit_py.ai_ml_integration

        self.assertIsNotNone(ipfs_kit_py.ai_ml_integration)

        # Check for correct flag settings
        self.assertIsInstance(ipfs_kit_py.ai_ml_integration.NUMPY_AVAILABLE, bool)
        self.assertIsInstance(ipfs_kit_py.ai_ml_integration.PANDAS_AVAILABLE, bool)
        self.assertIsInstance(ipfs_kit_py.ai_ml_integration.SKLEARN_AVAILABLE, bool)
        self.assertIsInstance(ipfs_kit_py.ai_ml_integration.TORCH_AVAILABLE, bool)
        self.assertIsInstance(ipfs_kit_py.ai_ml_integration.TF_AVAILABLE, bool)

    def test_model_registry_class(self):
        """Test behavior when using ModelRegistry without required dependencies."""
        from ipfs_kit_py.ai_ml_integration import ModelRegistry

        # Create a mock IPFS client
        mock_client = MagicMock()

        # Should always be able to create an instance (constructor handles graceful degradation)
        registry = ModelRegistry(mock_client)
        self.assertIsNotNone(registry)

        # Test model operations - these should provide helpful error messages if deps are missing
        try:
            # Create a very simple mock model for testing
            model = MagicMock()
            model.__class__.__name__ = "MockModel"

            result = registry.add_model(model, "test_model", version="1.0")

            # If execution continues, check that result includes necessary keys
            self.assertIn("success", result)

        except ImportError as e:
            # If an import error is raised, it should include helpful information
            error_message = str(e)
            if (
                "sklearn" in error_message
                or "torch" in error_message
                or "tensorflow" in error_message
            ):
                self.assertIn("pip install", error_message.lower())
            else:
                # Only raise if it's some other unexpected ImportError
                raise

    def test_fsspec_handling(self):
        """Test handling of missing fsspec dependency."""
        import ipfs_kit_py.ipfs_fsspec

        # Test if we can import the module
        self.assertIsNotNone(ipfs_kit_py.ipfs_fsspec)

        # Try to get the filesystem class
        # This should either return a proper class or raise a helpful ImportError
        try:
            from ipfs_kit_py.ipfs_fsspec import IPFSFileSystem

            self.assertIsNotNone(IPFSFileSystem)
        except ImportError as e:
            self.assertIn("fsspec", str(e).lower())
            self.assertIn("pip install", str(e).lower())

    def test_high_level_api_graceful_degradation(self):
        """Test High-Level API handling of missing dependencies."""
        try:
            from ipfs_kit_py.high_level_api import IPFSSimpleAPI

            # Create with testing_mode to avoid requiring IPFS daemon
            api = IPFSSimpleAPI(testing_mode=True)

            # Test get_filesystem handling - should return None or warn if fsspec missing
            fs = api.get_filesystem()

            # If execution continues, fs might be None but we shouldn't crash
            # If fsspec is available, fs should be a filesystem object

        except ImportError as e:
            # The only acceptable ImportError would be if fastapi itself is missing (api extra)
            if "fastapi" in str(e).lower():
                self.assertIn("pip install ipfs_kit_py[api]", str(e).lower())
            else:
                # Any other ImportError should be raised
                raise


if __name__ == "__main__":
    unittest.main()
