# IPFS Kit Dashboard

A comprehensive web-based monitoring and analytics dashboard for the IPFS Kit ecosystem. This dashboard provides real-time visualization of system performance, MCP server metrics, virtual filesystem behavior, and storage backend analytics.

## 🌟 Features

### Real-time Monitoring
- **WebSocket Updates**: Live data streaming with automatic reconnection
- **Interactive Charts**: Powered by Chart.js for responsive visualizations
- **Health Monitoring**: System-wide health scoring and status tracking
- **Alert System**: Configurable thresholds with alert management

### Data Sources
- **MCP Server**: Metrics and health endpoints monitoring
- **IPFS Kit**: Prometheus metrics integration
- **System Resources**: CPU, memory, and disk usage tracking
- **Virtual Filesystem**: Operation tracking and performance analytics

### Web Interface
- **Responsive Design**: Mobile-friendly interface
- **Multi-page Layout**: Dedicated views for metrics, health, and VFS analytics
- **REST API**: Programmatic access to all dashboard data
- **Static Asset Serving**: Embedded CSS, JavaScript, and templates

## 🚀 Quick Start

### Installation

Install the required dependencies:

```bash
pip install fastapi uvicorn jinja2 aiohttp psutil pyyaml
```

### Basic Usage

#### Command Line Interface

```bash
# Start dashboard with default settings
python -m dashboard start

# Start with custom host and port
python -m dashboard start --host 0.0.0.0 --port 3000

# Start with configuration file
python -m dashboard start --config dashboard_config.yaml

# Create sample configuration
python -m dashboard config --output my_config.yaml

# Validate configuration
python -m dashboard validate --config my_config.yaml
```

#### Python API

```python
import asyncio
from dashboard.config import DashboardConfig
from dashboard.web_dashboard import WebDashboard

async def run_dashboard():
    # Create configuration
    config = DashboardConfig(
        host="127.0.0.1",
        port=8080,
        mcp_server_url="http://localhost:8000",
        ipfs_kit_url="http://localhost:9090"
    )
    
    # Create and start dashboard
    dashboard = WebDashboard(config)
    await dashboard.start()

# Run the dashboard
asyncio.run(run_dashboard())
```

#### Quick Demo

```bash
# Run the interactive demo
python dashboard_example.py

# Or check dependencies first
python dashboard_example.py check
```

## 📊 Dashboard Interface

### Main URLs

Once running (default on `http://localhost:8080`):

- **Main Dashboard**: `/dashboard` - Overview with key metrics
- **Metrics View**: `/dashboard/metrics` - Detailed performance metrics
- **Health Status**: `/dashboard/health` - System health and alerts
- **VFS Analytics**: `/dashboard/vfs` - Virtual filesystem insights

### API Endpoints

- **Summary**: `/dashboard/api/summary` - Dashboard summary data
- **Metrics**: `/dashboard/api/metrics` - All metrics data
- **Health**: `/dashboard/api/health` - Health status and alerts
- **Analytics**: `/dashboard/api/analytics` - Performance and VFS analytics
- **WebSocket**: `/dashboard/ws` - Real-time updates

## ⚙️ Configuration

### Environment Variables

```bash
export DASHBOARD_HOST="0.0.0.0"
export DASHBOARD_PORT="8080"
export DASHBOARD_DEBUG="true"
export DASHBOARD_MCP_SERVER_URL="http://localhost:8000"
export DASHBOARD_IPFS_KIT_URL="http://localhost:9090"
```

### Configuration File

Create a YAML configuration file:

```yaml
# Server settings
host: "127.0.0.1"
port: 8080

# URL paths
dashboard_path: "/dashboard"
api_path: "/dashboard/api"
static_path: "/static"

# External service URLs
mcp_server_url: "http://localhost:8000"
ipfs_kit_url: "http://localhost:9090"

# Update intervals (seconds)
data_collection_interval: 10
metrics_update_interval: 5

# Data retention
max_data_points: 1000
data_retention_hours: 24

# Alerting
alert_enabled: true
alert_cooldown_minutes: 5

# Health monitoring thresholds
health_thresholds:
  cpu_usage_percent: 80.0
  memory_usage_percent: 85.0
  disk_usage_percent: 90.0
  response_time_seconds: 5.0

# Debug mode
debug: false
```

### Configuration Priority

1. Command-line arguments (highest priority)
2. Configuration file (if specified)
3. Environment variables
4. Default values (lowest priority)

## 🏗️ Architecture

### Core Components

#### DashboardConfig
- Centralized configuration management
- Environment variable support
- YAML file loading
- Validation and defaults

#### DataCollector
- Multi-source data collection
- Asynchronous HTTP requests
- System resource monitoring
- Metric storage and retrieval

#### MetricsAggregator
- Statistical analysis
- Health status calculation
- Alert generation and management
- Performance analytics

#### WebDashboard
- FastAPI web server
- WebSocket management
- Template rendering
- Static file serving

### Data Flow

```
External Sources → DataCollector → MetricsAggregator → WebDashboard → Browser
     ↓                ↓                    ↓               ↓
- MCP Server     - HTTP Requests    - Aggregation   - WebSocket
- IPFS Kit       - System Monitor   - Health Score  - REST API  
- System         - Data Storage     - Alerts        - Templates
```

## 📈 Monitoring Capabilities

