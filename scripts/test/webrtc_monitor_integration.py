#!/usr/bin/env python3
"""
WebRTC Monitor Integration for Enhanced MCP Server.

This script integrates the WebRTC monitor with the Enhanced MCP Server,
providing real-time WebRTC performance monitoring, metrics collection,
and adaptive streaming optimization.
"""

import os
import sys
import time
import logging
import json
import argparse
import anyio
from threading import Thread
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("webrtc_monitor.log")
    ]
)
logger = logging.getLogger(__name__)

# Try to import Prometheus components
try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server
except ImportError:
    logger.error("Prometheus client not available. Install with: pip install prometheus-client")
    HAS_PROMETHEUS = False
else:
    HAS_PROMETHEUS = True

# Try to import pandas and matplotlib for visualization
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    HAS_VISUALIZATION = True
except ImportError:
    logger.warning("Pandas or matplotlib not available. Visualization features disabled.")
    logger.warning("Install with: pip install pandas matplotlib")
    HAS_VISUALIZATION = False

# Try to import from ipfs_kit_py modules
try:
    from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import
    from ipfs_kit_py.fixes.webrtc_monitor import WebRTCMonitor, WebRTCStreamBuffer
    HAS_MCP = True
except ImportError:
    logger.warning("Could not import MCP server modules.")
    HAS_MCP = False

class WebRTCMetrics:
    """Prometheus metrics for WebRTC monitoring."""

    def __init__(self, prefix="webrtc"):
        """Initialize Prometheus metrics."""
        if not HAS_PROMETHEUS:
            logger.warning("Prometheus client not available. Metrics collection disabled.")
            return

        self.prefix = prefix

        # Connection metrics
        self.connections_total = Counter(
            f'{prefix}_connections_total',
            'Total number of WebRTC connections established',
            ['server_id']
        )

        self.active_connections = Gauge(
            f'{prefix}_active_connections',
            'Number of active WebRTC connections',
            ['server_id']
        )

        self.connection_duration = Histogram(
            f'{prefix}_connection_duration_seconds',
            'Duration of WebRTC connections',
            ['server_id'],
            buckets=(5, 15, 30, 60, 120, 300, 600, 1800, 3600)
        )

        # Frame metrics
        self.frames_sent = Counter(
            f'{prefix}_frames_sent_total',
            'Total number of frames sent',
            ['type', 'quality']  # type: video/audio, quality: low/medium/high
        )

        self.frames_received = Counter(
            f'{prefix}_frames_received_total',
            'Total number of frames received',
            ['type', 'quality']
        )

        self.frame_rate = Gauge(
            f'{prefix}_frame_rate',
            'Current frame rate',
            ['connection_id', 'type']
        )

        self.frame_size = Histogram(
            f'{prefix}_frame_size_bytes',
            'Size of frames in bytes',
            ['type', 'quality'],
            buckets=(1024, 5*1024, 10*1024, 50*1024, 100*1024, 500*1024, 1024*1024)
        )

        # Stream metrics
        self.buffer_level = Gauge(
            f'{prefix}_buffer_level_frames',
            'Number of frames in buffer',
            ['connection_id', 'type']
        )

        self.buffer_level_seconds = Gauge(
            f'{prefix}_buffer_level_seconds',
            'Buffer level in seconds',
            ['connection_id', 'type']
        )

        self.buffer_underruns = Counter(
            f'{prefix}_buffer_underruns_total',
            'Total number of buffer underruns',
            ['connection_id', 'type']
        )

        # Bandwidth metrics
        self.bandwidth_usage = Gauge(
            f'{prefix}_bandwidth_kbps',
            'Bandwidth usage in kilobits per second',
            ['connection_id', 'direction']  # direction: inbound/outbound
        )

        self.packet_loss = Gauge(
            f'{prefix}_packet_loss_percent',
            'Packet loss percentage',
            ['connection_id', 'direction']
        )

        # Latency metrics
        self.latency = Histogram(
            f'{prefix}_latency_ms',
            'Latency in milliseconds',
            ['connection_id', 'type'],  # type: signaling/media
            buckets=(10, 25, 50, 75, 100, 150, 200, 300, 500, 1000)
        )

        self.jitter = Gauge(
            f'{prefix}_jitter_ms',
            'Jitter in milliseconds',
            ['connection_id', 'type']
        )

        # Quality metrics
        self.video_quality = Gauge(
            f'{prefix}_video_quality_score',
            'Video quality score (0-100)',
            ['connection_id']
        )

        self.quality_switches = Counter(
            f'{prefix}_quality_switches_total',
            'Total number of quality switches',
            ['connection_id', 'from_quality', 'to_quality']
        )

        # Overall stream performance
        self.stream_health = Gauge(
            f'{prefix}_stream_health_score',
            'Overall stream health score (0-100)',
            ['connection_id']
        )

        # Cache/buffer optimization metrics
        self.prefetch_operations = Counter(
            f'{prefix}_prefetch_operations_total',
            'Total number of content prefetch operations',
            ['server_id', 'success']
        )

        self.prefetch_latency = Histogram(
            f'{prefix}_prefetch_latency_ms',
            'Content prefetch latency in milliseconds',
            ['server_id'],
            buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1000)
        )

        # Resource usage
        self.cpu_usage = Gauge(
            f'{prefix}_cpu_usage_percent',
            'CPU usage percentage',
            ['server_id']
        )

        self.memory_usage = Gauge(
            f'{prefix}_memory_usage_bytes',
            'Memory usage in bytes',
            ['server_id']
        )

        # ICE connectivity metrics
        self.ice_gathering_time = Histogram(
            f'{prefix}_ice_gathering_time_ms',
            'Time taken for ICE gathering in milliseconds',
            ['connection_id'],
            buckets=(50, 100, 250, 500, 1000, 2000, 5000)
        )

        self.ice_connection_time = Histogram(
            f'{prefix}_ice_connection_time_ms',
            'Time taken for ICE connection in milliseconds',
            ['connection_id'],
            buckets=(50, 100, 250, 500, 1000, 2000, 5000)
        )

        # Adaptive bitrate switching metrics
        self.abr_switches = Counter(
            f'{prefix}_abr_switches_total',
            'Total number of adaptive bitrate switches',
            ['connection_id', 'reason']  # reason: bandwidth/cpu/user
        )

        logger.info("WebRTC metrics initialized")

