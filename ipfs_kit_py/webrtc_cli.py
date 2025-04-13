#!/usr/bin/env python3
# ipfs_kit_py/webrtc_cli.py

"""
Command-line interface for WebRTC streaming and benchmarking.

This module provides commands for WebRTC-related operations including:
- Streaming content over WebRTC
- Conducting performance benchmarks
- Managing streaming connections
- Configuring WebRTC settings
"""

import os
import sys
import time
import json
import logging
import argparse
import textwrap
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from .webrtc_streaming import WebRTCStreamingManager, check_webrtc_dependencies, HAVE_WEBRTC
    from .webrtc_benchmark import WebRTCBenchmark, WebRTCStreamingManagerBenchmarkIntegration
except ImportError:
    # Allow running as a standalone script
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py.webrtc_streaming import WebRTCStreamingManager, check_webrtc_dependencies, HAVE_WEBRTC
    from ipfs_kit_py.webrtc_benchmark import WebRTCBenchmark, WebRTCStreamingManagerBenchmarkIntegration

# Terminal colors for better readability
class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    @staticmethod
    def supports_color():
        """Check if the terminal supports color output."""
        plat = sys.platform
        supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
        is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        return supported_platform and is_a_tty

# Disable colors if terminal doesn't support them
if not Colors.supports_color():
    for attr in dir(Colors):
        if not attr.startswith('__') and isinstance(getattr(Colors, attr), str):
            setattr(Colors, attr, '')

def create_table(headers: List[str], rows: List[List[Any]], title: Optional[str] = None) -> str:
    """Create a formatted ASCII table."""
    if not rows:
        return "No data available"
        
    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Create separator line
    sep_line = "+"
    for width in col_widths:
        sep_line += "-" * (width + 2) + "+"
    
    # Create header row
    header_row = "|"
    for i, header in enumerate(headers):
        header_row += f" {Colors.BOLD}{header}{Colors.ENDC}".ljust(col_widths[i] + 2) + "|"
    
    # Create data rows
    data_rows = []
    for row in rows:
        data_row = "|"
        for i, cell in enumerate(row):
            if i < len(col_widths):
                data_row += f" {cell}".ljust(col_widths[i] + 2) + "|"
        data_rows.append(data_row)
    
    # Assemble table
    table = []
    if title:
        # Center title over table
        table_width = len(sep_line)
        centered_title = title.center(table_width)
        table.append(f"{Colors.HEADER}{Colors.BOLD}{centered_title}{Colors.ENDC}")
        table.append("")
    
    table.append(sep_line)
    table.append(header_row)
    table.append(sep_line)
    for row in data_rows:
        table.append(row)
    table.append(sep_line)
    
    return "\n".join(table)

def handle_stream_content_command(args, api):
    """Handle the 'stream' command to stream IPFS content over WebRTC."""
    if not HAVE_WEBRTC:
        print(f"{Colors.RED}WebRTC dependencies are not available. Install them with: pip install ipfs_kit_py[webrtc]{Colors.ENDC}")
        print(f"\nRequired dependencies:")
        deps = check_webrtc_dependencies()
        for dep_name, available in deps.get("dependencies", {}).items():
            status = f"{Colors.GREEN}Available{Colors.ENDC}" if available else f"{Colors.RED}Missing{Colors.ENDC}"
            print(f"  - {dep_name}: {status}")
        return 1
    
    # Extract arguments
    cid = args.cid
    listen_address = args.address
    port = args.port
    quality = args.quality
    ice_servers = args.ice_servers
    benchmark = args.benchmark
    
    try:
        # Parse ice servers if provided
        if ice_servers:
            try:
                ice_servers = json.loads(ice_servers)
            except json.JSONDecodeError:
                print(f"{Colors.RED}Invalid ice_servers format. Must be a valid JSON array of objects.{Colors.ENDC}")
                print("Example: '[{\"urls\": [\"stun:stun.l.google.com:19302\"]}]'")
                return 1
        
        # Create streaming manager
        print(f"{Colors.CYAN}Initializing WebRTC streaming for IPFS content: {cid}{Colors.ENDC}")
        result = api.stream_content_webrtc(
            cid=cid,
            listen_address=listen_address,
            port=port,
            quality=quality,
            ice_servers=ice_servers,
            enable_benchmark=benchmark
        )
        
        if result.get("success", False):
            # Display information about streaming server
            url = result.get("url")
            print(f"\n{Colors.GREEN}WebRTC streaming server started successfully!{Colors.ENDC}")
            print(f"\nStreaming URL: {Colors.CYAN}{url}{Colors.ENDC}")
            print(f"Content CID: {cid}")
            print(f"Quality preset: {quality}")
            
            # Display connection info
            print(f"\n{Colors.HEADER}Connection Information{Colors.ENDC}")
            print(f"Listen address: {listen_address}")
            print(f"Port: {port}")
            
            if benchmark:
                print(f"\n{Colors.YELLOW}Performance benchmarking enabled - results will be saved to ~/.ipfs_kit/webrtc_benchmarks/{Colors.ENDC}")
            
            print(f"\n{Colors.YELLOW}Press Ctrl+C to stop streaming{Colors.ENDC}")
            
            # Wait for user to stop the server
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Stopping WebRTC streaming server...{Colors.ENDC}")
                shutdown_result = api.stop_webrtc_streaming(server_id=result.get("server_id"))
                if shutdown_result.get("success", False):
                    print(f"{Colors.GREEN}Streaming server stopped successfully.{Colors.ENDC}")
                else:
                    print(f"{Colors.RED}Error stopping streaming server: {shutdown_result.get('error', 'Unknown error')}{Colors.ENDC}")
        else:
            print(f"{Colors.RED}Failed to start WebRTC streaming: {result.get('error', 'Unknown error')}{Colors.ENDC}")
            return 1
        
    except Exception as e:
        print(f"{Colors.RED}Error: {str(e)}{Colors.ENDC}")
        return 1
    
    return 0

