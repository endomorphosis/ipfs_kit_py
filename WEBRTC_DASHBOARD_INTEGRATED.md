# Integrated WebRTC Dashboard and Video Player

## Overview

The Integrated WebRTC Dashboard and Video Player provides a comprehensive monitoring and control system for WebRTC streams in the ipfs_kit_py package. This system consists of two main components:

1. **WebRTC Dashboard**: A central monitoring interface for managing and tracking all WebRTC connections
2. **WebRTC Video Player**: A specialized player with random seek functionality for thorough stream testing

These components are tightly integrated to provide a seamless experience for monitoring, managing, and testing WebRTC streams.

## Features

### Dashboard Features

- **Connection Monitoring**: Real-time view of all active and closed WebRTC connections
- **Connection Management**: Start, stop, and test WebRTC connections directly from the dashboard
- **Operation History**: Track all WebRTC operations with timestamps and status
- **Connection Statistics**: View statistics like active connections count and average connection time
- **Operation Logs**: Detailed logs of all dashboard activities

### Video Player Features

- **Connection Integration**: Open the video player directly from the dashboard for any active connection
- **Full Video Controls**: Play, pause, stop, seek, volume control, and fullscreen options
- **Random Seek Testing**: Configure and run automatic random seeks to test stream resilience
- **Seek Statistics**: Track and analyze random seek patterns and performance
- **Connection Details**: View detailed information about the current connection

### Integration Points

- **Dashboard to Player Navigation**: Button on each active connection to open the corresponding video player
- **Parameter Passing**: Automatically pass connection details from dashboard to player
- **Auto-Connect Option**: Optional automatic connection on player launch from dashboard
- **Synchronized Connection State**: Connection status reflected in both interfaces
- **Return Navigation**: Easy navigation back to dashboard from player

## Architecture

The system is built on a Model-Controller-Persistence (MCP) architecture with these key components:

1. **MCP Server**: Core server that manages WebRTC functionality
2. **WebRTC Model**: Handles WebRTC operations and state management
3. **WebRTC Monitor**: Tracks and records WebRTC connections and operations
4. **Dashboard Controller**: Serves the dashboard UI and API endpoints
5. **Video Player Controller**: Serves the video player UI and integration endpoints
6. **FastAPI Routers**: Register all endpoints with appropriate prefixes

## Setup and Usage

### Prerequisites

- ipfs_kit_py package installed with WebRTC dependencies
- A functioning MCP Server

### Running the Integrated System

The integrated dashboard and player system can be run using the provided script:

```bash
python run_mcp_with_webrtc_dashboard.py
```

Command-line options:

- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 8000)
- `--debug`: Enable debug mode
- `--isolation`: Run with isolated settings
- `--open-browser`: Automatically open browser when server starts
- `--test-client`: Run a test client that simulates WebRTC connections

### Accessing the Dashboard

Open your browser and navigate to:

```
http://localhost:8000/api/v0/webrtc/dashboard
```

### Using the Video Player from Dashboard

1. Create or select an active WebRTC connection in the dashboard
2. Click the "Open Player" button next to the connection
3. The player opens in a new tab with connection details pre-populated
4. Optionally confirm auto-connection when prompted
5. Use the player controls to test the stream
6. Return to dashboard via the "Back to Dashboard" button

## API Endpoints

### Dashboard API Endpoints

- `GET /api/v0/webrtc/dashboard`: View the WebRTC monitoring dashboard
- `GET /api/v0/webrtc/connections`: Get list of all connections
- `GET /api/v0/webrtc/operations`: Get operation history
- `GET /api/v0/webrtc/tasks`: Get active and completed tasks
- `POST /api/v0/webrtc/test_connection`: Test a new connection
- `POST /api/v0/webrtc/stream_test_content`: Stream test content
- `POST /api/v0/webrtc/stream`: Stream content with specified CID
- `POST /api/v0/webrtc/close/{connection_id}`: Close specific connection
- `POST /api/v0/webrtc/close_all`: Close all active connections
- `POST /api/v0/webrtc/quality/{connection_id}`: Set quality for connection

### Video Player API Endpoints

- `GET /api/v0/webrtc/player`: View the video player (with optional connection parameters)
- `GET /api/v0/webrtc/connection/{connection_id}`: Get detailed connection information
- `GET /api/v0/webrtc/demo_video.mp4`: Get the demo video file for testing

## Implementation Details

### MCP Server Integration

The dashboard and player are integrated into the MCP server through FastAPI routers:

```python
# Create dashboard router
dashboard_router = create_webrtc_dashboard_router(
    webrtc_model=webrtc_model, 
    webrtc_monitor=monitor
)

# Add dashboard router to app
app.include_router(dashboard_router)

# Create video player router
video_player_router = create_webrtc_video_player_router(
    webrtc_model=webrtc_model
)

# Add video player router to app
app.include_router(video_player_router)
```

### Dashboard to Player Communication

The dashboard opens the video player with connection information via URL parameters:

```javascript
function openVideoPlayer(connectionId, contentCid) {
    const videoPlayerUrl = `/api/v0/webrtc/player?connection_id=${encodeURIComponent(connectionId)}&content_cid=${encodeURIComponent(contentCid)}`;
    window.open(videoPlayerUrl, '_blank');
}
```

The player receives and processes these parameters:

```python
connection_id = request.query_params.get("connection_id", "")
content_cid = request.query_params.get("content_cid", "")

# If connection parameters were provided, inject them into the HTML
if connection_id and content_cid:
    # Insert a script to auto-populate the form fields
    html_content = html_content.replace(
        "</body>",
        f'''
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                document.getElementById('content-cid').value = "{content_cid}";
                // Add connection handling code...
            }});
        </script>
        </body>'''
    )
```

## Security Considerations

- **Cross-Origin Resource Sharing**: Configure CORS appropriately for production
- **Content Security Policy**: Implement CSP headers for production use
- **Input Validation**: All user inputs are validated before processing
- **Authentication**: Add proper authentication for production use

## Performance Considerations

- **Caching**: Static assets are cached for performance
- **Connection Pooling**: API requests use connection pooling
- **Lazy Loading**: Player resources are loaded lazily
- **Event Debouncing**: UI updates are debounced to reduce overhead

## Future Enhancements

- **Real-time Updates**: WebSocket integration for live dashboard updates
- **Advanced Metrics**: Detailed performance metrics for streams
- **Multi-stream Support**: View multiple streams simultaneously
- **Recording Capability**: Record and replay streams for testing
- **Custom Testing Profiles**: Save and load custom random seek profiles
- **Mobile Support**: Enhanced responsive design for mobile devices

## Troubleshooting

### Dashboard Issues

- If connections don't appear, try refreshing the dashboard
- If operations fail, check the server logs for detailed error information
- If the dashboard doesn't load, verify that static files are properly served

### Video Player Issues

- If the player doesn't connect, try manual connection with the provided CID
- If video doesn't play, check browser console for media errors
- If random seeking causes issues, try reducing the seek frequency

## Contributing

Contributions to improve the WebRTC dashboard and video player are welcome:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This integrated system is part of the ipfs_kit_py package and is licensed under the same terms as the main package.