# WebRTC Monitoring for Enhanced MCP Server

This document describes the WebRTC monitoring capabilities of the Enhanced MCP Server. The monitoring system provides real-time performance metrics, streaming optimization, and Prometheus integration for dashboards.

## Features

The WebRTC monitoring system offers the following features:

- **Real-time Performance Metrics**: Collect detailed metrics on WebRTC connections, including bandwidth, packet loss, frame rates, buffer levels, and latency.
- **Streaming Optimization**: Automatically optimize streaming parameters based on network conditions and system resources.
- **Adaptive Quality Adjustment**: Dynamically adjust video quality based on stream health metrics.
- **Prometheus Integration**: Export all metrics to Prometheus for integration with monitoring dashboards.
- **Visualizations**: Generate performance dashboards and reports for analysis.
- **Buffer Optimization**: Intelligent buffer management to prevent playback interruptions.

## Getting Started

### Prerequisites

- Python 3.7 or higher
- IPFS Kit with MCP server installed
- Prometheus (optional, for metrics collection)
- Grafana (optional, for dashboards)

### Optional Dependencies

- `prometheus_client`: For metrics export (`pip install prometheus-client`)
- `pandas` and `matplotlib`: For visualization (`pip install pandas matplotlib`)

### Running the Server with Monitoring

The enhanced MCP server with WebRTC monitoring can be run using the provided script:

```bash
python run_enhanced_mcp_server_with_monitor.py
```

This will start the enhanced MCP server with WebRTC monitoring enabled.

### Command Line Options

The server supports many configuration options:

#### MCP Server Options:

- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to listen on (default: 8000)
- `--reload`: Enable auto-reload for development
- `--debug`: Enable debug mode
- `--isolation`: Use isolated storage for IPFS operations
- `--persistence-path`: Path for persistence files
- `--disable-metrics`: Disable Prometheus metrics export
- `--metrics-path`: Path for Prometheus metrics endpoint (default: /metrics)
- `--parquet-cache-path`: Path for ParquetCIDCache storage
- `--memory-cache-size`: Memory cache size in bytes
- `--disk-cache-size`: Disk cache size in bytes

#### WebRTC Monitor Options:

- `--disable-webrtc-monitor`: Disable WebRTC monitor
- `--webrtc-metrics-port`: WebRTC metrics server port (default: 9090)
- `--disable-webrtc-metrics`: Disable WebRTC metrics export
- `--disable-optimization`: Disable streaming optimization
- `--disable-auto-quality`: Disable automatic quality adjustment
- `--poll-interval`: WebRTC metrics polling interval in seconds (default: 2.0)
- `--visualization-interval`: Visualization update interval in seconds (default: 30.0)
- `--report-path`: Path for WebRTC reports and visualizations (default: ./webrtc_reports)
- `--webrtc-config-path`: Path to WebRTC monitor configuration file

### Example Commands

Start server with all monitoring features:

```bash
python run_enhanced_mcp_server_with_monitor.py --debug
```

Start server with disabled automatic quality adjustment:

```bash
python run_enhanced_mcp_server_with_monitor.py --disable-auto-quality
```

Start server with custom polling interval:

```bash
python run_enhanced_mcp_server_with_monitor.py --poll-interval 5.0
```

## Monitoring Configuration

The WebRTC monitoring system can be configured with a JSON configuration file:

```json
{
  "optimization": {
    "buffer_size_range": [15, 60],
    "prefetch_threshold_range": [0.2, 0.8],
    "quality_downgrade_threshold": 50,
    "quality_upgrade_threshold": 80,
    "buffer_underrun_threshold": 3,
    "network_sensitivity": 0.7,
    "cpu_sensitivity": 0.5,
    "memory_sensitivity": 0.3
  },
  "metrics": {
    "collect_detailed_stats": true,
    "collect_frame_stats": true,
    "collect_resource_stats": true,
    "collect_quality_metrics": true
  },
  "visualization": {
    "enabled": true,
    "live_update": false,
    "dashboard_update_interval": 30,
    "max_history_points": 1000,
    "plot_style": "dark_background"
  },
  "reporting": {
    "enabled": true,
    "save_raw_data": true,
    "interval": 300,
    "formats": ["json", "html"]
  }
}
```

## Prometheus Integration