def handle_benchmark_command(args, api):
    """Handle the 'benchmark' command to run WebRTC performance benchmarks."""
    if not HAVE_WEBRTC:
        print(f"{Colors.RED}WebRTC dependencies are not available. Install them with: pip install ipfs_kit_py[webrtc]{Colors.ENDC}")
        return 1
    
    # Extract arguments
    cid = args.cid
    duration = args.duration
    output_dir = args.output_dir
    report_format = args.format
    compare_with = args.compare_with
    
    try:
        # Run benchmark
        print(f"{Colors.CYAN}Running WebRTC streaming benchmark for CID: {cid}{Colors.ENDC}")
        print(f"Duration: {duration} seconds")
        
        result = api.run_webrtc_benchmark(
            cid=cid,
            duration_seconds=duration,
            output_dir=output_dir,
            report_format=report_format
        )
        
        if result.get("success", False):
            benchmark_id = result.get("benchmark_id")
            report_path = result.get("report_path")
            
            print(f"\n{Colors.GREEN}Benchmark completed successfully!{Colors.ENDC}")
            print(f"Benchmark ID: {benchmark_id}")
            
            # Display summary results
            summary = result.get("summary", {})
            if summary:
                headers = ["Metric", "Value"]
                rows = []
                
                # Extract key metrics
                for metric, value in summary.items():
                    if metric in ["avg_rtt_ms", "avg_jitter_ms", "avg_end_to_end_latency_ms", 
                                  "p95_latency_ms", "avg_bitrate_kbps", "throughput_mbps", 
                                  "avg_frames_per_second", "avg_quality_score"]:
                        rows.append([metric, value])
                
                print("\n" + create_table(headers, rows, "Benchmark Summary"))
            
            # Display report path
            if report_path:
                print(f"\nDetailed report saved to: {Colors.CYAN}{report_path}{Colors.ENDC}")
            
            # Compare with previous benchmark if requested
            if compare_with:
                print(f"\n{Colors.CYAN}Comparing with previous benchmark: {compare_with}{Colors.ENDC}")
                compare_result = api.compare_webrtc_benchmarks(
                    benchmark1=compare_with,
                    benchmark2=benchmark_id
                )
                
                if compare_result.get("success", False):
                    # Display comparison summary
                    comparison = compare_result.get("comparison", {})
                    if comparison:
                        # Display regressions if any
                        regressions = compare_result.get("regressions", [])
                        improvements = compare_result.get("improvements", [])
                        
                        if regressions:
                            print(f"\n{Colors.RED}Regressions detected:{Colors.ENDC}")
                            for metric in regressions:
                                detail = comparison.get(metric, {})
                                print(f"  - {metric}: {detail.get('baseline')} → {detail.get('current')} ({detail.get('percent_change', 0):.2f}%)")
                        
                        if improvements:
                            print(f"\n{Colors.GREEN}Improvements detected:{Colors.ENDC}")
                            for metric in improvements:
                                detail = comparison.get(metric, {})
                                print(f"  - {metric}: {detail.get('baseline')} → {detail.get('current')} ({detail.get('percent_change', 0):.2f}%)")
                        
                        if not regressions and not improvements:
                            print(f"\n{Colors.CYAN}No significant changes detected{Colors.ENDC}")
                else:
                    print(f"{Colors.RED}Failed to compare benchmarks: {compare_result.get('error', 'Unknown error')}{Colors.ENDC}")
        else:
            print(f"{Colors.RED}Failed to run benchmark: {result.get('error', 'Unknown error')}{Colors.ENDC}")
            return 1
        
    except Exception as e:
        print(f"{Colors.RED}Error: {str(e)}{Colors.ENDC}")
        return 1
    
    return 0

