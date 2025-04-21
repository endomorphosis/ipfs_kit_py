def pyarrow_mock_context():
    """Context manager stub for pyarrow mocks."""
    class DummyContext:
        def __enter__(self): pass
        def __exit__(self, exc_type, exc, tb): pass
    return DummyContext()


def patch_storage_wal_tests():
    """Stub for applying storage WAL tests patchers."""
    return []


def apply_pyarrow_mock_patches(func):
    """Decorator stub for applying pyarrow patches."""
    return func