# WebRTC Monitoring Dashboard

## Overview

The WebRTC Monitoring Dashboard provides a comprehensive visual interface for monitoring and managing WebRTC connections in the MCP server. This dashboard leverages the AnyIO-based event loop handling to properly work with FastAPI and the WebRTC monitoring capabilities to provide real-time visibility into WebRTC operations.

![WebRTC Dashboard Screenshot](dashboard_screenshot.png)

## Features

### Real-time Monitoring
- **Connection Status**: View active, connecting, and closed connections
- **Operation History**: Track all WebRTC operations with success/failure status
- **Task Monitoring**: View and track async tasks related to WebRTC operations
- **Performance Metrics**: Monitor connection time and operation duration

### Connection Management
- **Create Connections**: Start WebRTC streams with specified content CIDs
- **Test Connections**: Run test connections for verification
- **Close Connections**: Close individual or all connections
- **Quality Control**: Adjust streaming quality for active connections

### Debugging and Troubleshooting
- **Operation Logs**: Real-time logging of all operations
- **Error Reporting**: Detailed error information for failed operations
- **Status Visualization**: Color-coded status indicators for quick assessment

## Installation and Setup

### Prerequisites
- Python 3.8+
- FastAPI and Uvicorn
- ipfs_kit_py with WebRTC support (aiortc)

### Running the Dashboard

The dashboard is integrated with the MCP server and can be launched using the provided script:

```bash
python run_mcp_with_webrtc_dashboard.py --open-browser
```

Command-line options:
```
--host HOST           Host to bind server to (default: 127.0.0.1)
--port PORT           Port to bind server to (default: 8000)
--debug               Enable debug mode
--isolation           Run with isolated settings
--open-browser        Open browser automatically
--test-client         Run a test client for simulating connections
--log-level {DEBUG,INFO,WARNING,ERROR}  Set the logging level
```

#### Running with Test Client

To test the dashboard with simulated WebRTC connections:

1. Start the server in one terminal:
   ```bash
   python run_mcp_with_webrtc_dashboard.py
   ```

2. Start the test client in another terminal:
   ```bash
   python run_mcp_with_webrtc_dashboard.py --test-client
   ```

The test client will create connections, modify quality settings, and close connections randomly to simulate real-world usage patterns.

## Integration with MCP Server

The WebRTC monitoring dashboard is fully integrated with the MCP server architecture:

```
┌───────────────────────────────────────────────┐
│              FastAPI Application               │
└─────────────────────┬─────────────────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
┌─────────▼──────────┐   ┌────────▼──────────────┐
│     MCP Server      │   │  WebRTC Dashboard     │
│ (Core API Endpoints)│   │ (Monitoring Endpoints)│
└─────────┬──────────┘   └────────┬──────────────┘
          │                       │
          ▼                       ▼
┌─────────────────────┐   ┌─────────────────────┐
│     IPFS Model      │   │   WebRTC Monitor    │
│ (WebRTC Methods)    │◄──┤ (Tracking & Metrics)│
└─────────────────────┘   └─────────────────────┘
          │                       │
          └───────────┬───────────┘
                      │
                      ▼
┌───────────────────────────────────────────────┐
│        AnyIO Event Loop Handler                │
│  (Proper async handling in FastAPI context)    │
└───────────────────────────────────────────────┘
```

## Dashboard Architecture

The dashboard consists of several components:

1. **Frontend UI** (`static/webrtc_dashboard.html`):
   - Pure HTML/CSS/JavaScript implementation
   - Real-time data fetching from API endpoints
   - Interactive controls for WebRTC operations
   - Auto-refreshing data views

2. **API Controller** (`mcp/controllers/webrtc_dashboard_controller.py`):
   - FastAPI endpoints for dashboard data
   - Connection data access
   - Operation status reporting
   - Task monitoring

3. **WebRTC Monitor** (from `fixes/webrtc_monitor.py`):
   - Connection state tracking
   - Operation recording
   - Async task management
   - Timing and statistics collection

4. **AnyIO Integration** (from `fixes/webrtc_anyio_monitor_integration.py`):
   - Properly handles async operations in FastAPI context
   - Ensures WebRTC methods work correctly in async environment
   - Provides graceful degradation when direct execution isn't possible

## API Endpoints

The dashboard exposes the following API endpoints:

### Data Endpoints
- `GET /api/v0/webrtc/dashboard`: Returns the dashboard HTML
- `GET /api/v0/webrtc/connections`: Lists all WebRTC connections
- `GET /api/v0/webrtc/operations`: Lists WebRTC operations history
- `GET /api/v0/webrtc/tasks`: Lists active and completed tasks

### Control Endpoints
- `POST /api/v0/webrtc/test_connection`: Creates a test connection
- `POST /api/v0/webrtc/stream_test_content`: Streams test content
- `POST /api/v0/webrtc/stream`: Streams specified content
- `POST /api/v0/webrtc/close/{connection_id}`: Closes a specific connection
- `POST /api/v0/webrtc/close_all`: Closes all connections
- `POST /api/v0/webrtc/quality/{connection_id}`: Adjusts stream quality

## Implementation Details

### Frontend Implementation

The dashboard frontend is implemented as a single HTML file with embedded CSS and JavaScript. This approach simplifies deployment and reduces dependencies. The UI is designed to:

1. Auto-refresh data from API endpoints at regular intervals
2. Provide real-time feedback for user actions
3. Display data in a clean, organized layout
4. Handle error states gracefully
5. Provide filtering and sorting capabilities
6. Update live without page reloads

### Backend Integration

The WebRTC dashboard controller integrates with the existing MCP server architecture by:

1. Using dependency injection to access WebRTC model and monitor
2. Providing FastAPI-compatible endpoints for dashboard data
3. Converting internal data structures to API-friendly formats
4. Handling async operations properly in FastAPI context
5. Gracefully degrading when components are unavailable

### Event Loop Handling

The dashboard leverages the AnyIO-based event loop handling to ensure WebRTC methods work correctly in FastAPI's async environment. This addresses the core issue where methods like `close_webrtc_connection` would fail when running inside a FastAPI route due to event loop conflicts.

## Security Considerations

When deploying the WebRTC dashboard, consider these security aspects:

1. **Access Control**: The dashboard does not include authentication by default. Consider adding FastAPI security dependencies for production use.
2. **CORS Settings**: Configure appropriate CORS settings when accessing from different origins.
3. **Rate Limiting**: Consider adding rate limiting for API endpoints to prevent abuse.
4. **Input Validation**: All inputs are validated, but review for specific deployment needs.
5. **Error Exposure**: Configure appropriate error detail exposure based on environment.

## Troubleshooting

### Common Issues

1. **Dashboard shows "WebRTC model not available"**
   - Ensure the MCP server is initialized correctly
   - Verify that the IPFS model is accessible
   - Check for proper imports and dependencies

2. **Connection operations fail**
   - Verify WebRTC dependencies are available (aiortc)
   - Check server logs for detailed error information
   - Ensure event loop handling is properly configured

3. **Dashboard doesn't auto-refresh**
   - Check browser console for JavaScript errors
   - Verify API endpoints are accessible
   - Check network connection and CORS settings

### Debugging

For more detailed debugging:

1. Start the server with debug mode:
   ```bash
   python run_mcp_with_webrtc_dashboard.py --debug --log-level DEBUG
   ```

2. Use browser developer tools to monitor network requests and console output

3. Check server logs for detailed operation status

## Extending the Dashboard

### Adding New Metrics

To add new metrics to the dashboard:

1. Update the WebRTC monitor to track the new metrics
2. Modify the API controller to expose the new data
3. Update the dashboard HTML to display the new metrics

### Customizing the UI

The dashboard UI is contained in a single HTML file for simplicity. To customize:

1. Edit the CSS styles in `static/webrtc_dashboard.html`
2. Modify the HTML structure as needed
3. Update the JavaScript functions for additional functionality

### Adding New Endpoints

To add new API endpoints:

1. Extend the WebRTCDashboardController class in `mcp/controllers/webrtc_dashboard_controller.py`
2. Register the new routes in the `register_routes` method
3. Update the dashboard UI to use the new endpoints

## Conclusion

The WebRTC Monitoring Dashboard provides a comprehensive solution for monitoring and managing WebRTC connections in the MCP server. It addresses the event loop handling issues in FastAPI context while providing valuable visibility into WebRTC operations for debugging and operational monitoring.

By integrating the dashboard with the WebRTC monitor and AnyIO event loop handler, the system offers a robust solution for WebRTC operations in an asynchronous environment.