#!/usr/bin/env python3
"""
Run Enhanced MCP Server with WebRTC Monitor Integration.

This script launches the enhanced MCP server with WebRTC monitoring capabilities,
providing real-time performance metrics, streaming optimization, and a
Prometheus metrics endpoint for monitoring dashboards.
"""

import os
import sys
import time
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("enhanced_mcp_server.log")
    ]
)
logger = logging.getLogger(__name__)

# Import required components
try:
    # Import from local module
    from run_enhanced_mcp_server import EnhancedMCPServer, parse_args as parse_mcp_args
    from webrtc_monitor_integration import WebRTCMonitorIntegration
    
    HAS_REQUIRED_MODULES = True
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure run_enhanced_mcp_server.py and webrtc_monitor_integration.py exist")
    HAS_REQUIRED_MODULES = False

def parse_args():
    """Parse command line arguments, combining MCP args with monitor args."""
    parser = argparse.ArgumentParser(description="Enhanced MCP Server with WebRTC Monitor")
    
    # MCP server options (reusing from run_enhanced_mcp_server.py)
    mcp_group = parser.add_argument_group('MCP Server Options')
    mcp_group.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    mcp_group.add_argument("--port", type=int, default=8000, help="Port to listen on")
    mcp_group.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    mcp_group.add_argument("--debug", action="store_true", help="Enable debug mode")
    mcp_group.add_argument("--isolation", action="store_true", help="Use isolated storage for IPFS operations")
    mcp_group.add_argument("--persistence-path", help="Path for persistence files")
    mcp_group.add_argument("--disable-metrics", action="store_true", help="Disable Prometheus metrics export")
    mcp_group.add_argument("--metrics-path", default="/metrics", help="Path for Prometheus metrics endpoint")
    mcp_group.add_argument("--parquet-cache-path", help="Path for ParquetCIDCache storage")
    mcp_group.add_argument("--memory-cache-size", type=int, help="Memory cache size in bytes")
    mcp_group.add_argument("--disk-cache-size", type=int, help="Disk cache size in bytes")
    
    # WebRTC monitor options
    monitor_group = parser.add_argument_group('WebRTC Monitor Options')
    monitor_group.add_argument("--disable-webrtc-monitor", action="store_true", help="Disable WebRTC monitor")
    monitor_group.add_argument("--webrtc-metrics-port", type=int, default=9090, help="WebRTC metrics server port")
    monitor_group.add_argument("--disable-webrtc-metrics", action="store_true", help="Disable WebRTC metrics export")
    monitor_group.add_argument("--disable-optimization", action="store_true", help="Disable streaming optimization")
    monitor_group.add_argument("--disable-auto-quality", action="store_true", help="Disable automatic quality adjustment")
    monitor_group.add_argument("--poll-interval", type=float, default=2.0, help="WebRTC metrics polling interval in seconds")
    monitor_group.add_argument("--visualization-interval", type=float, default=30.0, help="Visualization update interval in seconds")
    monitor_group.add_argument("--report-path", default="./webrtc_reports", help="Path for WebRTC reports and visualizations")
    monitor_group.add_argument("--webrtc-config-path", help="Path to WebRTC monitor configuration file")
    
    return parser.parse_args()

def run_server_with_monitor():
    """Run the enhanced MCP server with WebRTC monitor integration."""
    if not HAS_REQUIRED_MODULES:
        sys.exit(1)
    
    # Parse arguments
    args = parse_args()
    
    try:
        # Build cache configuration
        cache_config = {}
        if args.memory_cache_size:
            cache_config["memory_cache_size"] = args.memory_cache_size
        if args.disk_cache_size:
            cache_config["disk_cache_size"] = args.disk_cache_size
        
        # Log configuration
        logger.info("Starting Enhanced MCP Server with WebRTC Monitor Integration")
        logger.info(f"Server: host={args.host}, port={args.port}, debug={args.debug}, isolation={args.isolation}")
        logger.info(f"WebRTC Monitor: enabled={not args.disable_webrtc_monitor}, metrics_port={args.webrtc_metrics_port}")
        
        # Create and start enhanced MCP server
        server = EnhancedMCPServer(
            debug_mode=args.debug,
            isolation_mode=args.isolation,
            persistence_path=args.persistence_path,
            enable_metrics=not args.disable_metrics,
            metrics_path=args.metrics_path,
            parquet_cache_path=args.parquet_cache_path,
            cache_config=cache_config
        )
        
        # Start WebRTC monitor if enabled
        monitor = None
        if not args.disable_webrtc_monitor:
            logger.info("Initializing WebRTC Monitor")
            
            # Create WebRTC monitor with direct integration to MCP server
            monitor = WebRTCMonitorIntegration(
                mcp_server=server.mcp_server,  # Direct integration
                mcp_host=args.host,
                mcp_port=args.port,
                metrics_port=args.webrtc_metrics_port,
                enable_metrics=not args.disable_webrtc_metrics,
                enable_optimization=not args.disable_optimization,
                auto_adjust_quality=not args.disable_auto_quality,
                poll_interval=args.poll_interval,
                visualization_interval=args.visualization_interval,
                report_path=args.report_path,
                config_path=args.webrtc_config_path
            )
            
            # Start the monitor
            monitor.start()
            logger.info("WebRTC Monitor started")
        
        # Run the server
        try:
            # Notify user that server is starting
            print(f"\nEnhanced MCP Server with WebRTC Monitor starting at: http://{args.host}:{args.port}")
            print(f"API Docs available at: http://{args.host}:{args.port}/docs")
            if not args.disable_metrics:
                print(f"MCP Metrics available at: http://{args.host}:{args.port}{args.metrics_path}")
            if not args.disable_webrtc_monitor and not args.disable_webrtc_metrics:
                print(f"WebRTC Metrics available at: http://{args.host}:{args.port+1090}")
            print("\nPress Ctrl+C to stop the server\n")
            
            # Run the server
            server.run_server(
                host=args.host,
                port=args.port,
                reload=args.reload
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Error running server: {e}")
        finally:
            # Stop the monitor if it was started
            if monitor:
                logger.info("Stopping WebRTC Monitor")
                monitor.stop()
    
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_server_with_monitor()