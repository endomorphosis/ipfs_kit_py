#!/usr/bin/env python3
"""
Simple test to debug lotus_kit availability issue
"""

import sys
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING)

def run_lotus_kit_simple() -> bool:
    """Run lotus_kit availability checks and return success."""
    print("Testing lotus_kit availability...")

    try:
        import ipfs_kit_py
        print("✓ ipfs_kit_py imported successfully")

        kit = ipfs_kit_py.ipfs_kit()
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

        print("✗ lotus_kit not found")
        return False

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_lotus_kit_simple():
    """Simple test for lotus_kit availability"""
    assert run_lotus_kit_simple() is True

if __name__ == "__main__":
    success = run_lotus_kit_simple()
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