### System Health

- **Overall Health Score**: Weighted calculation based on multiple factors
- **Component Status**: Individual service health tracking
- **Issue Detection**: Automatic problem identification
- **Trend Analysis**: Historical performance tracking

### Performance Analytics

- **MCP Server Metrics**: Operation counts, response times, success rates
- **IPFS Kit Performance**: Storage backend performance, cache efficiency
- **System Resources**: CPU, memory, disk utilization
- **Network Performance**: Request/response metrics

### Virtual Filesystem

- **Operation Tracking**: Read/write operation monitoring
- **Cache Analytics**: Hit rates and efficiency metrics
- **Performance Trends**: Response time analysis
- **Usage Patterns**: Access pattern identification

### Alerting System

- **Configurable Thresholds**: Customizable alert conditions
- **Multi-level Alerts**: Info, warning, and critical levels
- **Alert Management**: Acknowledgment and history tracking
- **Cooldown Periods**: Prevent alert spam

## 🛠️ Development

### Project Structure

```
dashboard/
├── __init__.py              # Module initialization
├── __main__.py              # CLI entry point
├── config.py                # Configuration management
├── data_collector.py        # Data collection from sources
├── metrics_aggregator.py    # Metrics processing and analysis
├── web_dashboard.py         # Web interface and server
├── static/                  # Static assets (CSS, JS, images)
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       └── dashboard.js
└── templates/               # HTML templates
    ├── base.html
    ├── index.html
    ├── metrics.html
    ├── health.html
    ├── vfs.html
    └── redirect.html
```

### Dependencies

#### Required
- **fastapi**: Web framework for REST API and templates
- **uvicorn**: ASGI server for running the web application
- **jinja2**: Template engine for HTML rendering
- **aiohttp**: HTTP client for external service requests
- **psutil**: System resource monitoring
- **pyyaml**: YAML configuration file support

#### Optional
- **prometheus_client**: Enhanced metrics collection
- **redis**: Caching and data persistence
- **celery**: Background task processing

### Testing

```bash
# Check dependencies
python dashboard_example.py check

# Run demo with debug output
python dashboard_example.py demo

# Validate configuration
python -m dashboard validate

# Test with minimal setup
python -m dashboard start --debug --host 127.0.0.1 --port 8080
```

## 🔧 Customization

### Custom Templates

Create custom HTML templates in the `templates/` directory:

```html
<!-- custom_page.html -->
{% extends "base.html" %}

{% block title %}Custom Dashboard Page{% endblock %}

{% block content %}
<div class="card">
    <h3>Custom Content</h3>
    <p>Your custom dashboard content here.</p>
</div>
{% endblock %}
```

### Custom Metrics

Extend the DataCollector to add custom metrics:

```python
from dashboard.data_collector import DataCollector

class CustomDataCollector(DataCollector):
    async def _collect_custom_data(self):
        # Implement custom data collection
        return {"custom_metric": "value"}
    
    async def collect_data(self):
        data = await super().collect_data()
        custom_data = await self._collect_custom_data()
        data.update(custom_data)
        return data
```

### Custom Alerts

Add custom alert conditions:

```python
from dashboard.metrics_aggregator import MetricsAggregator, Alert

class CustomMetricsAggregator(MetricsAggregator):
    def _check_custom_alerts(self):
        # Implement custom alert logic
        if self.some_condition():
            alert = Alert(
                id="custom_alert",
                title="Custom Alert",
                message="Custom condition detected",
                level="warning",
                metric_name="custom_metric"
            )
            self.active_alerts[alert.id] = alert
```

## 🤝 Integration

### MCP Server Integration

Ensure your MCP server exposes the required endpoints:

```python
# In your MCP server
@app.get("/metrics")
async def get_metrics():
    return {
        "operations_total": operation_count,
        "response_time_seconds": avg_response_time,
        "success_rate": success_rate
    }

@app.get("/health")
async def get_health():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }
```

### IPFS Kit Integration

Configure Prometheus metrics in IPFS Kit:

```python
# In your IPFS Kit configuration
prometheus_enabled = True
prometheus_port = 9090
prometheus_path = "/metrics"
```

## 🚨 Troubleshooting

### Common Issues

#### Import Errors
```
ImportError: No module named 'fastapi'
```
**Solution**: Install required dependencies:
```bash
pip install fastapi uvicorn jinja2 aiohttp psutil pyyaml
```

#### Connection Errors
```
aiohttp.ClientConnectionError: Cannot connect to host localhost:8000
```
**Solution**: Ensure MCP server and IPFS Kit are running and accessible.

#### Port Already in Use
```
OSError: [Errno 48] Address already in use
```
**Solution**: Use a different port:
```bash
python -m dashboard start --port 8081
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
python -m dashboard start --debug
```

Or set in configuration:
```yaml
debug: true
```

### Health Check

Check dashboard status:

```bash
# Validate configuration
python -m dashboard validate

# Check dependencies
python dashboard_example.py check

# View current status
python -m dashboard status
```

## 📝 License

This project is part of the IPFS Kit ecosystem and follows the same licensing terms.

## 🔗 Related Documentation

- [IPFS Kit Main Documentation](../README.md)
- [MCP Server Documentation](../mcp_module/README.md)
- [VFS Documentation](../ipfs_kit.py)

---

**Happy Monitoring!** 📊✨
