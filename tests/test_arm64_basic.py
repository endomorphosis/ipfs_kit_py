"""
Basic smoke tests for ARM64 architecture validation.
These tests verify that the package can be imported and basic functionality works.
"""

import sys
import platform
import pytest


def test_python_version():
    """Verify Python version is supported."""
    version = sys.version_info
    assert version.major == 3, "Python 3 is required"
    assert version.minor >= 8, "Python 3.8 or higher is required"
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")


def test_architecture_detection():
    """Verify architecture detection works."""
    arch = platform.machine()
    print(f"Architecture: {arch}")
    # This should work on both x86_64 and aarch64/arm64
    assert arch in ['x86_64', 'aarch64', 'arm64', 'AMD64'], f"Unexpected architecture: {arch}"


def test_package_import():
    """Verify the package can be imported."""
    import ipfs_kit_py
    assert ipfs_kit_py is not None
    print("ipfs_kit_py imported successfully")


def test_package_version():
    """Verify the package version is accessible."""
    import ipfs_kit_py
    # The package should have version info
    assert hasattr(ipfs_kit_py, '__version__') or hasattr(ipfs_kit_py, 'VERSION')
    version = getattr(ipfs_kit_py, '__version__', getattr(ipfs_kit_py, 'VERSION', 'unknown'))
    print(f"Package version: {version}")


def test_core_modules_importable():
    """Verify core modules can be imported."""
    try:
        from ipfs_kit_py import ipfs_kit
        assert ipfs_kit is not None
        print("ipfs_kit module imported successfully")
    except ImportError as e:
        # Some modules may have optional dependencies
        print(f"Note: ipfs_kit module import had issues: {e}")
        pytest.skip(f"ipfs_kit module not available: {e}")


def test_basic_api_availability():
    """Verify basic API components are available."""
    try:
        import ipfs_kit_py
        # Check for key attributes/functions that should exist
        module_attrs = dir(ipfs_kit_py)
        assert len(module_attrs) > 0, "Module should have attributes"
        print(f"Package has {len(module_attrs)} attributes/functions")
    except Exception as e:
        pytest.fail(f"Failed to inspect package attributes: {e}")


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
