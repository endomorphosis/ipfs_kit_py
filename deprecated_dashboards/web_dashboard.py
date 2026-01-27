"""
Web Dashboard Module

Provides a comprehensive web interface for monitoring IPFS Kit and MCP server
performance, including real-time metrics, health status, and analytics.
"""

import anyio
import json
import logging
import os
import time
import uuid
from typing import Dict, Any, List, Optional, Set
from pathlib import Path

# Web framework imports
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from .config import DashboardConfig
from .data_collector import DataCollector
from .metrics_aggregator import MetricsAggregator

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.debug(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.debug(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, data: Dict[str, Any]):
        """Broadcast data to all connected clients."""
        if not self.active_connections:
            return
        
        message = json.dumps(data)
        disconnected = set()
        
        for websocket in self.active_connections.copy():
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.debug(f"Failed to send WebSocket message: {e}")
                disconnected.add(websocket)
        
        # Remove disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)


class WebDashboard:
    """
    Web dashboard for IPFS Kit monitoring and analytics.
    
    Provides a comprehensive web interface that displays:
    - Real-time metrics and performance data
    - System health status and alerts
    - Virtual filesystem analytics
    - MCP server performance
    - Interactive charts and visualizations
    """
    
    def __init__(self, config: DashboardConfig):
        """Initialize the web dashboard."""
        if not WEB_FRAMEWORK_AVAILABLE:
            raise ImportError("FastAPI and uvicorn are required for the web dashboard")
        
        self.config = config
        self.app = FastAPI(
            title="IPFS Kit Dashboard",
            description="Monitoring and analytics dashboard for IPFS Kit",
            version="1.0.0"
        )
        
        # Initialize components
        self.data_collector = DataCollector(config)
        self.metrics_aggregator = MetricsAggregator(config, self.data_collector)
        self.websocket_manager = WebSocketManager()
        
        # Dashboard state
        self.is_running = False
        self.update_task = None
        
        # Setup web application
        self._setup_middleware()
        self._setup_static_files()
        self._setup_templates()
        self._setup_routes()
        
        logger.info("Web dashboard initialized")
    
    def _setup_middleware(self):
        """Setup middleware for the web application."""
        # CORS middleware for cross-origin requests
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # In production, specify allowed origins
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    
    def _setup_static_files(self):
        """Setup static file serving."""
        # Create static files directory if it doesn't exist
        static_dir = Path(__file__).parent / "static"
        static_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (static_dir / "css").mkdir(exist_ok=True)
        (static_dir / "js").mkdir(exist_ok=True)
        (static_dir / "images").mkdir(exist_ok=True)
        
        # Create basic CSS if it doesn't exist
        css_file = static_dir / "css" / "dashboard.css"
        if not css_file.exists():
            self._create_default_css(css_file)
        
        # Create basic JavaScript if it doesn't exist
        js_file = static_dir / "js" / "dashboard.js"
        if not js_file.exists():
            self._create_default_js(js_file)
        
        # Mount static files
        self.app.mount(
            self.config.static_path,
            StaticFiles(directory=str(static_dir)),
            name="static"
        )
        
        logger.info(f"Static files mounted at {self.config.static_path}")
    
    def _setup_templates(self):
        """Setup Jinja2 templates."""
        templates_dir = Path(__file__).parent / "templates"
        templates_dir.mkdir(exist_ok=True)
        
        # Create default templates if they don't exist
        if not (templates_dir / "index.html").exists():
            self._create_default_templates(templates_dir)
        
        self.templates = Jinja2Templates(directory=str(templates_dir))
        logger.info(f"Templates configured from {templates_dir}")
    
    def _setup_routes(self):
        """Setup web application routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Dashboard home page redirect."""
            return self.templates.TemplateResponse("redirect.html", {
                "request": request,
                "dashboard_url": self.config.dashboard_path
            })
        
        @self.app.get(self.config.dashboard_path, response_class=HTMLResponse)
        async def dashboard_index(request: Request):
            """Main dashboard page."""
            return self.templates.TemplateResponse("index.html", {
                "request": request,
                "config": self.config.to_dict()
            })
        
        @self.app.get(f"{self.config.dashboard_path}/metrics", response_class=HTMLResponse)
        async def dashboard_metrics(request: Request):
            """Metrics page."""
            return self.templates.TemplateResponse("metrics.html", {
                "request": request,
                "config": self.config.to_dict()
            })
        
        @self.app.get(f"{self.config.dashboard_path}/health", response_class=HTMLResponse)
        async def dashboard_health(request: Request):
            """Health status page."""
            return self.templates.TemplateResponse("health.html", {
                "request": request,
                "config": self.config.to_dict()
            })
        
        @self.app.get(f"{self.config.dashboard_path}/vfs", response_class=HTMLResponse)
        async def dashboard_vfs(request: Request):
            """Virtual filesystem analytics page."""
            return self.templates.TemplateResponse("vfs.html", {
                "request": request,
            "config": self.config.to_dict()
        })
        
        @self.app.get(f"{self.config.dashboard_path}/file_manager", response_class=HTMLResponse)
        async def dashboard_file_manager(request: Request):
            """File manager page."""
            return self.templates.TemplateResponse("file_manager.html", {
                "request": request,
                "config": self.config.to_dict()
            })

        @self.app.get(f"{self.config.api_path}/summary")
        async def api_summary():
            """Get dashboard summary data."""
            self.metrics_aggregator.update_aggregations()
            return self.metrics_aggregator.get_dashboard_summary()
        
        @self.app.get(f"{self.config.api_path}/metrics")
        async def api_metrics():
            """Get all metrics data."""
            metrics = self.data_collector.get_latest_values()
            aggregated = {
                name: metric.to_dict() 
                for name, metric in self.metrics_aggregator.get_aggregated_metrics().items()
            }
            return {
                "latest_values": metrics,
                "aggregated_metrics": aggregated,
                "collection_summary": self.data_collector.get_metric_summary()
            }
        
        @self.app.get(f"{self.config.api_path}/health")
        async def api_health():
            """Get health status."""
            self.metrics_aggregator.update_aggregations()
            health_status = self.metrics_aggregator.get_health_status()
            active_alerts, alert_history = self.metrics_aggregator.get_alerts()
            
            return {
                "health_status": health_status.to_dict(),
                "active_alerts": [alert.to_dict() for alert in active_alerts],
                "alert_history": [alert.to_dict() for alert in alert_history[-10:]]  # Last 10 alerts
            }
        
        @self.app.get(f"{self.config.api_path}/analytics")
        async def api_analytics():
            """Get performance and VFS analytics."""
            self.metrics_aggregator.update_aggregations()
            return {
                "performance_analytics": self.metrics_aggregator.get_performance_analytics(),
                "vfs_analytics": self.metrics_aggregator.get_vfs_analytics()
            }
        
        @self.app.post(f"{self.config.api_path}/alerts/{{alert_id}}/acknowledge")
        async def api_acknowledge_alert(alert_id: str):
            """Acknowledge an alert."""
            success = self.metrics_aggregator.acknowledge_alert(alert_id)
            if success:
                return {"status": "acknowledged", "alert_id": alert_id}
            else:
                raise HTTPException(status_code=404, detail="Alert not found")
        
        @self.app.websocket(f"{self.config.dashboard_path}/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates."""
            await self.websocket_manager.connect(websocket)
            
            try:
                # Send initial data
                await self._send_websocket_update(websocket)
                
                # Keep connection alive
                while True:
                    # Wait for client messages (like ping/pong)
                    try:
                        with anyio.fail_after(30.0):
                            data = await websocket.receive_text()
                        
                        # Handle client requests
                        if data == "get_update":
                            await self._send_websocket_update(websocket)
                        
                    except TimeoutError:
                        # Send periodic update
                        await self._send_websocket_update(websocket)
                    
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                self.websocket_manager.disconnect(websocket)
        
        logger.info("Dashboard routes configured")
    
    async def _send_websocket_update(self, websocket: WebSocket):
        """Send update data to a specific WebSocket."""
        try:
            self.metrics_aggregator.update_aggregations()
            data = {
                "timestamp": time.time(),
                "summary": self.metrics_aggregator.get_dashboard_summary(),
                "latest_metrics": self.data_collector.get_latest_values()
            }
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            logger.debug(f"Failed to send WebSocket update: {e}")
    
    def _create_default_css(self, css_file: Path):
        """Create default CSS file."""
        css_content = """
/* IPFS Kit Dashboard Styles */

:root {
    --primary-color: #2563eb;
    --secondary-color: #1f2937;
    --success-color: #10b981;
    --warning-color: #f59e0b;
    --danger-color: #ef4444;
    --light-color: #f9fafb;
    --dark-color: #111827;
    --text-color: #374151;
    --border-color: #d1d5db;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: var(--light-color);
    color: var(--text-color);
    line-height: 1.6;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

header {
    background-color: var(--secondary-color);
    color: white;
    padding: 1rem 0;
    margin-bottom: 2rem;
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
}

.logo h1 {
    font-size: 1.5rem;
    font-weight: 600;
}

nav ul {
    display: flex;
    list-style: none;
    gap: 2rem;
}

nav a {
    color: white;
    text-decoration: none;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    transition: background-color 0.2s;
}

nav a:hover {
    background-color: rgba(255, 255, 255, 0.1);
}

.grid {
    display: grid;
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.grid-cols-1 { grid-template-columns: 1fr; }
.grid-cols-2 { grid-template-columns: repeat(2, 1fr); }
.grid-cols-3 { grid-template-columns: repeat(3, 1fr); }
.grid-cols-4 { grid-template-columns: repeat(4, 1fr); }

@media (max-width: 768px) {
    .grid-cols-2,
    .grid-cols-3,
    .grid-cols-4 {
        grid-template-columns: 1fr;
    }
}

.card {
    background: white;
    border-radius: 0.5rem;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    border: 1px solid var(--border-color);
}

.card h3 {
    font-size: 1.125rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--secondary-color);
}

.metric-value {
    font-size: 2rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
}

.metric-label {
    font-size: 0.875rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.status-indicator {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.status-healthy {
    background-color: #dcfce7;
    color: #166534;
}

.status-warning {
    background-color: #fef3c7;
    color: #92400e;
}

.status-critical {
    background-color: #fee2e2;
    color: #991b1b;
}

.progress-bar {
    width: 100%;
    height: 0.5rem;
    background-color: #e5e7eb;
    border-radius: 0.25rem;
    overflow: hidden;
    margin: 0.5rem 0;
}

.progress-fill {
    height: 100%;
    background-color: var(--primary-color);
    border-radius: 0.25rem;
    transition: width 0.3s ease;
}

.progress-fill.warning {
    background-color: var(--warning-color);
}

.progress-fill.danger {
    background-color: var(--danger-color);
}

.chart-container {
    width: 100%;
    height: 300px;
    margin-top: 1rem;
}

.alert {
    padding: 1rem;
    border-radius: 0.375rem;
    margin-bottom: 1rem;
    border-left: 4px solid;
}

.alert-info {
    background-color: #dbeafe;
    border-color: var(--primary-color);
    color: #1e40af;
}

.alert-warning {
    background-color: #fef3c7;
    border-color: var(--warning-color);
    color: #92400e;
}

.alert-critical {
    background-color: #fee2e2;
    border-color: var(--danger-color);
    color: #991b1b;
}

.btn {
    display: inline-block;
    padding: 0.5rem 1rem;
    border-radius: 0.375rem;
    text-decoration: none;
    border: none;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    transition: all 0.2s;
}

.btn-primary {
    background-color: var(--primary-color);
    color: white;
}

.btn-primary:hover {
    background-color: #1d4ed8;
}

.loading {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid #f3f3f3;
    border-top: 3px solid var(--primary-color);
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

.hidden {
    display: none;
}

.text-center {
    text-align: center;
}

.mt-4 { margin-top: 1rem; }
.mb-4 { margin-bottom: 1rem; }
.ml-2 { margin-left: 0.5rem; }
.mr-2 { margin-right: 0.5rem; }
"""
        css_file.write_text(css_content)
        logger.info(f"Created default CSS file: {css_file}")
    
    def _create_default_js(self, js_file: Path):
        """Create default JavaScript file."""
        js_content = """
// IPFS Kit Dashboard JavaScript

class Dashboard {
    constructor() {
        this.websocket = null;
        this.charts = {};
        this.updateInterval = 30000; // 30 seconds
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }
    
    init() {
        console.log('Initializing IPFS Kit Dashboard');
        
        // Initialize WebSocket connection
        this.connectWebSocket();
        
        // Initialize charts if Chart.js is available
        if (typeof Chart !== 'undefined') {
            this.initializeCharts();
        }
        
        // Set up periodic updates as fallback
        setInterval(() => {
            this.fetchData();
        }, this.updateInterval);
        
        // Initial data fetch
        this.fetchData();
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/dashboard/ws`;
        
        console.log(`Connecting to WebSocket: ${wsUrl}`);
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = (event) => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.updateConnectionStatus(true);
        };
        
        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.updateDashboard(data);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        this.websocket.onclose = (event) => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
            this.scheduleReconnect();
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
            
            console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, delay);
        }
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.querySelector('.connection-status');
        if (statusElement) {
            statusElement.textContent = connected ? 'Connected' : 'Disconnected';
            statusElement.className = `connection-status ${connected ? 'connected' : 'disconnected'}`;
        }
    }
    
    async fetchData() {
        try {
            const [summaryResponse, metricsResponse, healthResponse] = await Promise.all([
                fetch('/dashboard/api/summary'),
                fetch('/dashboard/api/metrics'),
                fetch('/dashboard/api/health')
            ]);
            
            const [summary, metrics, health] = await Promise.all([
                summaryResponse.json(),
                metricsResponse.json(),
                healthResponse.json()
            ]);
            
            this.updateDashboard({
                timestamp: Date.now() / 1000,
                summary,
                latest_metrics: metrics.latest_values,
                health_status: health.health_status,
                active_alerts: health.active_alerts
            });
            
        } catch (error) {
            console.error('Error fetching data:', error);
        }
    }
    
    updateDashboard(data) {
        console.log('Updating dashboard with data:', data);
        
        // Update timestamp
        this.updateTimestamp(data.timestamp);
        
        // Update summary cards
        if (data.summary) {
            this.updateSummaryCards(data.summary);
        }
        
        // Update metrics
        if (data.latest_metrics) {
            this.updateMetrics(data.latest_metrics);
        }
        
        // Update health status
        if (data.health_status) {
            this.updateHealthStatus(data.health_status);
        }
        
        // Update alerts
        if (data.active_alerts) {
            this.updateAlerts(data.active_alerts);
        }
        
        // Update charts
        this.updateCharts(data);
    }
    
    updateTimestamp(timestamp) {
        const elements = document.querySelectorAll('.last-updated');
        const timeString = new Date(timestamp * 1000).toLocaleString();
        
        elements.forEach(element => {
            element.textContent = `Last updated: ${timeString}`;
        });
    }
    
    updateSummaryCards(summary) {
        // Health status
        const healthElement = document.querySelector('.health-status');
        if (healthElement && summary.health_status) {
            const status = summary.health_status.status;
            const score = summary.health_status.score;
            
            healthElement.innerHTML = `
                <div class="status-indicator status-${status}">${status}</div>
                <div class="metric-value">${score.toFixed(1)}%</div>
                <div class="metric-label">Health Score</div>
            `;
        }
        
        // Performance analytics
        if (summary.performance_analytics) {
            this.updatePerformanceCards(summary.performance_analytics);
        }
        
        // VFS analytics
        if (summary.vfs_analytics) {
            this.updateVFSCards(summary.vfs_analytics);
        }
    }
    
    updatePerformanceCards(analytics) {
        // MCP server performance
        if (analytics.mcp_server) {
            const mcpElement = document.querySelector('.mcp-performance');
            if (mcpElement) {
                const totalOps = analytics.mcp_server.total_operations || 0;
                const avgResponseTime = analytics.mcp_server.avg_response_time || 0;
                const successRate = analytics.mcp_server.avg_success_rate || 0;
                
                mcpElement.innerHTML = `
                    <h3>MCP Server</h3>
                    <div class="metric-value">${totalOps.toLocaleString()}</div>
                    <div class="metric-label">Total Operations</div>
                    <div class="mt-2">
                        <div>Avg Response: ${(avgResponseTime * 1000).toFixed(1)}ms</div>
                        <div>Success Rate: ${(successRate * 100).toFixed(1)}%</div>
                    </div>
                `;
            }
        }
        
        // System performance
        if (analytics.system) {
            const systemElement = document.querySelector('.system-performance');
            if (systemElement) {
                const cpuUsage = analytics.system.cpu_usage || 0;
                const memoryUsage = analytics.system.memory_usage || 0;
                const diskUsage = analytics.system.disk_usage || 0;
                
                systemElement.innerHTML = `
                    <h3>System Resources</h3>
                    <div class="resource-meter">
                        <label>CPU: ${cpuUsage.toFixed(1)}%</label>
                        <div class="progress-bar">
                            <div class="progress-fill ${cpuUsage > 80 ? 'danger' : cpuUsage > 60 ? 'warning' : ''}" 
                                 style="width: ${cpuUsage}%"></div>
                        </div>
                    </div>
                    <div class="resource-meter">
                        <label>Memory: ${memoryUsage.toFixed(1)}%</label>
                        <div class="progress-bar">
                            <div class="progress-fill ${memoryUsage > 90 ? 'danger' : memoryUsage > 75 ? 'warning' : ''}" 
                                 style="width: ${memoryUsage}%"></div>
                        </div>
                    </div>
                    <div class="resource-meter">
                        <label>Disk: ${diskUsage.toFixed(1)}%</label>
                        <div class="progress-bar">
                            <div class="progress-fill ${diskUsage > 95 ? 'danger' : diskUsage > 85 ? 'warning' : ''}" 
                                 style="width: ${diskUsage}%"></div>
                        </div>
                    </div>
                `;
            }
        }
    }
    
    updateVFSCards(analytics) {
        const vfsElement = document.querySelector('.vfs-analytics');
        if (vfsElement) {
            const totalOps = analytics.total_operations || 0;
            const cacheEffectiveness = analytics.cache_effectiveness || 0;
            const readRatio = analytics.read_ratio || 0;
            const writeRatio = analytics.write_ratio || 0;
            
            vfsElement.innerHTML = `
                <h3>Virtual Filesystem</h3>
                <div class="metric-value">${totalOps.toLocaleString()}</div>
                <div class="metric-label">Total Operations</div>
                <div class="mt-2">
                    <div>Cache Hit Rate: ${(cacheEffectiveness * 100).toFixed(1)}%</div>
                    <div>Read/Write Ratio: ${(readRatio * 100).toFixed(0)}%/${(writeRatio * 100).toFixed(0)}%</div>
                </div>
            `;
        }
    }
    
    updateMetrics(metrics) {
        // Update individual metric displays
        for (const [metricName, metricData] of Object.entries(metrics)) {
            const element = document.querySelector(`[data-metric="${metricName}"]`);
            if (element) {
                element.textContent = this.formatMetricValue(metricData.value);
            }
        }
    }
    
    updateHealthStatus(healthStatus) {
        const element = document.querySelector('.overall-health-status');
        if (element) {
            element.innerHTML = `
                <div class="status-indicator status-${healthStatus.status}">${healthStatus.status}</div>
                <div class="metric-value">${healthStatus.score.toFixed(1)}%</div>
                <div class="metric-label">Health Score</div>
            `;
        }
        
        // Update issues list
        const issuesElement = document.querySelector('.health-issues');
        if (issuesElement && healthStatus.issues) {
            issuesElement.innerHTML = healthStatus.issues.length > 0
                ? healthStatus.issues.map(issue => `<li>${issue}</li>`).join('')
                : '<li>No issues detected</li>';
        }
    }
    
    updateAlerts(alerts) {
        const alertsContainer = document.querySelector('.alerts-container');
        if (!alertsContainer) return;
        
        if (alerts.length === 0) {
            alertsContainer.innerHTML = '<div class="text-center">No active alerts</div>';
            return;
        }
        
        alertsContainer.innerHTML = alerts.map(alert => `
            <div class="alert alert-${alert.level}" data-alert-id="${alert.id}">
                <div class="alert-header">
                    <strong>${alert.title}</strong>
                    <button class="btn btn-sm" onclick="dashboard.acknowledgeAlert('${alert.id}')">
                        Acknowledge
                    </button>
                </div>
                <div>${alert.message}</div>
                <div class="alert-meta">
                    <small>Metric: ${alert.metric_name} | Value: ${alert.current_value.toFixed(2)} | Threshold: ${alert.threshold}</small>
                </div>
            </div>
        `).join('');
    }
    
    async acknowledgeAlert(alertId) {
        try {
            const response = await fetch(`/dashboard/api/alerts/${alertId}/acknowledge`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const alertElement = document.querySelector(`[data-alert-id="${alertId}"]`);
                if (alertElement) {
                    alertElement.style.opacity = '0.5';
                    setTimeout(() => {
                        alertElement.remove();
                    }, 1000);
                }
            }
        } catch (error) {
            console.error('Error acknowledging alert:', error);
        }
    }
    
    initializeCharts() {
        // Initialize charts if containers exist
        this.initMetricsChart();
        this.initPerformanceChart();
        this.initSystemChart();
    }
    
    initMetricsChart() {
        const ctx = document.getElementById('metricsChart');
        if (!ctx) return;
        
        this.charts.metrics = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Operations/sec',
                    data: [],
                    borderColor: 'rgb(37, 99, 235)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
    
    initPerformanceChart() {
        const ctx = document.getElementById('performanceChart');
        if (!ctx) return;
        
        this.charts.performance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['IPFS', 'S3', 'Filecoin'],
                datasets: [{
                    label: 'Response Time (ms)',
                    data: [0, 0, 0],
                    backgroundColor: ['rgb(16, 185, 129)', 'rgb(245, 158, 11)', 'rgb(99, 102, 241)']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
    
    initSystemChart() {
        const ctx = document.getElementById('systemChart');
        if (!ctx) return;
        
        this.charts.system = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['CPU', 'Memory', 'Disk'],
                datasets: [{
                    data: [0, 0, 0],
                    backgroundColor: ['rgb(239, 68, 68)', 'rgb(245, 158, 11)', 'rgb(37, 99, 235)']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    }
    
    updateCharts(data) {
        // Update charts with new data
        if (data.latest_metrics && this.charts.system) {
            const cpuUsage = data.latest_metrics['system_cpu_usage_percent']?.value || 0;
            const memoryUsage = data.latest_metrics['system_memory_usage_percent']?.value || 0;
            const diskUsage = data.latest_metrics['system_disk_usage_percent']?.value || 0;
            
            this.charts.system.data.datasets[0].data = [cpuUsage, memoryUsage, diskUsage];
            this.charts.system.update();
        }
    }
    
    formatMetricValue(value) {
        if (typeof value === 'number') {
            if (value > 1000000) {
                return (value / 1000000).toFixed(1) + 'M';
            } else if (value > 1000) {
                return (value / 1000).toFixed(1) + 'K';
            } else {
                return value.toFixed(2);
            }
        }
        return value;
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
"""
        js_file.write_text(js_content)
        logger.info(f"Created default JavaScript file: {js_file}")
    
    def _create_default_templates(self, templates_dir: Path):
        """Create default HTML templates."""
        # Base template
        base_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}IPFS Kit Dashboard{% endblock %}</title>
    <link rel="stylesheet" href="{{ config.static_path }}/css/dashboard.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    {% block head %}{% endblock %}
</head>
<body>
    <header>
        <div class="header-content">
            <div class="logo">
                <h1>IPFS Kit Dashboard</h1>
            </div>
            <nav>
                <ul>
                    <li><a href="{{ config.dashboard_path }}">Overview</a></li>
                    <li><a href="{{ config.dashboard_path }}/metrics">Metrics</a></li>
                    <li><a href="{{ config.dashboard_path }}/health">Health</a></li>
                    <li><a href="{{ config.dashboard_path }}/vfs">VFS Analytics</a></li>
                </ul>
            </nav>
        </div>
    </header>
    
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    
    <script src="{{ config.static_path }}/js/dashboard.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>"""
        
        # Index template
        index_template = """{% extends "base.html" %}

{% block title %}IPFS Kit Dashboard - Overview{% endblock %}

{% block content %}
<div class="grid grid-cols-4">
    <div class="card health-status">
        <h3>System Health</h3>
        <div class="loading" id="health-loading"></div>
        <div class="hidden" id="health-content">
            <div class="status-indicator">Loading...</div>
            <div class="metric-value">--%</div>
            <div class="metric-label">Health Score</div>
        </div>
    </div>
    
    <div class="card mcp-performance">
        <h3>MCP Server</h3>
        <div class="loading"></div>
    </div>
    
    <div class="card system-performance">
        <h3>System Resources</h3>
        <div class="loading"></div>
    </div>
    
    <div class="card vfs-analytics">
        <h3>Virtual Filesystem</h3>
        <div class="loading"></div>
    </div>
</div>

<div class="grid grid-cols-2">
    <div class="card">
        <h3>Performance Metrics</h3>
        <div class="chart-container">
            <canvas id="performanceChart"></canvas>
        </div>
    </div>
    
    <div class="card">
        <h3>System Usage</h3>
        <div class="chart-container">
            <canvas id="systemChart"></canvas>
        </div>
    </div>
</div>

<div class="card">
    <h3>Active Alerts</h3>
    <div class="alerts-container">
        <div class="loading"></div>
    </div>
</div>

<div class="text-center mt-4">
    <span class="last-updated">Loading...</span>
    <span class="connection-status ml-2">Connecting...</span>
</div>
{% endblock %}"""
        
        # Metrics template
        metrics_template = """{% extends "base.html" %}

{% block title %}IPFS Kit Dashboard - Metrics{% endblock %}

{% block content %}
<div class="card">
    <h3>Real-time Metrics</h3>
    <div class="chart-container">
        <canvas id="metricsChart"></canvas>
    </div>
</div>

<div class="grid grid-cols-3">
    <div class="card">
        <h3>MCP Operations</h3>
        <div class="metric-value" data-metric="mcp_operations_total">--</div>
        <div class="metric-label">Total Operations</div>
    </div>
    
    <div class="card">
        <h3>Cache Hit Rate</h3>
        <div class="metric-value" data-metric="ipfs_cache_hit_ratio">--%</div>
        <div class="metric-label">Cache Effectiveness</div>
    </div>
    
    <div class="card">
        <h3>VFS Operations</h3>
        <div class="metric-value" data-metric="ipfs_vfs_operations_total">--</div>
        <div class="metric-label">Filesystem Operations</div>
    </div>
</div>

<div class="text-center mt-4">
    <span class="last-updated">Loading...</span>
</div>
{% endblock %}"""
        
        # Health template
        health_template = """{% extends "base.html" %}

{% block title %}IPFS Kit Dashboard - Health{% endblock %}

{% block content %}
<div class="card">
    <h3>Overall Health Status</h3>
    <div class="overall-health-status">
        <div class="loading"></div>
    </div>
</div>

<div class="grid grid-cols-2">
    <div class="card">
        <h3>System Issues</h3>
        <ul class="health-issues">
            <li class="loading">Loading...</li>
        </ul>
    </div>
    
    <div class="card">
        <h3>Active Alerts</h3>
        <div class="alerts-container">
            <div class="loading"></div>
        </div>
    </div>
</div>

<div class="text-center mt-4">
    <span class="last-updated">Loading...</span>
</div>
{% endblock %}"""
        
        # VFS template
        vfs_template = """{% extends "base.html" %}

{% block title %}IPFS Kit Dashboard - VFS Analytics{% endblock %}

{% block content %}
<div class="grid grid-cols-3">
    <div class="card">
        <h3>Total Operations</h3>
        <div class="metric-value" data-metric="vfs_total_operations">--</div>
        <div class="metric-label">VFS Operations</div>
    </div>
    
    <div class="card">
        <h3>Read Operations</h3>
        <div class="metric-value" data-metric="vfs_read_operations">--</div>
        <div class="metric-label">Read Requests</div>
    </div>
    
    <div class="card">
        <h3>Write Operations</h3>
        <div class="metric-value" data-metric="vfs_write_operations">--</div>
        <div class="metric-label">Write Requests</div>
    </div>
</div>

<div class="card">
    <h3>Virtual Filesystem Performance</h3>
    <div class="chart-container">
        <canvas id="vfsChart"></canvas>
    </div>
</div>

<div class="text-center mt-4">
    <span class="last-updated">Loading...</span>
</div>
{% endblock %}"""
        
        # Redirect template
        redirect_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IPFS Kit Dashboard</title>
    <meta http-equiv="refresh" content="0; url={{ dashboard_url }}">
</head>
<body>
    <p>Redirecting to <a href="{{ dashboard_url }}">IPFS Kit Dashboard</a>...</p>
</body>
</html>"""
        
        # Write templates
        (templates_dir / "base.html").write_text(base_template)
        (templates_dir / "index.html").write_text(index_template)
        (templates_dir / "metrics.html").write_text(metrics_template)
        (templates_dir / "health.html").write_text(health_template)
        (templates_dir / "vfs.html").write_text(vfs_template)
        (templates_dir / "redirect.html").write_text(redirect_template)
        
        logger.info(f"Created default templates in {templates_dir}")
    
    async def start(self, host: Optional[str] = None, port: Optional[int] = None):
        """Start the web dashboard server."""
        if self.is_running:
            logger.warning("Dashboard is already running")
            return
        
        # Start data collection
        await self.data_collector.start()
        
        # Start periodic metric aggregation
        self.update_task = anyio.lowlevel.spawn_system_task(self._update_metrics_loop)
        
        # Configure server
        server_host = host or self.config.host
        server_port = port or self.config.port
        
        logger.info(f"Starting dashboard web server on {server_host}:{server_port}")
        
        # Run the server
        self.is_running = True
        config = uvicorn.Config(
            self.app,
            host=server_host,
            port=server_port,
            log_level="info" if self.config.debug else "warning"
        )
        server = uvicorn.Server(config)
        
        try:
            await server.serve()
        except Exception as e:
            logger.error(f"Dashboard server error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the web dashboard server."""
        if not self.is_running:
            return
        
        logger.info("Stopping dashboard web server")
        self.is_running = False
        
        # Stop update task
        if self.update_task:
            self.update_task.cancel()
            try:
                await self.update_task
            except anyio.get_cancelled_exc_class():
                pass
        
        # Stop data collection
        await self.data_collector.stop()
        
        logger.info("Dashboard stopped")
    
    async def _update_metrics_loop(self):
        """Periodic metrics update loop."""
        try:
            while self.is_running:
                # Update aggregations
                self.metrics_aggregator.update_aggregations()
                
                # Broadcast to WebSocket clients
                summary = self.metrics_aggregator.get_dashboard_summary()
                await self.websocket_manager.broadcast({
                    "timestamp": time.time(),
                    "summary": summary,
                    "latest_metrics": self.data_collector.get_latest_values()
                })
                
                # Wait for next update
                await anyio.sleep(self.config.metrics_update_interval)
                
        except anyio.get_cancelled_exc_class():
            logger.info("Metrics update loop cancelled")
        except Exception as e:
            logger.exception(f"Error in metrics update loop: {e}")


def create_dashboard(config: DashboardConfig) -> WebDashboard:
    """Create a dashboard instance."""
    return WebDashboard(config)


async def run_dashboard(config: DashboardConfig):
    """Run the dashboard server."""
    dashboard = create_dashboard(config)
    await dashboard.start()
