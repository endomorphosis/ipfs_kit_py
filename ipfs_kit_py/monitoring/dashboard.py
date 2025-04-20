"""
Web dashboard for MCP server monitoring.

This module provides a simple web dashboard for visualizing
monitoring metrics, health status, and system information.
"""

import os
import time
import json
import logging
import threading
import asyncio
from typing import Dict, Any, Optional, List, Union, Set, Callable

# Configure logger
logger = logging.getLogger(__name__)

# Import dependencies based on availability
try:
    from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    FASTAPI_AVAILABLE = True
except ImportError:
    logger.warning("FastAPI not available for dashboard. Install with: pip install fastapi jinja2")
    FASTAPI_AVAILABLE = False


class MonitoringDashboard:
    """
    Web dashboard for MCP server monitoring.
    
    This class provides a web interface for visualizing monitoring metrics,
    health status, and system information. It uses FastAPI and WebSockets
    for real-time updates.
    """
    
    def __init__(
        self,
        app=None,
        monitoring_manager=None,
        path_prefix="/dashboard",
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the monitoring dashboard.
        
        Args:
            app: FastAPI app instance
            monitoring_manager: MonitoringManager instance
            path_prefix: URL path prefix for dashboard routes
            options: Additional configuration options
        """
        if not FASTAPI_AVAILABLE:
            raise ImportError("FastAPI not available for dashboard")
            
        self.app = app
        self.monitoring_manager = monitoring_manager
        self.path_prefix = path_prefix
        self.options = options or {}
        
        # Websocket connections
        self.active_connections: Set[WebSocket] = set()
        self.connection_lock = threading.Lock()
        
        # Dashboard state
        self.metrics_update_interval = self.options.get("metrics_update_interval", 5)  # seconds
        self.dashboard_running = False
        self.update_thread = None
        
        # Set up templates
        templates_dir = self.options.get("templates_dir")
        if not templates_dir:
            # Use default templates directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            templates_dir = os.path.join(current_dir, "templates")
            
            # If directory doesn't exist, create it with default templates
            if not os.path.exists(templates_dir):
                os.makedirs(templates_dir, exist_ok=True)
                self._create_default_templates(templates_dir)
                
        self.templates = Jinja2Templates(directory=templates_dir)
        
        # Set up static files
        static_dir = self.options.get("static_dir")
        if not static_dir:
            # Use default static directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            static_dir = os.path.join(current_dir, "static")
            
            # If directory doesn't exist, create it with default static files
            if not os.path.exists(static_dir):
                os.makedirs(static_dir, exist_ok=True)
                self._create_default_static_files(static_dir)
                
        self.static_dir = static_dir
        
        # Configure routes if app provided
        if app:
            self.configure_routes(app)
            
    def _create_default_templates(self, templates_dir):
        """Create default templates for the dashboard."""
        # Create base template
        base_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}MCP Monitoring Dashboard{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', path='/css/styles.css') }}">
    <script src="{{ url_for('static', path='/js/chart.min.js') }}"></script>
    {% block head %}{% endblock %}
</head>
<body>
    <header>
        <div class="logo">
            <h1>MCP Monitoring</h1>
        </div>
        <nav>
            <ul>
                <li><a href="{{ url_for('dashboard_index') }}">Overview</a></li>
                <li><a href="{{ url_for('dashboard_backends') }}">Backends</a></li>
                <li><a href="{{ url_for('dashboard_metrics') }}">Metrics</a></li>
                <li><a href="{{ url_for('dashboard_health') }}">Health</a></li>
            </ul>
        </nav>
    </header>
    
    <main>
        {% block content %}{% endblock %}
    </main>
    
    <footer>
        <p>MCP Monitoring Dashboard © {% now 'Y' %}</p>
    </footer>
    
    <script src="{{ url_for('static', path='/js/dashboard.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
"""

        # Create index template
        index_template = """{% extends "base.html" %}

{% block title %}MCP Monitoring Dashboard{% endblock %}

{% block content %}
<section class="dashboard-overview">
    <h2>System Overview</h2>
    
    <div class="status-cards">
        <div class="card" id="server-status-card">
            <h3>Server Status</h3>
            <div class="status-indicator unknown" id="server-status-indicator">Unknown</div>
            <div class="details" id="server-status-details">
                <p>Uptime: <span id="server-uptime">--</span></p>
                <p>Last check: <span id="server-last-check">--</span></p>
            </div>
        </div>
        
        <div class="card" id="storage-status-card">
            <h3>Storage Status</h3>
            <div class="status-indicator unknown" id="storage-status-indicator">Unknown</div>
            <div class="details" id="storage-status-details">
                <p>Backends: <span id="storage-backends-count">--</span></p>
                <p>Last check: <span id="storage-last-check">--</span></p>
            </div>
        </div>
        
        <div class="card" id="resources-status-card">
            <h3>Resources</h3>
            <div class="details" id="resources-details">
                <div class="resource-meter">
                    <label>CPU:</label>
                    <div class="meter">
                        <div class="meter-bar" id="cpu-meter" style="width: 0%;">0%</div>
                    </div>
                </div>
                <div class="resource-meter">
                    <label>Memory:</label>
                    <div class="meter">
                        <div class="meter-bar" id="memory-meter" style="width: 0%;">0%</div>
                    </div>
                </div>
                <div class="resource-meter">
                    <label>Disk:</label>
                    <div class="meter">
                        <div class="meter-bar" id="disk-meter" style="width: 0%;">0%</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Backend Operations</h3>
        <canvas id="operations-chart"></canvas>
    </div>
</section>

<section class="backends-overview">
    <h2>Storage Backends</h2>
    <div class="backends-grid" id="backends-grid">
        <div class="loading">Loading backend information...</div>
    </div>
</section>
{% endblock %}

{% block scripts %}
<script>
    // Connect to WebSocket for real-time updates
    const socket = new WebSocket(`ws://${window.location.host}{{ url_for('dashboard_ws') }}`);
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateDashboard(data);
    };
    
    socket.onclose = function(event) {
        console.log('WebSocket connection closed');
        setTimeout(() => {
            location.reload();
        }, 5000);
    };
    
    function updateDashboard(data) {
        // Update status indicators
        if (data.health) {
            updateStatusCard('server', data.health.components.server || 'unknown');
            updateStatusCard('storage', data.health.components.storage || 'unknown');
            
            // Update resource meters
            if (data.health.components.resources && data.health.components.resources.details) {
                const resources = data.health.components.resources.details;
                if (resources.cpu) {
                    updateMeter('cpu', resources.cpu.percent);
                }
                if (resources.memory) {
                    updateMeter('memory', resources.memory.percent);
                }
                if (resources.disk) {
                    updateMeter('disk', resources.disk.percent);
                }
            }
        }
        
        // Update backends grid
        if (data.backends && data.backends.backends) {
            updateBackendsGrid(data.backends.backends);
        }
        
        // Update operations chart
        if (data.metrics && data.metrics.performance_metrics) {
            updateOperationsChart(data.metrics.performance_metrics);
        }
    }
    
    function updateStatusCard(type, status) {
        const indicator = document.getElementById(`${type}-status-indicator`);
        
        if (indicator) {
            // Update status text
            indicator.textContent = status.status || status;
            
            // Update status class
            indicator.className = 'status-indicator';
            indicator.classList.add(status.status || status);
            
            // Update details
            if (status.details) {
                const details = document.getElementById(`${type}-status-details`);
                
                if (type === 'server' && status.details.uptime) {
                    document.getElementById('server-uptime').textContent = formatUptime(status.details.uptime);
                }
                
                if (status.details.last_check) {
                    document.getElementById(`${type}-last-check`).textContent = formatTimestamp(status.details.last_check);
                }
            }
        }
    }
    
    function updateMeter(type, value) {
        const meter = document.getElementById(`${type}-meter`);
        
        if (meter) {
            meter.style.width = `${value}%`;
            meter.textContent = `${Math.round(value)}%`;
            
            // Update color based on value
            meter.className = 'meter-bar';
            if (value > 90) {
                meter.classList.add('critical');
            } else if (value > 75) {
                meter.classList.add('warning');
            } else {
                meter.classList.add('normal');
            }
        }
    }
    
    function updateBackendsGrid(backends) {
        const grid = document.getElementById('backends-grid');
        
        if (grid) {
            grid.innerHTML = '';
            
            for (const [backend, info] of Object.entries(backends)) {
                const backendCard = document.createElement('div');
                backendCard.className = 'backend-card';
                
                const status = info.status || 'unknown';
                
                backendCard.innerHTML = `
                    <h3>${backend}</h3>
                    <div class="status-indicator ${status}">${status}</div>
                    <div class="details">
                        <p>Last check: ${formatTimestamp(info.last_check || 0)}</p>
                    </div>
                `;
                
                grid.appendChild(backendCard);
            }
        }
    }
    
    let operationsChart = null;
    
    function updateOperationsChart(metrics) {
        const canvas = document.getElementById('operations-chart');
        
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Collect data from all backends
        const backends = Object.keys(metrics.performance_metrics || {});
        const operations = new Set();
        const data = {};
        
        backends.forEach(backend => {
            const backendOps = metrics.performance_metrics[backend] || {};
            Object.keys(backendOps).forEach(op => operations.add(op));
        });
        
        const operationsList = Array.from(operations);
        
        // Prepare data for chart
        const datasets = backends.map((backend, index) => {
            const backendOps = metrics.performance_metrics[backend] || {};
            
            return {
                label: backend,
                data: operationsList.map(op => {
                    const opData = backendOps[op] || {};
                    return opData.count || 0;
                }),
                backgroundColor: getColor(index, 0.7),
                borderColor: getColor(index, 1),
                borderWidth: 1
            };
        });
        
        // Create or update chart
        if (operationsChart) {
            operationsChart.data.labels = operationsList;
            operationsChart.data.datasets = datasets;
            operationsChart.update();
        } else {
            operationsChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: operationsList,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
    }
    
    function getColor(index, alpha) {
        const colors = [
            `rgba(54, 162, 235, ${alpha})`,
            `rgba(255, 99, 132, ${alpha})`,
            `rgba(75, 192, 192, ${alpha})`,
            `rgba(255, 206, 86, ${alpha})`,
            `rgba(153, 102, 255, ${alpha})`,
            `rgba(255, 159, 64, ${alpha})`,
            `rgba(199, 199, 199, ${alpha})`,
        ];
        
        return colors[index % colors.length];
    }
    
    function formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (days > 0) {
            return `${days}d ${hours}h ${minutes}m`;
        } else if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${Math.floor(seconds % 60)}s`;
        } else {
            return `${Math.floor(seconds)}s`;
        }
    }
    
    function formatTimestamp(timestamp) {
        if (!timestamp) return 'Never';
        
        const date = new Date(timestamp * 1000);
        return date.toLocaleString();
    }
    
    // Initial request for data
    fetch('{{ url_for("dashboard_data") }}')
        .then(response => response.json())
        .then(data => updateDashboard(data))
        .catch(error => console.error('Error fetching dashboard data:', error));
</script>
{% endblock %}
"""

        # Create other templates (backends, metrics, health)
        backends_template = """{% extends "base.html" %}

{% block title %}Storage Backends - MCP Monitoring Dashboard{% endblock %}

{% block content %}
<section class="backends-detail">
    <h2>Storage Backends</h2>
    
    <div class="backends-cards" id="backends-cards">
        <div class="loading">Loading backend details...</div>
    </div>
    
    <div class="chart-container">
        <h3>Backend Success Rates</h3>
        <canvas id="success-rates-chart"></canvas>
    </div>
    
    <div class="chart-container">
        <h3>Operation Latency</h3>
        <canvas id="latency-chart"></canvas>
    </div>
</section>
{% endblock %}

{% block scripts %}
<script>
    // Connect to WebSocket for real-time updates
    const socket = new WebSocket(`ws://${window.location.host}{{ url_for('dashboard_ws') }}`);
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateBackendsPage(data);
    };
    
    socket.onclose = function(event) {
        console.log('WebSocket connection closed');
        setTimeout(() => {
            location.reload();
        }, 5000);
    };
    
    function updateBackendsPage(data) {
        // Update backends cards
        if (data.backends && data.backends.backends) {
            updateBackendsCards(data.backends.backends);
        }
        
        // Update success rates chart
        if (data.metrics && data.metrics.performance_metrics) {
            updateSuccessRatesChart(data.metrics.performance_metrics);
            updateLatencyChart(data.metrics.performance_metrics);
        }
    }
    
    function updateBackendsCards(backends) {
        const container = document.getElementById('backends-cards');
        
        if (container) {
            container.innerHTML = '';
            
            for (const [backend, info] of Object.entries(backends)) {
                const card = document.createElement('div');
                card.className = 'backend-detail-card';
                
                const status = info.status || 'unknown';
                
                let detailsHtml = '';
                if (info.details && info.details.backends && info.details.backends[backend]) {
                    const backendInfo = info.details.backends[backend];
                    
                    if (backendInfo.details) {
                        const details = backendInfo.details;
                        
                        if (details.status_code) {
                            detailsHtml += `<p>Status code: ${details.status_code}</p>`;
                        }
                        
                        if (details.available !== undefined) {
                            detailsHtml += `<p>Available: ${details.available ? 'Yes' : 'No'}</p>`;
                        }
                        
                        if (details.stored_with) {
                            detailsHtml += `<p>Implementation: ${details.stored_with}</p>`;
                        }
                    }
                }
                
                card.innerHTML = `
                    <h3>${backend}</h3>
                    <div class="status-indicator ${status}">${status}</div>
                    <div class="details">
                        <p>Last check: ${formatTimestamp(info.last_check || 0)}</p>
                        ${detailsHtml}
                    </div>
                `;
                
                container.appendChild(card);
            }
        }
    }
    
    let successRatesChart = null;
    
    function updateSuccessRatesChart(metrics) {
        const canvas = document.getElementById('success-rates-chart');
        
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Collect data
        const backends = Object.keys(metrics.performance_metrics || {});
        const operations = new Set();
        
        backends.forEach(backend => {
            const backendOps = metrics.performance_metrics[backend] || {};
            Object.keys(backendOps).forEach(op => operations.add(op));
        });
        
        const operationsList = Array.from(operations);
        
        // Prepare data for chart
        const datasets = backends.map((backend, index) => {
            const backendOps = metrics.performance_metrics[backend] || {};
            
            return {
                label: backend,
                data: operationsList.map(op => {
                    const opData = backendOps[op] || {};
                    return opData.success_rate ? opData.success_rate * 100 : 0;
                }),
                backgroundColor: getColor(index, 0.7),
                borderColor: getColor(index, 1),
                borderWidth: 1
            };
        });
        
        // Create or update chart
        if (successRatesChart) {
            successRatesChart.data.labels = operationsList;
            successRatesChart.data.datasets = datasets;
            successRatesChart.update();
        } else {
            successRatesChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: operationsList,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            title: {
                                display: true,
                                text: 'Success Rate (%)'
                            }
                        }
                    }
                }
            });
        }
    }
    
    let latencyChart = null;
    
    function updateLatencyChart(metrics) {
        const canvas = document.getElementById('latency-chart');
        
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Collect data
        const backends = Object.keys(metrics.performance_metrics || {});
        const operations = new Set();
        
        backends.forEach(backend => {
            const backendOps = metrics.performance_metrics[backend] || {};
            Object.keys(backendOps).forEach(op => operations.add(op));
        });
        
        const operationsList = Array.from(operations);
        
        // Prepare data for chart
        const datasets = backends.map((backend, index) => {
            const backendOps = metrics.performance_metrics[backend] || {};
            
            return {
                label: backend,
                data: operationsList.map(op => {
                    const opData = backendOps[op] || {};
                    return opData.avg_time ? opData.avg_time * 1000 : 0;  // Convert to ms
                }),
                backgroundColor: getColor(index, 0.7),
                borderColor: getColor(index, 1),
                borderWidth: 1
            };
        });
        
        // Create or update chart
        if (latencyChart) {
            latencyChart.data.labels = operationsList;
            latencyChart.data.datasets = datasets;
            latencyChart.update();
        } else {
            latencyChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: operationsList,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Average Latency (ms)'
                            }
                        }
                    }
                }
            });
        }
    }
    
    function getColor(index, alpha) {
        const colors = [
            `rgba(54, 162, 235, ${alpha})`,
            `rgba(255, 99, 132, ${alpha})`,
            `rgba(75, 192, 192, ${alpha})`,
            `rgba(255, 206, 86, ${alpha})`,
            `rgba(153, 102, 255, ${alpha})`,
            `rgba(255, 159, 64, ${alpha})`,
            `rgba(199, 199, 199, ${alpha})`,
        ];
        
        return colors[index % colors.length];
    }
    
    function formatTimestamp(timestamp) {
        if (!timestamp) return 'Never';
        
        const date = new Date(timestamp * 1000);
        return date.toLocaleString();
    }
    
    // Initial request for data
    fetch('{{ url_for("dashboard_data") }}')
        .then(response => response.json())
        .then(data => updateBackendsPage(data))
        .catch(error => console.error('Error fetching dashboard data:', error));
</script>
{% endblock %}
"""

        metrics_template = """{% extends "base.html" %}

{% block title %}Metrics - MCP Monitoring Dashboard{% endblock %}

{% block content %}
<section class="metrics-detail">
    <h2>System Metrics</h2>
    
    <div class="chart-container">
        <h3>API Requests</h3>
        <canvas id="api-requests-chart"></canvas>
    </div>
    
    <div class="metrics-cards">
        <div class="card">
            <h3>Content</h3>
            <div class="chart-container small">
                <canvas id="content-chart"></canvas>
            </div>
        </div>
        
        <div class="card">
            <h3>Storage</h3>
            <div class="chart-container small">
                <canvas id="storage-chart"></canvas>
            </div>
        </div>
    </div>
    
    <div class="chart-container">
        <h3>Operations Timeline</h3>
        <canvas id="operations-timeline-chart"></canvas>
    </div>
</section>
{% endblock %}

{% block scripts %}
<script>
    // Connect to WebSocket for real-time updates
    const socket = new WebSocket(`ws://${window.location.host}{{ url_for('dashboard_ws') }}`);
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateMetricsPage(data);
    };
    
    socket.onclose = function(event) {
        console.log('WebSocket connection closed');
        setTimeout(() => {
            location.reload();
        }, 5000);
    };
    
    function updateMetricsPage(data) {
        // Update content chart
        if (data.metrics && data.metrics.capacity_metrics) {
            updateContentChart(data.metrics.capacity_metrics);
        }
        
        // Update storage chart
        if (data.metrics && data.metrics.capacity_metrics) {
            updateStorageChart(data.metrics.capacity_metrics);
        }
        
        // Update operations timeline
        if (data.metrics && data.metrics.performance_metrics) {
            updateOperationsTimelineChart(data.metrics.performance_metrics);
        }
        
        // Update API requests chart
        if (data.api_metrics) {
            updateApiRequestsChart(data.api_metrics);
        }
    }
    
    let contentChart = null;
    
    function updateContentChart(metrics) {
        const canvas = document.getElementById('content-chart');
        
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Extract content counts by backend
        const backends = {};
        
        for (const backend in metrics.backends) {
            if (metrics.backends[backend].content_count) {
                backends[backend] = metrics.backends[backend].content_count;
            }
        }
        
        // Create chart data
        const labels = Object.keys(backends);
        const values = Object.values(backends);
        
        // Create or update chart
        if (contentChart) {
            contentChart.data.labels = labels;
            contentChart.data.datasets[0].data = values;
            contentChart.update();
        } else {
            contentChart = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Content Count',
                        data: values,
                        backgroundColor: labels.map((_, i) => getColor(i, 0.7)),
                        borderColor: labels.map((_, i) => getColor(i, 1)),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'right',
                        },
                        title: {
                            display: true,
                            text: 'Content Distribution'
                        }
                    }
                }
            });
        }
    }
    
    let storageChart = null;
    
    function updateStorageChart(metrics) {
        const canvas = document.getElementById('storage-chart');
        
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Extract storage usage by backend
        const backends = [];
        const used = [];
        const available = [];
        
        for (const backend in metrics.backends) {
            const backendMetrics = metrics.backends[backend];
            
            if (backendMetrics.used !== undefined && backendMetrics.available !== undefined) {
                backends.push(backend);
                used.push(backendMetrics.used);
                available.push(backendMetrics.available);
            }
        }
        
        // Create or update chart
        if (storageChart) {
            storageChart.data.labels = backends;
            storageChart.data.datasets[0].data = used;
            storageChart.data.datasets[1].data = available;
            storageChart.update();
        } else {
            storageChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: backends,
                    datasets: [
                        {
                            label: 'Used',
                            data: used,
                            backgroundColor: 'rgba(255, 99, 132, 0.7)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        },
                        {
                            label: 'Available',
                            data: available,
                            backgroundColor: 'rgba(75, 192, 192, 0.7)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Bytes'
                            },
                            ticks: {
                                callback: function(value) {
                                    return formatBytes(value);
                                }
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Storage Usage'
                        }
                    }
                }
            });
        }
    }
    
    let operationsTimelineChart = null;
    let operationsData = [];
    
    function updateOperationsTimelineChart(metrics) {
        const canvas = document.getElementById('operations-timeline-chart');
        
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Initialize operationsData if empty
        if (operationsData.length === 0) {
            // Create initial data points
            const now = Date.now();
            
            // Create 20 empty data points for the last 10 minutes
            for (let i = 0; i < 20; i++) {
                operationsData.push({
                    timestamp: now - (19 - i) * 30000,  // 30-second intervals
                    operations: {}
                });
            }
        }
        
        // Add new data point
        const now = Date.now();
        
        // Calculate operations count for each backend/operation
        const operations = {};
        
        for (const backend in metrics.performance_metrics) {
            const backendOps = metrics.performance_metrics[backend];
            
            for (const op in backendOps) {
                const key = `${backend}/${op}`;
                operations[key] = backendOps[op].count || 0;
            }
        }
        
        // Add new data point
        operationsData.push({
            timestamp: now,
            operations: operations
        });
        
        // Keep only the last 20 data points
        if (operationsData.length > 20) {
            operationsData.shift();
        }
        
        // Prepare chart data
        const labels = operationsData.map(d => new Date(d.timestamp).toLocaleTimeString());
        
        // Get all operation keys across all data points
        const operationKeys = new Set();
        operationsData.forEach(d => {
            Object.keys(d.operations).forEach(key => operationKeys.add(key));
        });
        
        // Create datasets
        const datasets = Array.from(operationKeys).map((key, index) => {
            const [backend, operation] = key.split('/');
            
            // Get operation count at each timestamp
            // We need to get differences between consecutive data points
            const data = [];
            for (let i = 1; i < operationsData.length; i++) {
                const prev = operationsData[i-1].operations[key] || 0;
                const curr = operationsData[i].operations[key] || 0;
                data.push(curr - prev);
            }
            
            return {
                label: `${backend} - ${operation}`,
                data: data,
                backgroundColor: getColor(index, 0.7),
                borderColor: getColor(index, 1),
                borderWidth: 1
            };
        });
        
        // Create or update chart
        if (operationsTimelineChart) {
            operationsTimelineChart.data.labels = labels.slice(1);  // Skip first label for differences
            operationsTimelineChart.data.datasets = datasets;
            operationsTimelineChart.update();
        } else {
            operationsTimelineChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels.slice(1),  // Skip first label for differences
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Operations per 30s'
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Operations Timeline'
                        }
                    }
                }
            });
        }
    }
    
    let apiRequestsChart = null;
    
    function updateApiRequestsChart(metrics) {
        const canvas = document.getElementById('api-requests-chart');
        
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        // Create chart if it doesn't exist yet
        // (we don't update it here since we would need a timeline of API requests)
        if (!apiRequestsChart) {
            const endpoints = metrics.endpoints || [];
            const requestCounts = metrics.request_counts || {};
            
            const labels = endpoints;
            const data = endpoints.map(endpoint => requestCounts[endpoint] || 0);
            
            apiRequestsChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'API Requests',
                        data: data,
                        backgroundColor: labels.map((_, i) => getColor(i, 0.7)),
                        borderColor: labels.map((_, i) => getColor(i, 1)),
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Request Count'
                            }
                        }
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'API Requests by Endpoint'
                        }
                    }
                }
            });
        }
    }
    
    function getColor(index, alpha) {
        const colors = [
            `rgba(54, 162, 235, ${alpha})`,
            `rgba(255, 99, 132, ${alpha})`,
            `rgba(75, 192, 192, ${alpha})`,
            `rgba(255, 206, 86, ${alpha})`,
            `rgba(153, 102, 255, ${alpha})`,
            `rgba(255, 159, 64, ${alpha})`,
            `rgba(199, 199, 199, ${alpha})`,
        ];
        
        return colors[index % colors.length];
    }
    
    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }
    
    // Initial request for data
    fetch('{{ url_for("dashboard_data") }}')
        .then(response => response.json())
        .then(data => updateMetricsPage(data))
        .catch(error => console.error('Error fetching dashboard data:', error));
</script>
{% endblock %}
"""

        health_template = """{% extends "base.html" %}

{% block title %}Health - MCP Monitoring Dashboard{% endblock %}

{% block content %}
<section class="health-detail">
    <h2>System Health</h2>
    
    <div class="status-summary">
        <div class="status-card large">
            <h3>Overall Status</h3>
            <div class="status-indicator unknown" id="overall-status-indicator">Unknown</div>
            <div id="overall-status-since">Since: --</div>
        </div>
    </div>
    
    <div class="component-cards" id="component-cards">
        <div class="loading">Loading component health...</div>
    </div>
    
    <div class="health-details" id="health-details">
        <h3>Health Check Details</h3>
        <pre id="health-details-pre">Loading health details...</pre>
    </div>
</section>
{% endblock %}

{% block scripts %}
<script>
    // Connect to WebSocket for real-time updates
    const socket = new WebSocket(`ws://${window.location.host}{{ url_for('dashboard_ws') }}`);
    
    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        updateHealthPage(data);
    };
    
    socket.onclose = function(event) {
        console.log('WebSocket connection closed');
        setTimeout(() => {
            location.reload();
        }, 5000);
    };
    
    function updateHealthPage(data) {
        // Update overall status
        if (data.health) {
            updateOverallStatus(data.health);
        }
        
        // Update component cards
        if (data.health && data.health.components) {
            updateComponentCards(data.health.components);
        }
        
        // Update health details
        if (data.health) {
            updateHealthDetails(data.health);
        }
    }
    
    function updateOverallStatus(health) {
        const indicator = document.getElementById('overall-status-indicator');
        const since = document.getElementById('overall-status-since');
        
        if (indicator) {
            // Update status text
            indicator.textContent = health.status || 'unknown';
            
            // Update status class
            indicator.className = 'status-indicator';
            indicator.classList.add(health.status || 'unknown');
            
            // Update since timestamp
            if (health.timestamp) {
                since.textContent = `Since: ${formatTimestamp(health.timestamp)}`;
            }
        }
    }
    
    function updateComponentCards(components) {
        const container = document.getElementById('component-cards');
        
        if (container) {
            container.innerHTML = '';
            
            for (const [component, info] of Object.entries(components)) {
                const card = document.createElement('div');
                card.className = 'component-card';
                
                const status = info.status || 'unknown';
                
                card.innerHTML = `
                    <h3>${capitalizeFirst(component)}</h3>
                    <div class="status-indicator ${status}">${status}</div>
                    <div class="details">
                        <p>Last check: ${formatTimestamp(info.last_check || 0)}</p>
                    </div>
                `;
                
                container.appendChild(card);
            }
        }
    }
    
    function updateHealthDetails(health) {
        const pre = document.getElementById('health-details-pre');
        
        if (pre) {
            pre.textContent = JSON.stringify(health, null, 2);
        }
    }
    
    function capitalizeFirst(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
    
    function formatTimestamp(timestamp) {
        if (!timestamp) return 'Never';
        
        const date = new Date(timestamp * 1000);
        return date.toLocaleString();
    }
    
    // Initial request for data
    fetch('{{ url_for("dashboard_data") }}')
        .then(response => response.json())
        .then(data => updateHealthPage(data))
        .catch(error => console.error('Error fetching dashboard data:', error));
</script>
{% endblock %}
"""

        # Write templates to files
        with open(os.path.join(templates_dir, "base.html"), "w") as f:
            f.write(base_template)
        
        with open(os.path.join(templates_dir, "index.html"), "w") as f:
            f.write(index_template)
            
        with open(os.path.join(templates_dir, "backends.html"), "w") as f:
            f.write(backends_template)
            
        with open(os.path.join(templates_dir, "metrics.html"), "w") as f:
            f.write(metrics_template)
            
        with open(os.path.join(templates_dir, "health.html"), "w") as f:
            f.write(health_template)
            
        logger.info(f"Created default templates in {templates_dir}")
            
    def _create_default_static_files(self, static_dir):
        """Create default static files for the dashboard."""
        # Create CSS directory
        css_dir = os.path.join(static_dir, "css")
        os.makedirs(css_dir, exist_ok=True)
        
        # Create JS directory
        js_dir = os.path.join(static_dir, "js")
        os.makedirs(js_dir, exist_ok=True)
        
        # Create CSS file
        css_content = """/* Dashboard styles */
:root {
    --primary-color: #3498db;
    --secondary-color: #2c3e50;
    --success-color: #2ecc71;
    --warning-color: #f39c12;
    --danger-color: #e74c3c;
    --light-color: #ecf0f1;
    --dark-color: #2c3e50;
    --text-color: #333;
    --background-color: #f8f9fa;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    padding: 0;
    background-color: var(--background-color);
    color: var(--text-color);
}

header {
    background-color: var(--secondary-color);
    color: white;
    padding: 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

header h1 {
    margin: 0;
    font-size: 1.5rem;
}

nav ul {
    list-style: none;
    display: flex;
    margin: 0;
    padding: 0;
}

nav li {
    margin-left: 1rem;
}

nav a {
    color: white;
    text-decoration: none;
    padding: 0.5rem;
}

nav a:hover {
    text-decoration: underline;
}

main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 1rem;
}

section {
    margin-bottom: 2rem;
}

h2 {
    color: var(--secondary-color);
    border-bottom: 1px solid #ccc;
    padding-bottom: 0.5rem;
}

h3 {
    color: var(--secondary-color);
}

.status-cards,
.metrics-cards,
.backends-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
}

.card {
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    padding: 1rem;
}

.status-indicator {
    display: inline-block;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
}

.status-indicator.healthy {
    background-color: var(--success-color);
    color: white;
}

.status-indicator.degraded {
    background-color: var(--warning-color);
    color: white;
}

.status-indicator.unhealthy {
    background-color: var(--danger-color);
    color: white;
}

.status-indicator.unknown {
    background-color: #aaa;
    color: white;
}

.chart-container {
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    padding: 1rem;
    margin-bottom: 1rem;
}

.chart-container.small {
    height: 200px;
}

.resource-meter {
    margin-bottom: 0.5rem;
}

.resource-meter label {
    display: inline-block;
    width: 80px;
    font-weight: bold;
}

.meter {
    height: 1.5rem;
    background-color: #eee;
    border-radius: 0.25rem;
    overflow: hidden;
    display: inline-block;
    width: calc(100% - 85px);
}

.meter-bar {
    height: 100%;
    background-color: var(--primary-color);
    text-align: center;
    line-height: 1.5rem;
    color: white;
    font-weight: bold;
    transition: width 0.3s ease;
}

.meter-bar.normal {
    background-color: var(--success-color);
}

.meter-bar.warning {
    background-color: var(--warning-color);
}

.meter-bar.critical {
    background-color: var(--danger-color);
}

.backend-card,
.backend-detail-card {
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    padding: 1rem;
}

.backends-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
}

.component-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
}

.component-card {
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    padding: 1rem;
}

.status-card.large {
    grid-column: 1 / -1;
    text-align: center;
    padding: 2rem;
}

.status-card.large .status-indicator {
    font-size: 1.5rem;
    padding: 0.5rem 1rem;
}

.health-details {
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    padding: 1rem;
}

.health-details pre {
    overflow: auto;
    max-height: 400px;
    background-color: #f8f9fa;
    padding: 1rem;
    border-radius: 0.25rem;
}

.loading {
    text-align: center;
    padding: 1rem;
    color: #888;
}

footer {
    background-color: var(--secondary-color);
    color: white;
    padding: 1rem;
    text-align: center;
    margin-top: 2rem;
}

@media (max-width: 768px) {
    .status-cards,
    .metrics-cards,
    .backends-grid,
    .component-cards {
        grid-template-columns: 1fr;
    }
    
    header {
        flex-direction: column;
    }
    
    nav ul {
        margin-top: 1rem;
    }
}
"""
        
        with open(os.path.join(css_dir, "styles.css"), "w") as f:
            f.write(css_content)
            
        # Create empty JS file for dashboard custom code
        with open(os.path.join(js_dir, "dashboard.js"), "w") as f:
            f.write("// Custom dashboard JavaScript")
            
        # Download Chart.js for charting
        try:
            import requests
            chart_js_url = "https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"
            response = requests.get(chart_js_url)
            
            if response.status_code == 200:
                with open(os.path.join(js_dir, "chart.min.js"), "w") as f:
                    f.write(response.text)
                    logger.info("Downloaded Chart.js for dashboard")
            else:
                logger.warning(f"Failed to download Chart.js: HTTP {response.status_code}")
                # Create empty file with a warning
                with open(os.path.join(js_dir, "chart.min.js"), "w") as f:
                    f.write("// Failed to download Chart.js\n// Please manually download from https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js")
        except Exception as e:
            logger.warning(f"Failed to download Chart.js: {e}")
            # Create empty file with a warning
            with open(os.path.join(js_dir, "chart.min.js"), "w") as f:
                f.write("// Failed to download Chart.js\n// Please manually download from https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js")
        
        logger.info(f"Created default static files in {static_dir}")
            
    def configure_routes(self, app):
        """
        Configure dashboard routes with the FastAPI app.
        
        Args:
            app: FastAPI app instance
        """
        # Store app reference
        self.app = app
        
        try:
            # Mount static files
            app.mount(f"{self.path_prefix}/static", StaticFiles(directory=self.static_dir), name="static")
            logger.info(f"Mounted static files from {self.static_dir} at {self.path_prefix}/static")
            
            # Add routes
            @app.get(self.path_prefix, response_class=HTMLResponse, name="dashboard_index")
            async def dashboard_index(request: Request):
                """Dashboard index page."""
                return self.templates.TemplateResponse("index.html", {"request": request})
                
            @app.get(f"{self.path_prefix}/backends", response_class=HTMLResponse, name="dashboard_backends")
            async def dashboard_backends(request: Request):
                """Backends page."""
                return self.templates.TemplateResponse("backends.html", {"request": request})
                
            @app.get(f"{self.path_prefix}/metrics", response_class=HTMLResponse, name="dashboard_metrics")
            async def dashboard_metrics(request: Request):
                """Metrics page."""
                return self.templates.TemplateResponse("metrics.html", {"request": request})
                
            @app.get(f"{self.path_prefix}/health", response_class=HTMLResponse, name="dashboard_health")
            async def dashboard_health(request: Request):
                """Health page."""
                return self.templates.TemplateResponse("health.html", {"request": request})
                
            @app.get(f"{self.path_prefix}/data", name="dashboard_data")
            async def dashboard_data():
                """Get dashboard data."""
                return await self._get_dashboard_data()
                
            @app.websocket(f"{self.path_prefix}/ws", name="dashboard_ws")
            async def dashboard_ws(websocket: WebSocket):
                """WebSocket endpoint for real-time updates."""
                await websocket.accept()
                
                # Add to active connections
                with self.connection_lock:
                    self.active_connections.add(websocket)
                
                try:
                    # Start dashboard update thread if not already running
                    if not self.dashboard_running:
                        self.dashboard_running = True
                        self.update_thread = threading.Thread(
                            target=self._run_dashboard_updates,
                            daemon=True
                        )
                        self.update_thread.start()
                        logger.info("Started dashboard update thread")
                    
                    # Send initial data
                    await websocket.send_json(await self._get_dashboard_data())
                    
                    # Keep connection open
                    while True:
                        # This will handle disconnects
                        data = await websocket.receive_text()
                        
                        # Process any received commands
                        if data.startswith('refresh'):
                            await websocket.send_json(await self._get_dashboard_data())
                            
                except WebSocketDisconnect:
                    # Remove from active connections on disconnect
                    with self.connection_lock:
                        self.active_connections.remove(websocket)
                    logger.debug("WebSocket client disconnected")
                    
                except Exception as e:
                    logger.error(f"WebSocket error: {e}")
                    # Try to remove from active connections
                    with self.connection_lock:
                        if websocket in self.active_connections:
                            self.active_connections.remove(websocket)
            
            logger.info(f"Configured dashboard routes at {self.path_prefix}")
            
        except Exception as e:
            logger.error(f"Failed to configure dashboard routes: {e}")
            
    async def _get_dashboard_data(self):
        """
        Get data for the dashboard.
        
        Returns:
            Dictionary with dashboard data
        """
        data = {
            "timestamp": time.time(),
        }
        
        # Get data from monitoring manager
        if self.monitoring_manager:
            try:
                # Get health status
                health_status = self.monitoring_manager.get_health_status()
                data["health"] = health_status
                
                # Get backend status if monitoring system is available
                if hasattr(self.monitoring_manager, "monitoring_system") and self.monitoring_manager.monitoring_system:
                    try:
                        backend_status = self.monitoring_manager.monitoring_system.get_backend_status()
                        data["backends"] = backend_status
                    except Exception as e:
                        logger.error(f"Error getting backend status: {e}")
                        
                    try:
                        metrics = self.monitoring_manager.monitoring_system.get_all_metrics()
                        data["metrics"] = metrics
                    except Exception as e:
                        logger.error(f"Error getting metrics: {e}")
                        
            except Exception as e:
                logger.error(f"Error getting dashboard data from monitoring manager: {e}")
                
        # Fill with sample data for testing if needed
        if self.options.get("use_sample_data", False) and not data.get("backends"):
            data = self._get_sample_data()
            
        return data
        
    def _get_sample_data(self):
        """
        Generate sample data for testing.
        
        Returns:
            Dictionary with sample data
        """
        return {
            "timestamp": time.time(),
            "health": {
                "status": "healthy",
                "components": {
                    "server": {"status": "healthy", "last_check": time.time()},
                    "storage": {"status": "healthy", "last_check": time.time()},
                    "dependencies": {"status": "healthy", "last_check": time.time()},
                    "resources": {
                        "status": "healthy", 
                        "last_check": time.time(),
                        "details": {
                            "cpu": {"percent": 25},
                            "memory": {"percent": 40},
                            "disk": {"percent": 60}
                        }
                    }
                }
            },
            "backends": {
                "overall_status": "healthy",
                "backends": {
                    "ipfs": {"status": "healthy", "last_check": time.time()},
                    "s3": {"status": "healthy", "last_check": time.time()},
                    "filecoin": {"status": "healthy", "last_check": time.time()}
                }
            },
            "metrics": {
                "performance_metrics": {
                    "performance_metrics": {
                        "ipfs": {
                            "store": {"count": 120, "avg_time": 0.5, "success_rate": 0.98},
                            "retrieve": {"count": 250, "avg_time": 0.3, "success_rate": 0.99},
                            "delete": {"count": 30, "avg_time": 0.2, "success_rate": 0.95}
                        },
                        "s3": {
                            "store": {"count": 80, "avg_time": 0.8, "success_rate": 0.99},
                            "retrieve": {"count": 150, "avg_time": 0.4, "success_rate": 1.0},
                            "delete": {"count": 20, "avg_time": 0.3, "success_rate": 0.99}
                        }
                    }
                },
                "capacity_metrics": {
                    "backends": {
                        "ipfs": {"used": 1024*1024*100, "available": 1024*1024*900, "content_count": 250},
                        "s3": {"used": 1024*1024*50, "available": 1024*1024*950, "content_count": 100}
                    }
                }
            },
            "api_metrics": {
                "endpoints": ["/api/v0/storage", "/api/v0/filecoin", "/api/v0/search"],
                "request_counts": {
                    "/api/v0/storage": 150,
                    "/api/v0/filecoin": 75,
                    "/api/v0/search": 100
                }
            }
        }
        
    def _run_dashboard_updates(self):
        """Run continuous dashboard updates for connected clients."""
        logger.info("Starting dashboard update thread")
        
        try:
            while self.dashboard_running:
                try:
                    # Sleep first to avoid duplicate data with initial connection
                    time.sleep(self.metrics_update_interval)
                    
                    if not self.active_connections:
                        continue
                    
                    # Get latest data
                    data = asyncio.run(self._get_dashboard_data())
                    
                    # Send to all connected clients
                    disconnected = set()
                    
                    with self.connection_lock:
                        # Make a copy of active connections to avoid modification during iteration
                        connections = set(self.active_connections)
                    
                    # Send data to each connection
                    for websocket in connections:
                        try:
                            # This will raise an error if the connection is closed
                            # We need to run this in the async event loop
                            asyncio.run(self._send_update(websocket, data))
                        except Exception:
                            # Mark for removal
                            disconnected.add(websocket)
                    
                    # Remove disconnected clients
                    with self.connection_lock:
                        for websocket in disconnected:
                            if websocket in self.active_connections:
                                self.active_connections.remove(websocket)
                                
                except Exception as e:
                    logger.error(f"Error in dashboard update thread: {e}")
                    time.sleep(10)  # Sleep longer on error
                    
        except Exception as e:
            logger.exception(f"Fatal error in dashboard update thread: {e}")
        finally:
            logger.info("Dashboard update thread stopped")
            self.dashboard_running = False
    
    async def _send_update(self, websocket, data):
        """Send update to a websocket client."""
        await websocket.send_json(data)
        
    def stop(self):
        """Stop the dashboard update thread."""
        self.dashboard_running = False
        
        if self.update_thread:
            self.update_thread.join(timeout=5)
            logger.info("Stopped dashboard update thread")
            
        # Close all active connections
        for websocket in list(self.active_connections):
            try:
                # Run in async context
                asyncio.run(websocket.close())
            except Exception:
                pass
            
        self.active_connections.clear()
        logger.info("Closed all WebSocket connections")


def create_dashboard(
    app=None,
    monitoring_manager=None,
    path_prefix="/dashboard",
    options: Optional[Dict[str, Any]] = None,
):
    """
    Create and initialize a monitoring dashboard.
    
    Args:
        app: FastAPI app instance
        monitoring_manager: MonitoringManager instance
        path_prefix: URL path prefix for dashboard routes
        options: Additional configuration options
        
    Returns:
        Configured MonitoringDashboard instance
    """
    try:
        dashboard = MonitoringDashboard(
            app=app,
            monitoring_manager=monitoring_manager,
            path_prefix=path_prefix,
            options=options
        )
        
        logger.info(f"Created monitoring dashboard at {path_prefix}")
        return dashboard
    except ImportError as e:
        logger.warning(f"Failed to create dashboard (missing dependencies): {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to create dashboard: {e}")
        return None