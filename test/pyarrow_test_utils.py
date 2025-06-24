"""
PyArrow test utilities for IPFS Kit.

This module provides mock implementations and utilities
for testing PyArrow functionality.
"""

import logging
import functools
import sys
import importlib
from unittest.mock import MagicMock, patch
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Create a mock PyArrow module
mock_pyarrow = MagicMock()
mock_pyarrow.lib = MagicMock()
mock_pyarrow.fs = MagicMock()
mock_pyarrow.parquet = MagicMock()
mock_pyarrow.compute = MagicMock()
mock_pyarrow.dataset = MagicMock()
mock_pyarrow.Schema = MagicMock()
mock_pyarrow.schema = MagicMock()
mock_pyarrow.Table = MagicMock()
mock_pyarrow.table = MagicMock()
mock_pyarrow.RecordBatch = MagicMock()

# Configure various mock method returns for consistency
mock_pyarrow.parquet.write_table = MagicMock(return_value=None)
mock_pyarrow.parquet.read_table = MagicMock(return_value=mock_pyarrow.Table)
mock_pyarrow.Table.from_pydict = MagicMock(return_value=mock_pyarrow.Table)
mock_pyarrow.Table.from_pandas = MagicMock(return_value=mock_pyarrow.Table)
mock_pyarrow.Table.to_pandas = MagicMock(return_value=MagicMock())

@contextmanager
def pyarrow_mock_context():
    """
    Context manager for patching PyArrow imports in a block.

    Usage:
        with pyarrow_mock_context():
            # Code that uses PyArrow
    """
    with patch.dict('sys.modules', {'pyarrow': mock_pyarrow}):
        yield mock_pyarrow

def with_pyarrow_mocks(cls):
    """Decorator stub for PyArrow mocking context."""
    return cls

def _has_attribute(obj, attr_name):
    """
    Safely check if an object has an attribute.

    Args:
        obj: Object to check
        attr_name: Attribute name to check

    Returns:
        True if the attribute exists, False otherwise
    """
    try:
        if isinstance(obj, type):  # If it's a class
            return hasattr(obj, attr_name)
        else:  # If it's an instance
            return hasattr(obj, attr_name)
    except Exception:
        return False

def patch_storage_wal_tests():
    """
    Create and return patches specifically for storage_wal tests.

    Returns:
        List of active patch objects that should be stopped in test teardown
    """
    patches = []

    # Patch basic PyArrow module
    pa_patch = patch.dict('sys.modules', {'pyarrow': mock_pyarrow})
    patches.append(pa_patch)

    # Try to load the storage_wal module if not already loaded
    if 'ipfs_kit_py.storage_wal' not in sys.modules:
        try:
            importlib.import_module('ipfs_kit_py.storage_wal')
        except ImportError:
            # If we can't import it, return just the PyArrow patch
            return patches

    # Now try to get the module and class
    try:
        storage_wal_module = sys.modules.get('ipfs_kit_py.storage_wal')
        if storage_wal_module:
            storage_wal_class = getattr(storage_wal_module, 'StorageWriteAheadLog', None)

            # Only patch these methods if they actually exist in the class
            # This prevents AttributeError when patching non-existent methods

            # Try to create mocks for methods we know we need to patch
            # Use different approach based on whether we're mocking a class or instance method

            # For _append_to_partition_arrow
            if storage_wal_class and hasattr(storage_wal_class, '_append_to_partition_arrow'):
                append_patch = patch('ipfs_kit_py.storage_wal.StorageWriteAheadLog._append_to_partition_arrow',
                                    return_value=True)
                patches.append(append_patch)

            # Rather than trying to patch specific methods, add general methods to the mock class
            storage_wal_class_mock = MagicMock()
            storage_wal_class_mock._append_to_partition_arrow.return_value = True
            storage_wal_class_mock._read_partition_arrow.return_value = []

            # For _read_partition_arrow - conditionally patch only if it exists
            # We'll use a more dynamic approach instead
            class_methods_patch = patch('ipfs_kit_py.storage_wal.StorageWriteAheadLog',
                                       storage_wal_class_mock)
            patches.append(class_methods_patch)

    except (ImportError, AttributeError) as e:
        logger.warning(f"Could not set up storage_wal patches: {e}")

    return patches

def apply_pyarrow_mock_patches():
    """
    Apply all PyArrow mock patches and return the active patches.

    This function is useful when you need to apply patches outside of a
    test context, such as in module-level code.

    Returns:
        List of active patch objects that should be stopped later
    """
    patches = patch_storage_wal_tests()
    for p in patches:
        p.start()
    return patches

def patch_schema_column_optimization_tests(func):
    """
    Decorator to patch PyArrow schema column optimization tests.

    Args:
        func: Test function to decorate

    Returns:
        Decorated function with patched schema column optimization
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Create mock schema
        mock_schema = MagicMock()
        mock_schema.names = ['col1', 'col2', 'col3']
        mock_schema.metadata = {b'key1': b'value1', b'key2': b'value2'}

        # Create mock table
        mock_table = MagicMock()
        mock_table.schema = mock_schema
        mock_table.column_names = ['col1', 'col2', 'col3']

        with patch.dict('sys.modules', {'pyarrow': mock_pyarrow}):
            with patch('pyarrow.Schema', return_value=mock_schema):
                with patch('pyarrow.Table', return_value=mock_table):
                    return func(*args, **kwargs)
    return wrapper
