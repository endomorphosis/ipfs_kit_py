#!/usr/bin/env python3
"""
DEPRECATED: This script has been replaced by mcp_server_runner.py

This file is kept for reference only. Please use the new consolidated script instead.
See the README.md file for more information about the consolidated files.
"""

# Original content follows:

"""
DEPRECATED: This script has been replaced by server_runner.py

This file is kept for backward compatibility. Please use the unified server runner instead,
which provides comprehensive server capabilities including metrics, WebRTC monitoring, and more:

    python server_runner.py --server-type=anyio --metrics-enabled --webrtc-enabled

The server runner supports all enhanced configurations with additional options.
"""

import sys
import os
import subprocess
import warnings

def main():
    """Run the enhanced MCP server with WebRTC monitor using the new server_runner."""
    # Show deprecation warning
    warnings.warn(
        "run_enhanced_mcp_server_with_monitor.py is deprecated and will be removed in a future version. "
        "Please use server_runner.py instead.",
        DeprecationWarning, stacklevel=2
    )

    print("Starting enhanced MCP server with WebRTC monitor using the new server_runner module...")

    # Check if server_runner.py exists
    server_runner_path = os.path.join(os.path.dirname(__file__), "server_runner.py")
    if not os.path.exists(server_runner_path):
        print("ERROR: server_runner.py not found. Please make sure it's in the same directory.")
        return 1

    # Parse the original arguments to ensure we maintain compatibility
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced MCP Server with WebRTC Monitor")

    # MCP server options
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

    # Parse the original arguments
    args = parser.parse_args()

    # Build command for server_runner.py with equivalent parameters
    cmd = [
        sys.executable,
        server_runner_path,
        "--server-type=anyio",
        f"--host={args.host}",
        f"--port={args.port}"
    ]

    # Add debug and isolation parameters if specified
    if args.debug:
        cmd.append("--debug")

    if args.isolation:
        cmd.append("--isolation")

    # Add persistence path if specified
    if args.persistence_path:
        cmd.append(f"--persistence-path={args.persistence_path}")

    # Add metrics configuration
    if not args.disable_metrics:
        cmd.append("--metrics-enabled")

    # Add WebRTC configuration
    if not args.disable_webrtc_monitor:
        cmd.append("--webrtc-enabled")

    # Add watch mode if reload is specified
    if args.reload:
        cmd.append("--watch-mode")

    # Run server_runner
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print("\nStopping enhanced MCP server with WebRTC monitor...")
        return 0
    except Exception as e:
        print(f"Error running server: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