def handle_connections_command(args, api):
    """Handle the 'connections' command to manage WebRTC connections."""
    if not HAVE_WEBRTC:
        print(f"{Colors.RED}WebRTC dependencies are not available. Install them with: pip install ipfs_kit_py[webrtc]{Colors.ENDC}")
        return 1
    
    # Get active connections
    try:
        if args.action == "list":
            # List active connections
            result = api.list_webrtc_connections()
            
            if result.get("success", False):
                connections = result.get("connections", [])
                
                if connections:
                    headers = ["ID", "Status", "Created", "Tracks", "Quality"]
                    rows = []
                    
                    for conn in connections:
                        rows.append([
                            conn.get("id", "unknown"),
                            conn.get("status", "unknown"),
                            conn.get("created_at", "unknown"),
                            len(conn.get("tracks", [])),
                            conn.get("quality", "auto")
                        ])
                    
                    print(create_table(headers, rows, "Active WebRTC Connections"))
                else:
                    print(f"{Colors.YELLOW}No active WebRTC connections{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Failed to list connections: {result.get('error', 'Unknown error')}{Colors.ENDC}")
                return 1
        
        elif args.action == "stats":
            # Get detailed stats for a connection
            connection_id = args.id
            if not connection_id:
                print(f"{Colors.RED}Connection ID is required for stats{Colors.ENDC}")
                return 1
            
            result = api.get_webrtc_connection_stats(connection_id=connection_id)
            
            if result.get("success", False):
                stats = result.get("stats", {})
                
                if stats:
                    # Display general connection info
                    print(f"{Colors.HEADER}{Colors.BOLD}WebRTC Connection Stats: {connection_id}{Colors.ENDC}")
                    print(f"Connection State: {stats.get('connection_state', 'unknown')}")
                    print(f"ICE State: {stats.get('ice_state', 'unknown')}")
                    print(f"Uptime: {stats.get('uptime', 0):.2f} seconds")
                    
                    # Display network stats
                    network_stats = stats.get("network", {})
                    if network_stats:
                        headers = ["Metric", "Value"]
                        rows = [
                            ["RTT", f"{network_stats.get('rtt', 0):.2f} ms"],
                            ["Jitter", f"{network_stats.get('jitter', 0):.2f} ms"],
                            ["Packet Loss", f"{network_stats.get('packet_loss', 0) * 100:.2f}%"],
                            ["Bitrate", f"{network_stats.get('bitrate', 0) / 1000:.2f} kbps"],
                            ["Available Bandwidth", f"{network_stats.get('available_bandwidth', 0) / 1000:.2f} kbps"]
                        ]
                        
                        print("\n" + create_table(headers, rows, "Network Statistics"))
                    
                    # Display tracks info
                    tracks = stats.get("tracks", [])
                    if tracks:
                        headers = ["Track ID", "Kind", "Resolution", "FPS", "Status"]
                        rows = []
                        
                        for track in tracks:
                            resolution = f"{track.get('width', 0)}x{track.get('height', 0)}"
                            rows.append([
                                track.get("id", "unknown"),
                                track.get("kind", "unknown"),
                                resolution,
                                f"{track.get('fps', 0):.2f}",
                                "Active" if track.get("active", False) else "Inactive"
                            ])
                        
                        print("\n" + create_table(headers, rows, "Media Tracks"))
                else:
                    print(f"{Colors.YELLOW}No statistics available for connection: {connection_id}{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Failed to get connection stats: {result.get('error', 'Unknown error')}{Colors.ENDC}")
                return 1
        
        elif args.action == "close":
            # Close a specific connection or all connections
            connection_id = args.id
            
            if connection_id:
                # Close specific connection
                print(f"{Colors.CYAN}Closing WebRTC connection: {connection_id}{Colors.ENDC}")
                result = api.close_webrtc_connection(connection_id=connection_id)
            else:
                # Close all connections
                print(f"{Colors.CYAN}Closing all WebRTC connections{Colors.ENDC}")
                result = api.close_all_webrtc_connections()
            
            if result.get("success", False):
                print(f"{Colors.GREEN}Connection(s) closed successfully{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Failed to close connection(s): {result.get('error', 'Unknown error')}{Colors.ENDC}")
                return 1
        
        elif args.action == "quality":
            # Change connection quality
            connection_id = args.id
            quality = args.quality
            
            if not connection_id:
                print(f"{Colors.RED}Connection ID is required for quality change{Colors.ENDC}")
                return 1
            
            if not quality:
                print(f"{Colors.RED}Quality level is required (low, medium, high, or auto){Colors.ENDC}")
                return 1
            
            print(f"{Colors.CYAN}Changing quality for connection {connection_id} to: {quality}{Colors.ENDC}")
            result = api.set_webrtc_quality(
                connection_id=connection_id,
                quality=quality
            )
            
            if result.get("success", False):
                print(f"{Colors.GREEN}Quality changed successfully{Colors.ENDC}")
            else:
                print(f"{Colors.RED}Failed to change quality: {result.get('error', 'Unknown error')}{Colors.ENDC}")
                return 1
        
    except Exception as e:
        print(f"{Colors.RED}Error: {str(e)}{Colors.ENDC}")
        return 1
    
    return 0

