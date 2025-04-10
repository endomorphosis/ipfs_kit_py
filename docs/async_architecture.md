# Async Architecture and Anyio Migration Guide

## Overview

This document outlines the async architecture of the ipfs_kit_py project and the migration strategy from asyncio to anyio. The goal is to provide a more flexible async runtime that can work with multiple backends (asyncio, trio, curio) while simplifying the async code.

## Why Anyio?

[Anyio](https://anyio.readthedocs.io/) is a high-level asynchronous concurrency library that:

1. **Provides Backend Flexibility**: Allows code to run on multiple async backends (asyncio, trio, curio)
2. **Offers Simpler APIs**: Provides more intuitive APIs for common async patterns
3. **Improves Cancellation**: Uses more reliable cancellation mechanisms compared to asyncio
4. **Standardizes Timeouts**: Provides consistent timeout handling across all operations
5. **Better Resource Management**: Simplifies context management and resource cleanup
6. **Concurrent Task Management**: Simplified task groups for running concurrent tasks

By adopting anyio, we enhance the flexibility of ipfs_kit_py while making the async code more robust and maintainable.

## Migration Strategy

### Phase 1: Dependency and Infrastructure Setup ✅

- Add anyio as a project dependency ✅
- Create documentation for anyio migration (this document)
- Update development guidelines to promote anyio usage

### Phase 2: Core Infrastructure Migration

- Update base async utilities and helper functions
- Migrate the following core components first:
  - WebSocket peer discovery
  - Async HTTP clients
  - Event handling systems
  - Connection management

### Phase 3: Feature Migration

- Migrate remaining async features:
  - Streaming components
  - Async filesystem operations
  - Resource management
  - Task scheduling

### Phase 4: Tooling and Testing

- Update testing infrastructure for anyio compatibility
- Add anyio-specific testing utilities
- Create benchmarks to compare performance

## Migration Guidelines

### Direct Replacements

| asyncio                           | anyio                          |
|-----------------------------------|--------------------------------|
| `asyncio.sleep()`                 | `anyio.sleep()`                |
| `asyncio.gather()`                | `anyio.gather()`               |
| `asyncio.create_task()`           | `anyio.create_task()`          |
| `asyncio.wait_for()`              | `anyio.fail_after()`           |
| `asyncio.TimeoutError`            | `anyio.TimeoutError`           |
| `asyncio.run()`                   | `anyio.run()`                  |
| `asyncio.current_task()`          | `anyio.get_current_task()`     |
| `asyncio.create_task_group()`     | `anyio.create_task_group()`    |
| `asyncio.to_thread()`             | `anyio.to_thread.run_sync()`   |

### Task Groups

Anyio provides a more structured way to handle groups of tasks:

```python
# asyncio
async def main():
    task1 = asyncio.create_task(some_function())
    task2 = asyncio.create_task(another_function())
    await asyncio.gather(task1, task2)

# anyio
async def main():
    async with anyio.create_task_group() as tg:
        tg.start_soon(some_function)
        tg.start_soon(another_function)
```

### Timeouts

Anyio offers a more intuitive timeout API:

```python
# asyncio
try:
    await asyncio.wait_for(operation(), timeout=5.0)
except asyncio.TimeoutError:
    print("Operation timed out")

# anyio
try:
    async with anyio.fail_after(5.0):
        await operation()
except anyio.TimeoutError:
    print("Operation timed out")
```

### Streams and Sockets

Anyio provides a unified API for streams and sockets:

```python
# asyncio
reader, writer = await asyncio.open_connection(host, port)
data = await reader.read(1024)
writer.write(response)
await writer.drain()
writer.close()
await writer.wait_closed()

# anyio
async with await anyio.connect_tcp(host, port) as client:
    data = await client.receive(1024)
    await client.send(response)
```

### WebSockets

For WebSockets, anyio provides integrations with common libraries:

```python
# Using websockets with asyncio
async with websockets.connect(url) as websocket:
    await websocket.send(data)
    response = await websocket.recv()

# Using websockets with anyio backend
async with websockets.connect(url) as websocket:
    await anyio.to_thread.run_sync(websocket.send, data)
    response = await anyio.to_thread.run_sync(websocket.recv)
```

Better yet, use a native anyio-compatible WebSocket library like `trio-websocket` or `wsproto` with anyio.

## Best Practices

1. **Use Task Groups**: Prefer task groups over individual task creation for better error propagation and cleanup
2. **Be Explicit with Timeouts**: Always specify timeouts for I/O operations
3. **Avoid Backend-Specific Features**: Stay within anyio's API to maintain backend independence
4. **Cancellation Handling**: Always handle cancellation properly in long-running tasks
5. **Resource Management**: Use `async with` for managing async resources
6. **Threading**: Use `anyio.to_thread.run_sync()` for CPU-bound operations
7. **Blocking Operations**: Move blocking operations to threads using `anyio.to_thread.run_sync()`

## Testing with Anyio

For testing async code with anyio, use the built-in testing utilities:

```python
import anyio
import pytest

@pytest.mark.anyio
async def test_async_function():
    # This test will run on all available backends
    result = await some_async_function()
    assert result == expected_value
```

## FAQs

### Can I mix asyncio and anyio in the same project?

Yes, but it's recommended to use anyio consistently for new code and migrate existing code when possible.

### Will using anyio affect performance?

No, anyio is designed to be a thin wrapper around the underlying backends with minimal overhead.

### How do I specify which backend to use?

By default, anyio uses the asyncio backend. To specify a different backend:

```python
import anyio

anyio.run(main, backend="trio")  # Use trio backend
```

### Can I use asyncio-specific libraries with anyio?

Yes, most asyncio libraries will work with anyio's asyncio backend. For trio-specific features, you may need to use anyio's adapter utilities.

## Implementation Examples

### API Server Migration

The API server (`api.py`) was successfully migrated to an anyio-based implementation (`api_anyio.py`). This migration involved:

1. **Direct Replacements**: Replacing asyncio imports with anyio, and asyncio-specific functions with their anyio equivalents

```python
# Before (asyncio-based)
import asyncio

try:
    await asyncio.wait_for(operation(), timeout=5.0)
except asyncio.TimeoutError:
    # Handle timeout
    
# After (anyio-based)
import anyio

try:
    with anyio.fail_after(5.0):
        await operation()
except anyio.TimeoutError:
    # Handle timeout
```

2. **Timeout Handling**: Using anyio's context manager-based timeout handling for streaming operations

```python
# Before (with asyncio)
async def stream_content():
    try:
        # Use asyncio.wait_for for timeout
        result = await asyncio.wait_for(
            api.stream_media_async(path=path, chunk_size=chunk_size),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Timeout streaming content")

# After (with anyio)
async def stream_content():
    try:
        # Use anyio.move_on_after context manager
        with anyio.move_on_after(timeout):
            async for chunk in api.stream_media_async(
                path=path,
                chunk_size=chunk_size
            ):
                yield chunk
    except Exception as e:
        logger.error(f"Error during content streaming: {str(e)}")
        return
```

3. **Server Startup**: Using anyio.run to start the server to support different async backends

```python
# Before (asyncio-based)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000)
    
# After (anyio-based)
if __name__ == "__main__":
    async def run_server():
        config = uvicorn.Config(
            "api_anyio:app", 
            host=host, 
            port=port,
            log_level=log_level,
            reload=False
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    # Run with anyio to support multiple backends
    import anyio
    backend = os.environ.get("IPFS_KIT_ASYNC_BACKEND", "asyncio")
    anyio.run(run_server, backend=backend)
```

4. **Testing Integration**: Using pytest-anyio for testing the anyio components

```python
# Mark tests with pytest.mark.anyio
@pytest.mark.anyio
async def test_async_function():
    # Test implementation
    ...

# Use anyio.run for test execution
if __name__ == "__main__":
    anyio.run(
        pytest.main,
        ["-v", __file__]
    )
```

The migrated API server (`api_anyio.py`) preserves all the functionality of the original server while gaining the benefits of anyio - backend agnosticism, improved cancellation handling, and more intuitive concurrency patterns.

### WebSocket Notifications Migration

The WebSocket notifications system was migrated from asyncio to anyio in `websocket_notifications_anyio.py`, demonstrating these key patterns:

1. **Task Group for Connection Management**: 
   - Replacing individual task creation and manual tracking with task groups for better error propagation and cleanup.
   - Task groups automatically cancel all tasks when exiting the context.

2. **Memory Streams for Inter-Task Communication**:
   - Using anyio's memory object streams instead of asyncio queues.
   - Streams provide more consistent behavior across backends and better backpressure handling.

3. **Structured Cancellation**:
   - Properly handling cancellation to ensure resources are cleaned up.
   - Using anyio's cancel scopes for fine-grained control over cancellation.

### WAL WebSocket Migration

Similar patterns were applied when migrating the Write-Ahead Log WebSocket implementation:

1. **Converting Timeouts**:
   - Replacing `asyncio.wait_for()` with `anyio.fail_after()` context managers.
   - This provides more intuitive timeout handling with proper cleanup.

2. **Thread-to-Async Bridge**:
   - Using `anyio.from_thread.run()` instead of asyncio's thread functions.
   - This ensures compatibility across different backends.

3. **Proper Task Cancellation**:
   - Implementing proper cancellation handling with task groups.
   - Using `task_group.__aenter__()` and `task_group.__aexit__()` for explicit control when needed.

These implementation examples demonstrate how the migration to anyio improves code readability, robustness, and maintainability while enabling backend flexibility.

## References

- [Anyio Documentation](https://anyio.readthedocs.io/)
- [Trio Documentation](https://trio.readthedocs.io/)
- [AsyncIO Documentation](https://docs.python.org/3/library/asyncio.html)