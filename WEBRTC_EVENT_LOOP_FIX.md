# WebRTC Event Loop Fix and Monitoring for MCP Server

## Overview

This document explains the WebRTC event loop fixes and monitoring capabilities implemented for the IPFS Kit MCP Server. The solution addresses issues with WebRTC operations in FastAPI context, where event loops are already running, and adds comprehensive monitoring for debugging, troubleshooting, and operational visibility.

## Problem Description

The MCP server's WebRTC functionality had issues with three key methods:

1. `stop_webrtc_streaming`
2. `close_webrtc_connection`
3. `close_all_webrtc_connections`

These methods attempted to handle running event loops by creating new ones, but this approach fails in FastAPI context where an event loop is already running. The problematic pattern was:

```python
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # Create a new event loop for this operation
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        loop = new_loop
except RuntimeError:
    # No event loop in this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Then using loop.run_until_complete() which causes problems in FastAPI
```

When these methods were called within a FastAPI route handler (which already has a running event loop), they would attempt to create and use a new event loop, leading to errors.

## Solution

We provide three implementations of increasing sophistication:

### 1. Asyncio-based Solution

Located in `fixes/webrtc_event_loop_fix.py`:

1. **`AsyncEventLoopHandler` class**: A utility to safely run coroutines in any context (running event loop or not)
2. **Patched synchronous methods**: Fixed versions of the problematic methods that handle event loops properly
3. **Async versions**: New async methods designed for use in FastAPI route handlers

### 2. AnyIO-based Solution

Located in `fixes/webrtc_anyio_fix.py`:

1. **`AnyIOEventLoopHandler` class**: A utility that uses AnyIO to work across different async backends
2. **Patched synchronous methods**: Fixed versions using AnyIO for better compatibility
3. **Async versions**: New async methods for FastAPI route handlers

### 3. Enhanced AnyIO + Monitoring Solution (Recommended)

Located in `fixes/webrtc_anyio_monitor_integration.py` and `fixes/webrtc_monitor.py`:

1. **`AnyIOMonitoredEventLoopHandler` class**: Combines AnyIO event loop handling with monitoring capabilities
2. **WebRTC monitoring system**: Comprehensive tracking of connections, operations, and async tasks
3. **Enhanced patched methods**: Fixed versions with integrated monitoring and detailed logging
4. **REST API monitoring endpoints**: Real-time visibility into WebRTC operations and state
5. **Structured logging**: Detailed JSON-formatted logs for troubleshooting

The Enhanced AnyIO + Monitoring solution is recommended because:
- It provides the best of both worlds: proper event loop handling and comprehensive monitoring
- It works with multiple async backends (asyncio, trio, etc.) via AnyIO
- It integrates better with FastAPI which uses Starlette (built on AnyIO)
- It offers detailed operational metrics and troubleshooting capabilities
- It prevents resource leaks by tracking async tasks

### Key Improvements in All Solutions:

1. **Proper detection of running loops**: Correctly detects if an event loop is running
2. **Safe background tasks**: In a running loop, operations are scheduled as background tasks
3. **Graceful simulation**: When operations are scheduled in the background, a simulated success result is returned
4. **No nested loops**: Avoids creating nested loops which cause errors
5. **Both sync and async support**: Works in both synchronous contexts and FastAPI's asynchronous context

### Additional Benefits of the Enhanced Solution:

1. **Connection Tracking**: Monitor WebRTC connections with detailed state information
2. **Operation Monitoring**: Track method calls and their outcomes with timing metrics
3. **Async Task Management**: Prevent resource leaks by tracking background tasks
4. **Detailed Logging**: JSON-structured logs for post-mortem analysis
5. **REST API Monitoring**: Real-time visibility through Web API endpoints
6. **Lifecycle Events**: Track connection and operation state transitions

## Files Added

### Asyncio Solution
1. `/fixes/webrtc_event_loop_fix.py`: Core implementation with AsyncEventLoopHandler
2. `/fixes/apply_webrtc_fixes.py`: Script to apply the fixes
3. `/run_mcp_with_webrtc_fixed.py`: Script to run the MCP server with fixes
4. `/event_loop_issue_demo.py`: Demo script for the asyncio solution

### AnyIO Solution
1. `/fixes/webrtc_anyio_fix.py`: Core implementation with AnyIOEventLoopHandler
2. `/fixes/apply_webrtc_anyio_fixes.py`: Script to apply the AnyIO fixes
3. `/run_mcp_with_anyio_fixed.py`: Script to run the MCP server with AnyIO fixes
4. `/anyio_event_loop_demo.py`: Demo script for the AnyIO solution

### Enhanced AnyIO + Monitoring Solution
1. `/fixes/webrtc_monitor.py`: WebRTC monitoring implementation
2. `/fixes/webrtc_anyio_monitor_integration.py`: Integration of AnyIO fixes with monitoring
3. `/run_mcp_with_anyio_monitor.py`: Script to run the MCP server with enhanced solution
4. `/test_webrtc_anyio_monitor.py`: Test script for the enhanced solution

