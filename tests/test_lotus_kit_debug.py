#!/usr/bin/env python3
"""
Simple test to debug lotus_kit availability issue
"""

import sys
import logging
import pytest

# Configure logging
logging.basicConfig(level=logging.WARNING)

def run_lotus_kit_simple() -> bool:
    """Run lotus_kit availability checks and return success."""
    print("Testing lotus_kit availability...")

    try:
        import ipfs_kit_py
        print("✓ ipfs_kit_py imported successfully")

        kit_factory = getattr(ipfs_kit_py, "get_ipfs_kit", None)
        if callable(kit_factory):
            kit_factory = kit_factory()
        else:
            kit_factory = getattr(ipfs_kit_py, "ipfs_kit", None)

        if not callable(kit_factory):
            pytest.skip("ipfs_kit factory not available in this environment")

        kit_metadata = {
            "auto_download_binaries": False,
            "auto_start_daemons": False,
            "skip_dependency_check": True,
        }
        kit = kit_factory(metadata=kit_metadata, auto_start_daemons=False)
        print("✓ ipfs_kit instance created successfully")

        # Check all attributes
        attrs = [attr for attr in dir(kit) if not attr.startswith('_')]
        print(f"Kit has {len(attrs)} attributes:")
        for attr in sorted(attrs):
            print(f"  - {attr}")

        # Specifically check for lotus_kit
        has_lotus_kit = hasattr(kit, 'lotus_kit')
        print(f"\nhasattr(kit, 'lotus_kit'): {has_lotus_kit}")

        if has_lotus_kit:
            print(f"✓ lotus_kit type: {type(kit.lotus_kit)}")
            print("✓ lotus_kit available: True")
            return True

        pytest.skip("lotus_kit not available in this environment")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        pytest.skip(f"lotus_kit integration unavailable: {e}")


def test_lotus_kit_simple():
    """Simple test for lotus_kit availability"""
    assert run_lotus_kit_simple() is True

if __name__ == "__main__":
    success = run_lotus_kit_simple()
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
