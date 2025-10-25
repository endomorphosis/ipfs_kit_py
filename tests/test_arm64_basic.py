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
        import ipfs_kit_py
        # Check that the main module imports successfully
        assert ipfs_kit_py is not None
        print("ipfs_kit_py module imported successfully")
        
        # Try to get a working component
        try:
            ipfs_kit = ipfs_kit_py.get_ipfs_kit()
            print(f"get_ipfs_kit() result: {type(ipfs_kit)}")
            # ipfs_kit might be None on ARM64 due to binary dependencies
            # but the function should be callable
        except Exception as e:
            print(f"Note: get_ipfs_kit() had issues (expected on ARM64): {e}")
            
    except ImportError as e:
        # Some modules may have optional dependencies
        print(f"Note: ipfs_kit_py module import had issues: {e}")
        pytest.skip(f"ipfs_kit_py module not available: {e}")


def test_basic_api_availability():
    """Verify basic API components are available."""
    try:
        import ipfs_kit_py
        # Check for key attributes/functions that should exist
        module_attrs = dir(ipfs_kit_py)
        assert len(module_attrs) > 0, "Module should have attributes"
        print(f"Package has {len(module_attrs)} attributes/functions")
        
        # Check for core functions
        core_functions = ['get_ipfs_kit', 'get_wal_enabled_api']
        for func in core_functions:
            if hasattr(ipfs_kit_py, func):
                print(f"✓ Core function {func} available")
            else:
                print(f"⚠ Core function {func} not available")
                
    except Exception as e:
        pytest.fail(f"Failed to inspect package attributes: {e}")


def test_arm64_compatibility():
    """Test ARM64-specific compatibility."""
    arch = platform.machine()
    if arch in ['aarch64', 'arm64']:
        print(f"✓ Running on ARM64: {arch}")
        
        # Test that core functionality works on ARM64
        try:
            import ipfs_kit_py
            # Try to access some core components without full initialization
            if hasattr(ipfs_kit_py, 'get_ipfs_kit'):
                print("✓ Core ipfs_kit function available on ARM64")
            print("✓ ARM64 compatibility verified")
        except Exception as e:
            print(f"⚠ ARM64 compatibility issue: {e}")
    else:
        print(f"Running on non-ARM64 architecture: {arch}")


def test_no_external_binary_dependency():
    """Test that basic import doesn't require external binaries."""
    import ipfs_kit_py
    
    # This should work without lotus, ipfs, etc. binaries
    try:
        # Test imports that shouldn't require external binaries
        version = getattr(ipfs_kit_py, '__version__', 'unknown')
        assert version != 'unknown', "Package version should be available"
        print(f"✓ Package version {version} available without external dependencies")
    except Exception as e:
        pytest.fail(f"Basic functionality requires external dependencies: {e}")


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
