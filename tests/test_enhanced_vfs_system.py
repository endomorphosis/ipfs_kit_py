#!/usr/bin/env python3
"""
Test the enhanced VFS system with all backend integrations.
"""

import anyio
import tempfile
import shutil
from pathlib import Path
import pytest

pytestmark = pytest.mark.anyio


async def test_enhanced_vfs_system():
    """Test the enhanced VFS system with all available backends."""

    print("🧪 Testing Enhanced VFS System with All Backends")
    print("=" * 70)

    # Import VFS functions
    try:
        from ipfs_kit_py.ipfs_fsspec import (
            get_vfs,
            vfs_mount,
            vfs_write,
            vfs_read,
            vfs_list_mounts,
            vfs_ls,
        )

        print("✅ Enhanced VFS modules imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import enhanced VFS modules: {e}")
        return False

    # Initialize VFS
    vfs = get_vfs()
    print("✅ Enhanced VFS initialized")

    # Create test directory
    test_dir = Path(tempfile.mkdtemp(prefix="enhanced_vfs_test_"))
    print(f"✅ Created test directory: {test_dir}")

    try:
        # Test 1: Check available backends
        print("\n📁 Test 1: Available backends")
        available_backends = vfs.registry.list_backends()
        print(f"Available backends: {available_backends}")

        for backend in available_backends:
            backend_info = vfs.registry.get_backend(backend)
            if backend_info:
                print(
                    f"  ✅ {backend}: {backend_info['class'].__name__} - Available: {backend_info['available']}"
                )

        # Test 2: Mount various backends
        print("\n📁 Test 2: Mount backends")

        # Mount local filesystem
        local_dir = test_dir / "local"
        local_dir.mkdir(exist_ok=True)

        mount_result = await vfs_mount(str(local_dir), "/data", read_only=False)
        status = "✅" if mount_result["success"] else "❌"
        print(f"{status} Mount local backend: {mount_result['success']}")

        # Mount memory filesystem
        memory_mount_result = await vfs_mount("memory://", "/memory", read_only=False)
        status = "✅" if memory_mount_result["success"] else "❌"
        print(f"{status} Mount memory backend: {memory_mount_result['success']}")

        # Test mounting IPFS, Storacha, Lotus, Lassie (these may fail if not available, which is OK)
        for backend_name, mount_point in [
            ("ipfs", "/ipfs"),
            ("storacha", "/storacha"),
            ("lotus", "/lotus"),
            ("lassie", "/lassie"),
            ("arrow", "/arrow"),
        ]:
            try:
                backend_mount_result = await vfs_mount("", mount_point, read_only=True)
                status = "✅" if backend_mount_result["success"] else "⚠️"
                print(
                    f"{status} Mount {backend_name} backend: {backend_mount_result.get('success', False)}"
                )
            except Exception as e:
                print(f"⚠️  Mount {backend_name} backend: Not available ({e})")

        # Verify mounts
        mounts = await vfs_list_mounts()
        print(f"✅ Total active mounts: {mounts['count']}")

        # Test 3: Write and read files
        print("\n📝 Test 3: Write and read files")

        test_files = [
            ("/data/test1.txt", "Hello from enhanced VFS!"),
            ("/memory/test2.txt", "Memory storage test"),
            ("/data/config.json", '{"version": "1.0", "enhanced": true}'),
        ]

        for file_path, content in test_files:
            # Write file
            write_result = await vfs_write(file_path, content)
            status = "✅" if write_result["success"] else "❌"
            print(f"{status} Write {file_path}: {write_result['success']}")

            if write_result["success"]:
                # Read file back
                read_result = await vfs_read(file_path)
                if read_result["success"]:
                    match = read_result["content"] == content
                    status = "✅" if match else "❌"
                    print(f"{status} Read {file_path}: Content match: {match}")
                else:
                    print(f"❌ Read {file_path}: {read_result['error']}")

        # Test 4: Directory listing
        print("\n📂 Test 4: Directory operations")

        for directory in ["/data", "/memory"]:
            ls_result = await vfs_ls(directory)
            if ls_result["success"]:
                count = ls_result["count"]
                print(f"✅ List {directory}: {count} entries")
                for entry in ls_result["entries"][:3]:  # Show first 3
                    if isinstance(entry, dict):
                        print(f"  📄 {entry.get('name', 'unknown')}")
                    else:
                        print(f"  📄 {entry}")
            else:
                print(f"❌ List {directory}: {ls_result['error']}")

        # Test 5: Cache functionality
        print("\n💾 Test 5: Cache functionality")

        cache_stats = vfs.get_cache_stats()
        if "hits" in cache_stats:
            print(f"✅ Cache hits: {cache_stats['hits']}")
            print(f"✅ Cache misses: {cache_stats['misses']}")
            print(f"✅ Cache hit ratio: {cache_stats.get('hit_ratio', 0):.2%}")
        else:
            print("⚠️  Cache statistics not available")

        # Test 6: Backend-specific features
        print("\n⚙️  Test 6: Backend-specific features")

        # Test if we can access the tiered cache manager
        if hasattr(vfs, "cache_manager"):
            print("✅ Tiered cache manager available")
            if hasattr(vfs.cache_manager, "get_stats"):
                cache_detailed = vfs.cache_manager.get_stats()
                print(f"✅ Detailed cache stats: {len(cache_detailed)} metrics")

        # Test filesystem journal if available
        try:
            if hasattr(vfs, "journal_manager"):
                print("✅ Filesystem journal available")
            else:
                print("ℹ️  Filesystem journal not integrated yet")
        except Exception:
            print("ℹ️  Filesystem journal not available")

        # Test 7: Advanced features
        print("\n🔄 Test 7: Advanced features")

        # Test replication policies (basic test)
        try:
            policies_result = vfs.list_replication_policies()
            if policies_result["success"]:
                print(f"✅ Replication policies: {policies_result['count']} policies")
            else:
                print("ℹ️  No replication policies configured")
        except Exception as e:
            print(f"⚠️  Replication features: {e}")

        print("\n🎉 Enhanced VFS system test completed!")
        print(f"📊 Summary:")
        print(f"  - Available backends: {len(available_backends)}")
        print(f"  - Active mounts: {mounts['count']}")
        print(f"  - Files tested: {len(test_files)}")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Cleanup
        try:
            shutil.rmtree(test_dir)
            print(f"✅ Cleaned up test directory: {test_dir}")
        except Exception as e:
            print(f"⚠️  Failed to clean up: {e}")


if __name__ == "__main__":
    success = anyio.run(test_enhanced_vfs_system)
    exit(0 if success else 1)