The WebRTC monitoring system exports metrics to Prometheus for integration with monitoring dashboards. The metrics are available at:

- MCP metrics: `http://<host>:<port>/metrics`
- WebRTC metrics: `http://<host>:<webrtc-metrics-port>`

### Available Metrics

The WebRTC monitoring system exports the following metrics:

- **Connection Metrics**: webrtc_connections_total, webrtc_active_connections, webrtc_connection_duration_seconds
- **Frame Metrics**: webrtc_frames_sent_total, webrtc_frames_received_total, webrtc_frame_rate, webrtc_frame_size_bytes
- **Stream Metrics**: webrtc_buffer_level_frames, webrtc_buffer_level_seconds, webrtc_buffer_underruns_total
- **Bandwidth Metrics**: webrtc_bandwidth_kbps, webrtc_packet_loss_percent
- **Latency Metrics**: webrtc_latency_ms, webrtc_jitter_ms
- **Quality Metrics**: webrtc_video_quality_score, webrtc_quality_switches_total, webrtc_stream_health_score
- **Cache Metrics**: webrtc_prefetch_operations_total, webrtc_prefetch_latency_ms
- **Resource Metrics**: webrtc_cpu_usage_percent, webrtc_memory_usage_bytes
- **ICE Metrics**: webrtc_ice_gathering_time_ms, webrtc_ice_connection_time_ms
- **ABR Metrics**: webrtc_abr_switches_total

### Grafana Dashboard

A sample Grafana dashboard configuration is provided in the `webrtc_dashboard.json` file. This dashboard provides a comprehensive view of WebRTC performance metrics.

## Advanced Usage

### Programmatic Access

The WebRTC monitoring system can be used programmatically:

```python
from run_enhanced_mcp_server import EnhancedMCPServer
from webrtc_monitor_integration import WebRTCMonitorIntegration

# Create server
server = EnhancedMCPServer(debug_mode=True)

# Create monitor
monitor = WebRTCMonitorIntegration(
    mcp_server=server.mcp_server,
    enable_optimization=True,
    auto_adjust_quality=True
)

# Start monitor
monitor.start()

# Run server
server.run_server(host="127.0.0.1", port=8000)

# Stop monitor when done
monitor.stop()
```

### Custom Optimization Strategies

You can customize the optimization strategy by modifying the WebRTC monitoring configuration:

```python
monitor = WebRTCMonitorIntegration(
    config_path="custom_config.json"
)
```

## Troubleshooting

### Common Issues

1. **Metrics not showing up in Prometheus**: Ensure that the WebRTC metrics port is accessible and that Prometheus is configured to scrape it.

2. **Visualizations not generating**: Check that pandas and matplotlib are installed. If not, install them with `pip install pandas matplotlib`.

3. **No WebRTC connections detected**: Ensure that the WebRTC controller is properly initialized and that the MCP server is running.

4. **High CPU usage**: Adjust the polling interval to reduce CPU load. Try `--poll-interval 5.0` for less frequent updates.

### Logging

The WebRTC monitoring system logs to:

- `enhanced_mcp_server.log`: Main server log
- `webrtc_monitor.log`: WebRTC monitoring log

Check these logs for troubleshooting information.

## Performance Optimization

### Recommendations

1. **Buffer Size**: Adjust buffer size based on network conditions. Higher buffer size for unreliable networks, lower for low-latency requirements.

2. **Quality Adjustment**: Enable automatic quality adjustment for adaptive streaming that responds to network conditions.

3. **Polling Interval**: Adjust the polling interval based on your monitoring needs. Lower values provide more frequent updates but increase CPU usage.

4. **Resource Sensitivity**: Adjust network, CPU, and memory sensitivity values to balance performance and resource usage.

5. **Visualization**: Disable visualization if not needed to save resources.

### Best Practices

1. **Use Prometheus and Grafana**: For comprehensive monitoring and alerting.

2. **Enable Optimization**: Allow the monitoring system to optimize streaming parameters automatically.

3. **Configure Buffer Parameters**: Adjust buffer size and prefetch threshold based on your specific use case.

4. **Monitor System Resources**: Watch for high CPU or memory usage and adjust parameters accordingly.

5. **Regular Reporting**: Configure periodic reporting to track performance over time.

## License

This project is licensed under the same license as the main IPFS Kit project.