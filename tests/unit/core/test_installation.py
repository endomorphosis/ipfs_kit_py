#!/usr/bin/env python
"""
Test script to verify the IPFS Kit package installation and basic functionality.
This script should be run after installing the package to ensure everything is working properly.
"""

import sys
import importlib
import traceback

def check_import(module_name):
    """Check if a module can be imported."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

def check_optional_import(module_name):
    """Check if an optional module can be imported."""
    try:
        importlib.import_module(module_name)
        return "✅ Available"
    except ImportError:
        return "❌ Not available (requires optional dependencies)"

def test_optional_components():
    """Test optional components."""
    optional_modules = {
        "fsspec": "FSSpec integration",
        "pyarrow": "Arrow integration",
        "fastapi": "API server",
        "numpy": "AI/ML integration (basic)",
        "torch": "AI/ML integration (PyTorch)",
        "faiss": "Vector search capabilities",
        "networkx": "Knowledge graph capabilities",
        "matplotlib": "Visualization for performance metrics"
    }

    results = {}
    for module, description in optional_modules.items():
        results[description] = check_optional_import(module)

    return results

def test_ipfs_kit():
    """Test core IPFS Kit functionality."""
    try:
        from ipfs_kit_py import ipfs_kit, __version__

        print(f"IPFS Kit version: {__version__}")

        # Initialize the kit without starting external daemons or doing installer side-effects
        kit_metadata = {
            "auto_download_binaries": False,
            "auto_start_daemons": False,
            "skip_dependency_check": True,
        }
        kit = ipfs_kit(metadata=kit_metadata, auto_start_daemons=False)

        # Check version compatibility
        version_info = kit.get_version_info()
        print(f"Compatible with IPFS version: {version_info.get('version', 'Unknown')}")

        # Check available methods
        methods = [m for m in dir(kit) if not m.startswith('_') and callable(getattr(kit, m))]
        print(f"Available methods: {len(methods)}")

        # Test high-level API (pass through metadata via kwargs)
        from ipfs_kit_py import IPFSSimpleAPI
        api = IPFSSimpleAPI(metadata=kit_metadata)

        print("High-Level API initialized successfully")

        return True
    except Exception as e:
        print(f"Error testing IPFS Kit: {e}")
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    print("=== IPFS Kit Installation Test ===\n")

    # Check core imports
    core_modules = [
        "ipfs_kit_py",
        "ipfs_kit_py.ipfs_kit",
        "ipfs_kit_py.ipfs",
        "ipfs_kit_py.high_level_api",
        "ipfs_kit_py.error"
    ]

    all_imports_successful = True
    print("Core modules:")
    for module in core_modules:
        result = check_import(module)
        print(f"  {module}: {'✅' if result else '❌'}")
        all_imports_successful = all_imports_successful and result

    if not all_imports_successful:
        print("\n❌ Some core modules could not be imported. Installation may be incomplete.")
        sys.exit(1)

    # Test core functionality
    print("\nTesting core functionality:")
    if not test_ipfs_kit():
        print("\n❌ Core functionality tests failed.")
        sys.exit(1)

    # Check optional components
    print("\nOptional components:")
    optional_results = test_optional_components()
    for component, status in optional_results.items():
        print(f"  {component}: {status}")

    print("\n✅ Installation test completed successfully!")

    # Print installation tips
    print("\nInstallation tips:")
    print("  - To add optional components, install with extras: pip install ipfs_kit_py[fsspec,arrow]")
    print("  - For development setup: pip install ipfs_kit_py[dev]")
    print("  - For all features: pip install ipfs_kit_py[full]")

if __name__ == "__main__":
    main()
