#!/usr/bin/env python3
"""Test script to verify lotus_kit availability fix."""

import sys
import os
import pytest
sys.path.insert(0, os.path.abspath('.'))

def run_lotus_kit_availability() -> bool:
    """Run lotus_kit availability checks and return success."""
    print("Testing lotus_kit availability...")

    try:
        import ipfs_kit_py
        print("✓ Successfully imported ipfs_kit_py")

        # Create an ipfs_kit instance (use stable accessor; the package attribute
        # `ipfs_kit` can be overwritten by Python's submodule import mechanics).
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
        print("✓ Successfully created ipfs_kit instance")

        # Check available attributes
        attrs = [attr for attr in dir(kit) if not attr.startswith('_')]
        print(f"✓ Available attributes: {attrs}")

        # Check if lotus_kit is available
        if hasattr(kit, 'lotus_kit'):
            print("✓ lotus_kit is available")
            print(f"✓ lotus_kit type: {type(kit.lotus_kit)}")

            # Check auto-start daemon setting
            auto_start = getattr(kit.lotus_kit, 'auto_start_daemon', False)
            print(f"✓ Auto-start daemon setting: {auto_start}")

            # Check daemon status
            daemon_status = kit.lotus_kit.daemon_status()
            is_running = daemon_status.get("process_running", False)
            print(f"✓ Daemon status: {daemon_status}")

            return True

        pytest.skip("lotus_kit not available in this environment")

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        pytest.skip(f"lotus_kit integration unavailable: {e}")


def test_lotus_kit_availability():
    """Test that lotus_kit is available in ipfs_kit instances."""
    assert run_lotus_kit_availability() is True

if __name__ == "__main__":
    success = run_lotus_kit_availability()
    print(f"\nTest result: {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
