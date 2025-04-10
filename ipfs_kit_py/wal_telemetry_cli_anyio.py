#!/usr/bin/env python3
# ipfs_kit_py/wal_telemetry_cli_anyio.py

"""
Command-line interface for WAL telemetry metrics with AnyIO support.

This module provides a command-line interface for accessing telemetry metrics,
generating reports, and visualizing performance data from the WAL system,
with support for different async backends through AnyIO.
"""

import os
import sys
import time
import json
import logging
import argparse
import textwrap
import datetime
import webbrowser
from typing import Dict, Any, List, Optional, Tuple, Union

# Import AnyIO for backend-agnostic async I/O
import anyio
import sniffio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from .wal_telemetry_client_anyio import WALTelemetryClientAnyIO as WALTelemetryClient
    from .wal_telemetry_client_anyio import TelemetryMetricType, TelemetryAggregation
    from .wal import WAL
except ImportError:
    # Allow running as a standalone script
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ipfs_kit_py.wal_telemetry_client_anyio import WALTelemetryClientAnyIO as WALTelemetryClient
    from ipfs_kit_py.wal_telemetry_client_anyio import TelemetryMetricType, TelemetryAggregation
    from ipfs_kit_py.wal import WAL

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

def format_metric_value(metric_type: str, value: Any) -> str:
    """Format metric value for display based on metric type."""
    if value is None:
        return "N/A"
        
    if isinstance(value, dict):
        # Extract value from common formats
        if "average" in value:
            value = value["average"]
        elif "value" in value:
            value = value["value"]
            
    # Format based on metric type
    if metric_type in ["success_rate", "error_rate"]:
        if isinstance(value, (int, float)):
            return f"{value * 100:.2f}%"
    elif metric_type == "operation_latency":
        if isinstance(value, (int, float)):
            return f"{value:.2f} ms"
    elif metric_type == "throughput":
        if isinstance(value, (int, float)):
            return f"{value:.2f} ops/sec"
            
    # Default formatting
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)

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

def print_metrics_table(metrics: Dict[str, Any], metric_filter: Optional[List[str]] = None) -> None:
    """Print metrics in a formatted table."""
    # Prepare headers and rows
    headers = ["Metric", "Value", "Details"]
    rows = []
    
    # Filter metrics if specified
    display_metrics = {}
    if metric_filter:
        for metric_name in metric_filter:
            if metric_name in metrics:
                display_metrics[metric_name] = metrics[metric_name]
    else:
        display_metrics = metrics
    
    # Operation count gets special handling
    if "operation_count" in display_metrics:
        op_count = display_metrics.pop("operation_count")
        if isinstance(op_count, dict):
            total = sum(count for count in op_count.values() if isinstance(count, (int, float)))
            rows.append([
                f"{Colors.CYAN}operation_count{Colors.ENDC}",
                f"{Colors.GREEN}{total}{Colors.ENDC}",
                "Total operations"
            ])
            # Add rows for each operation type
            for op_type, count in op_count.items():
                rows.append([
                    f"  {op_type}",
                    count,
                    f"{(count / total * 100):.1f}% of total" if total > 0 else "N/A"
                ])
    
    # Add other metrics
    for metric_name, value in display_metrics.items():
        # Format value for display
        display_value = format_metric_value(metric_name, value)
        
        # Add color based on metric type
        colored_name = f"{Colors.CYAN}{metric_name}{Colors.ENDC}"
        
        if metric_name == "success_rate":
            if isinstance(value, dict) and "value" in value:
                success_value = value["value"]
            elif isinstance(value, (int, float)):
                success_value = value
            else:
                success_value = None
                
            if success_value is not None:
                if success_value >= 0.98:
                    colored_value = f"{Colors.GREEN}{display_value}{Colors.ENDC}"
                elif success_value >= 0.9:
                    colored_value = f"{Colors.YELLOW}{display_value}{Colors.ENDC}"
                else:
                    colored_value = f"{Colors.RED}{display_value}{Colors.ENDC}"
            else:
                colored_value = display_value
                
        elif metric_name == "error_rate":
            if isinstance(value, dict) and "value" in value:
                error_value = value["value"]
            elif isinstance(value, (int, float)):
                error_value = value
            else:
                error_value = None
                
            if error_value is not None:
                if error_value <= 0.01:
                    colored_value = f"{Colors.GREEN}{display_value}{Colors.ENDC}"
                elif error_value <= 0.05:
                    colored_value = f"{Colors.YELLOW}{display_value}{Colors.ENDC}"
                else:
                    colored_value = f"{Colors.RED}{display_value}{Colors.ENDC}"
            else:
                colored_value = display_value
                
        else:
            colored_value = display_value
        
        # Add details if available
        details = ""
        if isinstance(value, dict):
            additional_info = []
            if "min" in value:
                additional_info.append(f"Min: {format_metric_value(metric_name, value['min'])}")
            if "max" in value:
                additional_info.append(f"Max: {format_metric_value(metric_name, value['max'])}")
            if "percentile_95" in value:
                additional_info.append(f"P95: {format_metric_value(metric_name, value['percentile_95'])}")
            
            details = ", ".join(additional_info)
        
        rows.append([colored_name, colored_value, details])
    
    # Print table
    print(create_table(headers, rows, "WAL Telemetry Metrics"))

def format_timestamp(timestamp: Optional[float]) -> str:
    """Format Unix timestamp as human-readable string."""
    if timestamp is None:
        return "N/A"
    try:
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return str(timestamp)

async def watch_metrics_async(client: WALTelemetryClient, interval: int = 2, count: Optional[int] = None,
                           metrics_filter: Optional[List[str]] = None) -> None:
    """
    Watch metrics in real-time with periodic updates asynchronously.
    
    Args:
        client: WAL telemetry client instance
        interval: Update interval in seconds
        count: Maximum number of updates (None for infinite)
        metrics_filter: List of metric names to display
    """
    iteration = 0
    try:
        while count is None or iteration < count:
            # Clear screen
            os.system('cls' if os.name == 'nt' else 'clear')
            
            # Get metrics
            metrics = await client.get_realtime_metrics_async()
            
            # Print header
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"{Colors.HEADER}{Colors.BOLD}WAL TELEMETRY MONITOR{Colors.ENDC}")
            print(f"Time: {now} | Update: #{iteration+1}" + (f" of {count}" if count else ""))
            print(f"Interval: {interval}s | Press Ctrl+C to stop\n")
            
            # Print metrics
            print_metrics_table(metrics, metrics_filter)
            
            # Sleep for interval
            await anyio.sleep(interval)
            iteration += 1
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Monitoring stopped by user{Colors.ENDC}")

