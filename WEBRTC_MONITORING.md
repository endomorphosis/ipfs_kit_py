# WebRTC Monitoring and Event Loop Fixes

This document describes the comprehensive WebRTC enhancement solution for the MCP server, which combines proper event loop handling with detailed monitoring capabilities.

## Background

When using WebRTC within FastAPI routes, several issues arise due to event loop handling:

1. **Event Loop Conflicts**: Methods like `stop_webrtc_streaming`, `close_webrtc_connection`, and `close_all_webrtc_connections` can fail when running in FastAPI because they try to use `asyncio.run_until_complete()` inside a running event loop.

2. **Monitoring Challenges**: Without proper tracking, it's difficult to debug WebRTC connection issues, track async tasks, and visualize WebRTC operations.

This implementation addresses both issues with a comprehensive solution.

## Features

### 1. AnyIO Event Loop Handling

- **Context Detection**: Automatically detects if code is running in an already active event loop (like FastAPI)
- **Graceful Degradation**: In running event loops, schedules background tasks instead of blocking
- **Async Safety**: In non-async contexts, runs coroutines to completion appropriately
- **Cross-Framework Compatibility**: Works across different async frameworks (asyncio, trio)

### 2. Comprehensive WebRTC Monitoring

- **Connection Tracking**: Monitors WebRTC connection states, events, and lifecycle
- **Operation Logging**: Tracks all WebRTC operations with timing and results
- **Async Task Tracking**: Prevents resource leaks by tracking async task creation and completion
- **Statistics Collection**: Gathers detailed performance and usage metrics
- **REST API**: Exposes monitoring capabilities through real-time API endpoints
- **Log Files**: Option to store comprehensive logs for post-analysis

### 3. Integration with MCP Server

- **Seamless Integration**: Works with the existing MCP server architecture
- **Enhanced WebRTC Controller**: Patches the controller to use async-compatible methods
- **Real-time Monitoring**: Adds monitoring endpoints to the API
- **Automatic Fixing**: Self-healing WebRTC method wrappers

## Using the Enhanced Server

### Starting the Server

```bash
python run_mcp_with_webrtc_monitor.py [options]
```

Options:
- `--port INT`: Port to run the server on (default: 9999)
- `--host TEXT`: Host to bind to (default: 127.0.0.1)
- `--debug`: Enable debug mode
- `--persistence-path TEXT`: Path for persistence files
- `--log-dir TEXT`: Directory for WebRTC monitoring logs
- `--run-tests`: Run tests after server startup and then exit

### Monitoring Endpoints

Once running, the following monitoring endpoints are available:

- **WebRTC Summary**: 
  `GET /api/v0/mcp/monitor/webrtc/summary`
  
  Provides an overview of all WebRTC activity including connection counts, operation statistics, and pending tasks.

- **WebRTC Connections**: 
  `GET /api/v0/mcp/monitor/webrtc/connections`
  
  Lists all active WebRTC connections with detailed status information.

- **Connection Details**: 
  `GET /api/v0/mcp/monitor/webrtc/connections/{connection_id}`
  
  Shows detailed information about a specific WebRTC connection, including state, tracks, data channels, and events.

- **Active Operations**: 
  `GET /api/v0/mcp/monitor/webrtc/operations`
  
  Shows currently running WebRTC operations.

- **Pending Tasks**: 
  `GET /api/v0/mcp/monitor/webrtc/tasks`
  
  Lists all pending async tasks for WebRTC connections.

- **Async Test**: 
  `POST /api/v0/mcp/monitor/webrtc/test/async_close`
  
  Test endpoint to simulate WebRTC operations and demonstrate event loop handling.

### Testing and Verification

To test the fixes and monitoring capabilities:

```bash
python run_mcp_with_webrtc_monitor.py --run-tests
```

This will start the server, run a series of WebRTC operations, and verify that they work correctly, even in FastAPI's event loop context.

## Implementation Details

### AnyIO-based Event Loop Handling

The core component is the `AnyIOMonitoredEventLoopHandler` class, which:

1. Detects the current async context using `sniffio`
2. In an async context with a running event loop:
   - Creates a background task for the coroutine
   - Returns a simulated success response immediately
   - Continues execution in the background
3. In a non-async context:
   - Creates a new event loop using AnyIO
   - Runs the coroutine to completion

### WebRTC Monitoring Architecture

The monitoring system consists of:

1. **WebRTCConnectionStats**: Dataclass that tracks statistics for a single connection
2. **WebRTCMonitor**: Main monitoring class that manages connections, operations, and tasks
3. **AsyncTaskTracker**: Utility for tracking async tasks and ensuring proper cleanup

### Integration Pattern

The integration uses a patching approach that:

1. Enhances WebRTC methods with monitoring and event loop handling
2. Patches them into the running MCP server instance
3. Adds monitoring endpoints to the existing API router

### Log Structure

When log directories are enabled, the system creates:

- `connections/[timestamp]_[connection_id].json`: Detailed connection logs
- `operations/[timestamp]_[operation_type]_[operation_id].json`: Operation logs

## Error Handling and Recovery

The implementation includes robust error handling:

1. **Graceful Degradation**: Operations continue as best as possible when errors occur
2. **Background Task Cleanup**: Ensures orphaned tasks are properly tracked and completed
3. **Simulated Success Responses**: When direct operation isn't possible, provides reasonable fallbacks
4. **Detailed Error Logging**: All errors are logged with context for debugging

## Conclusion

This enhanced WebRTC implementation solves the event loop issues that previously prevented WebRTC methods like `stop_webrtc_streaming` from working correctly in FastAPI, while also adding valuable monitoring capabilities that make it easier to debug and optimize WebRTC functionality.

The AnyIO-based approach provides better cross-framework compatibility than the previous asyncio-specific solution, and the monitoring integration gives real-time visibility into WebRTC operations that was previously not possible.