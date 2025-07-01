#!/usr/bin/env python3
"""
MCP Server Blue/Green Runner - Enhanced Version

This script runs the MCP Server with advanced blue/green deployment capabilities,
providing real-time monitoring, intelligent traffic control, and automated
rollout management.
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
import contextlib
from pathlib import Path
from typing import Dict, Any, Optional, List

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_blue_green_runner")

# Ensure parent directory is in path for imports
parent_dir = str(Path(__file__).parent.absolute())
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Try to import necessary components
try:
    from ipfs_kit_py.mcp_server.blue_green_proxy import AsyncMCPServerProxy, DeploymentMode
    PROXY_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import AsyncMCPServerProxy: {e}")
    PROXY_AVAILABLE = False

try:
    from aiohttp import web
    AIOHTTP_AVAILABLE = True
except ImportError:
    logger.warning("aiohttp not available. Install with: pip install aiohttp")
    AIOHTTP_AVAILABLE = False

# Global server instance
server_proxy = None
app_runner = None

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

def setup_signal_handlers():
    """Set up signal handlers for graceful shutdown."""
    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        if asyncio.get_event_loop().is_running():
            asyncio.get_event_loop().create_task(shutdown())
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

async def shutdown():
    """Shut down the server gracefully."""
    global server_proxy, app_runner
    
    # Stop the web dashboard if running
    if app_runner:
        logger.info("Stopping web dashboard...")
        await app_runner.cleanup()
    
    # Stop the server proxy
    if server_proxy:
        logger.info("Stopping server proxy...")
        await server_proxy.stop()
    
    # Stop the event loop
    loop = asyncio.get_event_loop()
    loop.stop()

async def health_monitoring(interval: int = 60):
    """Periodically check server health and log statistics."""
    global server_proxy
    
    while True:
        try:
            if server_proxy and server_proxy.running:
                health = await server_proxy.check_health()
                logger.info(f"Health check: {health['status']}")
                
                # Log traffic split if available
                if "traffic_split" in health:
                    split = health["traffic_split"]
                    logger.info(f"Traffic split: Blue {split['blue_percentage']}%, Green {split['green_percentage']}%")
                
                # Log metrics if available
                if "metrics" in health:
                    metrics = health["metrics"]
                    blue_stats = metrics.get("blue", {})
                    green_stats = metrics.get("green", {})
                    
                    logger.info(f"Blue: {blue_stats.get('requests', 0)} requests, {blue_stats.get('success_rate', 0):.1f}% success")
                    logger.info(f"Green: {green_stats.get('requests', 0)} requests, {green_stats.get('success_rate', 0):.1f}% success")
                
                # Log validation stats if available
                if "validation" in health:
                    validation = health["validation"]
                    logger.info(f"Compatibility: {validation.get('compatible_rate', 0):.1f}%, "
                                f"Identical: {validation.get('identical_rate', 0):.1f}%")
                    
                    # Log recommendation if available
                    if "recommendations" in validation:
                        recommendation = validation["recommendations"]
                        logger.info(f"Recommendation: {recommendation.get('action')} - {recommendation.get('message')}")
            
            await asyncio.sleep(interval)
        
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in health monitoring: {e}")
            await asyncio.sleep(interval)

async def setup_web_dashboard(config: Dict[str, Any], host: str = "localhost", port: int = 8090):
    """Set up a web dashboard for monitoring the blue/green deployment."""
    global server_proxy, app_runner
    
    if not AIOHTTP_AVAILABLE:
        logger.warning("Web dashboard not available: aiohttp not installed")
        return None
    
    app = web.Application()
    
    # API routes
    async def health_handler(request):
        """Handler for health check endpoint."""
        if not server_proxy:
            return web.json_response({"error": "Server proxy not running"}, status=503)
        
        health = await server_proxy.check_health()
        return web.json_response(health)
    
    async def set_mode_handler(request):
        """Handler for setting deployment mode."""
        if not server_proxy:
            return web.json_response({"error": "Server proxy not running"}, status=503)
        
        try:
            data = await request.json()
            mode = data.get("mode")
            green_percentage = data.get("green_percentage")
            
            if not mode:
                return web.json_response({"error": "Mode not specified"}, status=400)
            
            result = server_proxy.set_mode(mode, green_percentage)
            return web.json_response(result)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
    
    # Serve static dashboard files
    async def index_handler(request):
        """Handler for the dashboard index page."""
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>MCP Blue/Green Dashboard</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { padding-top: 20px; }
                .card { margin-bottom: 20px; }
                .traffic-control { margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1 class="mb-4">MCP Blue/Green Deployment Dashboard</h1>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Deployment Status</h5>
                            </div>
                            <div class="card-body">
                                <p><strong>Mode:</strong> <span id="mode">Loading...</span></p>
                                <p><strong>Status:</strong> <span id="status">Loading...</span></p>
                                <p><strong>Traffic Split:</strong></p>
                                <div class="progress">
                                    <div id="blue-progress" class="progress-bar bg-primary" role="progressbar" style="width: 100%">Blue 100%</div>
                                    <div id="green-progress" class="progress-bar bg-success" role="progressbar" style="width: 0%">Green 0%</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Server Health</h5>
                            </div>
                            <div class="card-body">
                                <table class="table">
                                    <thead>
                                        <tr>
                                            <th>Server</th>
                                            <th>Status</th>
                                            <th>Success Rate</th>
                                            <th>Requests</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <tr>
                                            <td>Blue</td>
                                            <td id="blue-status">-</td>
                                            <td id="blue-success-rate">-</td>
                                            <td id="blue-requests">-</td>
                                        </tr>
                                        <tr>
                                            <td>Green</td>
                                            <td id="green-status">-</td>
                                            <td id="green-success-rate">-</td>
                                            <td id="green-requests">-</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Response Validation</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="validation-chart" height="200"></canvas>
                                <div id="recommendation" class="alert alert-info mt-3">Loading recommendation...</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Performance Comparison</h5>
                            </div>
                            <div class="card-body">
                                <canvas id="performance-chart" height="200"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="card traffic-control">
                    <div class="card-header">
                        <h5>Traffic Control</h5>
                    </div>
                    <div class="card-body">
                        <div class="row">
                            <div class="col-md-6">
                                <div class="mb-3">
                                    <label for="mode-select" class="form-label">Deployment Mode</label>
                                    <select id="mode-select" class="form-select">
                                        <option value="blue">Blue (Original)</option>
                                        <option value="green">Green (Refactored)</option>
                                        <option value="gradual">Gradual Rollout</option>
                                        <option value="parallel">Parallel (Comparison)</option>
                                        <option value="auto">Auto (AI-Controlled)</option>
                                    </select>
                                </div>
                            </div>
                            <div class="col-md-6" id="percentage-control">
                                <div class="mb-3">
                                    <label for="green-percentage" class="form-label">Green Traffic (%)</label>
                                    <input type="range" class="form-range" id="green-percentage" min="0" max="100" value="0">
                                    <span id="percentage-display">0%</span>
                                </div>
                            </div>
                        </div>
                        <button id="apply-button" class="btn btn-primary">Apply Changes</button>
                    </div>
                </div>
            </div>
            
            <script>
                // Charts
                const validationCtx = document.getElementById('validation-chart').getContext('2d');
                const validationChart = new Chart(validationCtx, {
                    type: 'pie',
                    data: {
                        labels: ['Identical', 'Compatible', 'Incompatible'],
                        datasets: [{
                            data: [0, 0, 0],
                            backgroundColor: ['#198754', '#0d6efd', '#dc3545']
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'right' }
                        }
                    }
                });
                
                const perfCtx = document.getElementById('performance-chart').getContext('2d');
                const perfChart = new Chart(perfCtx, {
                    type: 'bar',
                    data: {
                        labels: ['Success Rate', 'Avg Response Time'],
                        datasets: [
                            {
                                label: 'Blue',
                                data: [0, 0],
                                backgroundColor: '#0d6efd'
                            },
                            {
                                label: 'Green',
                                data: [0, 0],
                                backgroundColor: '#198754'
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
                
                // UI interaction
                const greenPercentage = document.getElementById('green-percentage');
                const percentageDisplay = document.getElementById('percentage-display');
                const modeSelect = document.getElementById('mode-select');
                const percentageControl = document.getElementById('percentage-control');
                const applyButton = document.getElementById('apply-button');
                
                greenPercentage.addEventListener('input', function() {
                    percentageDisplay.textContent = this.value + '%';
                });
                
                modeSelect.addEventListener('change', function() {
                    if (this.value === 'gradual' || this.value === 'auto') {
                        percentageControl.style.display = 'block';
                    } else {
                        percentageControl.style.display = 'none';
                    }
                });
                
                applyButton.addEventListener('click', async function() {
                    const mode = modeSelect.value;
                    let data = { mode };
                    
                    if (mode === 'gradual' || mode === 'auto') {
                        data.green_percentage = parseInt(greenPercentage.value);
                    }
                    
                    try {
                        const response = await fetch('/api/set_mode', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(data)
                        });
                        
                        const result = await response.json();
                        if (result.success) {
                            alert('Deployment mode updated successfully');
                            updateDashboard();
                        } else {
                            alert('Error: ' + result.message);
                        }
                    } catch (error) {
                        alert('Error applying changes: ' + error);
                    }
                });
                
                // Dashboard updates
                async function updateDashboard() {
                    try {
                        const response = await fetch('/api/health');
                        const data = await response.json();
                        
                        // Update status
                        document.getElementById('mode').textContent = data.mode || 'Unknown';
                        document.getElementById('status').textContent = data.status || 'Unknown';
                        
                        // Update traffic split
                        if (data.traffic_split) {
                            const blue = data.traffic_split.blue_percentage || 0;
                            const green = data.traffic_split.green_percentage || 0;
                            
                            document.getElementById('blue-progress').style.width = blue + '%';
                            document.getElementById('blue-progress').textContent = 'Blue ' + blue + '%';
                            
                            document.getElementById('green-progress').style.width = green + '%';
                            document.getElementById('green-progress').textContent = 'Green ' + green + '%';
                            
                            // Update the slider to match actual split
                            greenPercentage.value = green;
                            percentageDisplay.textContent = green + '%';
                        }
                        
                        // Update server health
                        if (data.components && data.components.blue) {
                            document.getElementById('blue-status').textContent = 
                                data.components.blue.success ? 'Healthy' : 'Unhealthy';
                        }
                        
                        if (data.components && data.components.green) {
                            document.getElementById('green-status').textContent = 
                                data.components.green.success ? 'Healthy' : 'Unhealthy';
                        }
                        
                        // Update metrics
                        if (data.metrics) {
                            const blue = data.metrics.blue || {};
                            const green = data.metrics.green || {};
                            
                            document.getElementById('blue-success-rate').textContent = 
                                (blue.success_rate || 0).toFixed(1) + '%';
                            document.getElementById('blue-requests').textContent = 
                                blue.requests || 0;
                            
                            document.getElementById('green-success-rate').textContent = 
                                (green.success_rate || 0).toFixed(1) + '%';
                            document.getElementById('green-requests').textContent = 
                                green.requests || 0;
                            
                            // Update performance chart
                            perfChart.data.datasets[0].data = [
                                blue.success_rate || 0,
                                blue.avg_response_time || 0
                            ];
                            
                            perfChart.data.datasets[1].data = [
                                green.success_rate || 0,
                                green.avg_response_time || 0
                            ];
                            
                            perfChart.update();
                        }
                        
                        // Update validation
                        if (data.validation) {
                            const validation = data.validation;
                            
                            // Update validation chart
                            validationChart.data.datasets[0].data = [
                                validation.identical_rate || 0,
                                (validation.compatible_rate || 0) - (validation.identical_rate || 0),
                                100 - (validation.compatible_rate || 0)
                            ];
                            validationChart.update();
                            
                            // Update recommendation
                            if (validation.recommendations) {
                                const rec = validation.recommendations;
                                let alertClass = 'alert-info';
                                
                                if (rec.action === 'rollback') {
                                    alertClass = 'alert-danger';
                                } else if (rec.action === 'green_safe') {
                                    alertClass = 'alert-success';
                                } else if (rec.action === 'increase_green_traffic') {
                                    alertClass = 'alert-primary';
                                }
                                
                                const recElem = document.getElementById('recommendation');
                                recElem.className = 'alert mt-3 ' + alertClass;
                                recElem.textContent = rec.message;
                            }
                        }
                        
                    } catch (error) {
                        console.error('Error updating dashboard:', error);
                    }
                }
                
                // Initial setup
                modeSelect.value = 'blue';
                percentageControl.style.display = 'none';
                
                // Update every 5 seconds
                updateDashboard();
                setInterval(updateDashboard, 5000);
            </script>
        </body>
        </html>
        """
        return web.Response(text=html, content_type='text/html')
    
    # Set up routes
    app.router.add_get('/', index_handler)
    app.router.add_get('/api/health', health_handler)
    app.router.add_post('/api/set_mode', set_mode_handler)
    
    # Start the web application
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"Web dashboard available at http://{host}:{port}/")
    
    # Store globally for cleanup
    app_runner = runner
    
    return runner