def handle_check_dependencies_command(args, api):
    """Check WebRTC dependencies and display status."""
    # Get dependency status
    deps = check_webrtc_dependencies()
    webrtc_available = deps.get("webrtc_available", False)
    dependencies = deps.get("dependencies", {})
    
    # Display status
    print(f"{Colors.HEADER}{Colors.BOLD}WebRTC Dependency Status{Colors.ENDC}")
    print(f"Overall WebRTC availability: {'✓' if webrtc_available else '✗'}")
    
    # Create table for dependencies
    headers = ["Dependency", "Status"]
    rows = []
    
    for dep_name, available in dependencies.items():
        status = f"{Colors.GREEN}Available{Colors.ENDC}" if available else f"{Colors.RED}Missing{Colors.ENDC}"
        rows.append([dep_name, status])
    
    print("\n" + create_table(headers, rows, "Required Dependencies"))
    
    # If not available, show installation command
    if not webrtc_available:
        print(f"\n{Colors.CYAN}To install required dependencies, run:{Colors.ENDC}")
        print(f"  pip install {deps.get('installation_command', 'ipfs_kit_py[webrtc]')}")
    
    return 0

def register_webrtc_commands(subparsers):
    """
    Register WebRTC-related commands with the CLI parser.
    
    Args:
        subparsers: Subparser object from argparse
    """
    # WebRTC command group
    webrtc_parser = subparsers.add_parser(
        "webrtc",
        help="WebRTC streaming and benchmarking operations",
    )
    webrtc_subparsers = webrtc_parser.add_subparsers(
        dest="webrtc_command", 
        help="WebRTC command to execute", 
        required=True
    )
    
    # Stream content command
    stream_parser = webrtc_subparsers.add_parser(
        "stream",
        help="Stream IPFS content over WebRTC",
    )
    stream_parser.add_argument(
        "cid",
        help="CID of the IPFS content to stream",
    )
    stream_parser.add_argument(
        "--address",
        default="127.0.0.1",
        help="Address to bind the WebRTC signaling server",
    )
    stream_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for the WebRTC signaling server",
    )
    stream_parser.add_argument(
        "--quality",
        choices=["low", "medium", "high", "auto"],
        default="medium",
        help="Video quality preset for streaming",
    )
    stream_parser.add_argument(
        "--ice-servers",
        help="JSON array of ICE server objects, e.g. '[{\"urls\": [\"stun:stun.l.google.com:19302\"]}]'",
    )
    stream_parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Enable performance benchmarking",
    )
    stream_parser.set_defaults(func=lambda api, args, kwargs: api.stream_content_webrtc(**kwargs))
    
    # Benchmark command
    benchmark_parser = webrtc_subparsers.add_parser(
        "benchmark",
        help="Run WebRTC streaming performance benchmark",
    )
    benchmark_parser.add_argument(
        "cid",
        help="CID of the IPFS content to benchmark",
    )
    benchmark_parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Benchmark duration in seconds",
    )
    benchmark_parser.add_argument(
        "--output-dir",
        help="Directory to save benchmark reports",
    )
    benchmark_parser.add_argument(
        "--format",
        choices=["json", "html", "csv"],
        default="json",
        help="Report output format",
    )
    benchmark_parser.add_argument(
        "--compare-with",
        help="Previous benchmark ID to compare results with",
    )
    benchmark_parser.set_defaults(func=lambda api, args, kwargs: api.run_webrtc_benchmark(**kwargs))
    
    # WebRTC connections management
    conn_parser = webrtc_subparsers.add_parser(
        "connections",
        help="Manage WebRTC connections",
    )
    conn_subparsers = conn_parser.add_subparsers(
        dest="action",
        help="Action to perform",
        required=True
    )
    
    # List connections
    list_parser = conn_subparsers.add_parser(
        "list",
        help="List active WebRTC connections",
    )
    list_parser.set_defaults(func=lambda api, args, kwargs: api.list_webrtc_connections(**kwargs))
    
    # Connection stats
    stats_parser = conn_subparsers.add_parser(
        "stats",
        help="Get statistics for a WebRTC connection",
    )
    stats_parser.add_argument(
        "--id",
        required=True,
        help="Connection ID",
    )
    stats_parser.set_defaults(func=lambda api, args, kwargs: api.get_webrtc_connection_stats(**kwargs))
    
    # Close connection
    close_parser = conn_subparsers.add_parser(
        "close",
        help="Close WebRTC connection(s)",
    )
    close_parser.add_argument(
        "--id",
        help="Connection ID (omit to close all connections)",
    )
    close_parser.set_defaults(func=lambda api, args, kwargs: api.close_webrtc_connection(**kwargs))
    
    # Change quality
    quality_parser = conn_subparsers.add_parser(
        "quality",
        help="Change streaming quality for a connection",
    )
    quality_parser.add_argument(
        "--id",
        required=True,
        help="Connection ID",
    )
    quality_parser.add_argument(
        "--quality",
        choices=["low", "medium", "high", "auto"],
        required=True,
        help="Quality preset to use",
    )
    quality_parser.set_defaults(func=lambda api, args, kwargs: api.set_webrtc_quality(**kwargs))
    
    # Check WebRTC dependencies
    check_parser = webrtc_subparsers.add_parser(
        "check",
        help="Check WebRTC dependencies",
    )
    check_parser.set_defaults(func=lambda api, args, kwargs: api.check_webrtc_dependencies(**kwargs))