def watch_metrics(client: WALTelemetryClient, interval: int = 2, count: Optional[int] = None,
                 metrics_filter: Optional[List[str]] = None) -> None:
    """
    Watch metrics in real-time with periodic updates.
    
    Args:
        client: WAL telemetry client instance
        interval: Update interval in seconds
        count: Maximum number of updates (None for infinite)
        metrics_filter: List of metric names to display
    """
    try:
        # Check if we're in an async context
        backend = None
        try:
            backend = sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            pass
        
        if backend is not None:
            # We're in an async context, so call the async version
            print(f"{Colors.YELLOW}Running in async context with {backend} backend{Colors.ENDC}")
            # This is unsafe - we should use anyio.run() but can't do it inside an existing async context
            # We leave it to the caller to use watch_metrics_async directly
            raise RuntimeError(
                f"Cannot call watch_metrics from an async {backend} context. "
                "Use watch_metrics_async instead."
            )
        
        # Run the async function using anyio.run
        anyio.run(
            watch_metrics_async,
            client, interval, count, metrics_filter
        )
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Monitoring stopped by user{Colors.ENDC}")

async def handle_metrics_command_async(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'metrics' command asynchronously."""
    # Handle watch mode
    if args.watch:
        await watch_metrics_async(
            client=client, 
            interval=args.interval, 
            count=args.count,
            metrics_filter=args.filter
        )
        return
    
    # Prepare filters for metrics query
    metric_type = args.type
    if metric_type and hasattr(TelemetryMetricType, metric_type.upper()):
        metric_type = getattr(TelemetryMetricType, metric_type.upper())
    
    operation_type = args.operation
    backend = args.backend
    status = args.status
    
    # Prepare time range if specified
    time_range = None
    if args.since:
        # Parse time string
        try:
            # Handle relative time strings
            if args.since.endswith('m'):
                minutes = int(args.since[:-1])
                start_time = time.time() - (minutes * 60)
            elif args.since.endswith('h'):
                hours = int(args.since[:-1])
                start_time = time.time() - (hours * 60 * 60)
            elif args.since.endswith('d'):
                days = int(args.since[:-1])
                start_time = time.time() - (days * 24 * 60 * 60)
            else:
                # Try to parse as absolute time
                dt = datetime.datetime.strptime(args.since, "%Y-%m-%d %H:%M:%S")
                start_time = dt.timestamp()
                
            time_range = (start_time, time.time())
            
        except (ValueError, TypeError):
            print(f"{Colors.RED}Error: Invalid time format for --since. Use '10m', '2h', '1d' or 'YYYY-MM-DD HH:MM:SS'.{Colors.ENDC}")
            return
    
    # Prepare aggregation if specified
    aggregation = args.aggregation
    if aggregation and hasattr(TelemetryAggregation, aggregation.upper()):
        aggregation = getattr(TelemetryAggregation, aggregation.upper())
    
    # Query metrics
    try:
        metrics = await client.get_metrics_async(
            metric_type=metric_type,
            operation_type=operation_type,
            backend=backend,
            status=status,
            time_range=time_range,
            aggregation=aggregation
        )
        
        # Check if metrics were returned
        if "metrics" in metrics:
            print_metrics_table(metrics["metrics"], args.filter)
        else:
            print(f"{Colors.YELLOW}No metrics available with the specified filters{Colors.ENDC}")
            
        # Print time range if applicable
        if time_range:
            print(f"\nTime range: {format_timestamp(time_range[0])} to {format_timestamp(time_range[1])}")
            
    except Exception as e:
        print(f"{Colors.RED}Error retrieving metrics: {str(e)}{Colors.ENDC}")

def handle_metrics_command(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'metrics' command."""
    try:
        # Check if we're in an async context
        backend = None
        try:
            backend = sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            pass
        
        if backend is not None:
            # We're in an async context, so call the async version
            print(f"{Colors.YELLOW}Running in async context with {backend} backend{Colors.ENDC}")
            # This is unsafe - we should use anyio.run() but can't do it inside an existing async context
            # We leave it to the caller to use handle_metrics_command_async directly
            raise RuntimeError(
                f"Cannot call handle_metrics_command from an async {backend} context. "
                "Use handle_metrics_command_async instead."
            )
        
        # Run the async function using anyio.run
        anyio.run(handle_metrics_command_async, args, client)
        
    except Exception as e:
        print(f"{Colors.RED}Error in metrics command: {str(e)}{Colors.ENDC}")

async def handle_report_command_async(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'report' command asynchronously."""
    # Prepare time range
    start_time = None
    end_time = time.time()
    
    if args.since:
        try:
            # Handle relative time strings
            if args.since.endswith('m'):
                minutes = int(args.since[:-1])
                start_time = time.time() - (minutes * 60)
            elif args.since.endswith('h'):
                hours = int(args.since[:-1])
                start_time = time.time() - (hours * 60 * 60)
            elif args.since.endswith('d'):
                days = int(args.since[:-1])
                start_time = time.time() - (days * 24 * 60 * 60)
            else:
                # Try to parse as absolute time
                dt = datetime.datetime.strptime(args.since, "%Y-%m-%d %H:%M:%S")
                start_time = dt.timestamp()
                
        except (ValueError, TypeError):
            print(f"{Colors.RED}Error: Invalid time format for --since. Use '10m', '2h', '1d' or 'YYYY-MM-DD HH:MM:SS'.{Colors.ENDC}")
            return
    
    # Generate report
    try:
        print(f"{Colors.CYAN}Generating performance report...{Colors.ENDC}")
        report = await client.generate_report_async(
            start_time=start_time,
            end_time=end_time,
            open_browser=args.browser
        )
        
        if report.get("success", False):
            print(f"{Colors.GREEN}Report generated successfully!{Colors.ENDC}")
            
            if "report_id" in report:
                print(f"\nReport ID: {report['report_id']}")
                
            if "report_url" in report:
                print(f"Report URL: {report['report_url']}")
                
            if "files" in report:
                print("\nReport Files:")
                for file_name in report["files"]:
                    print(f"  - {file_name}")
                    
            # Save report locally if requested
            if args.output:
                try:
                    # Create output directory if not exists
                    output_dir = os.path.dirname(args.output)
                    if output_dir and not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                        
                    # Get report index file
                    if "report_id" in report and "files" in report and "index.html" in report["files"]:
                        index_file = await client.get_report_file_async(
                            report_id=report["report_id"],
                            file_name="index.html",
                            save_path=args.output
                        )
                        
                        if index_file.get("saved", False):
                            print(f"\n{Colors.GREEN}Report saved to: {args.output}{Colors.ENDC}")
                            
                            # Open in browser if requested and not already opened
                            if args.browser and not report.get("opened_in_browser", False):
                                try:
                                    webbrowser.open(f"file://{args.output}")
                                    print(f"{Colors.CYAN}Opened report in browser{Colors.ENDC}")
                                except Exception as e:
                                    print(f"{Colors.YELLOW}Could not open browser: {str(e)}{Colors.ENDC}")
                        else:
                            print(f"{Colors.YELLOW}Failed to save report to {args.output}{Colors.ENDC}")
                    else:
                        print(f"{Colors.YELLOW}Report files not available{Colors.ENDC}")
                        
                except Exception as e:
                    print(f"{Colors.RED}Error saving report: {str(e)}{Colors.ENDC}")
        else:
            print(f"{Colors.RED}Failed to generate report: {report.get('error', 'Unknown error')}{Colors.ENDC}")
            
    except Exception as e:
        print(f"{Colors.RED}Error generating report: {str(e)}{Colors.ENDC}")

def handle_report_command(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'report' command."""
    try:
        # Check if we're in an async context
        backend = None
        try:
            backend = sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            pass
        
        if backend is not None:
            # We're in an async context, so call the async version
            print(f"{Colors.YELLOW}Running in async context with {backend} backend{Colors.ENDC}")
            # This is unsafe - we should use anyio.run() but can't do it inside an existing async context
            # We leave it to the caller to use handle_report_command_async directly
            raise RuntimeError(
                f"Cannot call handle_report_command from an async {backend} context. "
                "Use handle_report_command_async instead."
            )
        
        # Run the async function using anyio.run
        anyio.run(handle_report_command_async, args, client)
        
    except Exception as e:
        print(f"{Colors.RED}Error in report command: {str(e)}{Colors.ENDC}")

async def handle_viz_command_async(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'viz' command asynchronously."""
    # Check if metric type is valid
    metric_type = args.type
    if not metric_type:
        print(f"{Colors.RED}Error: Metric type is required{Colors.ENDC}")
        return
        
    if hasattr(TelemetryMetricType, metric_type.upper()):
        metric_type = getattr(TelemetryMetricType, metric_type.upper())
    
    # Prepare time range
    time_range = None
    if args.since:
        try:
            # Handle relative time strings
            if args.since.endswith('m'):
                minutes = int(args.since[:-1])
                start_time = time.time() - (minutes * 60)
            elif args.since.endswith('h'):
                hours = int(args.since[:-1])
                start_time = time.time() - (hours * 60 * 60)
            elif args.since.endswith('d'):
                days = int(args.since[:-1])
                start_time = time.time() - (days * 24 * 60 * 60)
            else:
                # Try to parse as absolute time
                dt = datetime.datetime.strptime(args.since, "%Y-%m-%d %H:%M:%S")
                start_time = dt.timestamp()
                
            time_range = (start_time, time.time())
            
        except (ValueError, TypeError):
            print(f"{Colors.RED}Error: Invalid time format for --since. Use '10m', '2h', '1d' or 'YYYY-MM-DD HH:MM:SS'.{Colors.ENDC}")
            return
    
    # Generate visualization
    try:
        print(f"{Colors.CYAN}Generating visualization for {args.type}...{Colors.ENDC}")
        
        # If output path is specified, ensure directory exists
        if args.output:
            output_dir = os.path.dirname(args.output)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
        # Generate visualization
        result = await client.get_visualization_async(
            metric_type=metric_type,
            operation_type=args.operation,
            backend=args.backend,
            status=args.status,
            time_range=time_range,
            width=args.width,
            height=args.height,
            save_path=args.output,
            open_browser=args.browser
        )
        
        if result.get("success", False):
            print(f"{Colors.GREEN}Visualization generated successfully!{Colors.ENDC}")
            
            if args.output and result.get("saved", False):
                print(f"\n{Colors.GREEN}Visualization saved to: {args.output}{Colors.ENDC}")
            
            if args.browser:
                print(f"{Colors.CYAN}Visualization opened in browser{Colors.ENDC}")
                
        else:
            print(f"{Colors.RED}Failed to generate visualization: {result.get('error', 'Unknown error')}{Colors.ENDC}")
            
    except Exception as e:
        print(f"{Colors.RED}Error generating visualization: {str(e)}{Colors.ENDC}")

def handle_viz_command(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'viz' command."""
    try:
        # Check if we're in an async context
        backend = None
        try:
            backend = sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            pass
        
        if backend is not None:
            # We're in an async context, so call the async version
            print(f"{Colors.YELLOW}Running in async context with {backend} backend{Colors.ENDC}")
            # This is unsafe - we should use anyio.run() but can't do it inside an existing async context
            # We leave it to the caller to use handle_viz_command_async directly
            raise RuntimeError(
                f"Cannot call handle_viz_command from an async {backend} context. "
                "Use handle_viz_command_async instead."
            )
        
        # Run the async function using anyio.run
        anyio.run(handle_viz_command_async, args, client)
        
    except Exception as e:
        print(f"{Colors.RED}Error in viz command: {str(e)}{Colors.ENDC}")

async def handle_config_command_async(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'config' command asynchronously."""
    if args.update:
        # Collect update parameters
        update_params = {}
        
        if args.enabled is not None:
            update_params["enabled"] = args.enabled
        if args.metrics_path is not None:
            update_params["metrics_path"] = args.metrics_path
        if args.retention_days is not None:
            update_params["retention_days"] = args.retention_days
        if args.sampling_interval is not None:
            update_params["sampling_interval"] = args.sampling_interval
        if args.detailed_timing is not None:
            update_params["enable_detailed_timing"] = args.detailed_timing
        if args.operation_hooks is not None:
            update_params["operation_hooks"] = args.operation_hooks
            
        # Update configuration if any parameters specified
        if update_params:
            try:
                print(f"{Colors.CYAN}Updating telemetry configuration...{Colors.ENDC}")
                result = await client.update_config_async(**update_params)
                
                if result.get("success", False):
                    print(f"{Colors.GREEN}Configuration updated successfully!{Colors.ENDC}")
                    
                    # Print updated configuration
                    config = result.get("config", {})
                    
                    headers = ["Setting", "Value"]
                    rows = []
                    
                    for key, value in config.items():
                        if key == "enabled":
                            value_str = f"{Colors.GREEN}Enabled{Colors.ENDC}" if value else f"{Colors.RED}Disabled{Colors.ENDC}"
                        else:
                            value_str = str(value)
                            
                        rows.append([key, value_str])
                        
                    print("\n" + create_table(headers, rows, "Updated Configuration"))
                    
                else:
                    print(f"{Colors.RED}Failed to update configuration: {result.get('error', 'Unknown error')}{Colors.ENDC}")
                    
            except Exception as e:
                print(f"{Colors.RED}Error updating configuration: {str(e)}{Colors.ENDC}")
                
        else:
            print(f"{Colors.YELLOW}No configuration parameters specified for update{Colors.ENDC}")
            
    else:
        # Get current configuration
        try:
            print(f"{Colors.CYAN}Retrieving telemetry configuration...{Colors.ENDC}")
            result = await client.get_config_async()
            
            if result.get("success", False):
                config = result.get("config", {})
                
                headers = ["Setting", "Value"]
                rows = []
                
                for key, value in config.items():
                    if key == "enabled":
                        value_str = f"{Colors.GREEN}Enabled{Colors.ENDC}" if value else f"{Colors.RED}Disabled{Colors.ENDC}"
                    else:
                        value_str = str(value)
                        
                    rows.append([key, value_str])
                    
                print("\n" + create_table(headers, rows, "Current Configuration"))
                
            else:
                print(f"{Colors.RED}Failed to retrieve configuration: {result.get('error', 'Unknown error')}{Colors.ENDC}")
                
        except Exception as e:
            print(f"{Colors.RED}Error retrieving configuration: {str(e)}{Colors.ENDC}")

def handle_config_command(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'config' command."""
    try:
        # Check if we're in an async context
        backend = None
        try:
            backend = sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            pass
        
        if backend is not None:
            # We're in an async context, so call the async version
            print(f"{Colors.YELLOW}Running in async context with {backend} backend{Colors.ENDC}")
            # This is unsafe - we should use anyio.run() but can't do it inside an existing async context
            # We leave it to the caller to use handle_config_command_async directly
            raise RuntimeError(
                f"Cannot call handle_config_command from an async {backend} context. "
                "Use handle_config_command_async instead."
            )
        
        # Run the async function using anyio.run
        anyio.run(handle_config_command_async, args, client)
        
    except Exception as e:
        print(f"{Colors.RED}Error in config command: {str(e)}{Colors.ENDC}")

async def handle_analyze_command_async(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'analyze' command asynchronously."""
    # Check if metric type is valid
    metric_type = args.type
    if not metric_type:
        print(f"{Colors.RED}Error: Metric type is required{Colors.ENDC}")
        return
        
    if hasattr(TelemetryMetricType, metric_type.upper()):
        metric_type = getattr(TelemetryMetricType, metric_type.upper())
    
    # Parse days
    days = 1  # Default to 1 day
    if args.days:
        try:
            days = int(args.days)
        except ValueError:
            print(f"{Colors.YELLOW}Invalid days value, using default of 1 day{Colors.ENDC}")
    
    # Get interval
    interval = args.interval
    if interval not in ["hour", "day", "week"]:
        print(f"{Colors.YELLOW}Invalid interval '{interval}', using 'hour'{Colors.ENDC}")
        interval = "hour"
    
    try:
        print(f"{Colors.CYAN}Analyzing {args.type} data for the past {days} day(s)...{Colors.ENDC}")
        
        # Get time series data
        time_series = await client.get_metrics_over_time_async(
            metric_type=metric_type,
            operation_type=args.operation,
            start_time=time.time() - (days * 24 * 60 * 60),
            end_time=time.time(),
            interval=interval
        )
        
        if not time_series.get("success", False):
            print(f"{Colors.RED}Failed to retrieve time series data: {time_series.get('error', 'Unknown error')}{Colors.ENDC}")
            return
            
        # Check if we have any data points
        data_points = time_series.get("time_series", [])
        if not data_points:
            print(f"{Colors.YELLOW}No data points available for analysis{Colors.ENDC}")
            return
            
        # Extract values for analysis
        values = []
        timestamps = []
        
        for point in data_points:
            metrics = point.get("metrics", {})
            
            # Handle different metric formats
            if isinstance(metrics, dict):
                # Try to get value from different possible formats
                if "average" in metrics:
                    value = metrics["average"]
                elif "value" in metrics:
                    value = metrics["value"]
                elif args.operation and args.operation in metrics:
                    value = metrics[args.operation].get("average", 0)
                else:
                    # If we can't find a specific value, use the first numeric value
                    value = next((v for v in metrics.values() 
                                if isinstance(v, (int, float))), 0)
            else:
                value = metrics
                
            if isinstance(value, (int, float)):
                values.append(value)
                timestamps.append(point.get("timestamp"))
        
        # Check if we have enough data points for analysis
        if len(values) < 2:
            print(f"{Colors.YELLOW}Not enough data points for analysis{Colors.ENDC}")
            return
            
        # Calculate statistics
        import statistics
        try:
            mean = statistics.mean(values)
            median = statistics.median(values)
            if len(values) > 1:
                stdev = statistics.stdev(values)
                variance = statistics.variance(values)
            else:
                stdev = 0
                variance = 0
                
            minimum = min(values)
            maximum = max(values)
            data_range = maximum - minimum
            
            # Calculate trend (simple linear regression)
            n = len(values)
            sum_x = sum(range(n))
            sum_y = sum(values)
            sum_x_squared = sum(x*x for x in range(n))
            sum_xy = sum(i*value for i, value in enumerate(values))
            
            # Avoid division by zero
            if n * sum_x_squared - sum_x * sum_x != 0:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x_squared - sum_x * sum_x)
                intercept = (sum_y - slope * sum_x) / n
            else:
                slope = 0
                intercept = mean if n > 0 else 0
                
            # Determine trend direction
            if abs(slope) < 0.05 * mean if mean != 0 else 0.01:
                trend = "stable"
            elif slope > 0:
                trend = "increasing"
            else:
                trend = "decreasing"
                
            # Calculate coefficient of variation
            cv = stdev / mean if mean != 0 else 0
            
            # Determine variability
            if cv < 0.1:
                variability = "low"
            elif cv < 0.3:
                variability = "moderate"
            else:
                variability = "high"
                
            # Print analysis results
            print(f"\n{Colors.HEADER}{Colors.BOLD}TIME SERIES ANALYSIS: {args.type.upper()}{Colors.ENDC}")
            if args.operation:
                print(f"Operation Type: {args.operation}")
                
            print(f"Time Range: {format_timestamp(timestamps[0])} to {format_timestamp(timestamps[-1])}")
            print(f"Interval: {interval}")
            print(f"Data Points: {len(values)}")
            
            # Print statistics table
            headers = ["Statistic", "Value"]
            rows = [
                ["Mean", format_metric_value(args.type, mean)],
                ["Median", format_metric_value(args.type, median)],
                ["Standard Deviation", format_metric_value(args.type, stdev)],
                ["Variance", format_metric_value(args.type, variance)],
                ["Minimum", format_metric_value(args.type, minimum)],
                ["Maximum", format_metric_value(args.type, maximum)],
                ["Range", format_metric_value(args.type, data_range)]
            ]
            
            print("\n" + create_table(headers, rows, "Statistics"))
            
            # Print trend analysis
            trend_color = Colors.CYAN
            if trend == "increasing":
                if args.type in ["operation_latency", "error_rate"]:
                    trend_color = Colors.RED
                else:
                    trend_color = Colors.GREEN
            elif trend == "decreasing":
                if args.type in ["operation_latency", "error_rate"]:
                    trend_color = Colors.GREEN
                else:
                    trend_color = Colors.RED
            
            headers = ["Metric", "Value"]
            rows = [
                ["Trend Direction", f"{trend_color}{trend.capitalize()}{Colors.ENDC}"],
                ["Slope", f"{slope:.6f}"],
                ["Y-Intercept", f"{intercept:.6f}"],
                ["Coefficient of Variation", f"{cv:.4f}"],
                ["Variability", f"{variability.capitalize()}"]
            ]
            
            print("\n" + create_table(headers, rows, "Trend Analysis"))
            
            # Print insights
            print(f"\n{Colors.HEADER}{Colors.BOLD}INSIGHTS{Colors.ENDC}")
            
            # Trend insights
            if trend == "increasing":
                if args.type in ["operation_latency", "error_rate"]:
                    print(f"{Colors.RED}⚠️ Performance degradation detected (increasing trend in negative metric){Colors.ENDC}")
                else:
                    print(f"{Colors.GREEN}✅ Positive trend detected{Colors.ENDC}")
            elif trend == "decreasing":
                if args.type in ["operation_latency", "error_rate"]:
                    print(f"{Colors.GREEN}✅ Performance improvement detected (decreasing trend in negative metric){Colors.ENDC}")
                elif args.type in ["success_rate", "throughput"]:
                    print(f"{Colors.RED}⚠️ Potential issue detected (decreasing trend in positive metric){Colors.ENDC}")
            else:
                print(f"{Colors.CYAN}✓ Metric is stable over the analyzed period{Colors.ENDC}")
            
            # Variability insights
            if variability == "high":
                print(f"{Colors.YELLOW}⚠️ High variability indicates inconsistent performance{Colors.ENDC}")
            elif variability == "low":
                print(f"{Colors.GREEN}✅ Low variability indicates consistent performance{Colors.ENDC}")
            
            # Specific metric insights
            if args.type == "operation_latency":
                if maximum > 500:
                    print(f"{Colors.RED}⚠️ Maximum latency ({maximum:.2f} ms) indicates potential performance issues{Colors.ENDC}")
                if cv > 0.5:
                    print(f"{Colors.YELLOW}⚠️ High latency variance indicates unpredictable performance{Colors.ENDC}")
                    
            elif args.type == "error_rate":
                if mean > 0.05:
                    print(f"{Colors.RED}⚠️ Error rate ({mean*100:.2f}%) is above acceptable threshold (5%){Colors.ENDC}")
                if maximum > 0.1:
                    print(f"{Colors.RED}⚠️ Maximum error rate ({maximum*100:.2f}%) indicates serious issues{Colors.ENDC}")
                    
            elif args.type == "success_rate":
                if mean < 0.95:
                    print(f"{Colors.RED}⚠️ Average success rate ({mean*100:.2f}%) is below acceptable threshold (95%){Colors.ENDC}")
                if minimum < 0.9:
                    print(f"{Colors.RED}⚠️ Minimum success rate ({minimum*100:.2f}%) indicates serious issues{Colors.ENDC}")
            
            # Visualization hint
            print(f"\n{Colors.CYAN}Hint: Generate a visualization with:{Colors.ENDC}")
            viz_cmd = f"telemetry viz {args.type}"
            if args.operation:
                viz_cmd += f" --operation {args.operation}"
            if days > 1:
                viz_cmd += f" --since {days}d"
                
            print(f"  {viz_cmd} --browser")
                    
        except Exception as e:
            print(f"{Colors.RED}Error analyzing time series: {str(e)}{Colors.ENDC}")
            
    except Exception as e:
        print(f"{Colors.RED}Error retrieving time series data: {str(e)}{Colors.ENDC}")

def handle_analyze_command(args: argparse.Namespace, client: WALTelemetryClient) -> None:
    """Handle 'analyze' command."""
    try:
        # Check if we're in an async context
        backend = None
        try:
            backend = sniffio.current_async_library()
        except sniffio.AsyncLibraryNotFoundError:
            pass
        
        if backend is not None:
            # We're in an async context, so call the async version
            print(f"{Colors.YELLOW}Running in async context with {backend} backend{Colors.ENDC}")
            # This is unsafe - we should use anyio.run() but can't do it inside an existing async context
            # We leave it to the caller to use handle_analyze_command_async directly
            raise RuntimeError(
                f"Cannot call handle_analyze_command from an async {backend} context. "
                "Use handle_analyze_command_async instead."
            )
        
        # Run the async function using anyio.run
        anyio.run(handle_analyze_command_async, args, client)
        
    except Exception as e:
        print(f"{Colors.RED}Error in analyze command: {str(e)}{Colors.ENDC}")

def register_wal_telemetry_commands(subparsers):
    """
    Register WAL Telemetry-related commands with the CLI parser.
    
    Args:
        subparsers: Subparser object from argparse
    """
    # WAL Telemetry command group
    telemetry_parser = subparsers.add_parser(
        "telemetry",
        help="WAL Telemetry system operations",
    )
    telemetry_subparsers = telemetry_parser.add_subparsers(
        dest="telemetry_command", 
        help="Telemetry command to execute", 
        required=True
    )
    
    # Initialize telemetry
    init_parser = telemetry_subparsers.add_parser(
        "init",
        help="Initialize WAL telemetry system",
    )
    init_parser.add_argument(
        "--enabled",
        action="store_true",
        default=True,
        help="Enable telemetry collection",
    )
    init_parser.add_argument(
        "--aggregation-interval",
        type=int,
        default=60,
        help="Interval in seconds for metric aggregation",
    )
    init_parser.add_argument(
        "--max-history",
        type=int,
        default=100,
        help="Maximum number of historical entries to keep",
    )
    init_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging level for telemetry events",
    )
    init_parser.set_defaults(func=lambda api, args, kwargs: api.initialize_telemetry(**kwargs))
    
    # Get metrics
    metrics_parser = telemetry_subparsers.add_parser(
        "metrics",
        help="Get WAL telemetry metrics",
    )
    metrics_parser.add_argument(
        "--metric-type",
        choices=["operation_count", "operation_latency", "success_rate", 
                "error_rate", "backend_health", "throughput", "queue_size", 
                "retry_count", "all"],
        default="all",
        help="Type of metric to retrieve",
    )
    metrics_parser.add_argument(
        "--aggregation",
        choices=["sum", "average", "minimum", "maximum", 
                "percentile_95", "percentile_99", "count", "rate"],
        default="average",
        help="Type of aggregation to apply",
    )
    metrics_parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Time interval in seconds for metrics aggregation",
    )
    metrics_parser.add_argument(
        "--operation",
        help="Filter by operation type",
    )
    metrics_parser.add_argument(
        "--backend",
        help="Filter by backend type",
    )
    metrics_parser.add_argument(
        "--since",
        help="Start time for metrics query (e.g., '10m', '2h', '1d')",
    )
    metrics_parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch metrics in real-time with periodic updates",
    )
    metrics_parser.add_argument(
        "--watch-interval",
        type=int,
        default=2,
        help="Interval in seconds for watch updates",
    )
    metrics_parser.set_defaults(func=lambda api, args, kwargs: api.get_telemetry_metrics(**kwargs))
    
    # Generate report
    report_parser = telemetry_subparsers.add_parser(
        "report",
        help="Generate WAL telemetry report",
    )
    report_parser.add_argument(
        "--output",
        required=True,
        help="Output file path for the report",
    )
    report_parser.add_argument(
        "--report-type",
        choices=["summary", "detailed", "operations", "backends", "performance"],
        default="summary",
        help="Type of report to generate",
    )
    report_parser.add_argument(
        "--time-range",
        choices=["hour", "day", "week", "month", "all"],
        default="day",
        help="Time range for the report",
    )
    report_parser.add_argument(
        "--include-visualizations",
        action="store_true",
        default=False,
        help="Include visualizations in the report",
    )
    report_parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the report in a browser after generation",
    )
    report_parser.set_defaults(func=lambda api, args, kwargs: api.generate_telemetry_report(**kwargs))
    
    # Prometheus integration
    prometheus_parser = telemetry_subparsers.add_parser(
        "prometheus",
        help="Manage Prometheus integration for telemetry metrics",
    )
    prometheus_subparsers = prometheus_parser.add_subparsers(
        dest="prometheus_command",
        help="Prometheus command",
        required=True
    )
    
    # Start Prometheus exporter
    prometheus_start_parser = prometheus_subparsers.add_parser(
        "start",
        help="Start Prometheus metrics exporter",
    )
    prometheus_start_parser.add_argument(
        "--port",
        type=int,
        default=9095,
        help="Port for Prometheus metrics server",
    )
    prometheus_start_parser.add_argument(
        "--address",
        default="127.0.0.1",
        help="Address to bind the server",
    )
    prometheus_start_parser.add_argument(
        "--metrics-path",
        default="/metrics",
        help="HTTP path for metrics endpoint",
    )
    prometheus_start_parser.set_defaults(func=lambda api, args, kwargs: api.start_prometheus_exporter(**kwargs))
    
    # Stop Prometheus exporter
    prometheus_stop_parser = prometheus_subparsers.add_parser(
        "stop",
        help="Stop Prometheus metrics exporter",
    )
    prometheus_stop_parser.set_defaults(func=lambda api, args, kwargs: api.stop_prometheus_exporter(**kwargs))
    
    # Grafana dashboard operations
    grafana_parser = telemetry_subparsers.add_parser(
        "grafana",
        help="Manage Grafana dashboards for telemetry",
    )
    grafana_subparsers = grafana_parser.add_subparsers(
        dest="grafana_command",
        help="Grafana command",
        required=True
    )
    
    # Generate Grafana dashboard
    grafana_generate_parser = grafana_subparsers.add_parser(
        "generate",
        help="Generate Grafana dashboard for telemetry",
    )
    grafana_generate_parser.add_argument(
        "--output",
        required=True,
        help="Output file path for the dashboard JSON",
    )
    grafana_generate_parser.add_argument(
        "--dashboard-title",
        default="IPFS Kit WAL Telemetry",
        help="Title for the dashboard",
    )
    grafana_generate_parser.add_argument(
        "--prometheus-datasource",
        default="Prometheus",
        help="Name of the Prometheus data source in Grafana",
    )
    grafana_generate_parser.set_defaults(func=lambda api, args, kwargs: api.generate_grafana_dashboard(**kwargs))
    
    # Distributed tracing commands
    tracing_parser = telemetry_subparsers.add_parser(
        "tracing",
        help="Manage distributed tracing for WAL operations",
    )
    tracing_subparsers = tracing_parser.add_subparsers(
        dest="tracing_command",
        help="Tracing command",
        required=True
    )
    
    # Initialize tracing
    tracing_init_parser = tracing_subparsers.add_parser(
        "init",
        help="Initialize distributed tracing system",
    )
    tracing_init_parser.add_argument(
        "--exporter-type",
        choices=["jaeger", "zipkin", "otlp", "console", "none"],
        default="console",
        help="Type of tracing exporter to use",
    )
    tracing_init_parser.add_argument(
        "--endpoint",
        help="Endpoint for the tracing collector/exporter",
    )
    tracing_init_parser.add_argument(
        "--service-name",
        default="ipfs-kit-wal",
        help="Service name for traces",
    )
    tracing_init_parser.set_defaults(func=lambda api, args, kwargs: api.initialize_tracing(**kwargs))
    
    # Start trace session
    tracing_start_parser = tracing_subparsers.add_parser(
        "start",
        help="Start a new trace session",
    )
    tracing_start_parser.add_argument(
        "--session-name",
        required=True,
        help="Name for the trace session",
    )
    tracing_start_parser.add_argument(
        "--correlate-with",
        help="Optional correlation ID to relate to other trace sessions",
    )
    tracing_start_parser.set_defaults(func=lambda api, args, kwargs: api.start_trace_session(**kwargs))
    
    # Stop trace session
    tracing_stop_parser = tracing_subparsers.add_parser(
        "stop",
        help="Stop an active trace session",
    )
    tracing_stop_parser.add_argument(
        "--session-name",
        required=True,
        help="Name of the trace session to stop",
    )
    tracing_stop_parser.set_defaults(func=lambda api, args, kwargs: api.stop_trace_session(**kwargs))
    
    # Export trace results
    tracing_export_parser = tracing_subparsers.add_parser(
        "export",
        help="Export trace results to a file",
    )
    tracing_export_parser.add_argument(
        "--output",
        required=True,
        help="Output file path for the trace export",
    )
    tracing_export_parser.add_argument(
        "--format",
        choices=["json", "zipkin", "jaeger", "otlp"],
        default="json",
        help="Format for the trace export",
    )
    tracing_export_parser.add_argument(
        "--session-name",
        help="Optional trace session name to export",
    )
    tracing_export_parser.set_defaults(func=lambda api, args, kwargs: api.export_traces(**kwargs))
    
    # Visualize trace results
    tracing_visualize_parser = tracing_subparsers.add_parser(
        "visualize",
        help="Visualize trace results as a flamegraph",
    )
    tracing_visualize_parser.add_argument(
        "--output",
        required=True,
        help="Output file path for the visualization",
    )
    tracing_visualize_parser.add_argument(
        "--session-name",
        help="Optional trace session name to visualize",
    )
    tracing_visualize_parser.add_argument(
        "--format",
        choices=["svg", "html", "pdf"],
        default="html",
        help="Format for the visualization",
    )
    tracing_visualize_parser.set_defaults(func=lambda api, args, kwargs: api.visualize_traces(**kwargs))
    
    # Analysis commands
    analysis_parser = telemetry_subparsers.add_parser(
        "analyze",
        help="Analyze telemetry metrics and trends",
    )
    analysis_parser.add_argument(
        "--metric-type",
        required=True,
        choices=["operation_latency", "success_rate", "error_rate", "throughput", "queue_size"],
        help="Type of metric to analyze",
    )
    analysis_parser.add_argument(
        "--operation",
        help="Filter by operation type",
    )
    analysis_parser.add_argument(
        "--backend",
        help="Filter by backend type",
    )
    analysis_parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to analyze",
    )
    analysis_parser.add_argument(
        "--output",
        help="Output file for analysis report",
    )
    analysis_parser.set_defaults(func=lambda api, args, kwargs: api.analyze_metrics(**kwargs))


async def main_async():
    """Main entry point for the CLI (async version)."""
    # Check for environment variables
    base_url = os.environ.get("WAL_TELEMETRY_API_URL", "http://localhost:8000")
    api_key = os.environ.get("WAL_TELEMETRY_API_KEY")
    timeout = int(os.environ.get("WAL_TELEMETRY_TIMEOUT", "30"))
    verify_ssl = os.environ.get("WAL_TELEMETRY_VERIFY_SSL", "1") != "0"
    
    # Create main parser
    parser = argparse.ArgumentParser(
        description="Command-line interface for WAL telemetry metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(f"""
            Environment Variables:
              WAL_TELEMETRY_API_URL     Base URL for the API (default: http://localhost:8000)
              WAL_TELEMETRY_API_KEY     API key for authentication
              WAL_TELEMETRY_TIMEOUT     Request timeout in seconds (default: 30)
              WAL_TELEMETRY_VERIFY_SSL  Whether to verify SSL certificates (default: 1)
              
            Examples:
              telemetry metrics --watch
              telemetry metrics --type operation_latency --since 1h
              telemetry report --browser
              telemetry viz --type throughput --output throughput.png
              telemetry analyze --type success_rate --days 7
              telemetry config
            
            Current API URL: {base_url}
        """)
    )
    
    # Add global arguments
    parser.add_argument("--url", help=f"API base URL (default: {base_url})")
    parser.add_argument("--key", help="API key")
    parser.add_argument("--timeout", type=int, help=f"Request timeout in seconds (default: {timeout})")
    parser.add_argument("--no-verify", action="store_true", help="Disable SSL verification")
    
    # Create subparsers
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Get telemetry metrics")
    metrics_parser.add_argument("--watch", "-w", action="store_true", help="Watch metrics in real-time")
    metrics_parser.add_argument("--interval", "-i", type=int, default=2, help="Update interval in seconds (default: 2)")
    metrics_parser.add_argument("--count", "-n", type=int, help="Number of updates (default: infinite)")
    metrics_parser.add_argument("--type", "-t", help="Type of metrics to retrieve")
    metrics_parser.add_argument("--operation", "-o", help="Filter by operation type")
    metrics_parser.add_argument("--backend", "-b", help="Filter by backend type")
    metrics_parser.add_argument("--status", "-s", help="Filter by operation status")
    metrics_parser.add_argument("--since", help="Get metrics since time (e.g., '10m', '2h', '1d', or 'YYYY-MM-DD HH:MM:SS')")
    metrics_parser.add_argument("--aggregation", "-a", help="Type of aggregation to apply")
    metrics_parser.add_argument("--filter", "-f", nargs="*", help="Filter metrics by name")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate performance report")
    report_parser.add_argument("--browser", "-b", action="store_true", help="Open report in browser")
    report_parser.add_argument("--output", "-o", help="Save report to file")
    report_parser.add_argument("--since", help="Include data since time (e.g., '10m', '2h', '1d', or 'YYYY-MM-DD HH:MM:SS')")
    
    # Visualization command
    viz_parser = subparsers.add_parser("viz", help="Generate metric visualization")
    viz_parser.add_argument("--type", "-t", required=True, help="Type of metrics to visualize")
    viz_parser.add_argument("--operation", "-o", help="Filter by operation type")
    viz_parser.add_argument("--backend", "-b", help="Filter by backend type")
    viz_parser.add_argument("--status", "-s", help="Filter by operation status")
    viz_parser.add_argument("--since", help="Include data since time (e.g., '10m', '2h', '1d', or 'YYYY-MM-DD HH:MM:SS')")
    viz_parser.add_argument("--width", type=int, default=12, help="Chart width in inches (default: 12)")
    viz_parser.add_argument("--height", type=int, default=8, help="Chart height in inches (default: 8)")
    viz_parser.add_argument("--output", "-o", help="Save visualization to file")
    viz_parser.add_argument("--browser", "-b", action="store_true", help="Open visualization in browser")
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Get or update telemetry configuration")
    config_parser.add_argument("--update", "-u", action="store_true", help="Update configuration")
    config_parser.add_argument("--enabled", type=bool, help="Whether telemetry is enabled")
    config_parser.add_argument("--metrics-path", help="Directory for telemetry metrics storage")
    config_parser.add_argument("--retention-days", type=int, help="Number of days to retain metrics")
    config_parser.add_argument("--sampling-interval", type=int, help="Interval in seconds between metric samples")
    config_parser.add_argument("--detailed-timing", type=bool, help="Whether to collect detailed timing data")
    config_parser.add_argument("--operation-hooks", type=bool, help="Whether to install operation hooks")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze time series metrics")
    analyze_parser.add_argument("--type", "-t", required=True, help="Type of metrics to analyze")
    analyze_parser.add_argument("--operation", "-o", help="Filter by operation type")
    analyze_parser.add_argument("--days", "-d", type=int, default=1, help="Number of days to analyze (default: 1)")
    analyze_parser.add_argument("--interval", "-i", choices=["hour", "day", "week"], default="hour", 
                             help="Time interval for analysis (default: hour)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Check if command was provided
    if not args.command:
        parser.print_help()
        return
    
    # Override defaults with command line arguments
    if args.url:
        base_url = args.url
    if args.key:
        api_key = args.key
    if args.timeout:
        timeout = args.timeout
    if args.no_verify:
        verify_ssl = False
    
    # Create client
    try:
        client = WALTelemetryClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            verify_ssl=verify_ssl
        )
        
        # Handle commands
        if args.command == "metrics":
            await handle_metrics_command_async(args, client)
        elif args.command == "report":
            await handle_report_command_async(args, client)
        elif args.command == "viz":
            await handle_viz_command_async(args, client)
        elif args.command == "config":
            await handle_config_command_async(args, client)
        elif args.command == "analyze":
            await handle_analyze_command_async(args, client)
        
    except Exception as e:
        print(f"{Colors.RED}Error: {str(e)}{Colors.ENDC}")
        return 1
    
    return 0

def main():
    """Main entry point for the CLI."""
    # Check if we're in an async context
    backend = None
    try:
        backend = sniffio.current_async_library()
    except sniffio.AsyncLibraryNotFoundError:
        pass
    
    if backend is not None:
        # We're in an async context, so call the async version
        print(f"{Colors.YELLOW}Running in async context with {backend} backend{Colors.ENDC}")
        # This is unsafe - we should use anyio.run() but can't do it inside an existing async context
        # We leave it to the caller to use main_async directly
        raise RuntimeError(
            f"Cannot call main from an async {backend} context. "
            "Use main_async instead."
        )
    
    # Run the async function using anyio.run
    try:
        return anyio.run(main_async)
    except Exception as e:
        print(f"{Colors.RED}Error in main: {str(e)}{Colors.ENDC}")
        return 1

if __name__ == "__main__":
    sys.exit(main())