async def run_server(args):
    """Run the MCP server with blue/green deployment."""
    global server_proxy
    
    if not PROXY_AVAILABLE:
        logger.error("AsyncMCPServerProxy not available. Cannot start server.")
        return 1
    
    # Load configuration
    config = load_config(args.config)
    
    # Override deployment mode if specified
    if args.mode:
        logger.info(f"Overriding deployment mode to: {args.mode}")
        if "deployment" not in config:
            config["deployment"] = {}
        config["deployment"]["mode"] = args.mode
    
    # Override green percentage if specified
    if args.green_percentage is not None:
        logger.info(f"Overriding green percentage to: {args.green_percentage}%")
        if "deployment" not in config:
            config["deployment"] = {}
        config["deployment"]["green_percentage"] = args.green_percentage
    
    # Configure logging based on config
    if "monitoring" in config and "logging" in config["monitoring"]:
        log_config = config["monitoring"]["logging"]
        log_level_name = log_config.get("level", "INFO")
        log_level = getattr(logging, log_level_name)
        
        # Set root logger level
        logging.getLogger().setLevel(log_level)
        
        # Configure file logging if specified
        if "file" in log_config:
            os.makedirs(os.path.dirname(log_config["file"]), exist_ok=True)
            file_handler = logging.FileHandler(log_config["file"])
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logging.getLogger().addHandler(file_handler)
    
    # Initialize and start the server proxy
    try:
        # Create server proxy
        server_proxy = AsyncMCPServerProxy(config)
        logger.info("Starting MCP Server Proxy...")
        
        # Start server proxy
        start_result = await server_proxy.start()
        if not start_result["success"]:
            logger.error(f"Failed to start server: {start_result['message']}")
            return 1
        
        logger.info(f"MCP Server Proxy started in {server_proxy.mode.value} mode")
        
        # Start web dashboard if enabled
        web_config = config.get("web_dashboard", {"enabled": False})
        if web_config.get("enabled", False) and not args.no_dashboard:
            web_host = web_config.get("host", "localhost")
            web_port = web_config.get("port", 8090)
            await setup_web_dashboard(config, web_host, web_port)
        
        # Start health monitoring task
        monitor_interval = 60
        if "deployment" in config and "health_check_interval" in config["deployment"]:
            monitor_interval = config["deployment"]["health_check_interval"]
        
        monitor_task = asyncio.create_task(health_monitoring(monitor_interval))
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
    
    except asyncio.CancelledError:
        logger.info("Server task cancelled")
    except Exception as e:
        logger.error(f"Error running server: {e}")
        return 1
    finally:
        # Clean up tasks
        if 'monitor_task' in locals():
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop server if still running
        if server_proxy and server_proxy.running:
            await server_proxy.stop()
    
    return 0

def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run MCP Server with blue/green deployment")
    parser.add_argument("--config", "-c", default="config/blue_green_config.json",
                        help="Path to configuration file")
    parser.add_argument("--mode", "-m", choices=["blue", "green", "gradual", "parallel", "auto"],
                        help="Deployment mode to use (overrides config)")
    parser.add_argument("--green-percentage", "-p", type=int,
                        help="Percentage of traffic to route to green for gradual mode")
    parser.add_argument("--no-dashboard", "-n", action="store_true",
                        help="Disable web dashboard even if enabled in config")
    args = parser.parse_args()
    
    # Set up signal handlers
    setup_signal_handlers()
    
    # Run the server
    try:
        loop = asyncio.get_event_loop()
        exit_code = loop.run_until_complete(run_server(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Ensure event loop is closed
        if not loop.is_closed():
            loop.close()

if __name__ == "__main__":
    main()