def main():
    """Main entry point for the CLI when run standalone."""
    parser = argparse.ArgumentParser(
        description="Command-line interface for WebRTC streaming and benchmarking",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              webrtc stream QmcNeBnS7K7c6GL91a5hc3pMyv8X3PxuZfFy7rVsHfEYoT --quality high
              webrtc benchmark QmcNeBnS7K7c6GL91a5hc3pMyv8X3PxuZfFy7rVsHfEYoT --duration 120
              webrtc connections list
              webrtc connections stats --id conn-123456
              webrtc check
        """)
    )
    
    # Create subparsers
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Register commands
    register_webrtc_commands(subparsers)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if command was provided
    if not hasattr(args, 'command') or not args.command:
        parser.print_help()
        return 1
    
    # Create a simple API object for standalone execution
    class SimpleAPI:
        def stream_content_webrtc(self, **kwargs):
            return {"success": False, "error": "Not implemented in standalone mode"}
        
        def run_webrtc_benchmark(self, **kwargs):
            return {"success": False, "error": "Not implemented in standalone mode"}
        
        def list_webrtc_connections(self, **kwargs):
            return {"success": False, "error": "Not implemented in standalone mode"}
        
        def get_webrtc_connection_stats(self, **kwargs):
            return {"success": False, "error": "Not implemented in standalone mode"}
        
        def close_webrtc_connection(self, **kwargs):
            return {"success": False, "error": "Not implemented in standalone mode"}
        
        def set_webrtc_quality(self, **kwargs):
            return {"success": False, "error": "Not implemented in standalone mode"}
        
        def check_webrtc_dependencies(self, **kwargs):
            return {"success": True, "dependencies": check_webrtc_dependencies()}
    
    api = SimpleAPI()
    
    # Handle commands
    if args.command == "webrtc":
        if args.webrtc_command == "stream":
            return handle_stream_content_command(args, api)
        elif args.webrtc_command == "benchmark":
            return handle_benchmark_command(args, api)
        elif args.webrtc_command == "connections":
            return handle_connections_command(args, api)
        elif args.webrtc_command == "check":
            return handle_check_dependencies_command(args, api)
    
    # If we got here, the command wasn't handled
    print(f"{Colors.RED}Unknown command: {args.command}{Colors.ENDC}")
    return 1

if __name__ == "__main__":
    sys.exit(main())