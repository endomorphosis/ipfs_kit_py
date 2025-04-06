# ipfs_kit_py/wal_telemetry_client.py

"""
Client for the WAL telemetry API.

This module provides a client for accessing the WAL telemetry API, providing
programmatic access to telemetry metrics, reports, and visualizations.
"""

import os
import time
import json
import logging
import requests
import webbrowser
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)

# Metric type and aggregation enums
class TelemetryMetricType(str, Enum):
    """Types of metrics collected by the telemetry system."""
    OPERATION_COUNT = "operation_count"
    OPERATION_LATENCY = "operation_latency"
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    BACKEND_HEALTH = "backend_health"
    THROUGHPUT = "throughput"
    QUEUE_SIZE = "queue_size"
    RETRY_COUNT = "retry_count"

class TelemetryAggregation(str, Enum):
    """Types of aggregation for telemetry metrics."""
    SUM = "sum"
    AVERAGE = "average"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    PERCENTILE_95 = "percentile_95"
    PERCENTILE_99 = "percentile_99"
    COUNT = "count"
    RATE = "rate"

class WALTelemetryClient:
    """
    Client for accessing the WAL telemetry API.
    
    This class provides methods for retrieving telemetry metrics, generating reports,
    and accessing visualizations from the WAL telemetry API.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None, 
                timeout: int = 30, verify_ssl: bool = True):
        """
        Initialize the WAL telemetry client.
        
        Args:
            base_url: Base URL for the API server
            api_key: Optional API key for authentication
            timeout: Timeout in seconds for API requests
            verify_ssl: Whether to verify SSL certificates
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        # Create session for connection pooling
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            "User-Agent": "WALTelemetryClient/1.0",
            "Accept": "application/json"
        })
        
        # Add API key to headers if provided
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
    
    def _request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, 
                data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None,
                files: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            data: Form data
            json_data: JSON data
            files: Files to upload
            
        Returns:
            API response as dictionary
            
        Raises:
            ValueError: If the API returns an error
            requests.RequestException: If the request fails
        """
        # Build URL
        url = f"{self.base_url}{endpoint}"
        
        try:
            # Make request
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json_data,
                files=files,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # Check for successful response
            response.raise_for_status()
            
            # Parse JSON response if available
            if response.headers.get("Content-Type", "").startswith("application/json"):
                result = response.json()
                
                # Check for API error
                if not result.get("success", False):
                    error_msg = result.get("error", "Unknown API error")
                    raise ValueError(f"API error: {error_msg}")
                
                return result
            else:
                # Return raw response for non-JSON content
                return {
                    "success": True,
                    "content_type": response.headers.get("Content-Type"),
                    "content": response.content,
                    "status_code": response.status_code
                }
            
        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise
    
    def get_metrics(self, metric_type: Optional[Union[str, TelemetryMetricType]] = None,
                   operation_type: Optional[str] = None, backend: Optional[str] = None,
                   status: Optional[str] = None, time_range: Optional[Tuple[float, float]] = None,
                   aggregation: Optional[Union[str, TelemetryAggregation]] = None) -> Dict[str, Any]:
        """
        Get telemetry metrics with optional filtering.
        
        Args:
            metric_type: Type of metrics to retrieve
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            time_range: Tuple of (start_time, end_time) to filter by
            aggregation: Type of aggregation to apply
            
        Returns:
            Dictionary with telemetry metrics
        """
        # Convert enums to strings
        if hasattr(metric_type, 'value'):
            metric_type = metric_type.value
            
        if hasattr(aggregation, 'value'):
            aggregation = aggregation.value
        
        # Prepare params
        params = {}
        if metric_type:
            params["metric_type"] = metric_type
        if operation_type:
            params["operation_type"] = operation_type
        if backend:
            params["backend"] = backend
        if status:
            params["status"] = status
        if time_range:
            params["start_time"] = time_range[0]
            params["end_time"] = time_range[1]
        if aggregation:
            params["aggregation"] = aggregation
        
        # Make request
        result = self._request(
            method="GET",
            endpoint="/api/v0/wal/telemetry/metrics",
            params=params
        )
        
        return result
    
    def get_realtime_metrics(self) -> Dict[str, Any]:
        """
        Get real-time telemetry metrics.
        
        Returns:
            Dictionary with real-time telemetry metrics
        """
        return self._request(
            method="GET",
            endpoint="/api/v0/wal/telemetry/realtime"
        )
    
    def generate_report(self, start_time: Optional[float] = None, end_time: Optional[float] = None,
                      open_browser: bool = False) -> Dict[str, Any]:
        """
        Generate a comprehensive telemetry report.
        
        Args:
            start_time: Start time for time range filter (Unix timestamp)
            end_time: End time for time range filter (Unix timestamp)
            open_browser: Whether to open the report in a browser
            
        Returns:
            Dictionary with report information
        """
        # Set default time range if not provided (last 24 hours)
        if end_time is None:
            end_time = time.time()
            
        if start_time is None:
            start_time = end_time - (24 * 60 * 60)  # 24 hours ago
        
        # Prepare data
        data = {
            "start_time": start_time,
            "end_time": end_time
        }
        
        # Make request
        result = self._request(
            method="POST",
            endpoint="/api/v0/wal/telemetry/report",
            data=data
        )
        
        # Open report in browser if requested
        if open_browser and "report_url" in result:
            try:
                webbrowser.open(result["report_url"])
            except Exception as e:
                logger.warning(f"Failed to open browser: {str(e)}")
        
        return result
    
    def get_report_file(self, report_id: str, file_name: str, save_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get a file from a telemetry report.
        
        Args:
            report_id: ID of the report
            file_name: Name of the file to retrieve
            save_path: Path to save the file (if None, file is not saved)
            
        Returns:
            Dictionary with file content or saved file information
        """
        # Make request
        result = self._request(
            method="GET",
            endpoint=f"/api/v0/wal/telemetry/reports/{report_id}/{file_name}"
        )
        
        # Save file if path provided
        if save_path and "content" in result:
            try:
                with open(save_path, "wb") as f:
                    f.write(result["content"])
                
                # Update result
                result["saved_path"] = save_path
                result["saved"] = True
            except Exception as e:
                logger.error(f"Failed to save file: {str(e)}")
                result["saved"] = False
                result["save_error"] = str(e)
        
        return result
    
    def get_visualization(self, metric_type: Union[str, TelemetryMetricType],
                        operation_type: Optional[str] = None, backend: Optional[str] = None,
                        status: Optional[str] = None, time_range: Optional[Tuple[float, float]] = None,
                        width: int = 12, height: int = 8, save_path: Optional[str] = None,
                        open_browser: bool = False) -> Dict[str, Any]:
        """
        Get a visualization of telemetry metrics.
        
        Args:
            metric_type: Type of metrics to visualize
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            time_range: Tuple of (start_time, end_time) to filter by
            width: Chart width in inches
            height: Chart height in inches
            save_path: Path to save the visualization (if None, visualization is not saved)
            open_browser: Whether to open the visualization in a browser
            
        Returns:
            Dictionary with visualization information
        """
        # Convert enum to string
        if hasattr(metric_type, 'value'):
            metric_type = metric_type.value
        
        # Prepare params
        params = {
            "width": width,
            "height": height
        }
        if operation_type:
            params["operation_type"] = operation_type
        if backend:
            params["backend"] = backend
        if status:
            params["status"] = status
        if time_range:
            params["start_time"] = time_range[0]
            params["end_time"] = time_range[1]
            
        # Build URL for browser opening
        browser_url = f"{self.base_url}/api/v0/wal/telemetry/visualization/{metric_type}"
        if params:
            browser_url += "?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        # Open in browser if requested
        if open_browser:
            try:
                webbrowser.open(browser_url)
            except Exception as e:
                logger.warning(f"Failed to open browser: {str(e)}")
            
            return {
                "success": True,
                "operation": "visualize_metrics",
                "url": browser_url,
                "message": "Visualization opened in browser"
            }
        
        # Make request to get image
        result = self._request(
            method="GET",
            endpoint=f"/api/v0/wal/telemetry/visualization/{metric_type}",
            params=params
        )
        
        # Save visualization if path provided
        if save_path and "content" in result:
            try:
                with open(save_path, "wb") as f:
                    f.write(result["content"])
                
                # Update result
                result["saved_path"] = save_path
                result["saved"] = True
            except Exception as e:
                logger.error(f"Failed to save visualization: {str(e)}")
                result["saved"] = False
                result["save_error"] = str(e)
        
        return result
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get the current telemetry configuration.
        
        Returns:
            Dictionary with telemetry configuration
        """
        return self._request(
            method="GET",
            endpoint="/api/v0/wal/telemetry/config"
        )
    
    def update_config(self, enabled: Optional[bool] = None, metrics_path: Optional[str] = None,
                    retention_days: Optional[int] = None, sampling_interval: Optional[int] = None,
                    enable_detailed_timing: Optional[bool] = None,
                    operation_hooks: Optional[bool] = None) -> Dict[str, Any]:
        """
        Update telemetry configuration.
        
        Args:
            enabled: Whether telemetry is enabled
            metrics_path: Directory for telemetry metrics storage
            retention_days: Number of days to retain metrics
            sampling_interval: Interval in seconds between metric samples
            enable_detailed_timing: Whether to collect detailed timing data
            operation_hooks: Whether to install operation hooks
            
        Returns:
            Dictionary with updated configuration
        """
        # Prepare config data
        config = {}
        if enabled is not None:
            config["enabled"] = enabled
        if metrics_path is not None:
            config["metrics_path"] = metrics_path
        if retention_days is not None:
            config["retention_days"] = retention_days
        if sampling_interval is not None:
            config["sampling_interval"] = sampling_interval
        if enable_detailed_timing is not None:
            config["enable_detailed_timing"] = enable_detailed_timing
        if operation_hooks is not None:
            config["operation_hooks"] = operation_hooks
        
        # Make request
        return self._request(
            method="POST",
            endpoint="/api/v0/wal/telemetry/config",
            json_data=config
        )
    
    def get_metrics_over_time(self, metric_type: Union[str, TelemetryMetricType],
                            operation_type: Optional[str] = None, backend: Optional[str] = None,
                            status: Optional[str] = None, 
                            start_time: Optional[float] = None,
                            end_time: Optional[float] = None,
                            interval: str = "hour") -> Dict[str, Any]:
        """
        Get metrics over time with specified interval.
        
        This is a convenience method that retrieves metrics for multiple time periods
        and organizes them into a time series.
        
        Args:
            metric_type: Type of metrics to retrieve
            operation_type: Filter by operation type
            backend: Filter by backend type
            status: Filter by operation status
            start_time: Start time (defaults to 24 hours ago)
            end_time: End time (defaults to now)
            interval: Time interval ('hour', 'day', 'week')
            
        Returns:
            Dictionary with time series metrics
        """
        # Set default time range if not provided
        if end_time is None:
            end_time = time.time()
            
        if start_time is None:
            start_time = end_time - (24 * 60 * 60)  # 24 hours ago
        
        # Calculate intervals
        intervals = []
        current_time = start_time
        
        if interval == "hour":
            step = 60 * 60  # 1 hour
        elif interval == "day":
            step = 24 * 60 * 60  # 1 day
        elif interval == "week":
            step = 7 * 24 * 60 * 60  # 1 week
        else:
            raise ValueError(f"Invalid interval: {interval}. Must be 'hour', 'day', or 'week'.")
        
        while current_time < end_time:
            next_time = min(current_time + step, end_time)
            intervals.append((current_time, next_time))
            current_time = next_time
        
        # Get metrics for each interval
        time_series = []
        for interval_start, interval_end in intervals:
            metrics = self.get_metrics(
                metric_type=metric_type,
                operation_type=operation_type,
                backend=backend,
                status=status,
                time_range=(interval_start, interval_end),
                aggregation=TelemetryAggregation.AVERAGE
            )
            
            # Add timestamp to metrics
            interval_data = {
                "start_time": interval_start,
                "end_time": interval_end,
                "timestamp": (interval_start + interval_end) / 2,  # Middle of interval
                "metrics": metrics.get("metrics", {})
            }
            
            time_series.append(interval_data)
        
        return {
            "success": True,
            "operation": "get_metrics_over_time",
            "timestamp": time.time(),
            "metric_type": metric_type,
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
            "time_series": time_series
        }
    
    def monitor_realtime(self, callback: callable, interval: int = 5, 
                        duration: Optional[int] = None) -> None:
        """
        Monitor real-time metrics at regular intervals.
        
        Args:
            callback: Function to call with each metrics update
            interval: Interval in seconds between updates
            duration: Total monitoring duration in seconds (None for indefinite)
        """
        start_time = time.time()
        iteration = 0
        
        try:
            while True:
                # Check if duration exceeded
                if duration is not None and time.time() - start_time >= duration:
                    break
                
                # Get real-time metrics
                metrics = self.get_realtime_metrics()
                
                # Call callback with metrics
                callback(metrics, iteration)
                
                # Increment iteration counter
                iteration += 1
                
                # Wait for next interval
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        except Exception as e:
            logger.error(f"Error during monitoring: {str(e)}")
            raise

# Example usage
if __name__ == "__main__":
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    
    # Create client
    client = WALTelemetryClient(base_url="http://localhost:8000")
    
    # Get real-time metrics
    try:
        metrics = client.get_realtime_metrics()
        print(f"Real-time metrics: {json.dumps(metrics, indent=2)}")
    except Exception as e:
        print(f"Failed to get metrics: {str(e)}")
    
    # Example monitor callback
    def print_metrics(metrics, iteration):
        """Print real-time metrics as they arrive."""
        print(f"\n=== Metrics Update #{iteration} ===")
        latency = metrics.get("latency", {})
        success_rate = metrics.get("success_rate", {})
        error_rate = metrics.get("error_rate", {})
        throughput = metrics.get("throughput", {})
        
        print(f"Latency: {latency}")
        print(f"Success Rate: {success_rate}")
        print(f"Error Rate: {error_rate}")
        print(f"Throughput: {throughput}")
    
    # Monitor for 10 seconds (uncomment to run)
    # client.monitor_realtime(print_metrics, interval=2, duration=10)
    
    # Generate visualization (uncomment to run)
    # client.get_visualization(
    #     metric_type=TelemetryMetricType.OPERATION_LATENCY,
    #     open_browser=True
    # )
    
    # Generate report (uncomment to run)
    # client.generate_report(open_browser=True)