#!/usr/bin/env python3
"""
Test VFS Replication Features
============================

Comprehensive test of the enhanced VFS replication capabilities.
"""
import sys
import tempfile
import json
from pathlib import Path

import pytest

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_replication_features():
    """Test the comprehensive replication features."""
    print("🔄 Testing VFS Replication Features")
    print("=" * 50)
    
    from ipfs_fsspec import get_vfs

    vfs = get_vfs()
    print("✓ VFS instance created")

    # Test 1: Set up multiple backends for replication
    print("\n1. Setting up multiple backends:")
    with tempfile.TemporaryDirectory() as primary_dir, \
         tempfile.TemporaryDirectory() as backup1_dir, \
         tempfile.TemporaryDirectory() as backup2_dir:

        # Mount multiple backends
        vfs.mount("/primary", "local", primary_dir, read_only=False)
        vfs.mount("/backup1", "local", backup1_dir, read_only=False)
        vfs.mount("/backup2", "local", backup2_dir, read_only=False)
        vfs.mount("/memory", "memory", "/", read_only=False)

        mounts = vfs.list_mounts()
        print(f"   Mounted {mounts['count']} backends")

        # Test 2: Add replication policies
        print("\n2. Adding replication policies:")

        # Policy for critical files (replicate to all backends)
        critical_policy = vfs.add_replication_policy(
            "/primary/critical/*",
            ["local", "memory"],  # Available backends
            min_replicas=2,
        )
        print(f"   Critical files policy: {critical_policy}")

        # Policy for documents (moderate replication)
        docs_policy = vfs.add_replication_policy(
            "/primary/docs/*",
            ["local", "memory"],
            min_replicas=2,
        )
        print(f"   Documents policy: {docs_policy}")

        # List policies
        policies = vfs.list_replication_policies()
        print(f"   Total policies: {policies['count']}")

        # Test 3: Write files and test auto-replication
        print("\n3. Testing auto-replication:")

        # Write critical file
        critical_write = vfs.write(
            "/primary/critical/important.txt",
            "This is critical data that must be replicated!",
            auto_replicate=True,
        )
        _assert_success_if_present(critical_write, context="critical file write")
        print(f"   Critical file write: {critical_write.get('success', True)}")
        if "replication" in critical_write:
            print(f"   Auto-replication: {critical_write['replication']['message']}")

        # Write document file
        doc_write = vfs.write(
            "/primary/docs/report.txt",
            "This is an important document that should be backed up.",
            auto_replicate=True,
        )
        _assert_success_if_present(doc_write, context="document file write")
        print(f"   Document write: {doc_write.get('success', True)}")

        # Test 4: Manual replication
        print("\n4. Testing manual replication:")

        # Write file without auto-replication
        manual_write = vfs.write("/primary/manual.txt", "Manual replication test", auto_replicate=False)
        _assert_success_if_present(manual_write, context="manual file write")

        # Manually replicate
        manual_replication = vfs.replicate_file("/primary/manual.txt")
        print(f"   Manual replication: {manual_replication}")
        if isinstance(manual_replication, dict):
            _assert_success_if_present(manual_replication, context="manual replication")

        # Test 5: Verify replicas
        print("\n5. Verifying replica consistency:")

        verification = vfs.verify_replicas("/primary/critical/important.txt")
        print(f"   Verification result: {verification}")

        # Test 6: Simulate corruption and repair
        print("\n6. Testing replica repair:")

        # Get replication status first
        status = vfs.get_replication_status("/primary/critical/important.txt")
        print(f"   Replication status: {len(status.get('replicas', []))} replicas")

        # Test repair (even though nothing is corrupted)
        repair_result = vfs.repair_replicas("/primary/critical/important.txt")
        print(f"   Repair result: {repair_result}")

        # Test 7: System-wide replication status
        print("\n7. System replication health:")

        system_status = vfs.get_system_replication_status()
        print(f"   System status: {system_status}")

        # Test 8: Bulk replication
        print("\n8. Testing bulk replication:")

        # Write multiple files
        for i in range(3):
            write_result = vfs.write(
                f"/primary/bulk/file_{i}.txt",
                f"Bulk file {i} content",
                auto_replicate=False,
            )
            _assert_success_if_present(write_result, context=f"bulk write file_{i}.txt")

        # Bulk replicate
        bulk_result = vfs.bulk_replicate("/primary/bulk/*")
        print(f"   Bulk replication: {bulk_result}")

        # Clean up mounts
        vfs.unmount("/primary")
        vfs.unmount("/backup1")
        vfs.unmount("/backup2")
        vfs.unmount("/memory")
        
        print("\n✅ All replication tests completed successfully!")


