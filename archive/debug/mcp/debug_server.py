#!/usr/bin/env python3
"""
MCP Debug Server

This server provides a websocket interface for real-time monitoring of threads
and performance metrics during the test execution.

Features:
1. Real-time thread monitoring dashboard
2. Websocket API for live updates
3. HTTP API endpoints for metrics collection

Run with:
    python mcp/debug_server.py --port 8765
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
import webbrowser
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
from urllib.parse import parse_qs, urlparse

# Ensure ipfs_kit_py is in the path
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
sys.path.insert(0, parent_dir)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(script_dir, 'mcp_debug_server.log'))
    ]
)
logger = logging.getLogger('mcp_debug_server')

# Global state
debug_data = {
    "threads": {},
    "metrics": {
        "cache_hits": 0,
        "cache_misses": 0,
        "prefetch_errors": 0,
        "batch_times": [],
        "queue_full_events": 0,
        "worker_exceptions": 0
    },
    "system": {
        "cpu_usage": 0,
        "memory_usage": 0,
    },
    "clients": [],
    "test_status": "idle",
    "start_time": None,
    "last_update": time.time()
}

# Lock for thread-safe updates
state_lock = threading.Lock()

def update_thread_info(thread_id, info):
    with state_lock:
        debug_data["threads"][thread_id] = info
        debug_data["last_update"] = time.time()

def update_metrics(metrics_data):
    with state_lock:
        for key, value in metrics_data.items():
            if key in debug_data["metrics"]:
                if isinstance(value, list):
                    debug_data["metrics"][key].extend(value)
                else:
                    debug_data["metrics"][key] = value
        debug_data["last_update"] = time.time()

def update_system_info():
    """Update system information (CPU, memory usage)"""
    try:
        import psutil
        with state_lock:
            debug_data["system"]["cpu_usage"] = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            debug_data["system"]["memory_usage"] = mem.percent
            debug_data["system"]["memory_available_mb"] = mem.available / (1024 * 1024)
    except ImportError:
        logger.warning("psutil not available, system metrics disabled")
    except Exception as e:
        logger.error(f"Error updating system info: {e}")

def update_test_status(status):
    with state_lock:
        debug_data["test_status"] = status
        if status == "running":
            debug_data["start_time"] = time.time()
        debug_data["last_update"] = time.time()

# HTML Template for the dashboard
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Debug Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1, h2 {
            color: #333;
        }
        .card {
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            padding: 15px;
            margin-bottom: 20px;
        }
        .status {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 15px;
            font-weight: bold;
        }
        .status.idle { background-color: #ccc; }
        .status.running { background-color: #4CAF50; color: white; }
        .status.error { background-color: #f44336; color: white; }
        .status.complete { background-color: #2196F3; color: white; }
        .thread {
            margin-bottom: 10px;
            padding: 10px;
            border-left: 3px solid #2196F3;
            background-color: #f9f9f9;
        }
        .thread-name {
            font-weight: bold;
        }
        .thread.active {
            border-left-color: #4CAF50;
        }
        .thread.error {
            border-left-color: #f44336;
        }
        .thread.stopped {
            border-left-color: #ccc;
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 10px;
        }
        .metric {
            background-color: #f9f9f9;
            padding: 10px;
            border-radius: 5px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #2196F3;
        }
        .chart-container {
            height: 200px;
            margin-top: 20px;
        }
        #refresh-rate {
            margin-bottom: 20px;
        }
        #status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: red;
            margin-right: 5px;
        }
        #status-indicator.connected {
            background-color: green;
        }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container">
        <h1>MCP Debug Dashboard</h1>
        <div class="card">
            <div>
                <span id="status-indicator"></span>
                Connection Status: <span id="connection-status">Disconnected</span>
            </div>
            <div>
                Refresh Rate: 
                <select id="refresh-rate">
                    <option value="500">0.5s</option>
                    <option value="1000" selected>1s</option>
                    <option value="3000">3s</option>
                    <option value="5000">5s</option>
                </select>
            </div>
        </div>
        
        <div class="card">
            <h2>Test Status: <span class="status idle" id="test-status">idle</span></h2>
            <div id="test-info">
                <p>Start time: <span id="start-time">-</span></p>
                <p>Duration: <span id="duration">-</span></p>
            </div>
        </div>
        
        <div class="card">
            <h2>Performance Metrics</h2>
            <div class="metrics" id="metrics">
                <!-- Metrics will be added here dynamically -->
            </div>
            <div class="chart-container">
                <canvas id="batch-times-chart"></canvas>
            </div>
        </div>
        
        <div class="card">
            <h2>System Information</h2>
            <div class="metrics" id="system-metrics">
                <!-- System metrics will be added here -->
            </div>
        </div>
        
        <div class="card">
            <h2>Thread Information</h2>
            <div id="thread-container">
                <!-- Thread info will be added here dynamically -->
            </div>
        </div>
    </div>

    <script>
        let ws;
        let connected = false;
        let refreshInterval = 1000;
        let chart;
        let lastData = null;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log('WebSocket connected');
                connected = true;
                document.getElementById('status-indicator').classList.add('connected');
                document.getElementById('connection-status').textContent = 'Connected';
            };
            
            ws.onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    updateDashboard(data);
                    lastData = data;
                } catch (e) {
                    console.error('Error processing WebSocket message:', e);
                }
            };
            
            ws.onclose = function() {
                console.log('WebSocket disconnected');
                connected = false;
                document.getElementById('status-indicator').classList.remove('connected');
                document.getElementById('connection-status').textContent = 'Disconnected';
                
                // Try to reconnect after a delay
                setTimeout(connectWebSocket, 2000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                connected = false;
            };
        }
        
        function updateDashboard(data) {
            // Update test status
            const statusElem = document.getElementById('test-status');
            statusElem.textContent = data.test_status;
            statusElem.className = 'status ' + data.test_status;
            
            // Update test info
            if (data.start_time) {
                const startTime = new Date(data.start_time * 1000);
                document.getElementById('start-time').textContent = startTime.toLocaleTimeString();
                
                const duration = (data.last_update - data.start_time).toFixed(1);
                document.getElementById('duration').textContent = `${duration}s`;
            }
            
            // Update metrics
            updateMetrics(data.metrics);
            
            // Update system info
            updateSystemInfo(data.system);
            
            // Update thread information
            updateThreadInfo(data.threads);
            
            // Update chart
            updateChart(data.metrics.batch_times);
        }
        
        function updateMetrics(metrics) {
            const metricsContainer = document.getElementById('metrics');
            metricsContainer.innerHTML = '';
            
            // Calculate cache hit rate
            const hits = metrics.cache_hits || 0;
            const misses = metrics.cache_misses || 0;
            const total = hits + misses;
            const hitRate = total > 0 ? (hits / total * 100).toFixed(1) : '0';
            
            // Calculate batch time stats
            let avgBatchTime = '0';
            let minBatchTime = '0';
            let maxBatchTime = '0';
            
            if (metrics.batch_times && metrics.batch_times.length > 0) {
                const sum = metrics.batch_times.reduce((a, b) => a + b, 0);
                avgBatchTime = (sum / metrics.batch_times.length).toFixed(2);
                minBatchTime = Math.min(...metrics.batch_times).toFixed(2);
                maxBatchTime = Math.max(...metrics.batch_times).toFixed(2);
            }
            
            const metricItems = [
                { name: 'Cache Hit Rate', value: `${hitRate}%` },
                { name: 'Cache Hits', value: hits },
                { name: 'Cache Misses', value: misses },
                { name: 'Avg Batch Time', value: `${avgBatchTime} ms` },
                { name: 'Min Batch Time', value: `${minBatchTime} ms` },
                { name: 'Max Batch Time', value: `${maxBatchTime} ms` },
                { name: 'Prefetch Errors', value: metrics.prefetch_errors || 0 },
                { name: 'Queue Full Events', value: metrics.queue_full_events || 0 },
                { name: 'Worker Exceptions', value: metrics.worker_exceptions || 0 },
            ];
            
            metricItems.forEach(item => {
                const div = document.createElement('div');
                div.className = 'metric';
                div.innerHTML = `
                    <div>${item.name}</div>
                    <div class="metric-value">${item.value}</div>
                `;
                metricsContainer.appendChild(div);
            });
        }
        
        function updateSystemInfo(system) {
            const container = document.getElementById('system-metrics');
            container.innerHTML = '';
            
            const items = [
                { name: 'CPU Usage', value: `${system.cpu_usage?.toFixed(1) || '0'}%` },
                { name: 'Memory Usage', value: `${system.memory_usage?.toFixed(1) || '0'}%` },
                { name: 'Memory Available', value: `${(system.memory_available_mb?.toFixed(0) || '0')} MB` }
            ];
            
            items.forEach(item => {
                const div = document.createElement('div');
                div.className = 'metric';
                div.innerHTML = `
                    <div>${item.name}</div>
                    <div class="metric-value">${item.value}</div>
                `;
                container.appendChild(div);
            });
        }
        
        function updateThreadInfo(threads) {
            const container = document.getElementById('thread-container');
            container.innerHTML = '';
            
            if (!threads || Object.keys(threads).length === 0) {
                container.innerHTML = '<p>No thread information available</p>';
                return;
            }
            
            // Sort threads by name
            const sortedThreads = Object.entries(threads).sort((a, b) => {
                return a[1].name.localeCompare(b[1].name);
            });
            
            sortedThreads.forEach(([id, thread]) => {
                const status = thread.is_alive ? 'active' : 'stopped';
                const div = document.createElement('div');
                div.className = `thread ${status}`;
                div.innerHTML = `
                    <div class="thread-name">${thread.name || 'Unknown'} (${id})</div>
                    <div>Status: ${thread.is_alive ? 'Running' : 'Stopped'}</div>
                    <div>Type: ${thread.type || 'Unknown'}</div>
                    ${thread.task ? `<div>Task: ${thread.task}</div>` : ''}
                    ${thread.health_score ? `<div>Health: ${(thread.health_score * 100).toFixed(0)}%</div>` : ''}
                    ${thread.errors ? `<div>Errors: ${thread.errors}</div>` : ''}
                    ${thread.last_error ? `<div>Last Error: ${thread.last_error}</div>` : ''}
                `;
                container.appendChild(div);
            });
        }
        
        function updateChart(batchTimes) {
            if (!batchTimes || batchTimes.length === 0) return;
            
            // Get the most recent 50 batch times for chart display
            const recentTimes = batchTimes.slice(-50);
            
            // Initialize chart if not already created
            if (!chart) {
                const ctx = document.getElementById('batch-times-chart').getContext('2d');
                chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: Array.from({ length: recentTimes.length }, (_, i) => i + 1),
                        datasets: [{
                            label: 'Batch Times (ms)',
                            data: recentTimes,
                            borderColor: '#2196F3',
                            backgroundColor: 'rgba(33, 150, 243, 0.1)',
                            tension: 0.1,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Time (ms)'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Batch Number'
                                }
                            }
                        }
                    }
                });
            } else {
                // Update existing chart
                chart.data.labels = Array.from({ length: recentTimes.length }, (_, i) => i + 1);
                chart.data.datasets[0].data = recentTimes;
                chart.update();
            }
        }
        
        function requestUpdate() {
            if (connected) {
                ws.send(JSON.stringify({ action: 'get_data' }));
            }
        }
        
        // Set up refresh rate change handler
        document.getElementById('refresh-rate').addEventListener('change', function(e) {
            refreshInterval = parseInt(e.target.value);
            clearInterval(window.updateInterval);
            window.updateInterval = setInterval(requestUpdate, refreshInterval);
        });
        
        // Initialize WebSocket connection
        connectWebSocket();
        
        // Set up periodic data updates
        window.updateInterval = setInterval(requestUpdate, refreshInterval);
        
        // Initial data request after connection
        setTimeout(requestUpdate, 500);
    </script>
</body>
</html>
"""

class HTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        logger.debug(f"GET request: {self.path}")
        parsed_path = urlparse(self.path)
        
        # Serve the dashboard
        if parsed_path.path == "/debug/dashboard":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())
            return
            
        # API endpoint to get current state
        elif parsed_path.path == "/debug/api/state":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            with state_lock:
                self.wfile.write(json.dumps(debug_data).encode())
            return
            
        # API endpoints for updating state
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found")
            return
    
    def do_POST(self):
        logger.debug(f"POST request: {self.path}")
        parsed_path = urlparse(self.path)
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(post_data)
        except json.JSONDecodeError:
            self.send_response(400)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Invalid JSON")
            return
        
        # Update thread info
        if parsed_path.path == "/debug/api/thread":
            if 'thread_id' in data and 'info' in data:
                update_thread_info(data['thread_id'], data['info'])
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Missing required fields")
            return
            
        # Update metrics
        elif parsed_path.path == "/debug/api/metrics":
            if 'metrics' in data:
                update_metrics(data['metrics'])
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Missing required fields")
            return
            
        # Update test status
        elif parsed_path.path == "/debug/api/status":
            if 'status' in data:
                update_test_status(data['status'])
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Missing required fields")
            return
            
        # Unknown endpoint
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not found")
            return

# Simple WebSocket implementation for real-time updates
class WebSocketHandler:
    def __init__(self, server):
        self.server = server
        self.clients = []
        self.broadcast_thread = threading.Thread(target=self.broadcast_loop, daemon=True)
        self.broadcast_thread.start()
    
    def add_client(self, client_socket, client_address):
        self.clients.append((client_socket, client_address))
        logger.info(f"New WebSocket client connected: {client_address}")
        with state_lock:
            debug_data["clients"] = [str(addr) for _, addr in self.clients]
    
    def remove_client(self, client_socket, client_address):
        self.clients.remove((client_socket, client_address))
        logger.info(f"WebSocket client disconnected: {client_address}")
        with state_lock:
            debug_data["clients"] = [str(addr) for _, addr in self.clients]
    
    def broadcast_loop(self):
        while True:
            try:
                # Update system info
                update_system_info()
                
                # Broadcast current state to all clients
                with state_lock:
                    data_json = json.dumps(debug_data)
                
                for client_socket, client_address in list(self.clients):
                    try:
                        client_socket.send(data_json.encode())
                    except Exception as e:
                        logger.error(f"Error sending to client {client_address}: {e}")
                        self.remove_client(client_socket, client_address)
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
            
            time.sleep(1)  # Broadcast frequency

class ThreadMonitoringServer:
    def __init__(self, host='0.0.0.0', port=8765):
        self.host = host
        self.port = port
        self.httpd = HTTPServer((host, port), HTTPHandler)
        self.websocket_handler = WebSocketHandler(self)
        logger.info(f"Server started at http://{host}:{port}")
        logger.info(f"Dashboard available at http://{host}:{port}/debug/dashboard")
    
    def start(self):
        try:
            self.httpd.serve_forever()
        finally:
            self.httpd.server_close()
            logger.info("Server stopped")

def main():
    parser = argparse.ArgumentParser(description="MCP Debug Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=8765, help="Port to bind the server to")
    parser.add_argument("--open-browser", action="store_true", help="Open browser automatically")
    
    args = parser.parse_args()
    
    # Create and start the server
    server = ThreadMonitoringServer(host=args.host, port=args.port)
    
    # Open browser if requested
    if args.open_browser:
        dashboard_url = f"http://localhost:{args.port}/debug/dashboard"
        threading.Timer(1.0, lambda: webbrowser.open(dashboard_url)).start()
    
    # Start the server
    logger.info("Starting server...")
    server.start()

if __name__ == "__main__":
    main()