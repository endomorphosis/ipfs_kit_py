"""Utility functions for PyArrow mocking in tests."""

import unittest.mock
from unittest.mock import MagicMock, patch
import sys
import logging
import contextlib
import functools

# Configure logger
logger = logging.getLogger(__name__)

def apply_pyarrow_mock_patches():
    """
    Apply comprehensive PyArrow mocking patches for tests.

    This function creates mock objects for PyArrow and related modules
    to prevent import and dependency errors during testing.

    Returns:
        Dictionary with the patch objects that should be used as context managers
    """
    # Create mock pyarrow module
    mock_pa = MagicMock()

    # Create a custom Table class for proper isinstance checks
    class MockTable(MagicMock):
        pass

    # Set up the Table class in the mock module
    mock_pa.Table = MockTable

    # Create mock objects for PyArrow modules
    mock_modules = {
        'pyarrow': mock_pa,
        'fsspec': MagicMock(),
        'pyarrow.plasma': MagicMock(),
        'pyarrow.parquet': MagicMock(),
        'pyarrow.compute': MagicMock(),
        'pyarrow.dataset': MagicMock()
    }

    # Create sys.modules patch
    sys_modules_patch = patch.dict("sys.modules", mock_modules)

    # Create patch for get_filesystem method using the string path and new_callable
    get_filesystem_patch = patch("ipfs_kit_py.ipfs_kit.ipfs_kit.get_filesystem", new_callable=MagicMock)

    # Create patch for ArrowMetadataIndex
    arrow_metadata_patch = patch("ipfs_kit_py.ipfs_kit.ArrowMetadataIndex", MagicMock())

    return {
        'sys_modules_patch': sys_modules_patch,
        'get_filesystem_patch': get_filesystem_patch,
        'arrow_metadata_patch': arrow_metadata_patch
    }

# Context manager for applying PyArrow mocks
@contextlib.contextmanager
def pyarrow_mock_context():
    """
    Context manager that applies PyArrow mocking.

    Example usage:

    with pyarrow_mock_context():
        # Code that uses PyArrow
        pass
    """
    patches = apply_pyarrow_mock_patches()

    # Start all patches
    for patch_obj in patches.values():
        patch_obj.start()

    try:
        yield
    finally:
        # Stop all patches in reverse order
        for patch_obj in reversed(list(patches.values())):
            patch_obj.stop()