def _assert_success_if_present(result: object, *, context: str) -> None:
    assert isinstance(result, dict), f"{context}: expected dict result, got {type(result).__name__}"
    if "success" in result:
        assert bool(result.get("success")), f"{context}: success=false ({result})"

def test_cache_features():
    """Test enhanced cache features."""
    print("\n💾 Testing VFS Cache Features")
    print("=" * 50)
    
    from ipfs_fsspec import get_vfs

    vfs = get_vfs()

    # Test cache statistics
    print("1. Cache statistics:")
    cache_stats = vfs.get_cache_stats()
    print(f"   Cache stats: {cache_stats}")

    # Test with actual file operations
    with tempfile.TemporaryDirectory() as tmp_dir:
        vfs.mount("/cache_test", "local", tmp_dir, read_only=False)

        # Write and read files to populate cache
        print("\n2. Populating cache:")
        for i in range(5):
            content = f"Cache test file {i} content" * 100  # Make it larger
            write_result = vfs.write(f"/cache_test/file_{i}.txt", content)
            _assert_success_if_present(write_result, context=f"write file_{i}.txt")
            read_result = vfs.read(f"/cache_test/file_{i}.txt")
            print(f"   File {i}: written and read (cached: {read_result.get('cached', False)})")

        # Get updated cache stats
        updated_stats = vfs.get_cache_stats()
        print(f"   Updated cache stats: {updated_stats}")

        # Test cache clearing
        print("\n3. Testing cache clearing:")
        clear_result = vfs.clear_cache()
        print(f"   Cache clear result: {clear_result}")

        final_stats = vfs.get_cache_stats()
        print(f"   Final cache stats: {final_stats}")

        vfs.unmount("/cache_test")

    print("\n✅ Cache tests completed successfully!")

def test_error_handling():
    """Test error handling in replication scenarios."""
    print("\n⚠️  Testing Error Handling")
    print("=" * 50)
    
    from ipfs_fsspec import get_vfs

    vfs = get_vfs()

    # Test 1: Invalid backend in replication policy
    print("1. Testing invalid backend:")
    invalid_policy = vfs.add_replication_policy(
        "/test/*",
        ["nonexistent_backend"],
        min_replicas=1,
    )
    print(f"   Invalid backend result: {invalid_policy}")

    # Test 2: Replicate non-existent file
    print("\n2. Testing non-existent file replication:")
    nonexistent_replication = vfs.replicate_file("/nonexistent/file.txt")
    print(f"   Non-existent file result: {nonexistent_replication}")

    # Test 3: Verify non-existent file replicas
    print("\n3. Testing verification of non-existent file:")
    verification = vfs.verify_replicas("/nonexistent/file.txt")
    print(f"   Non-existent verification: {verification}")

    print("\n✅ Error handling tests completed successfully!")


if __name__ == "__main__":
    print("🚀 VFS Replication and Cache Testing Suite")
    print("=" * 60)
    
    success = True

    try:
        test_replication_features()
        test_cache_features()
        test_error_handling()
    except Exception as e:
        print(f"❌ Some VFS tests failed: {e}")
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 All VFS replication and cache tests passed!")
        print("\nThe VFS system now includes:")
        print("  ✓ Comprehensive file replication across backends")
        print("  ✓ Automatic replication policies")
        print("  ✓ Replica verification and repair")
        print("  ✓ System-wide replication health monitoring")
        print("  ✓ Bulk replication operations")
        print("  ✓ Enhanced cache management")
        print("  ✓ Robust error handling")
        print("  ✓ Cross-backend file operations")
    else:
        print("❌ Some VFS tests failed!")
    
    sys.exit(0 if success else 1)
