#!/usr/bin/env python3
# examples/wal_telemetry_client_example.py

"""
Example demonstrating the WAL Telemetry Client for monitoring and analysis.

This example shows how to use the WALTelemetryClient to:
1. Retrieve telemetry metrics
2. Generate and visualize time series data
3. Create and access performance reports
4. Set up real-time monitoring with alerting
5. Collect and analyze performance statistics
"""

import os
import sys
import time
import json
import logging
import argparse
import threading
import datetime
import platform
import webbrowser
from typing import Dict, Any, List, Optional, Tuple, Union

# Add parent directory to path for importing from ipfs_kit_py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import WAL components
from ipfs_kit_py.wal_telemetry_client import WALTelemetryClient, TelemetryMetricType, TelemetryAggregation
from ipfs_kit_py.wal import WAL
from ipfs_kit_py.wal_api import create_api_app, start_api_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("wal_telemetry_example.log")
    ]
)
logger = logging.getLogger(__name__)

class MetricAlert:
    """
    Simple alerting system for telemetry metrics.
    
    This class defines thresholds for different metrics and triggers
    alerts when thresholds are exceeded.
    """
    
    def __init__(self, thresholds: Optional[Dict[str, Dict[str, float]]] = None):
        """
        Initialize the alerting system with thresholds.
        
        Args:
            thresholds: Dictionary mapping metric types to thresholds.
                Example: {"operation_latency": {"warning": 100, "critical": 500}}
        """
        # Default thresholds
        self.thresholds = {
            "operation_latency": {"warning": 100, "critical": 500},  # ms
            "error_rate": {"warning": 0.05, "critical": 0.1},  # 5% and 10%
            "queue_size": {"warning": 100, "critical": 500},  # operations
            "success_rate": {"warning": 0.95, "critical": 0.9}  # 95% and 90%
        }
        
        # Update with custom thresholds if provided
        if thresholds:
            for metric_type, metric_thresholds in thresholds.items():
                if metric_type in self.thresholds:
                    self.thresholds[metric_type].update(metric_thresholds)
                else:
                    self.thresholds[metric_type] = metric_thresholds
        
        # Track alert state to avoid repeated alerts
        self.alert_state = {}
        
    def check_metrics(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check metrics against thresholds and generate alerts.
        
        Args:
            metrics: Dictionary of metrics from telemetry client
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        timestamp = time.time()
        
        # Process each metric type
        for metric_type, thresholds in self.thresholds.items():
            if metric_type not in metrics:
                continue
            
            value = metrics[metric_type]
            
            # Handle different metric formats
            if isinstance(value, dict) and "average" in value:
                value = value["average"]
            elif isinstance(value, dict) and "value" in value:
                value = value["value"]
            
            # Special case for success_rate (should be high)
            if metric_type == "success_rate":
                # Critical alert if below critical threshold
                if value < thresholds.get("critical", 0.9):
                    alert_level = "critical"
                    alert_message = f"{metric_type} is critically low: {value:.2f} (threshold: {thresholds['critical']:.2f})"
                # Warning alert if below warning threshold
                elif value < thresholds.get("warning", 0.95):
                    alert_level = "warning"
                    alert_message = f"{metric_type} is below warning threshold: {value:.2f} (threshold: {thresholds['warning']:.2f})"
                else:
                    # No alert needed
                    alert_level = None
                    alert_message = None
            else:
                # Critical alert if above critical threshold
                if value > thresholds.get("critical", float("inf")):
                    alert_level = "critical"
                    alert_message = f"{metric_type} is critically high: {value:.2f} (threshold: {thresholds['critical']:.2f})"
                # Warning alert if above warning threshold
                elif value > thresholds.get("warning", float("inf")):
                    alert_level = "warning"
                    alert_message = f"{metric_type} is above warning threshold: {value:.2f} (threshold: {thresholds['warning']:.2f})"
                else:
                    # No alert needed
                    alert_level = None
                    alert_message = None
            
            # Create alert if needed
            if alert_level and alert_message:
                # Check if this is a new alert or state change
                previous_state = self.alert_state.get(metric_type, {"level": None, "value": None})
                if previous_state["level"] != alert_level or abs(previous_state["value"] - value) > (value * 0.1):
                    alert = {
                        "metric_type": metric_type,
                        "level": alert_level,
                        "message": alert_message,
                        "value": value,
                        "threshold": thresholds.get(alert_level),
                        "timestamp": timestamp
                    }
                    alerts.append(alert)
                    
                    # Update alert state
                    self.alert_state[metric_type] = {"level": alert_level, "value": value}
                    
        return alerts

class WALTelemetryDashboard:
    """
    Simple dashboard for WAL telemetry metrics.
    
    This class provides an interface for monitoring and analyzing telemetry data
    from the WAL system.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None,
                alerts_enabled: bool = True):
        """
        Initialize the telemetry dashboard.
        
        Args:
            base_url: Base URL for the API server
            api_key: Optional API key for authentication
            alerts_enabled: Whether to enable automated alerting
        """
        self.client = WALTelemetryClient(base_url=base_url, api_key=api_key)
        self.alerts_enabled = alerts_enabled
        self.alert_system = MetricAlert() if alerts_enabled else None
        self.monitoring_thread = None
        self.stop_monitoring = threading.Event()
        self.monitoring_running = False
        
        # Create directories for storing visualizations and reports
        self.output_dir = os.path.join(os.getcwd(), "telemetry_output")
        self.visualizations_dir = os.path.join(self.output_dir, "visualizations")
        self.reports_dir = os.path.join(self.output_dir, "reports")
        
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.visualizations_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        
    def start_monitoring(self, interval: int = 5, callback: Optional[callable] = None) -> None:
        """
        Start monitoring telemetry metrics in a background thread.
        
        Args:
            interval: Interval in seconds between updates
            callback: Optional callback function for metric updates
        """
        if self.monitoring_running:
            logger.warning("Monitoring already running")
            return
        
        self.stop_monitoring.clear()
        self.monitoring_running = True
        
        def monitor_thread():
            """Background thread for continuous monitoring."""
            iteration = 0
            
            while not self.stop_monitoring.is_set():
                try:
                    # Get real-time metrics
                    metrics = self.client.get_realtime_metrics()
                    
                    # Check for alerts if enabled
                    if self.alerts_enabled and self.alert_system:
                        alerts = self.alert_system.check_metrics(metrics)
                        for alert in alerts:
                            self._handle_alert(alert)
                    
                    # Call custom callback if provided
                    if callback:
                        callback(metrics, iteration)
                    
                    # Print basic stats
                    if iteration % 10 == 0:  # Every 10 iterations
                        self._print_status_summary(metrics)
                    
                    # Increment iteration counter
                    iteration += 1
                    
                except Exception as e:
                    logger.error(f"Error in monitoring thread: {str(e)}")
                
                # Wait for next interval (with early exit)
                self.stop_monitoring.wait(interval)
        
        # Start the monitoring thread
        self.monitoring_thread = threading.Thread(target=monitor_thread)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        
        logger.info(f"Monitoring started with interval {interval}s")
        
    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        if not self.monitoring_running:
            logger.warning("Monitoring not running")
            return
        
        # Signal stop and wait for thread to exit
        self.stop_monitoring.set()
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
        
        self.monitoring_running = False
        logger.info("Monitoring stopped")
        
    def _handle_alert(self, alert: Dict[str, Any]) -> None:
        """
        Handle a metric alert.
        
        Args:
            alert: Alert information dictionary
        """
        # Log the alert
        log_message = f"[{alert['level'].upper()}] {alert['message']}"
        if alert['level'] == "critical":
            logger.critical(log_message)
        else:
            logger.warning(log_message)
        
        # Print to console 
        alert_time = datetime.datetime.fromtimestamp(alert['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n{'!' * 5} ALERT {'!' * 5}")
        print(f"Time: {alert_time}")
        print(f"Level: {alert['level'].upper()}")
        print(f"Metric: {alert['metric_type']}")
        print(f"Message: {alert['message']}")
        print(f"{'!' * 20}")
        
        # For critical alerts, we could add email notifications,
        # integration with monitoring systems, etc.
    
    def _print_status_summary(self, metrics: Dict[str, Any]) -> None:
        """
        Print a summary of current telemetry metrics.
        
        Args:
            metrics: Metrics from telemetry client
        """
        print("\n" + "=" * 50)
        print("WAL TELEMETRY STATUS SUMMARY")
        print("=" * 50)
        
        # Format timestamp
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Time: {now}")
        
        # Extract key metrics with fallbacks
        latency = metrics.get("operation_latency", {}).get("average", "N/A")
        success_rate = metrics.get("success_rate", {}).get("value", "N/A")
        error_rate = metrics.get("error_rate", {}).get("value", "N/A")
        throughput = metrics.get("throughput", {}).get("value", "N/A")
        queue_size = metrics.get("queue_size", {}).get("value", "N/A")
        
        # Format as percentages where appropriate
        if isinstance(success_rate, (int, float)):
            success_rate = f"{success_rate * 100:.2f}%"
        if isinstance(error_rate, (int, float)):
            error_rate = f"{error_rate * 100:.2f}%"
        
        # Print metrics
        print(f"Average Latency: {latency} ms")
        print(f"Success Rate: {success_rate}")
        print(f"Error Rate: {error_rate}")
        print(f"Throughput: {throughput} ops/sec")
        print(f"Queue Size: {queue_size} operations")
        
        # Operation type breakdown
        print("\nOperation Types:")
        for op_type, count in metrics.get("operation_count", {}).items():
            print(f"  - {op_type}: {count}")
        
        print("=" * 50)
    
    def generate_performance_report(self, time_range: Optional[Tuple[float, float]] = None,
                                   save_to_file: bool = True) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.
        
        Args:
            time_range: Optional tuple of (start_time, end_time)
            save_to_file: Whether to save the report to a file
            
        Returns:
            Dictionary with report data
        """
        # Get time range or default to last 24 hours
        end_time = time.time()
        start_time = time_range[0] if time_range else (end_time - 24 * 60 * 60)
        
        # Generate report through API
        report_result = self.client.generate_report(
            start_time=start_time,
            end_time=end_time
        )
        
        # Get report ID
        report_id = report_result.get("report_id")
        if not report_id:
            logger.error("Failed to generate report")
            return report_result
        
        # Get report index file
        try:
            index_file = self.client.get_report_file(
                report_id=report_id, 
                file_name="index.html"
            )
            
            # Save report if requested
            if save_to_file and "content" in index_file:
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                report_dir = os.path.join(self.reports_dir, f"report_{timestamp}")
                os.makedirs(report_dir, exist_ok=True)
                
                # Save index.html
                index_path = os.path.join(report_dir, "index.html")
                with open(index_path, "wb") as f:
                    f.write(index_file["content"])
                
                # Save report data
                data_path = os.path.join(report_dir, "report_data.json")
                with open(data_path, "w") as f:
                    json.dump(report_result, f, indent=2)
                
                report_result["local_path"] = index_path
                logger.info(f"Report saved to {index_path}")
        
        except Exception as e:
            logger.error(f"Error retrieving report file: {str(e)}")
        
        return report_result
    
    def generate_visualizations(self, metrics: Optional[List[TelemetryMetricType]] = None,
                              time_range: Optional[Tuple[float, float]] = None) -> Dict[str, str]:
        """
        Generate visualizations for key metrics.
        
        Args:
            metrics: List of metric types to visualize
            time_range: Optional tuple of (start_time, end_time)
            
        Returns:
            Dictionary mapping metric types to saved file paths
        """
        # Use default metrics if none provided
        if metrics is None:
            metrics = [
                TelemetryMetricType.OPERATION_LATENCY,
                TelemetryMetricType.SUCCESS_RATE,
                TelemetryMetricType.ERROR_RATE,
                TelemetryMetricType.THROUGHPUT,
                TelemetryMetricType.QUEUE_SIZE
            ]
        
        # Create timestamp for file naming
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate visualizations for each metric type
        results = {}
        for metric_type in metrics:
            try:
                # Define save path
                if hasattr(metric_type, 'value'):
                    metric_name = metric_type.value
                else:
                    metric_name = str(metric_type)
                
                save_path = os.path.join(
                    self.visualizations_dir, 
                    f"{metric_name}_{timestamp}.png"
                )
                
                # Generate visualization
                result = self.client.get_visualization(
                    metric_type=metric_type,
                    time_range=time_range,
                    save_path=save_path
                )
                
                if result.get("saved", False):
                    results[metric_name] = save_path
                    logger.info(f"Visualization for {metric_name} saved to {save_path}")
                else:
                    logger.error(f"Failed to save visualization for {metric_name}")
            
            except Exception as e:
                logger.error(f"Error generating visualization for {metric_type}: {str(e)}")
        
        return results
    
    def analyze_time_series(self, metric_type: Union[str, TelemetryMetricType],
                          operation_type: Optional[str] = None,
                          days: int = 1, interval: str = "hour") -> Dict[str, Any]:
        """
        Analyze time series data for a specific metric.
        
        Args:
            metric_type: Type of metric to analyze
            operation_type: Optional filter by operation type
            days: Number of days of history to analyze
            interval: Time interval for analysis ('hour', 'day', 'week')
            
        Returns:
            Dictionary with analysis results
        """
        # Calculate time range
        end_time = time.time()
        start_time = end_time - (days * 24 * 60 * 60)
        
        # Get time series data
        time_series = self.client.get_metrics_over_time(
            metric_type=metric_type,
            operation_type=operation_type,
            start_time=start_time,
            end_time=end_time,
            interval=interval
        )
        
        # Extract values for analysis
        values = []
        timestamps = []
        for point in time_series.get("time_series", []):
            metrics = point.get("metrics", {})
            
            # Handle different metric formats
            if isinstance(metrics, dict):
                # Try to get value from different possible formats
                if "average" in metrics:
                    value = metrics["average"]
                elif "value" in metrics:
                    value = metrics["value"]
                elif operation_type and operation_type in metrics:
                    value = metrics[operation_type].get("average", 0)
                else:
                    # If we can't find a specific value, use the first numeric value
                    value = next((v for v in metrics.values() 
                                if isinstance(v, (int, float))), 0)
            else:
                value = metrics
            
            values.append(value)
            timestamps.append(point.get("timestamp"))
        
        # Skip analysis if not enough data points
        if len(values) < 2:
            return {
                "success": False,
                "error": "Not enough data points for analysis",
                "time_series": time_series
            }
        
        # Calculate basic statistics
        import statistics
        try:
            mean = statistics.mean(values)
            median = statistics.median(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0
            minimum = min(values)
            maximum = max(values)
            
            # Calculate trend (simple linear regression)
            n = len(values)
            sum_x = sum(range(n))
            sum_y = sum(values)
            sum_x_squared = sum(x*x for x in range(n))
            sum_xy = sum(i*value for i, value in enumerate(values))
            
            m = (n * sum_xy - sum_x * sum_y) / (n * sum_x_squared - sum_x * sum_x)
            b = (sum_y - m * sum_x) / n
            
            # Determine trend direction
            if m > 0.05 * mean:  # Significant positive trend
                trend = "increasing"
            elif m < -0.05 * mean:  # Significant negative trend
                trend = "decreasing"
            else:
                trend = "stable"
                
            # Calculate coefficient of variation
            cv = stdev / mean if mean != 0 else 0
            
            # Determine variability
            if cv < 0.1:
                variability = "low"
            elif cv < 0.3:
                variability = "moderate"
            else:
                variability = "high"
            
            # Format datetime for readability
            format_time = lambda ts: datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            readable_times = [format_time(ts) for ts in timestamps]
            
            # Build analysis result
            analysis = {
                "success": True,
                "metric_type": metric_type,
                "operation_type": operation_type,
                "time_range": (start_time, end_time),
                "interval": interval,
                "data_points": len(values),
                "statistics": {
                    "mean": mean,
                    "median": median,
                    "stdev": stdev,
                    "min": minimum,
                    "max": maximum,
                    "range": maximum - minimum
                },
                "trend": {
                    "direction": trend,
                    "slope": m,
                    "intercept": b
                },
                "variability": {
                    "coefficient_of_variation": cv,
                    "assessment": variability
                },
                "timestamps": {
                    "raw": timestamps,
                    "readable": readable_times
                },
                "values": values,
                "time_series": time_series
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing time series: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "time_series": time_series
            }
    
    def print_analysis_summary(self, analysis: Dict[str, Any]) -> None:
        """
        Print a summary of time series analysis.
        
        Args:
            analysis: Analysis result from analyze_time_series()
        """
        if not analysis.get("success", False):
            print(f"Analysis failed: {analysis.get('error', 'Unknown error')}")
            return
        
        print("\n" + "=" * 60)
        print(f"TIME SERIES ANALYSIS: {analysis['metric_type']}")
        if analysis.get("operation_type"):
            print(f"Operation Type: {analysis['operation_type']}")
        print("=" * 60)
        
        # Time range
        start_time = datetime.datetime.fromtimestamp(analysis['time_range'][0]).strftime('%Y-%m-%d %H:%M:%S')
        end_time = datetime.datetime.fromtimestamp(analysis['time_range'][1]).strftime('%Y-%m-%d %H:%M:%S')
        print(f"Time Range: {start_time} to {end_time}")
        print(f"Interval: {analysis['interval']}")
        print(f"Data Points: {analysis['data_points']}")
        
        # Statistics
        stats = analysis['statistics']
        print("\nStatistics:")
        print(f"  Mean: {stats['mean']:.4f}")
        print(f"  Median: {stats['median']:.4f}")
        print(f"  Standard Deviation: {stats['stdev']:.4f}")
        print(f"  Range: {stats['min']:.4f} to {stats['max']:.4f}")
        
        # Trend
        trend = analysis['trend']
        print("\nTrend Analysis:")
        print(f"  Direction: {trend['direction'].capitalize()}")
        print(f"  Slope: {trend['slope']:.6f}")
        
        # Variability
        var = analysis['variability']
        print("\nVariability:")
        print(f"  Coefficient of Variation: {var['coefficient_of_variation']:.4f}")
        print(f"  Assessment: {var['assessment'].capitalize()}")
        
        # Provide insights based on analysis
        print("\nInsights:")
        
        # Trend insights
        if trend['direction'] == "increasing":
            if analysis['metric_type'] in ["operation_latency", "error_rate"]:
                print("  ⚠️ Performance degradation detected (increasing trend in negative metric)")
            else:
                print("  ✅ Positive trend detected")
        elif trend['direction'] == "decreasing":
            if analysis['metric_type'] in ["operation_latency", "error_rate"]:
                print("  ✅ Performance improvement detected (decreasing trend in negative metric)")
            elif analysis['metric_type'] in ["success_rate", "throughput"]:
                print("  ⚠️ Potential issue detected (decreasing trend in positive metric)")
        else:
            print("  ✓ Metric is stable over the analyzed period")
        
        # Variability insights
        if var['assessment'] == "high":
            print("  ⚠️ High variability indicates inconsistent performance")
        elif var['assessment'] == "low":
            print("  ✅ Low variability indicates consistent performance")
        
        print("=" * 60)

def setup_test_environment(data_dir: str = "/tmp/wal_telemetry_example",
                         api_port: int = 8000) -> Tuple[WAL, int]:
    """
    Set up a test WAL and API server for demonstration.
    
    Args:
        data_dir: Directory for WAL data
        api_port: Port for API server
        
    Returns:
        Tuple of (WAL instance, API server port)
    """
    # Create data directory
    os.makedirs(data_dir, exist_ok=True)
    
    # Initialize WAL with telemetry enabled
    os.environ["WAL_TELEMETRY_ENABLED"] = "1"
    os.environ["WAL_TELEMETRY_PATH"] = os.path.join(data_dir, "telemetry")
    
    # Create WAL instance
    wal = WAL(data_dir=data_dir)
    
    # Start API server in background thread
    app = create_api_app(wal=wal)
    server_thread = threading.Thread(
        target=start_api_server,
        args=(app, api_port)
    )
    server_thread.daemon = True
    server_thread.start()
    
    # Wait for server to start
    time.sleep(1)
    logger.info(f"API server started on port {api_port}")
    
    return wal, api_port

def generate_test_operations(wal: WAL, count: int = 1000, delay: float = 0.01) -> None:
    """
    Generate test operations for the WAL.
    
    Args:
        wal: WAL instance
        count: Number of operations to generate
        delay: Delay between operations in seconds
    """
    logger.info(f"Generating {count} test operations...")
    
    # Operation types
    op_types = ["append", "read", "update", "delete"]
    
    # Generate random operations
    import random
    for i in range(count):
        op_type = random.choice(op_types)
        
        # Generate random data
        key = f"key_{random.randint(1, 100)}"
        value = {
            "timestamp": time.time(),
            "data": random.randint(1, 1000),
            "text": f"Test operation {i}"
        }
        
        # Execute operation based on type
        try:
            if op_type == "append":
                wal.append(key, value)
            elif op_type == "read":
                wal.get(key)
            elif op_type == "update":
                wal.update(key, value)
            elif op_type == "delete":
                wal.delete(key)
                
            # Add occasional error
            if random.random() < 0.05:  # 5% error rate
                try:
                    wal.get(f"nonexistent_key_{random.randint(1000, 9999)}")
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Error in test operation: {str(e)}")
        
        # Add delay between operations
        time.sleep(delay)
    
    logger.info(f"Completed generating {count} test operations")

def run_dashboard_demo(base_url: str = "http://localhost:8000", 
                     generate_ops: bool = True,
                     duration: int = 60) -> None:
    """
    Run a demonstration of the telemetry dashboard.
    
    Args:
        base_url: Base URL for API server
        generate_ops: Whether to generate test operations
        duration: Duration of demo in seconds
    """
    print(f"\n{'='*70}")
    print(f"RUNNING WAL TELEMETRY DASHBOARD DEMO")
    print(f"{'='*70}")
    print(f"Base URL: {base_url}")
    print(f"Duration: {duration} seconds")
    print(f"Generate Operations: {generate_ops}")
    print(f"System: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"{'='*70}\n")
    
    # Start dashboard
    dashboard = WALTelemetryDashboard(base_url=base_url, alerts_enabled=True)
    
    # Start monitoring
    dashboard.start_monitoring(interval=2)
    print("Monitoring started. Press Ctrl+C to stop...")
    
    # Generate test operations in background if requested
    if generate_ops:
        def generate_ops_thread():
            # Get WAL instance
            wal = WAL(data_dir="/tmp/wal_telemetry_example")
            
            # Generate continuous operations
            count = 0
            start_time = time.time()
            while time.time() - start_time < duration:
                generate_test_operations(wal, count=50, delay=0.02)
                count += 50
                time.sleep(2)
            
            print(f"Generated {count} test operations")
            
        # Start operations thread
        ops_thread = threading.Thread(target=generate_ops_thread)
        ops_thread.daemon = True
        ops_thread.start()
    
    # Run for the specified duration
    try:
        # Wait for a bit to collect some data
        time.sleep(15)
        
        # Generate visualizations for different metrics
        print("\nGenerating visualizations...")
        dashboard.generate_visualizations()
        
        # Analyze time series data
        print("\nAnalyzing time series data...")
        analysis = dashboard.analyze_time_series(
            metric_type=TelemetryMetricType.OPERATION_LATENCY,
            interval="hour"
        )
        dashboard.print_analysis_summary(analysis)
        
        # Generate comprehensive report
        print("\nGenerating performance report...")
        report = dashboard.generate_performance_report()
        
        # Print report URL if available
        if "local_path" in report:
            print(f"\nReport generated at: {report['local_path']}")
            print("Opening report in browser...")
            try:
                webbrowser.open(f"file://{report['local_path']}")
            except:
                print("Could not open browser automatically. Please open the report manually.")
        
        # Continue monitoring for the rest of the duration
        remaining_time = duration - 15
        if remaining_time > 0:
            print(f"\nContinuing monitoring for {remaining_time} seconds...")
            time.sleep(remaining_time)
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    finally:
        # Stop monitoring
        dashboard.stop_monitoring()
        print("\nMonitoring stopped")
        
    print(f"\n{'='*70}")
    print(f"WAL TELEMETRY DASHBOARD DEMO COMPLETED")
    print(f"{'='*70}\n")

def main():
    """Main entry point for example."""
    parser = argparse.ArgumentParser(description="WAL Telemetry Client Example")
    parser.add_argument("--setup", action="store_true", help="Set up test environment")
    parser.add_argument("--ops", action="store_true", help="Generate test operations")
    parser.add_argument("--dashboard", action="store_true", help="Run dashboard demo")
    parser.add_argument("--port", type=int, default=8000, help="API server port")
    parser.add_argument("--duration", type=int, default=60, help="Demo duration in seconds")
    args = parser.parse_args()
    
    # Set up test environment if requested
    wal = None
    if args.setup:
        wal, api_port = setup_test_environment(api_port=args.port)
        print(f"Test environment set up with API server on port {api_port}")
    
    # Generate test operations if requested
    if args.ops:
        if wal is None:
            wal = WAL(data_dir="/tmp/wal_telemetry_example")
        generate_test_operations(wal, count=100)
        print("Generated test operations")
    
    # Run dashboard demo if requested
    if args.dashboard:
        run_dashboard_demo(
            base_url=f"http://localhost:{args.port}",
            generate_ops=True,
            duration=args.duration
        )
    
    # If no specific action requested, run everything
    if not (args.setup or args.ops or args.dashboard):
        wal, api_port = setup_test_environment(api_port=args.port)
        generate_test_operations(wal, count=100)
        run_dashboard_demo(
            base_url=f"http://localhost:{api_port}",
            generate_ops=True,
            duration=args.duration
        )

if __name__ == "__main__":
    main()