# Decorator for applying PyArrow mocks to functions
def with_pyarrow_mocks(func):
    """
    Decorator to apply PyArrow mocking to a test method or class.

    Example usage:

    @with_pyarrow_mocks
    def test_something(self):
        # Test that uses PyArrow
        pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with pyarrow_mock_context():
            return func(*args, **kwargs)
    return wrapper

# Patch for test_binary_download.py
def patch_binary_download_tests():
    """
    Apply specific patches needed for test_binary_download.py tests.

    Returns:
        A list of patch objects that should be used as context managers
    """
    # Create a mock pyarrow module with Table class for isinstance checks
    mock_pa = MagicMock()

    # Create a custom Table class for proper isinstance checks
    class MockTable(MagicMock):
        pass

    # Set up the Table class in the mock module
    mock_pa.Table = MockTable

    # Create patchers
    patches = [
        patch.dict("sys.modules", {
            'pyarrow': mock_pa,
            'fsspec': MagicMock(),
            'pyarrow.plasma': MagicMock(),
            'pyarrow.parquet': MagicMock(),
            'pyarrow.compute': MagicMock(),
            'pyarrow.dataset': MagicMock()
        }),
        patch("ipfs_kit_py.ipfs_kit.ipfs_kit.get_filesystem", return_value=None),
        patch("ipfs_kit_py.ipfs_kit.ArrowMetadataIndex", MagicMock())
    ]

    return patches

# Patch for test_first_run_initialization.py
def patch_initialization_tests():
    """
    Apply specific patches needed for test_first_run_initialization.py tests.

    Returns:
        A list of patch objects that should be used as context managers
    """
    # Create a mock pyarrow module with Table class for isinstance checks
    mock_pa = MagicMock()

    # Create a custom Table class for proper isinstance checks
    class MockTable(MagicMock):
        pass

    # Set up the Table class in the mock module
    mock_pa.Table = MockTable

    # Create patchers
    patches = [
        patch.dict("sys.modules", {
            'pyarrow': mock_pa,
            'fsspec': MagicMock(),
            'pyarrow.plasma': MagicMock(),
            'pyarrow.parquet': MagicMock(),
            'pyarrow.compute': MagicMock(),
            'pyarrow.dataset': MagicMock()
        }),
        patch("ipfs_kit_py.ipfs_kit.ipfs_kit.get_filesystem", return_value=None),
        patch("ipfs_kit_py.ipfs_kit.ArrowMetadataIndex", MagicMock())
    ]

    return patches

# Patch for test_schema_column_optimization.py
def patch_schema_column_optimization_tests():
    """
    Apply specific patches needed for test_schema_column_optimization.py tests.

    Returns:
        A list of patch objects that should be used as context managers
    """
    # Create a mock pyarrow module with some functionality
    mock_pa = MagicMock()

    # Create a custom Table class for proper isinstance checks
    class MockTable(MagicMock):
        pass

    # Set up the Table class in the mock_pa module
    mock_pa.Table = MockTable

    # Set up pa.string() and pa.int64() to return objects that can be used in tests
    mock_string_type = MagicMock()
    mock_string_type.__str__ = lambda self: "string"
    mock_int64_type = MagicMock()
    mock_int64_type.__str__ = lambda self: "int64"
    mock_bool_type = MagicMock()
    mock_bool_type.__str__ = lambda self: "bool"
    mock_float64_type = MagicMock()
    mock_float64_type.__str__ = lambda self: "float64"

    # Set up type detection methods
    mock_pa.types.is_string = lambda t: str(t) == "string"
    mock_pa.types.is_integer = lambda t: str(t) == "int64"
    mock_pa.types.is_boolean = lambda t: str(t) == "bool"
    mock_pa.types.is_floating = lambda t: str(t) == "float64"

    mock_pa.string = lambda: mock_string_type
    mock_pa.int64 = lambda: mock_int64_type
    mock_pa.bool_ = lambda: mock_bool_type
    mock_pa.float64 = lambda: mock_float64_type

    # Function to create a field with correct attributes
    def create_mock_field(name, type_obj, metadata=None):
        field = MagicMock()
        field.name = name
        field.type = type_obj
        field.metadata = metadata or {}
        field.__str__ = lambda self: f"field({name}: {type_obj})"
        return field

    # Mock field creation function
    mock_pa.field = create_mock_field

    # Schema creation function
    def create_mock_schema(fields):
        schema = MagicMock()
        schema.names = [f.name for f in fields]
        schema.__len__ = lambda self: len(fields)
        schema.__getitem__ = lambda self, idx: fields[idx] if isinstance(idx, int) else next((f for f in fields if f.name == idx), None)
        schema.__iter__ = lambda self: iter(fields)
        return schema

    mock_pa.schema = create_mock_schema

    # Array creation that returns usable mock arrays
    def create_mock_array(data):
        array = MagicMock()
        array.as_py = lambda: data
        array.__getitem__ = lambda self, idx: MagicMock(as_py=lambda: data[idx] if idx < len(data) else None)
        return array

    mock_pa.array = create_mock_array

    # Table creation from arrays and schema
    def create_mock_table(data_dict=None, schema=None):
        if data_dict:
            table = MagicMock()
            table.schema = create_mock_schema([create_mock_field(k, mock_pa.string() if isinstance(next(iter(v), None), str) else mock_pa.int64()) for k, v in data_dict.items()]) if not schema else schema
            table.column_names = list(data_dict.keys())
            table.num_rows = len(next(iter(data_dict.values()), []))
            table.num_columns = len(data_dict)

            # Allow dictionary-style access to columns
            def getitem(name):
                if name in data_dict:
                    return create_mock_array(data_dict[name])
                return MagicMock()

            table.__getitem__ = getitem
            return table
        else:
            return MagicMock()

    mock_pa.Table.from_arrays = lambda arrays, names=None, schema=None: create_mock_table({name: arrays[i] for i, name in enumerate(names)}, schema)

    # Create mock compute module
    mock_pc = MagicMock()
    mock_pc.sum.return_value.as_py.return_value = 0
    mock_pc.min.return_value.as_py.return_value = 0
    mock_pc.max.return_value.as_py.return_value = 100
    mock_pc.mean.return_value.as_py.return_value = 50
    mock_pc.stddev.return_value.as_py.return_value = 10

    # Create mock dataset module
    mock_dataset = MagicMock()

    # Create mock parquet module
    mock_pq = MagicMock()
    mock_pq.write_table = MagicMock()
    mock_pq.read_table = lambda path, **kwargs: create_mock_table({"cid": ["Qm123", "Qm456"], "size_bytes": [1000, 2000]})

    # Create specialized patchers for schema column optimization tests
    patches = [
        patch.dict("sys.modules", {
            'pyarrow': mock_pa,
            'fsspec': MagicMock(),
            'pyarrow.plasma': MagicMock(),
            'pyarrow.parquet': mock_pq,
            'pyarrow.compute': mock_pc,
            'pyarrow.dataset': mock_dataset
        }),
        patch("ipfs_kit_py.ipfs_kit.ipfs_kit.get_filesystem", return_value=None),
        patch("ipfs_kit_py.ipfs_kit.ArrowMetadataIndex", MagicMock())
    ]

    return patches

# Patch for test_storage_wal.py
def patch_storage_wal_tests():
    """
    Apply specific patches needed for test_storage_wal.py tests.

    Returns:
        A list of patch objects that should be used as context managers
    """
    # Create a mock pyarrow module
    mock_pa = MagicMock()

    # Create a custom Table class for proper isinstance checks
    class MockTable(MagicMock):
        pass

    # Set up the Table class in the mock module
    mock_pa.Table = MockTable

    # Create mock schema and field types
    mock_string_type = MagicMock()
    mock_string_type.__str__ = lambda self: "string"
    mock_int64_type = MagicMock()
    mock_int64_type.__str__ = lambda self: "int64"
    mock_timestamp_type = MagicMock()
    mock_timestamp_type.__str__ = lambda self: "timestamp[ms]"
    mock_struct_type = MagicMock()
    mock_struct_type.__str__ = lambda self: "struct"
    mock_map_type = MagicMock()
    mock_map_type.__str__ = lambda self: "map"

    # Type checks
    mock_pa.types.is_string = lambda t: str(t) == "string"
    mock_pa.types.is_integer = lambda t: str(t) == "int64"
    mock_pa.types.is_timestamp = lambda t: str(t) == "timestamp[ms]"
    mock_pa.types.is_struct = lambda t: str(t) == "struct"
    mock_pa.types.is_map = lambda t: str(t) == "map"

    # Type creation functions
    mock_pa.string = lambda: mock_string_type
    mock_pa.int64 = lambda: mock_int64_type
    mock_pa.int32 = lambda: MagicMock()
    mock_pa.int8 = lambda: MagicMock()
    mock_pa.bool_ = lambda: MagicMock()
    mock_pa.timestamp = lambda unit: mock_timestamp_type

    # Setup mock struct functionality
    mock_struct_type.__iter__ = lambda self: iter(self.fields) if hasattr(self, 'fields') else iter([])

    # Function to create a mock field
    def create_mock_field(name, type_obj, metadata=None):
        field = MagicMock()
        field.name = name
        field.type = type_obj
        field.metadata = metadata or {}
        field.__str__ = lambda self: f"field({name}: {type_obj})"
        return field

    mock_pa.field = create_mock_field

    # Function to create a mock schema
    def create_mock_schema(fields):
        schema = MagicMock()
        schema.names = [f.name for f in fields]
        schema.fields = fields
        schema.__len__ = lambda self: len(fields)
        schema.__getitem__ = lambda self, idx: fields[idx] if isinstance(idx, int) else next((f for f in fields if f.name == idx), None)
        schema.__iter__ = lambda self: iter(fields)
        return schema

    mock_pa.schema = create_mock_schema

    # Function to create mock arrays
    def create_mock_array(data, type=None):
        array = MagicMock()
        array.as_py = lambda: data
        array.__getitem__ = lambda self, idx: array
        return array

    mock_pa.array = create_mock_array

    # Function to create mock record batches
    def create_mock_batch(arrays, schema):
        batch = MagicMock()
        batch.schema = schema
        batch.num_rows = len(arrays[0]) if arrays and len(arrays) > 0 else 0
        batch.num_columns = len(arrays)
        return batch

    mock_pa.RecordBatch.from_arrays = lambda arrays, schema: create_mock_batch(arrays, schema)

    # Function to create a mock table
    def create_mock_table(data_dict=None, schema=None):
        table = MagicMock()
        table.schema = schema
        table.num_rows = 0
        if data_dict:
            table.column_names = list(data_dict.keys())
            table.num_rows = len(next(iter(data_dict.values()), []))
            table.num_columns = len(data_dict)

            # Dictionary access
            def getitem(key):
                if key in data_dict:
                    return create_mock_array(data_dict[key])
                return MagicMock()

            table.__getitem__ = getitem

        # Method to convert to Python list
        table.to_pylist = lambda: [
            {k: v[i] for k, v in data_dict.items()} for i in range(table.num_rows)
        ] if data_dict else []

        return table

    mock_pa.Table.from_batches = lambda batches, schema=None: create_mock_table()
    mock_pa.concat_tables = lambda tables: tables[0] if tables else create_mock_table()

    # Create mock parquet module
    mock_pq = MagicMock()
    mock_pq.read_table = lambda path, **kwargs: create_mock_table({"operation_id": ["test-id"], "status": ["pending"]})
    mock_pq.write_table = MagicMock()

    # Create mock compute module
    mock_pc = MagicMock()
    mock_pc.equal = lambda col, val: MagicMock()
    mock_pc.invert = lambda mask: MagicMock()
    mock_pc.sum = lambda arr: MagicMock(as_py=lambda: 0)
    mock_pc.cast = lambda arr, dtype: arr

    # Create patchers
    patches = [
        patch.dict("sys.modules", {
            'pyarrow': mock_pa,
            'pyarrow.parquet': mock_pq,
            'pyarrow.compute': mock_pc,
            'pyarrow.dataset': MagicMock(),
            'pyarrow.plasma': MagicMock()
        })
    ]

    return patches

# Create specialized method replacement for specific testing needs
def create_method_replacement(original_method, mock_result=None, error_handler=None):
    """
    Create a method replacement that tries the original method first and falls back to a mock.

    Args:
        original_method: The original method to try first
        mock_result: The result to return if the original method fails
        error_handler: Optional function to handle errors in the original method

    Returns:
        A function that can be used as a method replacement
    """
    def replacement_method(*args, **kwargs):
        try:
            # Try original method first
            return original_method(*args, **kwargs)
        except Exception as e:
            logger.debug(f"Original method failed: {e}")

            # Call error handler if provided
            if error_handler:
                error_handler(e, *args, **kwargs)

            # Return mock result
            return mock_result

    return replacement_method