## Usage

### Option 1: Start MCP Server with Enhanced AnyIO + Monitoring Solution (Recommended)

```bash
# First, install required dependencies
pip install -r fixes/requirements.txt

# Run the server with the enhanced solution
python run_mcp_with_anyio_monitor.py --debug --port 9999 --log-dir ./logs --webrtc-test --run-tests
```

Command line options for the enhanced script:
- `--debug`: Enable detailed debug logging
- `--port PORT`: Port for the MCP server (default: 9999)
- `--host HOST`: Host to bind the server to (default: 127.0.0.1)
- `--log-dir PATH`: Directory to store WebRTC monitoring logs (default: ./logs)
- `--isolation`: Run in isolation mode
- `--webrtc-test`: Include WebRTC test endpoint
- `--run-tests`: Run WebRTC tests after starting server

### Option 2: Start MCP Server with Basic AnyIO Fixes

```bash
# Install AnyIO dependencies
pip install anyio sniffio

# Run the server with AnyIO fixes
python run_mcp_with_anyio_fixed.py --debug --port 9999
```

### Option 3: Start MCP Server with Asyncio Fixes

```bash
python run_mcp_with_webrtc_fixed.py --debug --port 9999
```

### Option 4: Apply Enhanced AnyIO + Monitoring to an Existing Project

```python
from ipfs_kit_py.mcp.server import MCPServer

# Create the MCP server
mcp_server = MCPServer(debug_mode=True)

# Apply enhanced AnyIO + Monitoring solution
from fixes.webrtc_anyio_monitor_integration import apply_enhanced_fixes
monitor = apply_enhanced_fixes(
    mcp_server,
    log_dir="./logs",
    debug_mode=True
)

# Use the enhanced server with monitoring
```

### Option 5: Apply Basic AnyIO Fixes to an Existing Project

```python
from ipfs_kit_py.mcp.server import MCPServer

# Create the MCP server
mcp_server = MCPServer(debug_mode=True)

# For AnyIO solution
from fixes.apply_webrtc_anyio_fixes import apply_fixes
apply_fixes(mcp_server)

# Use the patched server as normal
```

## Monitoring Features

The WebRTC monitoring system in the enhanced solution provides these capabilities:

### 1. Connection Tracking
- Track WebRTC connection states (ice, connection, signaling, gathering)
- Monitor media tracks and data channels
- Record connection lifecycle events with timestamps
- Calculate connection age and idle time
- Detect closed and failed connections

### 2. Operation Monitoring
- Track WebRTC operations (e.g., close connections) with timing and results
- Record operation success/failure with detailed error information
- Generate unique operation IDs for correlation
- Measure operation duration and response times

### 3. Async Task Management
- Track background async tasks with proper cleanup
- Prevent resource leaks from orphaned tasks
- Monitor background task execution and completion
- Provide task correlation with operations and connections

### 4. Logging & Metrics
- Store connection and operation logs in structured JSON format
- Provide summary statistics and health metrics
- Enable optional debug logging for detailed troubleshooting
- Store logs in a hierarchical directory structure

### 5. REST API Monitoring
When using `run_mcp_with_anyio_monitor.py`, these endpoints are available:
- `/webrtc/monitor/summary`: Overall monitoring summary
- `/webrtc/monitor/connections`: List of all connections
- `/webrtc/monitor/connections/{connection_id}`: Specific connection details
- `/webrtc/monitor/operations`: Active operations
- `/webrtc/monitor/tasks`: Pending async tasks

## Testing

### Testing the Enhanced Solution

```bash
# Run the dedicated test script for the enhanced solution
python test_webrtc_anyio_monitor.py

# OR start the server with automatic tests
python run_mcp_with_anyio_monitor.py --debug --port 9999 --webrtc-test --run-tests

# Check the monitoring dashboard
curl http://127.0.0.1:9999/webrtc/monitor/summary
```

### Testing the Basic Solutions

```bash
# Start the patched server first (AnyIO version recommended)
python run_mcp_with_anyio_fixed.py --debug --port 9999

# In another terminal, run the test
python test_webrtc_event_loop_fix.py --server-url http://127.0.0.1:9999 --verbose
```

### Demo Scripts

To see the issue and solution in action without the full MCP server:

```bash
# For AnyIO solution
python anyio_event_loop_demo.py

# OR for asyncio solution
python event_loop_issue_demo.py
```

## Implementation Details

### Enhanced AnyIO + Monitoring Solution

The core of the enhanced solution is the `AnyIOMonitoredEventLoopHandler` class that combines event loop handling with monitoring:

```python
class AnyIOMonitoredEventLoopHandler:
    def __init__(self, monitor):
        self.monitor = monitor
        self.task_tracker = AsyncTaskTracker(monitor)
        
    def run_monitored_coroutine_sync(self, coro, connection_id, 
                                     operation_name=None, fallback_result=None):
        """
        Run a coroutine with monitoring in any context (sync or async).
        
        This method will:
        1. Use AnyIO to detect the current async environment
        2. If in an async context, schedule as a monitored task and return fallback
        3. If in a sync context, run the coroutine to completion with monitoring
        """
        # Detect if we're in an async context and handle accordingly
        # Track the operation in the monitor
        # Run the coroutine with appropriate error handling
        # Update the monitor with the results
```

### AnyIO Implementation

The core of the AnyIO solution is the `AnyIOEventLoopHandler` class:

```python
class AnyIOEventLoopHandler:
    @staticmethod
    def run_coroutine(coro, fallback_result=None):
        """Run a coroutine in any context using AnyIO."""
        # Detect if we're already in an async context
        in_async_context = False
        
        if HAS_SNIFFIO:
            try:
                current_async_lib = sniffio.current_async_library()
                in_async_context = True
            except sniffio.AsyncLibraryNotFoundError:
                # Not in an async context
                pass
                
        if in_async_context:
            # We're already in an async context (likely FastAPI/Starlette)
            # Schedule background task with AnyIO
            asyncio.create_task(_schedule_background())
            return fallback_result
        else:
            # Not in async context, run synchronously
            return anyio.run(lambda: coro)
```

### Asyncio Implementation

The core of the asyncio solution is the `AsyncEventLoopHandler` class:

```python
class AsyncEventLoopHandler:
    @staticmethod
    def run_coroutine(coro, fallback_result=None):
        """Run a coroutine in any context (sync or async)."""
        try:
            loop = asyncio.get_event_loop()
            
            if loop.is_running():
                # Schedule the coroutine without waiting in a running loop
                asyncio.create_task(coro)
                return fallback_result
            else:
                return loop.run_until_complete(coro)
        except RuntimeError:
            # Create new loop if none exists
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
```

## Monitoring Architecture

The monitoring system is implemented in `webrtc_monitor.py` and provides a layered approach:

1. **Data Model Layer**:
   - `WebRTCConnectionStats`: Tracks connection state, lifecycle, and async tasks
   - Records events, errors, and state transitions with timestamps

2. **Core Monitoring Layer**:
   - `WebRTCMonitor`: Central monitoring component that tracks connections and operations
   - Provides metrics, summary statistics, and logging capabilities
   - Implements thread-safe operations for concurrent access

3. **Task Management Layer**:
   - `AsyncTaskTracker`: Tracks and manages async tasks
   - Ensures cleanup even when exceptions occur
   - Prevents resource leaks from background tasks

4. **API Layer**:
   - REST endpoints for real-time monitoring
   - JSON-formatted data for easy consumption
   - Summary and detailed views for different monitoring needs

5. **Logging Layer**:
   - Structured JSON logs for connections and operations
   - Hierarchical directory organization
   - Debug and release mode logging options

## Major Update: AnyIO Migration Progress

The WebRTC controller has been successfully migrated to use AnyIO primitives throughout the entire implementation. This is a significant milestone in the overall AnyIO migration for the project.

### Key Achievements:

1. **Full AnyIO Implementation**: The WebRTC controller (`ipfs_kit_py/mcp/controllers/webrtc_controller.py`) now exclusively uses AnyIO for asynchronous operations, completely replacing asyncio.

2. **Improved Thread Safety**: All synchronous operations now use `anyio.to_thread.run_sync()` for proper thread handling, which works better in both asyncio and trio contexts.

3. **Simplified Task Management**: Task creation and cancellation now use straightforward AnyIO patterns that work across backends.

4. **Better Error Handling**: AnyIO's cancellation handling provides cleaner error recovery.

5. **Controller-Level Async Methods**: All controller methods now natively support async/await patterns for better integration with FastAPI.

6. **Compatibility Maintenance**: The migration includes fallback mechanisms and compatibility layers to ensure integration with existing code works correctly.

The WebRTC controller now makes full use of AnyIO primitives. This approach is used across all controllers for a consistent implementation.

## Conclusion

The complete WebRTC solution offers both event loop fixes and comprehensive monitoring capabilities for the MCP server. The event loop fixes enable WebRTC operations to work properly in all contexts, including FastAPI's asynchronous environment. The monitoring system provides detailed visibility into WebRTC operations, connections, and performance, making it easier to debug issues and understand system behavior.

The Enhanced AnyIO + Monitoring solution is recommended for most use cases as it provides the most comprehensive functionality while maintaining compatibility with different async frameworks and integration with FastAPI. With the migration of the WebRTC controller to full AnyIO compatibility, this recommendation is even stronger, as the controller now natively supports both asyncio and trio backends.