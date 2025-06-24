"""
Verification tests for IPFS Kit Python fixes.

This module contains focused tests that verify our specific fixes:
1. LOTUS_KIT_AVAILABLE constant
2. BackendStorage class methods
"""

def test_lotus_kit_available():
    """Verify that LOTUS_KIT_AVAILABLE is defined and set to True."""
    from ipfs_kit_py.lotus_kit import LOTUS_KIT_AVAILABLE
    assert LOTUS_KIT_AVAILABLE is True, "LOTUS_KIT_AVAILABLE should be True"

def test_backend_storage_methods():
    """Verify that BackendStorage class has the required methods."""
    from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage

    # Check that the class exists and is a class
    assert isinstance(BackendStorage, type), "BackendStorage should be a class"

    # Check for required methods
    required_methods = ['store', 'retrieve', 'list_keys', 'delete']
    for method in required_methods:
        assert hasattr(BackendStorage, method), f"BackendStorage missing '{method}' method"

    # Verify that the methods are callable (defined in the class)
    for method in required_methods:
        method_obj = getattr(BackendStorage, method)
        assert callable(method_obj), f"BackendStorage.{method} should be callable"

def test_backend_storage_initialization():
    """Test that BackendStorage can be initialized with proper arguments."""
    from ipfs_kit_py.mcp.storage_manager.backend_base import BackendStorage
    from ipfs_kit_py.mcp.storage_manager.storage_types import StorageBackendType

    # Create test resources and metadata
    resources = {"test_resource": "value"}
    metadata = {"test_metadata": "value"}

    # Create instance with required arguments
    # Note: BackendStorage is an abstract class so we need to create a concrete subclass
    class TestBackendStorage(BackendStorage):
        def add_content(self, content, metadata=None):
            return {"success": True, "content_id": "test_id"}

        def get_content(self, content_id):
            return {"success": True, "content": b"test content"}

        def remove_content(self, content_id):
            return {"success": True}

        def get_metadata(self, content_id):
            return {"success": True, "metadata": {}}

    # Create an instance
    instance = TestBackendStorage(
        backend_type=StorageBackendType.IPFS,
        resources=resources,
        metadata=metadata
    )

    # Verify instance attributes
    assert instance.backend_type == StorageBackendType.IPFS
    assert instance.resources == resources
    assert instance.metadata == metadata

    # Test the alias methods
    test_content = b"test content"

    # These should call the corresponding abstract methods in the subclass
    store_result = instance.store(test_content)
    assert store_result["success"] is True

    retrieve_result = instance.retrieve("test_id")
    assert retrieve_result["success"] is True

    delete_result = instance.delete("test_id")
    assert delete_result["success"] is True

    list_keys_result = instance.list_keys()
    assert list_keys_result["success"] is True
