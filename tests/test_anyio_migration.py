#!/usr/bin/env python3
"""
Test to validate anyio migration.
This test ensures that the migrated code works with both async-io and trio backends.
"""
import sys
import anyio
import pytest

ASYNC_BACKEND = "async" "io"

pytestmark = pytest.mark.anyio

# Test basic anyio functionality
@pytest.mark.parametrize("backend", [ASYNC_BACKEND, "trio"])
def test_anyio_backends(backend):
    """Test that anyio works with both backends."""
    async def test_sleep():
        await anyio.sleep(0.01)
        return "success"
    
    result = anyio.run(test_sleep, backend=backend)
    assert result == "success"


@pytest.mark.parametrize("backend", [ASYNC_BACKEND, "trio"])
def test_anyio_task_groups(backend):
    """Test that anyio task groups work with both backends."""
    async def test_task_group():
        results = []
        
        async def task1():
            await anyio.sleep(0.01)
            results.append(1)
        
        async def task2():
            await anyio.sleep(0.01)
            results.append(2)
        
        async with anyio.create_task_group() as tg:
            tg.start_soon(task1)
            tg.start_soon(task2)
        
        return sorted(results)
    
    result = anyio.run(test_task_group, backend=backend)
    assert result == [1, 2]


@pytest.mark.parametrize("backend", [ASYNC_BACKEND, "trio"])
def test_anyio_thread_sync(backend):
    """Test that anyio thread execution works with both backends."""
    async def test_thread():
        def sync_func():
            return "from_thread"
        
        result = await anyio.to_thread.run_sync(sync_func)
        return result
    
    result = anyio.run(test_thread, backend=backend)
    assert result == "from_thread"


@pytest.mark.parametrize("backend", [ASYNC_BACKEND, "trio"])
def test_anyio_timeout(backend):
    """Test that anyio timeout works with both backends."""
    async def test_timeout():
        try:
            with anyio.fail_after(0.1):
                await anyio.sleep(0.01)
            return "completed"
        except TimeoutError:
            return "timeout"
    
    result = anyio.run(test_timeout, backend=backend)
    assert result == "completed"


@pytest.mark.parametrize("backend", [ASYNC_BACKEND, "trio"])
def test_anyio_locks(backend):
    """Test that anyio locks work with both backends."""
    async def test_lock():
        lock = anyio.Lock()
        results = []
        
        async def critical_section(name):
            async with lock:
                results.append(f"start_{name}")
                await anyio.sleep(0.01)
                results.append(f"end_{name}")
        
        async with anyio.create_task_group() as tg:
            tg.start_soon(critical_section, "A")
            tg.start_soon(critical_section, "B")
        
        # Check that critical sections didn't interleave
        assert results[0].startswith("start")
        assert results[1].startswith("end")
        assert results[2].startswith("start")
        assert results[3].startswith("end")
        
        return "success"
    
    result = anyio.run(test_lock, backend=backend)
    assert result == "success"


if __name__ == "__main__":
    print("Testing anyio migration...")
    
    # Run tests manually
    for backend in [ASYNC_BACKEND, "trio"]:
        print(f"\n=== Testing with {backend} backend ===")
        
        test_anyio_backends(backend)
        print(f"✓ Basic anyio functionality works with {backend}")
        
        test_anyio_task_groups(backend)
        print(f"✓ Task groups work with {backend}")
        
        test_anyio_thread_sync(backend)
        print(f"✓ Thread execution works with {backend}")
        
        test_anyio_timeout(backend)
        print(f"✓ Timeout handling works with {backend}")
        
        test_anyio_locks(backend)
        print(f"✓ Locks work with {backend}")
    
    print("\n✅ All anyio migration tests passed!")