class WebRTCMonitorIntegration:
    """Integration of WebRTC monitoring with MCP server."""

    def __init__(self,
                 mcp_server: Optional[MCPServer] = None,
                 mcp_host: str = "localhost",
                 mcp_port: int = 8000,
                 metrics_port: int = 9090,
                 enable_metrics: bool = True,
                 enable_optimization: bool = True,
                 auto_adjust_quality: bool = True,
                 poll_interval: float = 2.0,
                 visualization_interval: float = 30.0,
                 report_path: str = "./reports",
                 config_path: Optional[str] = None):
        """
        Initialize WebRTC Monitor Integration.

        Args:
            mcp_server: Optional MCP server instance for direct integration
            mcp_host: MCP server host for API access
            mcp_port: MCP server port for API access
            metrics_port: Port for Prometheus metrics server
            enable_metrics: Whether to enable Prometheus metrics
            enable_optimization: Whether to enable streaming optimization
            auto_adjust_quality: Whether to automatically adjust quality based on metrics
            poll_interval: Interval between metrics polls in seconds
            visualization_interval: Interval between visualization updates in seconds
            report_path: Path for reports and visualizations
            config_path: Path to configuration file (optional)
        """
        self.mcp_server = mcp_server
        self.mcp_host = mcp_host
        self.mcp_port = mcp_port
        self.metrics_port = metrics_port
        self.enable_metrics = enable_metrics and HAS_PROMETHEUS
        self.enable_optimization = enable_optimization
        self.auto_adjust_quality = auto_adjust_quality
        self.poll_interval = poll_interval
        self.visualization_interval = visualization_interval
        self.report_path = os.path.expanduser(report_path)

        # Create report directory if it doesn't exist
        os.makedirs(self.report_path, exist_ok=True)

        # Initialize metrics
        if self.enable_metrics:
            self.metrics = WebRTCMetrics()
            # Start Prometheus HTTP server
            try:
                start_http_server(self.metrics_port)
                logger.info(f"Started Prometheus metrics server on port {self.metrics_port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus metrics server: {e}")
                self.enable_metrics = False

        # Initialize WebRTC monitor
        try:
            self.monitor = WebRTCMonitor(
                auto_optimize=self.enable_optimization,
                auto_quality_adjustment=self.auto_adjust_quality
            )
            logger.info("WebRTC Monitor initialized")
        except Exception as e:
            logger.error(f"Failed to initialize WebRTC Monitor: {e}")
            self.monitor = None

        # Initialize data storage for metrics history
        self.metrics_history = {
            "timestamps": [],
            "connections": {},
            "servers": {},
            "global": {
                "active_connections": [],
                "bandwidth_usage": [],
                "packet_loss": [],
                "buffer_level": [],
                "frame_rate": [],
                "quality_score": []
            }
        }

        # Load configuration
        self.config = self.load_config(config_path)

        # Status flags
        self.running = False
        self.poll_task = None
        self.visualization_task = None

        # Set up REST API client for MCP communication
        self.setup_api_client()

        logger.info("WebRTC Monitor Integration initialized")

    def load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from file.

        Args:
            config_path: Path to configuration file (optional)

        Returns:
            Configuration dictionary
        """
        # Default configuration
        default_config = {
            "optimization": {
                "buffer_size_range": [15, 60],  # Min and max buffer size in frames
                "prefetch_threshold_range": [0.2, 0.8],  # Min and max prefetch threshold
                "quality_downgrade_threshold": 50,  # Health score below which to downgrade quality
                "quality_upgrade_threshold": 80,  # Health score above which to upgrade quality
                "buffer_underrun_threshold": 3,  # Number of underruns before action
                "network_sensitivity": 0.7,  # How sensitive optimization is to network conditions (0-1)
                "cpu_sensitivity": 0.5,  # How sensitive optimization is to CPU usage (0-1)
                "memory_sensitivity": 0.3  # How sensitive optimization is to memory usage (0-1)
            },
            "metrics": {
                "collect_detailed_stats": True,  # Whether to collect detailed connection stats
                "collect_frame_stats": True,  # Whether to collect frame-level statistics
                "collect_resource_stats": True,  # Whether to collect resource usage statistics
                "collect_quality_metrics": True  # Whether to collect quality metrics
            },
            "visualization": {
                "enabled": HAS_VISUALIZATION,  # Whether to enable visualization
                "live_update": False,  # Whether to update visualizations in real-time
                "dashboard_update_interval": 30,  # Seconds between dashboard updates
                "max_history_points": 1000,  # Maximum number of history points to store
                "plot_style": "dark_background"  # Matplotlib style
            },
            "reporting": {
                "enabled": True,  # Whether to enable reporting
                "save_raw_data": True,  # Whether to save raw metrics data
                "interval": 300,  # Interval between reports in seconds
                "formats": ["json", "html"]  # Report formats
            }
        }

        # If no config path provided, use default config
        if not config_path:
            return default_config

        # Load configuration from file
        try:
            with open(os.path.expanduser(config_path), 'r') as f:
                user_config = json.load(f)

            # Merge user configuration with defaults
            merged_config = default_config.copy()
            for section, items in user_config.items():
                if section in merged_config:
                    if isinstance(merged_config[section], dict) and isinstance(items, dict):
                        merged_config[section].update(items)
                    else:
                        merged_config[section] = items
                else:
                    merged_config[section] = items

            logger.info(f"Loaded configuration from {config_path}")
            return merged_config

        except Exception as e:
            logger.error(f"Failed to load configuration from {config_path}: {e}")
            logger.info("Using default configuration")
            return default_config

    def setup_api_client(self):
        """Set up REST API client for MCP communication."""
        try:
            import requests
            self.api_client = requests
            self.api_base_url = f"http://{self.mcp_host}:{self.mcp_port}/api/v0/mcp"
            logger.info(f"API client set up with base URL: {self.api_base_url}")
        except ImportError:
            logger.error("requests module not available. Install with: pip install requests")
            self.api_client = None

    def start(self):
        """Start WebRTC monitoring."""
        if self.running:
            logger.warning("Monitor is already running")
            return False

        logger.info("Starting WebRTC Monitor Integration")
        self.running = True

        # Start polling task
        if not self.poll_task:
            if sys.version_info >= (3, 7):
                # For Python 3.7+, use asyncio directly
                self.poll_task = anyio.create_task(self._poll_loop())
                if HAS_VISUALIZATION and self.config["visualization"]["enabled"]:
                    self.visualization_task = anyio.create_task(self._visualization_loop())
            else:
                # For older Python versions, use background thread approach
                self._start_background_tasks()

        logger.info("WebRTC Monitor Integration started")
        return True

    def _start_background_tasks(self):
        """Start background tasks using threading for older Python versions."""
        # Start polling loop in a background thread
        def poll_thread_func():
            anyio.run(self._poll_loop())

        poll_thread = Thread(target=poll_thread_func, daemon=True)
        poll_thread.start()

        # Start visualization loop in a background thread if enabled
        if HAS_VISUALIZATION and self.config["visualization"]["enabled"]:
            def viz_thread_func():
                anyio.run(self._visualization_loop())

            viz_thread = Thread(target=viz_thread_func, daemon=True)
            viz_thread.start()

    async def _poll_loop(self):
        """Background task to poll for WebRTC metrics."""
        try:
            logger.info("Starting metrics polling loop")
            while self.running:
                try:
                    # Poll for metrics
                    await self.poll_metrics()

                    # Apply optimizations if enabled
                    if self.enable_optimization:
                        await self.apply_optimizations()

                    # Sleep until next poll interval
                    await anyio.sleep(self.poll_interval)
                except anyio.CancelledError:
                    logger.info("Polling task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in polling loop: {e}")
                    # Sleep before retrying to avoid rapid error loops
                    await anyio.sleep(self.poll_interval)

            logger.info("Polling loop stopped")
        except Exception as e:
            logger.error(f"Fatal error in polling loop: {e}")

    async def _visualization_loop(self):
        """Background task to update visualizations."""
        if not HAS_VISUALIZATION or not self.config["visualization"]["enabled"]:
            return

        try:
            logger.info("Starting visualization loop")
            while self.running:
                try:
                    # Update visualizations
                    self.update_visualizations()

                    # Sleep until next visualization interval
                    await anyio.sleep(self.visualization_interval)
                except anyio.CancelledError:
                    logger.info("Visualization task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in visualization loop: {e}")
                    await anyio.sleep(self.visualization_interval)

            logger.info("Visualization loop stopped")
        except Exception as e:
            logger.error(f"Fatal error in visualization loop: {e}")

    async def poll_metrics(self):
        """Poll for WebRTC metrics from MCP server."""
        if not self.api_client:
            logger.warning("API client not available, cannot poll metrics")
            return

        try:
            # If we have direct access to MCP server, use it
            if self.mcp_server:
                # Check if MCP server has a WebRTC controller
                if hasattr(self.mcp_server, 'controllers') and 'webrtc' in self.mcp_server.controllers:
                    webrtc_controller = self.mcp_server.controllers['webrtc']

                    # Get resource stats from the controller directly
                    stats = webrtc_controller.get_resource_stats()

                    # Get connection stats for each active connection
                    await self.poll_connection_stats(webrtc_controller)

                    # Update metrics with resource stats
                    self.update_metrics_from_stats(stats)
            else:
                # Use REST API to get metrics
                stats_url = f"{self.api_base_url}/webrtc/stats/resources"
                try:
                    response = self.api_client.get(stats_url)
                    if response.status_code == 200:
                        stats = response.json()

                        # Update metrics with resource stats
                        self.update_metrics_from_stats(stats)

                        # Get connection stats for each active connection
                        await self.poll_connection_stats_api()
                    else:
                        logger.warning(f"Failed to get resource stats: HTTP {response.status_code}")
                except Exception as e:
                    logger.error(f"Error fetching resource stats via API: {e}")

        except Exception as e:
            logger.error(f"Error polling metrics: {e}")

    async def poll_connection_stats(self, webrtc_controller):
        """Poll stats for each connection directly from the controller."""
        try:
            # Get list of connections
            connections_result = await webrtc_controller.list_connections()

            if connections_result.get("success", False):
                connections = connections_result.get("connections", [])

                # Poll stats for each connection
                for connection in connections:
                    connection_id = connection.get("id")
                    if not connection_id:
                        continue

                    try:
                        # Get stats for this connection
                        stats_result = await webrtc_controller.get_connection_stats(connection_id)

                        if stats_result.get("success", False):
                            connection_stats = stats_result.get("stats", {})

                            # Update metrics for this connection
                            self.update_connection_metrics(connection_id, connection_stats)

                            # Store in history
                            self.store_connection_history(connection_id, connection_stats)
                    except Exception as conn_e:
                        logger.error(f"Error getting stats for connection {connection_id}: {conn_e}")
        except Exception as e:
            logger.error(f"Error polling connection stats: {e}")

    async def poll_connection_stats_api(self):
        """Poll connection stats via REST API."""
        try:
            # Get list of connections
            connections_url = f"{self.api_base_url}/webrtc/connections"
            response = self.api_client.get(connections_url)

            if response.status_code == 200:
                connections_result = response.json()

                if connections_result.get("success", False):
                    connections = connections_result.get("connections", [])

                    # Poll stats for each connection
                    for connection in connections:
                        connection_id = connection.get("id")
                        if not connection_id:
                            continue

                        try:
                            # Get stats for this connection
                            stats_url = f"{self.api_base_url}/webrtc/connections/{connection_id}/stats"
                            stats_response = self.api_client.get(stats_url)

                            if stats_response.status_code == 200:
                                stats_result = stats_response.json()

                                if stats_result.get("success", False):
                                    connection_stats = stats_result.get("stats", {})

                                    # Update metrics for this connection
                                    self.update_connection_metrics(connection_id, connection_stats)

                                    # Store in history
                                    self.store_connection_history(connection_id, connection_stats)
                        except Exception as conn_e:
                            logger.error(f"Error getting stats for connection {connection_id} via API: {conn_e}")
        except Exception as e:
            logger.error(f"Error polling connection stats via API: {e}")

    def update_metrics_from_stats(self, stats):
        """
        Update Prometheus metrics from resource stats.

        Args:
            stats: Resource statistics dictionary
        """
        if not self.enable_metrics or not hasattr(self, 'metrics'):
            return

        try:
            timestamp = stats.get("timestamp", time.time())

            # Add timestamp to history
            self.metrics_history["timestamps"].append(timestamp)

            # Limit history size
            max_history = self.config["visualization"]["max_history_points"]
            if len(self.metrics_history["timestamps"]) > max_history:
                self.metrics_history["timestamps"] = self.metrics_history["timestamps"][-max_history:]

            # Update server metrics
            for server_info in stats.get("servers", {}).get("servers", []):
                server_id = server_info.get("id")
                if not server_id:
                    continue

                # Track servers in history
                if server_id not in self.metrics_history["servers"]:
                    self.metrics_history["servers"][server_id] = {
                        "connection_count": [],
                        "impact_score": [],
                        "age_seconds": []
                    }

                # Update server metrics
                connection_count = server_info.get("connection_count", 0)
                self.metrics.active_connections.labels(server_id=server_id).set(connection_count)

                # Store in history
                server_history = self.metrics_history["servers"][server_id]
                server_history["connection_count"].append(connection_count)
                server_history["impact_score"].append(server_info.get("impact_score", 0))
                server_history["age_seconds"].append(server_info.get("age_seconds", 0))

                # Limit history size
                for key in server_history:
                    if len(server_history[key]) > max_history:
                        server_history[key] = server_history[key][-max_history:]

            # Update global metrics
            global_history = self.metrics_history["global"]
            active_conn_count = stats.get("connections", {}).get("count", 0)
            global_history["active_connections"].append(active_conn_count)

            # Limit history size
            for key in global_history:
                if len(global_history[key]) > max_history:
                    global_history[key] = global_history[key][-max_history:]

            # Update system metrics if available
            if "system" in stats and isinstance(stats["system"], dict):
                system = stats["system"]

                # CPU usage
                if "cpu" in system and "percent" in system["cpu"]:
                    for server_id in self.metrics_history["servers"]:
                        self.metrics.cpu_usage.labels(server_id=server_id).set(system["cpu"]["percent"])

                # Memory usage
                if "memory" in system and "used" in system["memory"]:
                    for server_id in self.metrics_history["servers"]:
                        self.metrics.memory_usage.labels(server_id=server_id).set(system["memory"]["used"])

        except Exception as e:
            logger.error(f"Error updating metrics from stats: {e}")

    def update_connection_metrics(self, connection_id, stats):
        """
        Update metrics for a specific connection.

        Args:
            connection_id: ID of the connection
            stats: Connection statistics dictionary
        """
        if not self.enable_metrics or not hasattr(self, 'metrics'):
            return

        try:
            # Bandwidth metrics
            if "bandwidth" in stats:
                bandwidth = stats["bandwidth"]

                # Outbound bandwidth
                if "outbound" in bandwidth:
                    self.metrics.bandwidth_usage.labels(
                        connection_id=connection_id,
                        direction="outbound"
                    ).set(bandwidth["outbound"].get("kbps", 0))

                # Inbound bandwidth
                if "inbound" in bandwidth:
                    self.metrics.bandwidth_usage.labels(
                        connection_id=connection_id,
                        direction="inbound"
                    ).set(bandwidth["inbound"].get("kbps", 0))

            # Packet loss metrics
            if "packet_loss" in stats:
                packet_loss = stats["packet_loss"]

                # Outbound packet loss
                if "outbound" in packet_loss:
                    self.metrics.packet_loss.labels(
                        connection_id=connection_id,
                        direction="outbound"
                    ).set(packet_loss["outbound"].get("percent", 0))

                # Inbound packet loss
                if "inbound" in packet_loss:
                    self.metrics.packet_loss.labels(
                        connection_id=connection_id,
                        direction="inbound"
                    ).set(packet_loss["inbound"].get("percent", 0))

            # Frame metrics
            if "frames" in stats:
                frames = stats["frames"]

                # Video frame rate
                if "video" in frames:
                    self.metrics.frame_rate.labels(
                        connection_id=connection_id,
                        type="video"
                    ).set(frames["video"].get("fps", 0))

                # Audio frame rate
                if "audio" in frames:
                    self.metrics.frame_rate.labels(
                        connection_id=connection_id,
                        type="audio"
                    ).set(frames["audio"].get("fps", 0))

            # Buffer metrics
            if "buffer" in stats:
                buffer = stats["buffer"]

                # Video buffer level
                if "video" in buffer:
                    self.metrics.buffer_level.labels(
                        connection_id=connection_id,
                        type="video"
                    ).set(buffer["video"].get("frames", 0))

                    self.metrics.buffer_level_seconds.labels(
                        connection_id=connection_id,
                        type="video"
                    ).set(buffer["video"].get("seconds", 0))

                    self.metrics.buffer_underruns.labels(
                        connection_id=connection_id,
                        type="video"
                    ).inc(buffer["video"].get("underruns", 0))

                # Audio buffer level
                if "audio" in buffer:
                    self.metrics.buffer_level.labels(
                        connection_id=connection_id,
                        type="audio"
                    ).set(buffer["audio"].get("frames", 0))

                    self.metrics.buffer_level_seconds.labels(
                        connection_id=connection_id,
                        type="audio"
                    ).set(buffer["audio"].get("seconds", 0))

                    self.metrics.buffer_underruns.labels(
                        connection_id=connection_id,
                        type="audio"
                    ).inc(buffer["audio"].get("underruns", 0))

            # Latency metrics
            if "latency" in stats:
                latency = stats["latency"]

                # Signaling latency
                if "signaling" in latency:
                    self.metrics.latency.labels(
                        connection_id=connection_id,
                        type="signaling"
                    ).observe(latency["signaling"].get("ms", 0))

                # Media latency
                if "media" in latency:
                    self.metrics.latency.labels(
                        connection_id=connection_id,
                        type="media"
                    ).observe(latency["media"].get("ms", 0))

                # Jitter
                if "jitter" in latency:
                    self.metrics.jitter.labels(
                        connection_id=connection_id,
                        type="media"
                    ).set(latency["jitter"].get("ms", 0))

            # Quality metrics
            if "quality_metrics" in stats:
                quality = stats["quality_metrics"]

                # Video quality score
                if "score" in quality:
                    self.metrics.video_quality.labels(
                        connection_id=connection_id
                    ).set(quality["score"])

                # Stream health score
                if "health_score" in quality:
                    self.metrics.stream_health.labels(
                        connection_id=connection_id
                    ).set(quality["health_score"])

        except Exception as e:
            logger.error(f"Error updating connection metrics: {e}")

    def store_connection_history(self, connection_id, stats):
        """
        Store connection statistics in history.

        Args:
            connection_id: ID of the connection
            stats: Connection statistics dictionary
        """
        try:
            # Initialize connection history if needed
            if connection_id not in self.metrics_history["connections"]:
                self.metrics_history["connections"][connection_id] = {
                    "bandwidth": {
                        "outbound": [],
                        "inbound": []
                    },
                    "packet_loss": {
                        "outbound": [],
                        "inbound": []
                    },
                    "frame_rate": {
                        "video": [],
                        "audio": []
                    },
                    "buffer_level": {
                        "video": [],
                        "audio": []
                    },
                    "latency": {
                        "signaling": [],
                        "media": []
                    },
                    "quality": {
                        "score": [],
                        "health_score": []
                    }
                }

            history = self.metrics_history["connections"][connection_id]
            max_history = self.config["visualization"]["max_history_points"]

            # Bandwidth metrics
            if "bandwidth" in stats:
                bandwidth = stats["bandwidth"]

                # Outbound bandwidth
                if "outbound" in bandwidth:
                    history["bandwidth"]["outbound"].append(bandwidth["outbound"].get("kbps", 0))
                    # Update global stats
                    self.metrics_history["global"]["bandwidth_usage"].append(bandwidth["outbound"].get("kbps", 0))

                # Inbound bandwidth
                if "inbound" in bandwidth:
                    history["bandwidth"]["inbound"].append(bandwidth["inbound"].get("kbps", 0))

            # Packet loss metrics
            if "packet_loss" in stats:
                packet_loss = stats["packet_loss"]

                # Outbound packet loss
                if "outbound" in packet_loss:
                    history["packet_loss"]["outbound"].append(packet_loss["outbound"].get("percent", 0))
                    # Update global stats
                    self.metrics_history["global"]["packet_loss"].append(packet_loss["outbound"].get("percent", 0))

                # Inbound packet loss
                if "inbound" in packet_loss:
                    history["packet_loss"]["inbound"].append(packet_loss["inbound"].get("percent", 0))

            # Frame metrics
            if "frames" in stats:
                frames = stats["frames"]

                # Video frame rate
                if "video" in frames:
                    history["frame_rate"]["video"].append(frames["video"].get("fps", 0))
                    # Update global stats
                    self.metrics_history["global"]["frame_rate"].append(frames["video"].get("fps", 0))

                # Audio frame rate
                if "audio" in frames:
                    history["frame_rate"]["audio"].append(frames["audio"].get("fps", 0))

            # Buffer metrics
            if "buffer" in stats:
                buffer = stats["buffer"]

                # Video buffer level
                if "video" in buffer:
                    history["buffer_level"]["video"].append(buffer["video"].get("frames", 0))
                    # Update global stats
                    self.metrics_history["global"]["buffer_level"].append(buffer["video"].get("frames", 0))

                # Audio buffer level
                if "audio" in buffer:
                    history["buffer_level"]["audio"].append(buffer["audio"].get("frames", 0))

            # Latency metrics
            if "latency" in stats:
                latency = stats["latency"]

                # Signaling latency
                if "signaling" in latency:
                    history["latency"]["signaling"].append(latency["signaling"].get("ms", 0))

                # Media latency
                if "media" in latency:
                    history["latency"]["media"].append(latency["media"].get("ms", 0))

            # Quality metrics
            if "quality_metrics" in stats:
                quality = stats["quality_metrics"]

                # Video quality score
                if "score" in quality:
                    history["quality"]["score"].append(quality["score"])
                    # Update global stats
                    self.metrics_history["global"]["quality_score"].append(quality["score"])

                # Stream health score
                if "health_score" in quality:
                    history["quality"]["health_score"].append(quality["health_score"])

            # Limit history size
            for category in history:
                for key in history[category]:
                    if len(history[category][key]) > max_history:
                        history[category][key] = history[category][key][-max_history:]

        except Exception as e:
            logger.error(f"Error storing connection history: {e}")

    async def apply_optimizations(self):
        """Apply optimizations based on collected metrics."""
        if not self.enable_optimization or not self.monitor:
            return

        try:
            # Get optimization configuration
            optimization_config = self.config["optimization"]

            # Find connections with issues
            for connection_id, history in self.metrics_history["connections"].items():
                # Skip if history is empty
                if not history["quality"]["health_score"]:
                    continue

                # Check if stream health score is below threshold for quality downgrade
                health_scores = history["quality"]["health_score"]
                recent_scores = health_scores[-5:] if len(health_scores) >= 5 else health_scores
                avg_health_score = sum(recent_scores) / len(recent_scores)

                if avg_health_score < optimization_config["quality_downgrade_threshold"]:
                    # Stream health is poor, consider quality downgrade
                    await self.optimize_connection(connection_id, "downgrade")
                elif avg_health_score > optimization_config["quality_upgrade_threshold"]:
                    # Stream health is good, consider quality upgrade
                    await self.optimize_connection(connection_id, "upgrade")

                # Check for buffer underruns
                if "buffer" in history:
                    # Get latest buffer level
                    buffer_levels = history["buffer_level"]["video"]
                    if buffer_levels and buffer_levels[-1] < 5:  # Critical buffer level
                        # Apply buffer optimization
                        await self.optimize_buffer(connection_id)

        except Exception as e:
            logger.error(f"Error applying optimizations: {e}")

    async def optimize_connection(self, connection_id, action):
        """
        Optimize a connection by adjusting quality.

        Args:
            connection_id: ID of the connection
            action: "upgrade" or "downgrade"
        """
        if not self.auto_adjust_quality:
            return

        try:
            # Get current quality if possible
            current_quality = "medium"  # Default assumption
            if connection_id in self.metrics_history["connections"]:
                history = self.metrics_history["connections"][connection_id]
                if "current_quality" in history:
                    current_quality = history["current_quality"]

            # Determine new quality based on action
            new_quality = current_quality
            if action == "downgrade":
                if current_quality == "high":
                    new_quality = "medium"
                elif current_quality == "medium":
                    new_quality = "low"
            elif action == "upgrade":
                if current_quality == "low":
                    new_quality = "medium"
                elif current_quality == "medium":
                    new_quality = "high"

            # Skip if no change
            if new_quality == current_quality:
                return

            logger.info(f"Adjusting quality for connection {connection_id}: {current_quality} -> {new_quality}")

            # Apply quality change
            if self.mcp_server:
                # Use direct controller access if available
                if hasattr(self.mcp_server, 'controllers') and 'webrtc' in self.mcp_server.controllers:
                    webrtc_controller = self.mcp_server.controllers['webrtc']

                    # Use set_quality method
                    request = webrtc_controller.QualityRequest(
                        connection_id=connection_id,
                        quality=new_quality
                    )
                    result = await webrtc_controller.set_quality(request)

                    if result.get("success", False):
                        logger.info(f"Successfully adjusted quality for {connection_id} to {new_quality}")

                        # Update metrics
                        if self.enable_metrics and hasattr(self, 'metrics'):
                            self.metrics.quality_switches.labels(
                                connection_id=connection_id,
                                from_quality=current_quality,
                                to_quality=new_quality
                            ).inc()

                            # Record reason for adaptive bitrate switch
                            self.metrics.abr_switches.labels(
                                connection_id=connection_id,
                                reason="auto"
                            ).inc()

                        # Store current quality in history
                        if connection_id in self.metrics_history["connections"]:
                            self.metrics_history["connections"][connection_id]["current_quality"] = new_quality
                    else:
                        logger.warning(f"Failed to adjust quality: {result.get('error', 'Unknown error')}")
            else:
                # Use REST API
                if self.api_client:
                    quality_url = f"{self.api_base_url}/webrtc/connections/quality"
                    payload = {
                        "connection_id": connection_id,
                        "quality": new_quality
                    }

                    try:
                        response = self.api_client.post(quality_url, json=payload)
                        if response.status_code == 200:
                            result = response.json()
                            if result.get("success", False):
                                logger.info(f"Successfully adjusted quality for {connection_id} to {new_quality}")

                                # Update metrics
                                if self.enable_metrics and hasattr(self, 'metrics'):
                                    self.metrics.quality_switches.labels(
                                        connection_id=connection_id,
                                        from_quality=current_quality,
                                        to_quality=new_quality
                                    ).inc()

                                    # Record reason for adaptive bitrate switch
                                    self.metrics.abr_switches.labels(
                                        connection_id=connection_id,
                                        reason="auto"
                                    ).inc()

                                # Store current quality in history
                                if connection_id in self.metrics_history["connections"]:
                                    self.metrics_history["connections"][connection_id]["current_quality"] = new_quality
                            else:
                                logger.warning(f"Failed to adjust quality: {result.get('error', 'Unknown error')}")
                        else:
                            logger.warning(f"Failed to adjust quality: HTTP {response.status_code}")
                    except Exception as e:
                        logger.error(f"Error adjusting quality via API: {e}")

        except Exception as e:
            logger.error(f"Error optimizing connection {connection_id}: {e}")

    async def optimize_buffer(self, connection_id):
        """
        Optimize buffer settings for a connection.

        Args:
            connection_id: ID of the connection
        """
        try:
            # This would require a new API endpoint to adjust buffer settings
            # For now, just log the need for buffer optimization
            logger.info(f"Buffer optimization needed for connection {connection_id}")

            # In a real implementation, we would adjust buffer size, prefetch threshold, etc.
            # based on network conditions and playback requirements
        except Exception as e:
            logger.error(f"Error optimizing buffer for {connection_id}: {e}")

    def update_visualizations(self):
        """Update visualization dashboards."""
        if not HAS_VISUALIZATION or not self.config["visualization"]["enabled"]:
            return

        try:
            # Create visualizations directory if it doesn't exist
            viz_dir = os.path.join(self.report_path, "visualizations")
            os.makedirs(viz_dir, exist_ok=True)

            # Set matplotlib style
            plt.style.use(self.config["visualization"]["plot_style"])

            # Generate visualizations
            self.create_connection_dashboard(viz_dir)
            self.create_performance_dashboard(viz_dir)

            logger.debug("Updated visualizations")
        except Exception as e:
            logger.error(f"Error updating visualizations: {e}")

    def create_connection_dashboard(self, output_dir):
        """
        Create dashboard of connection metrics.

        Args:
            output_dir: Output directory for visualization files
        """
        if not self.metrics_history["connections"]:
            return

        try:
            # Create a figure with multiple subplots
            fig, axs = plt.subplots(3, 2, figsize=(15, 10))
            fig.suptitle('WebRTC Connection Dashboard', fontsize=16)

            # Only use the first connection for example
            connection_id = next(iter(self.metrics_history["connections"].keys()))
            history = self.metrics_history["connections"][connection_id]
            timestamps = self.metrics_history["timestamps"][-len(history["bandwidth"]["outbound"]):]

            # Plot bandwidth
            ax = axs[0, 0]
            if history["bandwidth"]["outbound"]:
                ax.plot(timestamps, history["bandwidth"]["outbound"], label="Outbound")
            if history["bandwidth"]["inbound"]:
                ax.plot(timestamps, history["bandwidth"]["inbound"], label="Inbound")
            ax.set_title(f"Bandwidth (Connection: {connection_id[:8]}...)")
            ax.set_ylabel("Kbps")
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Plot packet loss
            ax = axs[0, 1]
            if history["packet_loss"]["outbound"]:
                ax.plot(timestamps, history["packet_loss"]["outbound"], label="Outbound")
            if history["packet_loss"]["inbound"]:
                ax.plot(timestamps, history["packet_loss"]["inbound"], label="Inbound")
            ax.set_title("Packet Loss")
            ax.set_ylabel("Percentage")
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Plot frame rate
            ax = axs[1, 0]
            if history["frame_rate"]["video"]:
                ax.plot(timestamps, history["frame_rate"]["video"], label="Video")
            if history["frame_rate"]["audio"]:
                ax.plot(timestamps, history["frame_rate"]["audio"], label="Audio")
            ax.set_title("Frame Rate")
            ax.set_ylabel("FPS")
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Plot buffer level
            ax = axs[1, 1]
            if history["buffer_level"]["video"]:
                ax.plot(timestamps, history["buffer_level"]["video"], label="Video")
            if history["buffer_level"]["audio"]:
                ax.plot(timestamps, history["buffer_level"]["audio"], label="Audio")
            ax.set_title("Buffer Level")
            ax.set_ylabel("Frames")
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Plot latency
            ax = axs[2, 0]
            if history["latency"]["signaling"]:
                ax.plot(timestamps, history["latency"]["signaling"], label="Signaling")
            if history["latency"]["media"]:
                ax.plot(timestamps, history["latency"]["media"], label="Media")
            ax.set_title("Latency")
            ax.set_ylabel("Milliseconds")
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Plot quality
            ax = axs[2, 1]
            if history["quality"]["score"]:
                ax.plot(timestamps, history["quality"]["score"], label="Quality Score")
            if history["quality"]["health_score"]:
                ax.plot(timestamps, history["quality"]["health_score"], label="Health Score")
            ax.set_title("Stream Quality")
            ax.set_ylabel("Score (0-100)")
            ax.legend()
            ax.grid(True, alpha=0.3)

            # Adjust layout
            plt.tight_layout(rect=[0, 0, 1, 0.95])

            # Save figure
            dashboard_path = os.path.join(output_dir, "connection_dashboard.png")
            plt.savefig(dashboard_path, dpi=120)
            plt.close(fig)

            logger.debug(f"Created connection dashboard: {dashboard_path}")

        except Exception as e:
            logger.error(f"Error creating connection dashboard: {e}")

    def create_performance_dashboard(self, output_dir):
        """
        Create dashboard of performance metrics.

        Args:
            output_dir: Output directory for visualization files
        """
        try:
            # Create a figure with multiple subplots
            fig, axs = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('WebRTC Performance Dashboard', fontsize=16)

            # Get global history data
            global_history = self.metrics_history["global"]
            timestamps = self.metrics_history["timestamps"]

            # Ensure timestamps and data points match in length
            data_length = min(len(timestamps), len(global_history["active_connections"]))
            plot_timestamps = timestamps[-data_length:] if data_length > 0 else []

            # Plot active connections
            ax = axs[0, 0]
            if global_history["active_connections"] and plot_timestamps:
                ax.plot(plot_timestamps, global_history["active_connections"][-data_length:])
            ax.set_title("Active Connections")
            ax.set_ylabel("Count")
            ax.grid(True, alpha=0.3)

            # Plot bandwidth usage
            ax = axs[0, 1]
            if global_history["bandwidth_usage"] and plot_timestamps:
                ax.plot(plot_timestamps, global_history["bandwidth_usage"][-data_length:])
            ax.set_title("Average Bandwidth Usage")
            ax.set_ylabel("Kbps")
            ax.grid(True, alpha=0.3)

            # Plot buffer level
            ax = axs[1, 0]
            if global_history["buffer_level"] and plot_timestamps:
                ax.plot(plot_timestamps, global_history["buffer_level"][-data_length:])
            ax.set_title("Average Buffer Level")
            ax.set_ylabel("Frames")
            ax.grid(True, alpha=0.3)

            # Plot quality score
            ax = axs[1, 1]
            if global_history["quality_score"] and plot_timestamps:
                ax.plot(plot_timestamps, global_history["quality_score"][-data_length:])
            ax.set_title("Average Quality Score")
            ax.set_ylabel("Score (0-100)")
            ax.grid(True, alpha=0.3)

            # Adjust layout
            plt.tight_layout(rect=[0, 0, 1, 0.95])

            # Save figure
            dashboard_path = os.path.join(output_dir, "performance_dashboard.png")
            plt.savefig(dashboard_path, dpi=120)
            plt.close(fig)

            logger.debug(f"Created performance dashboard: {dashboard_path}")

        except Exception as e:
            logger.error(f"Error creating performance dashboard: {e}")

    def stop(self):
        """Stop WebRTC monitoring."""
        if not self.running:
            logger.warning("Monitor is not running")
            return False

        logger.info("Stopping WebRTC Monitor Integration")
        self.running = False

        # Cancel polling task
        if self.poll_task:
            try:
                # Different cancellation methods depending on task type
                if hasattr(self.poll_task, 'cancel'):
                    self.poll_task.cancel()
                self.poll_task = None
            except Exception as e:
                logger.error(f"Error cancelling poll task: {e}")

        # Cancel visualization task
        if self.visualization_task:
            try:
                if hasattr(self.visualization_task, 'cancel'):
                    self.visualization_task.cancel()
                self.visualization_task = None
            except Exception as e:
                logger.error(f"Error cancelling visualization task: {e}")

        logger.info("WebRTC Monitor Integration stopped")
        return True

    def get_status(self):
        """Get monitoring status."""
        return {
            "running": self.running,
            "poll_interval": self.poll_interval,
            "metrics_enabled": self.enable_metrics,
            "optimization_enabled": self.enable_optimization,
            "auto_adjust_quality": self.auto_adjust_quality,
            "connection_count": len(self.metrics_history["connections"]),
            "metrics_history_points": len(self.metrics_history["timestamps"]),
            "visualization_enabled": HAS_VISUALIZATION and self.config["visualization"]["enabled"],
            "visualization_interval": self.visualization_interval,
            "prometheus_port": self.metrics_port if self.enable_metrics else None
        }

    def export_metrics_history(self, format="json"):
        """
        Export metrics history.

        Args:
            format: Export format ("json" or "csv")

        Returns:
            Path to exported file
        """
        try:
            # Create reports directory if it doesn't exist
            os.makedirs(self.report_path, exist_ok=True)

            # Export timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")

            if format == "json":
                # Export to JSON
                output_path = os.path.join(self.report_path, f"metrics_history_{timestamp}.json")
                with open(output_path, 'w') as f:
                    json.dump(self.metrics_history, f, indent=2)

                logger.info(f"Exported metrics history to {output_path}")
                return output_path

            elif format == "csv" and HAS_VISUALIZATION:
                # Export to CSV using pandas
                output_path = os.path.join(self.report_path, f"metrics_history_{timestamp}.csv")

                # Convert to DataFrame
                data = {
                    "timestamp": self.metrics_history["timestamps"]
                }

                # Add global metrics
                for key, values in self.metrics_history["global"].items():
                    data[f"global_{key}"] = values

                # Add server metrics (first server only for simplicity)
                if self.metrics_history["servers"]:
                    server_id = next(iter(self.metrics_history["servers"].keys()))
                    for key, values in self.metrics_history["servers"][server_id].items():
                        data[f"server_{key}"] = values

                # Add connection metrics (first connection only for simplicity)
                if self.metrics_history["connections"]:
                    connection_id = next(iter(self.metrics_history["connections"].keys()))
                    for category, metrics in self.metrics_history["connections"][connection_id].items():
                        if isinstance(metrics, dict):
                            for key, values in metrics.items():
                                data[f"connection_{category}_{key}"] = values

                # Create DataFrame and export
                df = pd.DataFrame(data)
                df.to_csv(output_path, index=False)

                logger.info(f"Exported metrics history to {output_path}")
                return output_path

            else:
                logger.warning(f"Unsupported export format: {format}")
                return None

        except Exception as e:
            logger.error(f"Error exporting metrics history: {e}")
            return None

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="WebRTC Monitor Integration for MCP Server")

    # MCP server options
    parser.add_argument("--mcp-host", default="localhost", help="MCP server host")
    parser.add_argument("--mcp-port", type=int, default=8000, help="MCP server port")

    # Metrics options
    parser.add_argument("--metrics-port", type=int, default=9090, help="Prometheus metrics server port")
    parser.add_argument("--disable-metrics", action="store_true", help="Disable Prometheus metrics")

    # Optimization options
    parser.add_argument("--disable-optimization", action="store_true", help="Disable streaming optimization")
    parser.add_argument("--disable-auto-quality", action="store_true", help="Disable automatic quality adjustment")

    # Polling options
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Metrics polling interval in seconds")
    parser.add_argument("--visualization-interval", type=float, default=30.0, help="Visualization update interval in seconds")

    # Output options
    parser.add_argument("--report-path", default="./reports", help="Path for reports and visualizations")
    parser.add_argument("--config-path", help="Path to configuration file")

    # Run options
    parser.add_argument("--daemon", action="store_true", help="Run as daemon (background)")

    return parser.parse_args()

async def run_monitor(monitor):
    """Run the monitor until interrupted."""
    try:
        # Start monitoring
        monitor.start()

        # Keep running until interrupted
        while True:
            await anyio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Stop monitoring
        monitor.stop()

        # Export metrics history at exit
        if monitor.config["reporting"]["save_raw_data"]:
            monitor.export_metrics_history()

def main():
    """Main function."""
    # Parse command line arguments
    args = parse_args()

    # Create monitor
    monitor = WebRTCMonitorIntegration(
        mcp_host=args.mcp_host,
        mcp_port=args.mcp_port,
        metrics_port=args.metrics_port,
        enable_metrics=not args.disable_metrics,
        enable_optimization=not args.disable_optimization,
        auto_adjust_quality=not args.disable_auto_quality,
        poll_interval=args.poll_interval,
        visualization_interval=args.visualization_interval,
        report_path=args.report_path,
        config_path=args.config_path
    )

    if args.daemon:
        # Run as daemon
        logger.info("Starting WebRTC monitor in daemon mode")

        # Create a background thread
        import threading
        def run_in_thread():
            anyio.run(run_monitor(monitor))

        thread = threading.Thread(target=run_in_thread, daemon=True)
        thread.start()

        # Return to allow importing as a module
        return monitor
    else:
        # Run interactively
        logger.info("Starting WebRTC monitor in interactive mode")
        logger.info("Press Ctrl+C to stop")

        # Run until interrupted
        anyio.run(run_monitor(monitor))

        logger.info("WebRTC monitor stopped")

if __name__ == "__main__":
    main()
